from __future__ import annotations

import collections.abc
from typing import BinaryIO

import rwmem.helpers
import rwmem.mmaptarget
import rwmem.target

__all__ = ['MappedRegister', 'MappedRegisterBlock', 'MappedRegisterFile']


class MappedRegister:
    def __init__(self, map, reg: rwmem.Register, block_offset):
        self._map = map
        self._reg = reg
        self._frozen = None
        self._block_offset = block_offset

    def freeze(self):
        if self._frozen is not None:
            raise RuntimeError('Register already frozen')

        self._frozen = self._read()

    def unfreeze(self):
        if self._frozen is None:
            raise RuntimeError('Register not frozen')
        self._write(self._frozen)
        self._frozen = None

    def get_fields(self):
        self.freeze()

        fields = {}
        for f in self._reg.values():
            fields[f.name] = self[f.name]

        self.unfreeze()

        return fields

    def _read(self) -> int:
        """Read the register, in its own data size and endianness."""
        return self._map.read(
            self._block_offset + self._reg.offset,
            data_size=self._reg.effective_data_size,
            data_endianness=self._reg.effective_data_endianness,
        )

    def _write(self, value: int) -> None:
        """Write the register, in its own data size and endianness."""
        self._map.write(
            self._block_offset + self._reg.offset,
            value,
            data_size=self._reg.effective_data_size,
            data_endianness=self._reg.effective_data_endianness,
        )

    def get_value(self) -> int:
        if self._frozen is None:
            return self._read()
        else:
            return self._frozen

    def set_value(self, val):
        if isinstance(val, dict):
            self.freeze()
            for k, v in val.items():
                self[k] = v
            self.unfreeze()
        else:
            if self._frozen is None:
                self._write(val)
            else:
                self._frozen = val

    def get_field_value(self, idx: str | int | slice):
        reg_value = self.get_value()

        if isinstance(idx, str):
            f = self._reg[idx]
            if not f:
                raise IndexError('Field not found')

            return rwmem.helpers.get_field_value(reg_value, f.high, f.low)

        elif isinstance(idx, int):
            if idx < 0 or idx >= self._reg.effective_data_size * 8:
                raise IndexError('Index out of bounds')

            return rwmem.helpers.get_field_value(reg_value, idx, idx)
        elif isinstance(idx, slice):
            indices = idx.indices(self._reg.effective_data_size * 8 - 1)

            low = indices[0]
            high = indices[1]

            if low > high:
                low, high = high, low

            return rwmem.helpers.get_field_value(reg_value, high, low)
        else:
            raise IndexError('Field not found')

    def set_field_value(self, idx: str | int | slice, val: int):
        if isinstance(idx, str):
            f = self._reg[idx]
            if not f:
                raise IndexError('Field not found')

            v = self.get_value()
            v = rwmem.helpers.set_field_value(v, f.high, f.low, val)
        elif isinstance(idx, int):
            if idx < 0 or idx >= self._reg.effective_data_size * 8:
                raise IndexError('Index out of bounds')

            v = self.get_value()
            v = rwmem.helpers.set_field_value(v, idx, idx, val)
        elif isinstance(idx, slice):
            indices = idx.indices(self._reg.effective_data_size * 8 - 1)

            low = indices[0]
            high = indices[1]

            if low > high:
                low, high = high, low

            v = self.get_value()
            v = rwmem.helpers.set_field_value(v, high, low, val)
        else:
            raise IndexError('Field not found')

        self.set_value(v)

    @property
    def value(self):
        return self.get_value()

    def __int__(self):
        return self.get_value()

    def __str__(self):
        return '{:#x}'.format(self.get_value())

    def __getitem__(self, idx):
        return self.get_field_value(idx)

    def __setitem__(self, idx, val):
        self.set_field_value(idx, val)

    def __contains__(self, key):
        return key in self._reg


class MappedRegisterBlock(collections.abc.Mapping):
    def __init__(
        self,
        file: str | BinaryIO | rwmem.target.Target,
        regblock: rwmem.RegisterBlock,
        offset: int | None = None,
        mode=None,
    ):
        self._regblock = regblock

        self._offset = regblock.offset if offset is None else offset

        if isinstance(file, rwmem.target.Target):
            # A ready-made target. It was opened with its own mode, so a
            # mode given here would be ignored. It must cover
            # [offset, offset + regblock.size). The block takes ownership
            # and closes it on exit, as with its own MMapTarget.
            if mode is not None:
                raise ValueError('mode cannot be given with an already opened Target')

            self._map = file
        else:
            self._map = rwmem.mmaptarget.MMapTarget(
                file,
                self._offset,
                self._regblock.size,
                regblock.data_endianness,
                regblock.data_size,
                rwmem.MapMode.ReadWrite if mode is None else mode,
            )

        self._registers: dict[str, MappedRegister | None] = dict.fromkeys(regblock.keys())

    def close(self):
        """Close the target and drop the register views. Idempotent."""
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

    def __getitem__(self, key: str):
        if key not in self._registers:
            raise KeyError(f'MappedRegister "{key}" not found')

        mr = self._registers.get(key)
        if mr:
            return mr

        r = self._regblock.get(key)
        if r:
            mr = MappedRegister(self._map, r, self._offset)
            self._registers[r.name] = mr
            return mr

        raise RuntimeError()

    def __iter__(self):
        return iter(self._registers)

    def __len__(self):
        return len(self._registers)


class MappedRegisterFile(collections.abc.Mapping):
    def __init__(
        self,
        rf: rwmem.RegisterFile,
        target_factory: collections.abc.Callable[[rwmem.RegisterBlock], rwmem.target.Target]
        | None = None,
    ) -> None:
        """
        ``target_factory`` is called with a ``RegisterBlock`` and must return a
        ``Target`` covering it. By default blocks are mapped from ``/dev/mem``.
        """
        self._rf = rf
        self._target_factory = target_factory
        self._regblocks: dict[str, MappedRegisterBlock | None] = dict.fromkeys(rf.keys())

    def close(self):
        """Close the opened blocks and drop the references to them. Idempotent.

        Needed before the ``RegisterFile`` is closed: the blocks hold views
        into its mmap, which cannot be closed while they are alive.
        """
        for mrb in self._regblocks.values():
            if mrb:
                mrb.close()
        self._regblocks.clear()
        self._rf = None

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, exc_tb):
        self.close()

    def __getitem__(self, key: str):
        if key not in self._regblocks:
            raise KeyError(f'MappedRegisterBlock "{key}" not found')

        mrb = self._regblocks.get(key)
        if mrb:
            return mrb

        assert self._rf is not None
        rbi = self._rf.get(key)
        if rbi:
            if self._target_factory is not None:
                mrb = MappedRegisterBlock(self._target_factory(rbi), rbi)
            else:
                mrb = MappedRegisterBlock('/dev/mem', rbi)
            self._regblocks[rbi.name] = mrb
            return mrb

        raise RuntimeError()

    def __iter__(self):
        return iter(self._regblocks)

    def __len__(self):
        return len(self._regblocks)
