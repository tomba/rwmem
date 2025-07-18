from __future__ import annotations

import io
import struct
from dataclasses import dataclass

from .enums import Endianness


@dataclass
class PackedField:
    name: str
    name_offset: int
    high: int
    low: int


@dataclass
class PackedRegister:
    name: str
    name_offset: int
    offset: int
    fields: list[PackedField]
    first_field_index: int


@dataclass
class PackedBlock:
    name: str
    name_offset: int
    offset: int
    size: int
    regs: list[PackedRegister]
    first_reg_index: int
    addr_endianness: Endianness
    addr_size: int
    data_endianness: Endianness
    data_size: int


@dataclass
class PackedRegFile:
    name: str
    name_offset: int
    blocks: list[PackedBlock]
    strings: dict[str, int]


class RegFilePacker:
    def __init__(self, regfile):
        self.regfile = regfile

    def prepare(self) -> PackedRegFile:
        # Phase 1: Build string table
        strings = {'': 0}
        str_idx = 1

        def get_str_idx(s: str) -> int:
            nonlocal str_idx
            if s not in strings:
                strings[s] = str_idx
                str_idx += len(s) + 1
            return strings[s]

        # Phase 2: Sort blocks and compute indices
        sorted_blocks = sorted(self.regfile.blocks, key=lambda b: b.offset)

        name_offset = get_str_idx(self.regfile.name)

        packed_blocks = []
        num_regs = 0
        num_fields = 0

        for block in sorted_blocks:
            # Sort registers without modifying original
            sorted_regs = sorted(block.regs, key=lambda r: r.offset)

            # Calculate block size if needed
            block_size = block.size
            if block_size == 0 and sorted_regs:
                last_reg = max(sorted_regs, key=lambda r: r.offset)
                block_size = last_reg.offset + (block.data_size if block.data_size else 4)

            block_name_offset = get_str_idx(block.name)
            first_reg_index = num_regs

            packed_regs = []
            for reg in sorted_regs:
                # Sort fields without modifying original
                sorted_fields = sorted(reg.fields, key=lambda f: f.high, reverse=True)

                reg_name_offset = get_str_idx(reg.name)
                first_field_index = num_fields

                packed_fields = []
                for field in sorted_fields:
                    field_name_offset = get_str_idx(field.name)
                    packed_fields.append(PackedField(
                        name=field.name,
                        name_offset=field_name_offset,
                        high=field.high,
                        low=field.low
                    ))
                    num_fields += 1

                packed_regs.append(PackedRegister(
                    name=reg.name,
                    name_offset=reg_name_offset,
                    offset=reg.offset,
                    fields=packed_fields,
                    first_field_index=first_field_index
                ))
                num_regs += 1

            packed_blocks.append(PackedBlock(
                name=block.name,
                name_offset=block_name_offset,
                offset=block.offset,
                size=block_size,
                regs=packed_regs,
                first_reg_index=first_reg_index,
                addr_endianness=block.addr_endianness,
                addr_size=block.addr_size,
                data_endianness=block.data_endianness,
                data_size=block.data_size
            ))

        return PackedRegFile(
            name=self.regfile.name,
            name_offset=name_offset,
            blocks=packed_blocks,
            strings=strings
        )

    def pack_to(self, out: io.IOBase, packed: PackedRegFile | None = None):
        if packed is None:
            packed = self.prepare()

        num_blocks = len(packed.blocks)
        num_regs = sum(len(block.regs) for block in packed.blocks)
        num_fields = sum(len(reg.fields) for block in packed.blocks for reg in block.regs)

        # Write regfile header
        out.write(pack_regfile(packed.name_offset, num_blocks, num_regs, num_fields))

        # Write all blocks
        for block in packed.blocks:
            out.write(pack_block(
                block.name_offset, block.offset, block.size,
                len(block.regs), block.first_reg_index,
                block.addr_endianness, block.addr_size,
                block.data_endianness, block.data_size
            ))

        # Write all registers
        for block in packed.blocks:
            for reg in block.regs:
                out.write(pack_register(
                    reg.name_offset, reg.offset,
                    len(reg.fields), reg.first_field_index
                ))

        # Write all fields
        for block in packed.blocks:
            for reg in block.regs:
                for field in reg.fields:
                    out.write(pack_field(
                        field.name_offset, field.high, field.low
                    ))

        # Write strings table
        first_pos = out.tell()
        for s, idx in packed.strings.items():
            assert idx == out.tell() - first_pos
            out.write(bytes(s, 'ascii'))
            out.write(b'\0')

    def pack_to_bytes(self) -> bytes:
        with io.BytesIO() as f:
            self.pack_to(f)
            return f.getvalue()


def pack_regfile(name_offset, num_blocks, num_regs, num_fields):
    RWMEM_MAGIC = 0x00e11554
    RWMEM_VERSION = 2
    fmt_regfile = '>IIIIII'
    return struct.pack(fmt_regfile, RWMEM_MAGIC, RWMEM_VERSION, name_offset, num_blocks, num_regs, num_fields)


def pack_block(name_offset, block_offset, block_size, num_regs, first_reg_index,
               addr_e, addr_s, data_e, data_s):
    fmt_block = '>IQQIIBBBB'
    return struct.pack(fmt_block, name_offset, block_offset, block_size, num_regs, first_reg_index,
                       addr_e.value, addr_s, data_e.value, data_s)


def pack_register(name_offset, reg_offset, num_fields, first_field_index):
    fmt_reg = '>IQII'
    return struct.pack(fmt_reg, name_offset, reg_offset, num_fields, first_field_index)


def pack_field(name_offset, high, low):
    fmt_field = '>IBB'
    return struct.pack(fmt_field, name_offset, high, low)
