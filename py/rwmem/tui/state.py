"""Runtime state classes for rwmem-tui."""

from __future__ import annotations

from rwmem.gen import UnpackedRegBlock, UnpackedRegFile
from rwmem.target import Target

from .types import ValueFormat


class BlockState:
    """Runtime state for a register block."""

    def __init__(self, block: UnpackedRegBlock) -> None:
        self.block = block
        self.target: Target | None = None
        self.error: str | None = None
        self.reg_values: dict[str, int | None] = {}
        self.reg_errors: dict[str, str | None] = {}
        self.watched: set[str] = set()
        self.watch_all: bool = False

        for reg in block.regs:
            self.reg_values[reg.name] = None
            self.reg_errors[reg.name] = None

    def is_reg_watched(self, reg_name: str) -> bool:
        return self.watch_all or reg_name in self.watched

    def has_any_watched(self) -> bool:
        return self.watch_all or len(self.watched) > 0


# Default poll intervals per target type (seconds). 0 means disabled.
DEFAULT_POLL_INTERVALS = {
    'mmap': 0.1,
    'i2c': 0.0,
}


class AppState:
    """Application-level state."""

    def __init__(self, target_mode: str) -> None:
        self.target_str: str = ''
        self.regfile: UnpackedRegFile | None = None
        self.regdb_path: str | None = None
        self.block_states: dict[str, BlockState] = {}
        self.value_format: ValueFormat = ValueFormat.HEX
        self.show_values: bool = False
        self.watch_all: bool = False
        self.poll_interval: float = DEFAULT_POLL_INTERVALS.get(target_mode, 1.0)
