"""Leaf-level data types and formatting helpers for rwmem-tui."""

from __future__ import annotations

import enum
from dataclasses import dataclass

from rwmem.gen import UnpackedField, UnpackedRegBlock, UnpackedRegister


@dataclass
class BlockNodeData:
    block: UnpackedRegBlock


@dataclass
class RegisterNodeData:
    block: UnpackedRegBlock
    reg: UnpackedRegister


@dataclass
class FieldNodeData:
    block: UnpackedRegBlock
    reg: UnpackedRegister
    field: UnpackedField


class ValueFormat(enum.Enum):
    HEX = 'hex'
    DEC = 'dec'
    BIN = 'bin'


def format_value(value: int, fmt: ValueFormat, width_bits: int) -> str:
    if fmt == ValueFormat.HEX:
        nchars = (width_bits + 3) // 4
        return f'0x{value:0{nchars}X}'
    elif fmt == ValueFormat.DEC:
        return str(value)
    elif fmt == ValueFormat.BIN:
        return f'0b{value:0{width_bits}b}'
    return hex(value)


# Field colors for bit diagram
FIELD_COLORS = [
    'cyan',
    'magenta',
    'green',
    'yellow',
    'blue',
    'red',
    'bright_cyan',
    'bright_magenta',
]
