from __future__ import annotations

import io
from dataclasses import dataclass

from .enums import Endianness
from ._structs import (
    RegisterFileDataV3,
    RegisterBlockDataV3,
    RegisterDataV3,
    FieldDataV3,
    RegisterIndexV3,
    FieldIndexV3,
    RWMEM_MAGIC_V3,
    RWMEM_VERSION_V3,
)


@dataclass
class PackedField:
    name: str
    high: int
    low: int
    description: str | None = None


@dataclass
class PackedRegister:
    name: str
    offset: int
    fields: list[PackedField]
    first_field_index: int
    description: str | None = None
    reset_value: int = 0
    data_endianness: Endianness | None = None
    data_size: int | None = None


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
    description: str | None = None


@dataclass
class PackedRegFile:
    name: str
    blocks: list[PackedBlock]
    all_registers: list[PackedRegister]  # Global deduplicated register list
    all_fields: list[PackedField]  # Global deduplicated field list
    strings: dict[str, int]
    description: str | None = None


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
        if self.regfile.description:
            get_str_idx(self.regfile.description)  # Ensure description is in strings

        packed_blocks = []
        unique_register_sets = {}  # signature -> (packed_regs, first_reg_index, first_field_index)
        all_packed_regs = []  # Global list of all unique registers
        all_packed_fields = []  # Global list of all unique fields
        current_reg_list_index = 0  # Track position in RegisterIndex array

        for block in sorted_blocks:
            # Sort registers without modifying original
            sorted_regs = sorted(block.regs, key=lambda r: r.offset)

            # Calculate block size if needed
            block_size = block.size
            if block_size == 0 and sorted_regs:
                last_reg = max(sorted_regs, key=lambda r: r.offset)
                # Use register's effective data size or block default
                reg_data_size = last_reg.get_effective_data_size(block.data_size)
                block_size = last_reg.offset + reg_data_size

            get_str_idx(block.name)  # Ensure name is in strings
            if block.description:
                get_str_idx(block.description)  # Ensure description is in strings

            # Create signature for this block's register set
            reg_signature = self._compute_register_signature(sorted_regs)

            if reg_signature in unique_register_sets:
                # Reuse existing register definitions
                packed_regs, first_reg_index, first_field_index = unique_register_sets[
                    reg_signature
                ]
            else:
                # Create new register definitions
                first_reg_index = len(all_packed_regs)
                first_field_index = len(all_packed_fields)

                packed_regs = []
                for reg in sorted_regs:
                    # Sort fields without modifying original
                    sorted_fields = sorted(reg.fields, key=lambda f: f.high, reverse=True)

                    get_str_idx(reg.name)  # Ensure name is in strings
                    if reg.description:
                        get_str_idx(reg.description)  # Ensure description is in strings
                    reg_first_field_index = len(all_packed_fields)

                    packed_fields = []
                    for field in sorted_fields:
                        get_str_idx(field.name)  # Ensure name is in strings
                        if field.description:
                            get_str_idx(field.description)  # Ensure description is in strings
                        packed_field = PackedField(
                            name=field.name,
                            high=field.high,
                            low=field.low,
                            description=field.description,
                        )
                        packed_fields.append(packed_field)
                        all_packed_fields.append(packed_field)

                    packed_reg = PackedRegister(
                        name=reg.name,
                        offset=reg.offset,
                        fields=packed_fields,
                        first_field_index=reg_first_field_index,
                        description=reg.description,
                        reset_value=reg.reset_value,
                        data_endianness=reg.data_endianness,
                        data_size=reg.data_size,
                    )
                    packed_regs.append(packed_reg)
                    all_packed_regs.append(packed_reg)

                # Cache this register set for reuse
                unique_register_sets[reg_signature] = (
                    packed_regs,
                    first_reg_index,
                    first_field_index,
                )

            packed_blocks.append(
                PackedBlock(
                    name=block.name,
                    offset=block.offset,
                    size=block_size,
                    regs=packed_regs,
                    first_reg_index=current_reg_list_index,  # This is now first_reg_list_index
                    addr_endianness=block.addr_endianness,
                    addr_size=block.addr_size,
                    data_endianness=block.data_endianness,
                    data_size=block.data_size,
                    description=block.description,
                )
            )

            # Update the position in RegisterIndex array
            current_reg_list_index += len(packed_regs)

        return PackedRegFile(
            name=self.regfile.name,
            blocks=packed_blocks,
            all_registers=all_packed_regs,
            all_fields=all_packed_fields,
            strings=strings_map,
            description=self.regfile.description,
        )

    def _compute_register_signature(self, regs):
        """Compute a signature for a set of registers to enable deduplication."""
        signature_parts = []
        for reg in regs:
            # Sort fields for consistent signature
            sorted_fields = sorted(reg.fields, key=lambda f: (f.name, f.high, f.low))
            field_sig = tuple((f.name, f.high, f.low, f.description) for f in sorted_fields)
            reg_sig = (
                reg.name,
                reg.offset,
                field_sig,
                reg.description,
                reg.reset_value,
                reg.data_endianness,
                reg.data_size,
            )
            signature_parts.append(reg_sig)
        return tuple(signature_parts)

    def pack_to(self, out: io.IOBase, packed: PackedRegFile | None = None):
        if packed is None:
            packed = self.prepare()

        # Write regfile header
        out.write(pack_regfile(packed))

        # Write all blocks
        for block in packed.blocks:
            out.write(pack_block(block, packed.strings))

        # Write all unique registers (deduplicated)
        for reg in packed.all_registers:
            out.write(pack_register(reg, packed.strings))

        # Write all unique fields (deduplicated)
        for field in packed.all_fields:
            out.write(pack_field(field, packed.strings))

        # Write register index arrays
        for block in packed.blocks:
            for reg in block.regs:
                # Find the index of this register in the global all_registers array
                reg_index = None
                for i, global_reg in enumerate(packed.all_registers):
                    if global_reg is reg:
                        reg_index = i
                        break
                if reg_index is None:
                    raise RuntimeError(f'Register {reg.name} not found in global register array')
                out.write(pack_register_index(reg_index))

        # Write field index arrays (1:1 mapping for now)
        for reg in packed.all_registers:
            for i in range(len(reg.fields)):
                out.write(pack_field_index(reg.first_field_index + i))

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


def pack_regfile(regfile: PackedRegFile):
    # Calculate indirection array sizes
    num_reg_indices = sum(len(block.regs) for block in regfile.blocks)
    num_field_indices = sum(len(reg.fields) for reg in regfile.all_registers)

    data = RegisterFileDataV3(
        magic=RWMEM_MAGIC_V3,
        version=RWMEM_VERSION_V3,
        name_offset=regfile.strings[regfile.name],
        num_blocks=len(regfile.blocks),
        num_regs=len(regfile.all_registers),
        num_fields=len(regfile.all_fields),
        num_reg_indices=num_reg_indices,
        num_field_indices=num_field_indices,
    )
    return bytes(data)


def pack_block(block: PackedBlock, strings: dict[str, int]):
    description_offset = strings.get(block.description, 0) if block.description else 0
    data = RegisterBlockDataV3(
        name_offset=strings[block.name],
        description_offset=description_offset,
        offset=block.offset,
        size=block.size,
        num_regs=len(block.regs),
        first_reg_list_index=block.first_reg_index,
        default_addr_endianness=block.addr_endianness.value,
        default_addr_size=block.addr_size,
        default_data_endianness=block.data_endianness.value,
        default_data_size=block.data_size,
    )
    return bytes(data)


def pack_register(reg: PackedRegister, strings: dict[str, int]):
    description_offset = strings.get(reg.description, 0) if reg.description else 0
    # Convert None values to 0 for inheritance
    data_endianness = reg.data_endianness.value if reg.data_endianness is not None else 0
    data_size = reg.data_size if reg.data_size is not None else 0

    data = RegisterDataV3(
        name_offset=strings[reg.name],
        description_offset=description_offset,
        offset=reg.offset,
        reset_value=reg.reset_value,
        num_fields=len(reg.fields),
        first_field_list_index=reg.first_field_index,
        data_endianness=data_endianness,
        data_size=data_size,
    )
    return bytes(data)


def pack_field(field: PackedField, strings: dict[str, int]):
    description_offset = strings.get(field.description, 0) if field.description else 0
    data = FieldDataV3(
        name_offset=strings[field.name],
        description_offset=description_offset,
        high=field.high,
        low=field.low,
    )
    return bytes(data)


def pack_register_index(register_index):
    data = RegisterIndexV3(register_index=register_index)
    return bytes(data)


def pack_field_index(field_index):
    data = FieldIndexV3(field_index=field_index)
    return bytes(data)
