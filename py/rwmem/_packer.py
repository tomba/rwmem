from __future__ import annotations

import io
import struct
from dataclasses import dataclass

from .enums import Endianness


@dataclass
class PackedField:
    name: str
    high: int
    low: int


@dataclass
class PackedRegister:
    name: str
    offset: int
    fields: list[PackedField]
    first_field_index: int


@dataclass
class PackedBlock:
    name: str
    offset: int
    size: int
    regs: list[PackedRegister]
    addr_endianness: Endianness
    addr_size: int
    data_endianness: Endianness
    data_size: int
    first_reg_index: int


@dataclass
class PackedRegFile:
    name: str
    blocks: list[PackedBlock]
    all_registers: list[PackedRegister]  # Global deduplicated register list
    all_fields: list[PackedField]  # Global deduplicated field list
    strings: dict[str, int]


class RegFilePacker:
    def __init__(self, regfile):
        self.regfile = regfile

    def prepare(self) -> PackedRegFile:
        # Create strings_map with an empty string
        strings_map = {'': 0}
        strings_len = 1

        def get_str_idx(s: str) -> int:
            nonlocal strings_map, strings_len
            if s not in strings_map:
                strings_map[s] = strings_len
                strings_len += len(s) + 1
            return strings_map[s]

        # Phase 2: Sort blocks and compute indices with deduplication
        sorted_blocks = sorted(self.regfile.blocks, key=lambda b: b.offset)

        get_str_idx(self.regfile.name)  # Ensure name is in strings

        packed_blocks = []
        unique_register_sets = {}  # signature -> (packed_regs, first_reg_index, first_field_index)
        all_packed_regs = []  # Global list of all unique registers
        all_packed_fields = []  # Global list of all unique fields

        for block in sorted_blocks:
            # Sort registers without modifying original
            sorted_regs = sorted(block.regs, key=lambda r: r.offset)

            # Calculate block size if needed
            block_size = block.size
            if block_size == 0 and sorted_regs:
                last_reg = max(sorted_regs, key=lambda r: r.offset)
                block_size = last_reg.offset + (block.data_size if block.data_size else 4)

            get_str_idx(block.name)  # Ensure name is in strings

            # Create signature for this block's register set
            reg_signature = self._compute_register_signature(sorted_regs)

            if reg_signature in unique_register_sets:
                # Reuse existing register definitions
                packed_regs, first_reg_index, first_field_index = unique_register_sets[reg_signature]
            else:
                # Create new register definitions
                first_reg_index = len(all_packed_regs)
                first_field_index = len(all_packed_fields)

                packed_regs = []
                for reg in sorted_regs:
                    # Sort fields without modifying original
                    sorted_fields = sorted(reg.fields, key=lambda f: f.high, reverse=True)

                    get_str_idx(reg.name)  # Ensure name is in strings
                    reg_first_field_index = len(all_packed_fields)

                    packed_fields = []
                    for field in sorted_fields:
                        get_str_idx(field.name)  # Ensure name is in strings
                        packed_field = PackedField(
                            name=field.name,
                            high=field.high,
                            low=field.low
                        )
                        packed_fields.append(packed_field)
                        all_packed_fields.append(packed_field)

                    packed_reg = PackedRegister(
                        name=reg.name,
                        offset=reg.offset,
                        fields=packed_fields,
                        first_field_index=reg_first_field_index
                    )
                    packed_regs.append(packed_reg)
                    all_packed_regs.append(packed_reg)

                # Cache this register set for reuse
                unique_register_sets[reg_signature] = (packed_regs, first_reg_index, first_field_index)

            packed_blocks.append(PackedBlock(
                name=block.name,
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
            blocks=packed_blocks,
            all_registers=all_packed_regs,
            all_fields=all_packed_fields,
            strings=strings_map
        )

    def _compute_register_signature(self, regs):
        """Compute a signature for a set of registers to enable deduplication."""
        signature_parts = []
        for reg in regs:
            # Sort fields for consistent signature
            sorted_fields = sorted(reg.fields, key=lambda f: (f.name, f.high, f.low))
            field_sig = tuple((f.name, f.high, f.low) for f in sorted_fields)
            signature_parts.append((reg.name, reg.offset, field_sig))
        return tuple(signature_parts)

    def pack_to(self, out: io.IOBase, packed: PackedRegFile | None = None):
        if packed is None:
            packed = self.prepare()

        num_blocks = len(packed.blocks)
        num_regs = len(packed.all_registers)
        num_fields = len(packed.all_fields)

        # Write regfile header
        out.write(pack_regfile(packed.strings[packed.name], num_blocks, num_regs, num_fields))

        # Write all blocks
        for block in packed.blocks:
            out.write(pack_block(
                packed.strings[block.name], block.offset, block.size,
                len(block.regs), block.first_reg_index,
                block.addr_endianness, block.addr_size,
                block.data_endianness, block.data_size
            ))

        # Write all unique registers (deduplicated)
        for reg in packed.all_registers:
            out.write(pack_register(
                packed.strings[reg.name], reg.offset,
                len(reg.fields), reg.first_field_index
            ))

        # Write all unique fields (deduplicated)
        for field in packed.all_fields:
            out.write(pack_field(
                packed.strings[field.name], field.high, field.low
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
