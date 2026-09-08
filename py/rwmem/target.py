from __future__ import annotations

import sys
from abc import ABC, abstractmethod
from collections.abc import Sequence

from .enums import Endianness

__all__ = [
    'Target',
]


class Target(ABC):
    @abstractmethod
    def read(
        self,
        addr: int,
        data_size: int | None = None,
        data_endianness: Endianness = Endianness.Default,
        addr_size: int | None = None,
        addr_endianness: Endianness = Endianness.Default,
    ) -> int: ...

    @abstractmethod
    def write(
        self,
        addr: int,
        value: int,
        data_size: int | None = None,
        data_endianness: Endianness = Endianness.Default,
        addr_size: int | None = None,
        addr_endianness: Endianness = Endianness.Default,
    ): ...

    @abstractmethod
    def close(self): ...

    def read_many(self, reads: Sequence[tuple[int, int | None, Endianness]]) -> list[int]:
        """Read several registers; each entry is ``(addr, data_size, data_endianness)``.

        The default reads them one at a time. Targets that can do better,
        such as RemoteTarget, override this.
        """
        return [
            self.read(addr, data_size, data_endianness)
            for addr, data_size, data_endianness in reads
        ]

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, exc_tb):
        self.close()

    def _endianness_to_bo(self, endianness: Endianness):
        if endianness == Endianness.Default:
            return sys.byteorder
        elif endianness == Endianness.Little:
            return 'little'
        elif endianness == Endianness.Big:
            return 'big'

        raise NotImplementedError()
