"""Register access by name, binding a register database to a Target.

Two ways to reach a register, over the same handles underneath:

- String keys do I/O and are the short form. A key is an rwmem register
  path: ``mrf['DSS.REVISION']`` reads a register, ``mrf['DSS.REVISION'] =
  0x10`` writes it, ``mrf['DSS.REVISION:MAJOR']`` reads a field,
  ``mrf['DSS.REVISION:7:3']`` a bit range, and ``mrf['DSS.*']`` the whole
  block in one round trip. Indexing a block scope drops the block prefix:
  ``mrf['DSS']['REVISION:MAJOR'] = 4``.

- Methods return handles, looked up once and then read and written without
  parsing a path again: ``reg = mrf.reg('DSS.REVISION'); reg.read();
  reg.write(0x10)``, and ``reg.field('MAJOR')`` for a field handle.

Reading a register returns a ``RegisterValue``, an ``int`` that also decodes
its own fields: ``v = mrf['DSS.REVISION']; v['MAJOR']`` needs no new read.
"""

from __future__ import annotations

import collections.abc
from dataclasses import dataclass
from typing import BinaryIO

from rwmem.enums import Endianness, MapMode
from rwmem.helpers import genmask, get_field_value, set_field_value
from rwmem.mmaptarget import MMapTarget
from rwmem.registerfile import Register, RegisterBlock, RegisterFile
from rwmem.target import Target

__all__ = [
    'RegisterValue',
    'MappedField',
    'MappedRegister',
    'MappedRegisterBlock',
    'MappedRegisterFile',
]


@dataclass(frozen=True)
class _Layout:
    """A register's field map, copied out of the database so a value can
    outlive the RegisterFile's mmap."""

    name: str
    bits: int
    fields: tuple[tuple[str, int, int], ...]  # (name, high, low)

    def field_map(self) -> dict[str, tuple[int, int]]:
        return {name: (high, low) for name, high, low in self.fields}


def _resolve_bits(idx: str | int | slice, bits: int, fields: dict[str, tuple[int, int]]):
    """A field index -> (high, low). ``idx`` is a field name, a bit, or a
    ``[high:low]`` slice (inclusive both ends). Raises for anything out of
    range; nothing is clamped."""
    if isinstance(idx, str):
        if idx not in fields:
            raise KeyError(f'Field "{idx}" not found')
        return fields[idx]

    if isinstance(idx, slice):
        if idx.step not in (None, 1):
            raise ValueError('a bit range takes no step')
        if idx.start is None or idx.stop is None:
            raise ValueError('a bit range needs both ends')
        high, low = idx.start, idx.stop
        if low > high:
            high, low = low, high
    elif isinstance(idx, int):
        high = low = idx
    else:
        raise TypeError(f'bad field index {idx!r}')

    if low < 0 or high >= bits:
        raise ValueError(f'bits {high}:{low} out of range for a {bits}-bit register')
    return high, low


def _spec_to_idx(spec: str, fields: dict[str, tuple[int, int]]) -> str | int | slice:
    """The field part of a path, e.g. 'MAJOR', '7:3' or '3', as an index."""
    if spec in fields:
        return spec
    if ':' in spec:
        hi, lo = spec.split(':', 1)
        return slice(int(hi, 0), int(lo, 0))
    try:
        return int(spec, 0)
    except ValueError:
        raise KeyError(f'Field "{spec}" not found') from None


class RegisterValue(int):
    """A register's value: an ``int`` that also decodes its fields.

    ``v['MAJOR']``, ``v[3]`` and ``v[7:3]`` extract from the value already
    read, without touching hardware. Everything else is plain ``int``.
    """

    _layout: _Layout

    def __new__(cls, value: int, layout: _Layout):
        self = super().__new__(cls, value)
        self._layout = layout
        return self

    def __getitem__(self, idx: str | int | slice) -> int:
        high, low = _resolve_bits(idx, self._layout.bits, self._layout.field_map())
        return get_field_value(int(self), high, low)

    def __setitem__(self, idx, val):
        raise TypeError('a register value is read-only')

    @property
    def fields(self) -> dict[str, int]:
        """All fields decoded from this value."""
        return {
            name: get_field_value(int(self), high, low) for name, high, low in self._layout.fields
        }

    def __repr__(self) -> str:
        width = self._layout.bits // 4 or 1
        s = f'{int(self):#0{width + 2}x}'
        if self._layout.fields:
            s += '  ' + ' '.join(f'{n}={v:#x}' for n, v in self.fields.items())
        return s


class MappedField:
    """A handle on one field of a register. Reading and writing go through
    the register, as a read and a read-modify-write."""

    def __init__(self, reg: MappedRegister, high: int, low: int, name: str | None) -> None:
        self._reg = reg
        self._high = high
        self._low = low
        self.name = name

    @property
    def high(self) -> int:
        return self._high

    @property
    def low(self) -> int:
        return self._low

    @property
    def width(self) -> int:
        return self._high - self._low + 1

    @property
    def mask(self) -> int:
        return genmask(self._high, self._low)

    @property
    def register(self) -> MappedRegister:
        return self._reg

    def read(self) -> int:
        return self._reg._read_bits(self._high, self._low)

    def write(self, value: int) -> None:
        self._reg._write_bits(self._high, self._low, value)

    def __repr__(self) -> str:
        name = self.name or f'[{self._high}:{self._low}]'
        return f'<MappedField {self._reg.block.name}.{self._reg.name}:{name} [{self._high}:{self._low}]>'


class MappedRegister:
    """A handle on one register: the unit of reads and writes.

    ``read()`` returns a RegisterValue, ``write(v)`` takes an int or a
    ``{field: value}`` dict. Indexing reads and writes a field, by name,
    bit or ``[high:low]`` slice, each a read or read-modify-write.
    """

    def __init__(self, block: MappedRegisterBlock, reg: Register) -> None:
        self._block = block
        self._reg = reg
        self.name = reg.name
        self._layout_cache: _Layout | None = None

    # --- metadata -------------------------------------------------------

    @property
    def offset(self) -> int:
        """The register's offset in its block, from the database."""
        return self._reg.offset

    @property
    def address(self) -> int:
        """The address the register is accessed at."""
        return self._block.address + self._reg.offset

    @property
    def data_size(self) -> int:
        return self._reg.effective_data_size

    @property
    def data_endianness(self) -> Endianness:
        return self._reg.effective_data_endianness

    @property
    def bits(self) -> int:
        return self._reg.effective_data_size * 8

    @property
    def reset_value(self) -> int:
        return self._reg.reset_value

    @property
    def description(self) -> str | None:
        return self._reg.description

    @property
    def block(self) -> MappedRegisterBlock:
        return self._block

    def _layout(self) -> _Layout:
        if self._layout_cache is None:
            fields = tuple((f.name, f.high, f.low) for f in self._reg.values())
            self._layout_cache = _Layout(self.name, self.bits, fields)
        return self._layout_cache

    # --- I/O ------------------------------------------------------------

    def read(self) -> RegisterValue:
        raw = self._block._map.read(self.address, self.data_size, self.data_endianness)
        return RegisterValue(raw, self._layout())

    def write(self, value: int | dict[str, int]) -> None:
        if isinstance(value, dict):
            fields = self._layout().field_map()
            v = int(self.read())
            for name, fv in value.items():
                high, low = _resolve_bits(name, self.bits, fields)
                v = set_field_value(v, high, low, fv)
            self._block._map.write(self.address, v, self.data_size, self.data_endianness)
        else:
            self._block._map.write(self.address, value, self.data_size, self.data_endianness)

    def _read_bits(self, high: int, low: int) -> int:
        return get_field_value(int(self.read()), high, low)

    def _write_bits(self, high: int, low: int, value: int) -> None:
        v = int(self.read())
        v = set_field_value(v, high, low, value)
        self._block._map.write(self.address, v, self.data_size, self.data_endianness)

    def __getitem__(self, idx: str | int | slice) -> int:
        high, low = _resolve_bits(idx, self.bits, self._layout().field_map())
        return self._read_bits(high, low)

    def __setitem__(self, idx: str | int | slice, value: int) -> None:
        high, low = _resolve_bits(idx, self.bits, self._layout().field_map())
        self._write_bits(high, low, value)

    def __contains__(self, name: str) -> bool:
        return name in self._reg

    def __getattr__(self, name: str) -> MappedField:
        """Attribute access navigates to a field handle: reg.MODE. Read-only;
        a field named like an attribute of this class is reachable only
        through field()."""
        if name.startswith('_'):
            raise AttributeError(name)
        if name in self._reg:
            return self.field(name)
        raise AttributeError(name)

    def __dir__(self):
        fields = (n for n, _, _ in self._layout().fields if n.isidentifier())
        return [*super().__dir__(), *fields]

    # --- field handles --------------------------------------------------

    def field(self, name_or_high: str | int, low: int | None = None) -> MappedField:
        """A field handle, by name (``field('MAJOR')``), by single bit
        (``field(3)``) or by range (``field(7, 3)``)."""
        if low is not None:
            if not isinstance(name_or_high, int):
                raise TypeError('with two arguments both are bit numbers')
            high, low = _resolve_bits(slice(name_or_high, low), self.bits, {})
            return MappedField(self, high, low, None)
        high, low = _resolve_bits(name_or_high, self.bits, self._layout().field_map())
        name = name_or_high if isinstance(name_or_high, str) else None
        return MappedField(self, high, low, name)

    def __repr__(self) -> str:
        layout = self._layout()
        s = f'<MappedRegister {self._block.name}.{self.name} @{self.address:#x}, {self.bits} bits'
        if layout.fields:
            s += ', ' + ' '.join(f'{n}[{h}:{l}]' for n, h, l in layout.fields)
        return s + '>'


class MappedRegisterBlock(collections.abc.Mapping):
    """A block bound to a Target: a scope of registers keyed by name.

    Indexing does I/O with a register-and-field path without the block
    prefix (``block['REVISION:MAJOR']``); ``reg()`` returns a register
    handle. Iterating gives register names and touches no hardware.
    """

    def __init__(
        self,
        file: str | BinaryIO | Target,
        regblock: RegisterBlock,
        offset: int | None = None,
        mode=None,
    ):
        self._regblock = regblock
        self.name = regblock.name
        self._offset = regblock.offset if offset is None else offset

        if isinstance(file, Target):
            # A ready-made target, e.g. a RemoteTarget. It was opened with
            # its own mode, so a mode given here would be ignored. It must
            # cover [offset, offset + regblock.size). The block takes
            # ownership and closes it on exit, as with its own MMapTarget.
            if mode is not None:
                raise ValueError('mode cannot be given with an already opened Target')
            self._map = file
        else:
            self._map = MMapTarget(
                file,
                self._offset,
                regblock.size,
                regblock.data_endianness,
                regblock.data_size,
                MapMode.ReadWrite if mode is None else mode,
            )

        self._registers: dict[str, MappedRegister | None] = dict.fromkeys(regblock.keys())

    # --- metadata -------------------------------------------------------

    @property
    def offset(self) -> int:
        """The block's offset in the database."""
        return self._regblock.offset

    @property
    def address(self) -> int:
        """The address the block is accessed at (its offset unless overridden)."""
        return self._offset

    @property
    def size(self) -> int:
        return self._regblock.size

    @property
    def data_size(self) -> int:
        return self._regblock.data_size

    @property
    def data_endianness(self) -> Endianness:
        return self._regblock.data_endianness

    @property
    def description(self) -> str | None:
        return self._regblock.description

    # --- handles --------------------------------------------------------

    def reg(self, name: str) -> MappedRegister:
        """A register handle, created on first use and then cached."""
        if name not in self._registers:
            raise KeyError(f'Register "{name}" not found')
        mr = self._registers.get(name)
        if mr is None:
            mr = MappedRegister(self, self._regblock[name])
            self._registers[name] = mr
        return mr

    # --- I/O ------------------------------------------------------------

    def read(self, names: collections.abc.Sequence[str] | None = None) -> dict[str, RegisterValue]:
        """Read registers into ``{name: value}``, one round trip on a
        remote target. Defaults to every register in the block."""
        regs = [self.reg(n) for n in (names if names is not None else self._registers)]
        reads = [(r.address, r.data_size, r.data_endianness) for r in regs]
        values = self._map.read_many(reads)
        return {r.name: RegisterValue(v, r._layout()) for r, v in zip(regs, values, strict=True)}

    def __getitem__(self, key: str):
        regname, _, fieldspec = key.partition(':')
        if regname == '*' and not fieldspec:
            return self.read()
        reg = self.reg(regname)
        if not fieldspec:
            return reg.read()
        return reg[_spec_to_idx(fieldspec, reg._layout().field_map())]

    def __setitem__(self, key: str, value) -> None:
        regname, _, fieldspec = key.partition(':')
        reg = self.reg(regname)
        if not fieldspec:
            reg.write(value)
        else:
            reg[_spec_to_idx(fieldspec, reg._layout().field_map())] = value

    def _ipython_key_completions_(self) -> list[str]:
        keys: list[str] = ['*']
        for rname in self._registers:
            keys.append(rname)
            for f in self._regblock[rname].values():
                keys.append(f'{rname}:{f.name}')
        return keys

    def __getattr__(self, name: str) -> MappedRegister:
        """Attribute access navigates to a register handle: block.REVISION.
        Read-only; a register named like an attribute of this class is
        reachable only through reg()."""
        if name.startswith('_'):
            raise AttributeError(name)
        if name in self._registers:
            return self.reg(name)
        raise AttributeError(name)

    def __dir__(self):
        regs = (n for n in self._registers if n.isidentifier())
        return [*super().__dir__(), *regs]

    def close(self):
        """Close the target and drop the register handles. Idempotent."""
        if self._map is None:
            return
        self._map.close()
        self._map = None
        del self._regblock
        self._registers.clear()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, exc_tb):
        self.close()

    def __iter__(self):
        return iter(self._registers)

    def __len__(self):
        return len(self._registers)

    def __repr__(self) -> str:
        return (
            f'<MappedRegisterBlock {self.name} @{self.address:#x}, '
            f'{len(self._registers)} registers>'
        )


class MappedRegisterFile(collections.abc.Mapping):
    """A register database bound to targets, keyed by register path.

    ``mrf['BLOCK']`` is a block scope and does no I/O; ``mrf['BLOCK.REG']``
    and ``mrf['BLOCK.REG:FIELD']`` read and write. Given a file name or
    bytes instead of a RegisterFile, it opens and owns one.
    """

    def __init__(
        self,
        rf: RegisterFile | str | bytes | BinaryIO,
        target_factory: collections.abc.Callable[[RegisterBlock], Target] | None = None,
    ) -> None:
        """
        ``target_factory`` is called with a ``RegisterBlock`` and must return
        a ``Target`` covering it. By default blocks are mapped from
        ``/dev/mem``; use ``RemoteConnection.mmap_factory()`` for a device.
        """
        if isinstance(rf, RegisterFile):
            self._rf: RegisterFile | None = rf
            self._owns_rf = False
        else:
            self._rf = RegisterFile(rf)
            self._owns_rf = True

        self._target_factory = target_factory
        self._blocks: dict[str, MappedRegisterBlock | None] = dict.fromkeys(self._rf.keys())

    # --- navigation and I/O ---------------------------------------------

    def block(self, name: str) -> MappedRegisterBlock:
        """A block scope, its target opened on first use and then cached."""
        if name not in self._blocks:
            raise KeyError(f'Block "{name}" not found')
        mrb = self._blocks.get(name)
        if mrb is None:
            assert self._rf is not None
            rb = self._rf[name]
            if self._target_factory is not None:
                mrb = MappedRegisterBlock(self._target_factory(rb), rb)
            else:
                mrb = MappedRegisterBlock('/dev/mem', rb)
            self._blocks[name] = mrb
        return mrb

    def reg(self, path: str) -> MappedRegister:
        """A register handle from a ``'BLOCK.REG'`` path."""
        block, regname = self._split(path)
        if regname is None or ':' in regname or regname == '*':
            raise KeyError(f'reg() takes a BLOCK.REG path, not {path!r}')
        return self.block(block).reg(regname)

    def field(self, path: str) -> MappedField:
        """A field handle from a ``'BLOCK.REG:FIELD'`` (or ``:7:3``) path."""
        block, regfield = self._split(path)
        if regfield is None or ':' not in regfield:
            raise KeyError(f'field() takes a BLOCK.REG:FIELD path, not {path!r}')
        regname, _, spec = regfield.partition(':')
        reg = self.block(block).reg(regname)
        idx = _spec_to_idx(spec, reg._layout().field_map())
        if isinstance(idx, slice):
            return reg.field(idx.start, idx.stop)
        return reg.field(idx)

    def read(self, paths: collections.abc.Sequence[str]) -> dict[str, RegisterValue]:
        """Read several ``'BLOCK.REG'`` paths, one round trip per block."""
        by_block: dict[str, list[str]] = {}
        for path in paths:
            block, regname = self._split(path)
            if regname is None or ':' in regname or regname == '*':
                raise KeyError(f'read() takes BLOCK.REG paths, not {path!r}')
            by_block.setdefault(block, []).append(regname)

        result: dict[str, RegisterValue] = {}
        for block, regnames in by_block.items():
            values = self.block(block).read(regnames)
            for regname in regnames:
                result[f'{block}.{regname}'] = values[regname]
        return result

    @staticmethod
    def _split(key: str) -> tuple[str, str | None]:
        """'BLOCK.rest' -> ('BLOCK', 'rest'); 'BLOCK' -> ('BLOCK', None)."""
        block, sep, rest = key.partition('.')
        return (block, rest if sep else None)

    def __getitem__(self, key: str):
        block, rest = self._split(key)
        scope = self.block(block)
        if rest is None:
            return scope
        return scope[rest]

    def __setitem__(self, key: str, value) -> None:
        block, rest = self._split(key)
        if rest is None:
            raise KeyError(f'"{key}" is a block, not a register or field')
        self.block(block)[rest] = value

    def _ipython_key_completions_(self) -> list[str]:
        assert self._rf is not None
        keys: list[str] = []
        for bname in self._blocks:
            keys.append(bname)
            keys.append(f'{bname}.*')
            for rname in self._rf[bname]:
                keys.append(f'{bname}.{rname}')
                for f in self._rf[bname][rname].values():
                    keys.append(f'{bname}.{rname}:{f.name}')
        return keys

    def __getattr__(self, name: str) -> MappedRegisterBlock:
        """Attribute access navigates to a block scope: mrf.DSS, and from
        there mrf.DSS.REVISION.MAJOR. Read-only, and it does no I/O; a block
        named like an attribute of this class is reachable only through
        block()."""
        if name.startswith('_'):
            raise AttributeError(name)
        if name in self._blocks:
            return self.block(name)
        raise AttributeError(name)

    def __dir__(self):
        blocks = (n for n in self._blocks if n.isidentifier())
        return [*super().__dir__(), *blocks]

    def close(self):
        """Close the opened blocks, and the RegisterFile if this owns it.

        The blocks hold views into the file's mmap, so they are closed
        first. Idempotent. A RegisterValue copies its field layout, so it
        stays valid after this; a register or field handle does not, and a
        handle still referenced keeps an owned file mapped until it is gone,
        which is harmless.
        """
        for mrb in self._blocks.values():
            if mrb:
                mrb.close()
        self._blocks.clear()
        if self._owns_rf and self._rf is not None:
            try:
                self._rf.close()
            except BufferError:
                pass
        self._rf = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, exc_tb):
        self.close()

    def __iter__(self):
        return iter(self._blocks)

    def __len__(self):
        return len(self._blocks)
