"""Conversion from read-only RegisterFile to mutable UnpackedRegFile."""

from __future__ import annotations

from .enums import Endianness
from .gen import UnpackedField, UnpackedRegBlock, UnpackedRegFile, UnpackedRegister
from .registerfile import RegisterFile


def registerfile_to_unpacked(rf: RegisterFile) -> UnpackedRegFile:
    """Convert a read-only RegisterFile to a mutable UnpackedRegFile.

    This iterates all blocks, registers, and fields in the binary RegisterFile
    and produces the corresponding unpacked mutable structures.
    """
    blocks = []

    for block_name in rf:
        block = rf[block_name]
        regs = []

        for reg_name in block:
            reg = block[reg_name]
            fields = []

            for field_name in reg:
                field = reg[field_name]
                fields.append(
                    UnpackedField(
                        name=field.name,
                        high=field.high,
                        low=field.low,
                        description=field.description,
                    )
                )

            data_endianness = None
            if reg.rd.data_endianness != 0:
                data_endianness = Endianness(reg.rd.data_endianness)

            data_size = None
            if reg.rd.data_size != 0:
                data_size = reg.rd.data_size

            regs.append(
                UnpackedRegister(
                    name=reg.name,
                    offset=reg.offset,
                    fields=fields,
                    description=reg.description,
                    reset_value=reg.reset_value,
                    data_endianness=data_endianness,
                    data_size=data_size,
                )
            )

        blocks.append(
            UnpackedRegBlock(
                name=block.name,
                offset=block.offset,
                size=block.size,
                regs=regs,
                addr_endianness=block.addr_endianness,
                addr_size=block.addr_size,
                data_endianness=block.data_endianness,
                data_size=block.data_size,
                description=block.description,
            )
        )

    return UnpackedRegFile(
        name=rf.name,
        blocks=blocks,
    )
