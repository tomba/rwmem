"""Register database plus runtime state for rwmem-tui."""

from __future__ import annotations

import enum

from rwmem.gen import UnpackedField, UnpackedRegBlock, UnpackedRegFile, UnpackedRegister

from .session import RegRef


class Format(enum.Enum):
    HEX = 'hex'
    DEC = 'dec'
    BIN = 'bin'

    def next(self) -> Format:
        members = list(Format)
        return members[(members.index(self) + 1) % len(members)]


def format_value(value: int, fmt: Format, bits: int) -> str:
    if fmt == Format.HEX:
        return f'0x{value:0{(bits + 3) // 4}x}'
    if fmt == Format.BIN:
        return f'0b{value:0{bits}b}'
    return str(value)


def field_value(value: int, field: UnpackedField) -> int:
    return (value >> field.low) & ((1 << (field.high - field.low + 1)) - 1)


def field_mask(field: UnpackedField) -> int:
    return ((1 << (field.high - field.low + 1)) - 1) << field.low


def set_field_value(value: int, field: UnpackedField, fv: int) -> int:
    mask = field_mask(field)
    return (value & ~mask) | ((fv << field.low) & mask)


class RegState:
    def __init__(self) -> None:
        self.value: int | None = None
        self.error: str | None = None
        self.changed = False  # value differed from the previous read


class Model:
    def __init__(
        self,
        regfile: UnpackedRegFile,
        *,
        bases: dict[str, int] | None = None,
        ignore_base: bool = False,
    ) -> None:
        """
        ``bases`` maps block names to the address to access them at, instead
        of the block offset in the database. ``ignore_base`` accesses every
        other block at address 0, as rwmem's --ignore-base does for dump files.
        """
        self.regfile = regfile
        self.bases: dict[str, int] = {}
        self.refs: dict[tuple[str, str], RegRef] = {}
        self.states: dict[tuple[str, str], RegState] = {}

        bases = bases or {}
        unknown = set(bases) - {b.name for b in regfile.blocks}
        if unknown:
            raise ValueError(f'Unknown block(s) in base override: {", ".join(sorted(unknown))}')

        for block in regfile.blocks:
            base = bases.get(block.name, 0 if ignore_base else block.offset)
            self.bases[block.name] = base
            for reg in block.regs:
                ref = RegRef(block, reg, base)
                self.refs[ref.key] = ref
                self.states[ref.key] = RegState()

        self.fmt = Format.HEX
        self.watch_all = False
        self.watched_blocks: set[str] = set()
        self.watched_regs: set[tuple[str, str]] = set()

    def ref(self, block: UnpackedRegBlock, reg: UnpackedRegister) -> RegRef:
        return self.refs[(block.name, reg.name)]

    def state(self, ref: RegRef) -> RegState:
        return self.states[ref.key]

    def refs_in(self, block: UnpackedRegBlock | None = None) -> list[RegRef]:
        """All registers, or those of one block."""
        if block is None:
            return list(self.refs.values())
        return [self.refs[(block.name, reg.name)] for reg in block.regs]

    def is_watched(self, ref: RegRef) -> bool:
        return (
            self.watch_all or ref.block.name in self.watched_blocks or ref.key in self.watched_regs
        )

    def watched_refs(self) -> list[RegRef]:
        return [ref for ref in self.refs.values() if self.is_watched(ref)]

    def apply(self, ref: RegRef, result: int | Exception) -> bool:
        """Store a read result. Returns True if the value changed."""
        st = self.state(ref)
        if isinstance(result, Exception):
            st.error = str(result)
            st.changed = False
            return False

        changed = st.value is not None and st.value != result
        st.value = result
        st.error = None
        st.changed = changed
        return changed
