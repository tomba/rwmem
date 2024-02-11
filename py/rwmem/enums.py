from __future__ import annotations

from enum import Enum

__all__ = [ 'Endianness', 'MapMode', ]


class Endianness(Enum):
    Default = 0
    Big = 1
    Little  = 2
    BigSwapped = 3
    LittleSwapped  = 4


class MapMode(Enum):
    Read = 0
    Write = 1
    ReadWrite = 2
