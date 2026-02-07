"""Conversion from a RegisterFile to an UnpackedRegFile.

A RegisterFile is a read-only view into a packed register database, backed
by a mapping that cannot be closed while any of its blocks, registers or
fields are still referenced. An UnpackedRegFile is plain mutable objects
with no ties to the file, which is what a program that keeps a database
around, edits it, or writes it back out wants.
"""

from __future__ import annotations

from .gen import UnpackedField, UnpackedRegBlock, UnpackedRegFile, UnpackedRegister
from .registerfile import RegisterFile

__all__ = ['registerfile_to_unpacked']


def registerfile_to_unpacked(rf: RegisterFile) -> UnpackedRegFile:
    """Copy the blocks, registers and fields of ``rf`` into an UnpackedRegFile.

    The result shares nothing with ``rf``, which can be closed afterwards.
    """
    blocks = []
    for block in rf.values():
        regs = []
        for reg in block.values():
            fields = [
                UnpackedField(field.name, field.high, field.low, field.description)
                for field in reg.values()
            ]
            regs.append(
                UnpackedRegister(
                    reg.name,
                    reg.offset,
                    fields,
                    description=reg.description,
                    reset_value=reg.reset_value,
                    data_endianness=reg.data_endianness,
                    data_size=reg.data_size,
                )
            )
        blocks.append(
            UnpackedRegBlock(
                block.name,
                block.offset,
                block.size,
                regs,
                addr_endianness=block.addr_endianness,
                addr_size=block.addr_size,
                data_endianness=block.data_endianness,
                data_size=block.data_size,
                description=block.description,
            )
        )

    # The file format stores no description for the register file itself.
    return UnpackedRegFile(rf.name, blocks)
