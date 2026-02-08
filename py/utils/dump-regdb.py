#!/usr/bin/env python3

import argparse
import ctypes
import rwmem as rw
import tabulate
from rwmem._structs import (
    RegisterFileDataV3 as RegisterFileData,
    RegisterBlockDataV3 as RegisterBlockData,
    RegisterDataV3 as RegisterData,
    FieldDataV3 as FieldData,
    RegisterIndexV3,
    FieldIndexV3,
    RWMEM_MAGIC_V3 as RWMEM_MAGIC,
    RWMEM_VERSION_V3 as RWMEM_VERSION,
)
from rwmem.enums import Endianness

tabulate.PRESERVE_WHITESPACE = True


def format_endianness(val):
    """Format endianness enum value."""
    try:
        return Endianness(val).name
    except ValueError:
        return f'INVALID({val})'


def format_hex(val):
    """Format integer as hex string."""
    return f'0x{val:x}'


def format_size(val):
    """Format size with human readable suffix."""
    if val >= 1024:
        return f'{val} ({val // 1024}KB)'
    return str(val)


def dump_file_header(rf):
    """Dump file format header information."""
    print('=' * 80)
    print('FILE FORMAT ANALYSIS')
    print('=' * 80)

    # Basic file info
    file_size = len(rf._map)
    print(f'File: {rf.name}')
    print(f'Size: {format_size(file_size)}')
    print()

    # Header validation
    header_table = [
        [
            'Magic',
            format_hex(rf.rfd.magic),
            format_hex(RWMEM_MAGIC),
            '✓' if rf.rfd.magic == RWMEM_MAGIC else '✗',
        ],
        [
            'Version',
            str(rf.rfd.version),
            str(RWMEM_VERSION),
            '✓' if rf.rfd.version == RWMEM_VERSION else '✗',
        ],
        [
            'Name Offset',
            str(rf.rfd.name_offset),
            '-',
            '✓' if rf.rfd.name_offset < file_size else '✗',
        ],
    ]

    print('Header Validation:')
    print(tabulate.tabulate(header_table, ['Field', 'Value', 'Expected', 'Status']))
    print()

    # Counts summary
    counts_table = [
        ['Blocks', rf.rfd.num_blocks],
        ['Registers', rf.rfd.num_regs],
        ['Fields', rf.rfd.num_fields],
        ['Register Indices', rf.rfd.num_reg_indices],
        ['Field Indices', rf.rfd.num_field_indices],
    ]

    print('Entity Counts:')
    print(tabulate.tabulate(counts_table, ['Type', 'Count']))
    print()


def dump_memory_layout(rf):
    """Dump memory layout and section offsets."""
    print('MEMORY LAYOUT')
    print('=' * 80)

    file_size = len(rf._map)

    # Calculate section sizes
    header_size = ctypes.sizeof(RegisterFileData)
    blocks_size = ctypes.sizeof(RegisterBlockData) * rf.rfd.num_blocks
    registers_size = ctypes.sizeof(RegisterData) * rf.rfd.num_regs
    fields_size = ctypes.sizeof(FieldData) * rf.rfd.num_fields
    reg_indices_size = ctypes.sizeof(RegisterIndexV3) * rf.rfd.num_reg_indices
    field_indices_size = ctypes.sizeof(FieldIndexV3) * rf.rfd.num_field_indices
    strings_size = file_size - rf.strings_offset

    layout_table = [
        ['Header', 0, header_size, header_size, '✓'],
        [
            'Blocks',
            rf.blocks_offset,
            blocks_size,
            rf.registers_offset,
            '✓' if rf.blocks_offset + blocks_size == rf.registers_offset else '✗',
        ],
        [
            'Registers',
            rf.registers_offset,
            registers_size,
            rf.fields_offset,
            '✓' if rf.registers_offset + registers_size == rf.fields_offset else '✗',
        ],
        [
            'Fields',
            rf.fields_offset,
            fields_size,
            rf.register_indices_offset,
            '✓' if rf.fields_offset + fields_size == rf.register_indices_offset else '✗',
        ],
        [
            'Reg Indices',
            rf.register_indices_offset,
            reg_indices_size,
            rf.field_indices_offset,
            '✓'
            if rf.register_indices_offset + reg_indices_size == rf.field_indices_offset
            else '✗',
        ],
        [
            'Field Indices',
            rf.field_indices_offset,
            field_indices_size,
            rf.strings_offset,
            '✓' if rf.field_indices_offset + field_indices_size == rf.strings_offset else '✗',
        ],
        [
            'Strings',
            rf.strings_offset,
            strings_size,
            file_size,
            '✓' if rf.strings_offset + strings_size == file_size else '✗',
        ],
    ]

    print(tabulate.tabulate(layout_table, ['Section', 'Offset', 'Size', 'Next Offset', 'Valid']))
    print()


def dump_blocks_raw(rf):
    """Dump raw block structure data."""
    print('RAW BLOCK STRUCTURES')
    print('=' * 80)

    for idx in range(rf.rfd.num_blocks):
        offset = rf._get_regblock_offset(idx)
        rbd = RegisterBlockData.from_buffer(rf._map, offset)
        name = rf._get_str(rbd.name_offset)

        print(f'Block {idx}: {name}')

        block_table = [
            ['name_offset', rbd.name_offset],
            ['description_offset', rbd.description_offset],
            ['offset', format_hex(rbd.offset)],
            ['size', format_hex(rbd.size)],
            ['num_regs', rbd.num_regs],
            ['first_reg_list_index', rbd.first_reg_list_index],
            [
                'default_addr_endianness',
                f'{rbd.default_addr_endianness} ({format_endianness(rbd.default_addr_endianness)})',
            ],
            ['default_addr_size', rbd.default_addr_size],
            [
                'default_data_endianness',
                f'{rbd.default_data_endianness} ({format_endianness(rbd.default_data_endianness)})',
            ],
            ['default_data_size', rbd.default_data_size],
        ]

        print(tabulate.tabulate(block_table, ['Field', 'Value']))
        print()


def dump_registers_raw(rf):
    """Dump raw register structure data."""
    print('RAW REGISTER STRUCTURES')
    print('=' * 80)

    for idx in range(rf.rfd.num_regs):
        offset = rf._get_register_offset(idx)
        rd = RegisterData.from_buffer(rf._map, offset)
        name = rf._get_str(rd.name_offset)

        print(f'Register {idx}: {name}')

        reg_table = [
            ['name_offset', rd.name_offset],
            ['description_offset', rd.description_offset],
            ['offset', format_hex(rd.offset)],
            ['reset_value', format_hex(rd.reset_value)],
            ['num_fields', rd.num_fields],
            ['first_field_list_index', rd.first_field_list_index],
            [
                'addr_endianness',
                f'{rd.addr_endianness} ({format_endianness(rd.addr_endianness) if rd.addr_endianness else "inherit"})',
            ],
            ['addr_size', f'{rd.addr_size} {"(inherit)" if rd.addr_size == 0 else ""}'],
            [
                'data_endianness',
                f'{rd.data_endianness} ({format_endianness(rd.data_endianness) if rd.data_endianness else "inherit"})',
            ],
            ['data_size', f'{rd.data_size} {"(inherit)" if rd.data_size == 0 else ""}'],
        ]

        print(tabulate.tabulate(reg_table, ['Field', 'Value']))
        print()


def dump_fields_raw(rf):
    """Dump raw field structure data."""
    print('RAW FIELD STRUCTURES')
    print('=' * 80)

    for idx in range(rf.rfd.num_fields):
        offset = rf._get_field_offset(idx)
        fd = FieldData.from_buffer(rf._map, offset)
        name = rf._get_str(fd.name_offset)

        print(f'Field {idx}: {name}')

        field_table = [
            ['name_offset', fd.name_offset],
            ['description_offset', fd.description_offset],
            ['high', fd.high],
            ['low', fd.low],
        ]

        print(tabulate.tabulate(field_table, ['Field', 'Value']))
        print()


def dump_indices(rf):
    """Dump index arrays."""
    print('INDEX ARRAYS')
    print('=' * 80)

    # Register indices
    print('Register Indices:')
    reg_indices_table = []
    for idx in range(rf.rfd.num_reg_indices):
        reg_index_offset = rf.register_indices_offset + ctypes.sizeof(RegisterIndexV3) * idx
        reg_index_data = RegisterIndexV3.from_buffer(rf._map, reg_index_offset)
        reg_indices_table.append([idx, reg_index_data.register_index])

    print(tabulate.tabulate(reg_indices_table, ['Index', 'Register Index']))
    print()

    # Field indices
    print('Field Indices:')
    field_indices_table = []
    for idx in range(rf.rfd.num_field_indices):
        field_index_offset = rf.field_indices_offset + ctypes.sizeof(FieldIndexV3) * idx
        field_index_data = FieldIndexV3.from_buffer(rf._map, field_index_offset)
        field_indices_table.append([idx, field_index_data.field_index])

    print(tabulate.tabulate(field_indices_table, ['Index', 'Field Index']))
    print()


def dump_strings(rf):
    """Dump string table."""
    print('STRING TABLE')
    print('=' * 80)

    file_size = len(rf._map)
    strings_size = file_size - rf.strings_offset
    print(f'String pool: offset {rf.strings_offset}, size {strings_size}')
    print()

    # Extract all strings by scanning the string pool
    strings_table = []
    current_offset = 0

    while current_offset < strings_size:
        try:
            # Find null terminator
            null_pos = rf._map.find(b'\0', rf.strings_offset + current_offset)
            if null_pos == -1:
                break

            # Extract string
            string_bytes = rf._map[rf.strings_offset + current_offset : null_pos]
            if string_bytes:  # Skip empty strings
                try:
                    string_value = string_bytes.decode('ascii')
                    strings_table.append([current_offset, len(string_bytes), repr(string_value)])
                except UnicodeDecodeError:
                    strings_table.append(
                        [current_offset, len(string_bytes), f'<invalid: {string_bytes}>']
                    )

            current_offset = null_pos - rf.strings_offset + 1
        except Exception:
            break

    print('All Strings:')
    print(tabulate.tabulate(strings_table, ['Offset', 'Length', 'Value']))
    print()


def main():
    parser = argparse.ArgumentParser(
        description='Dump detailed register database internal structure'
    )
    parser.add_argument('regfile', help='Register database file to analyze')
    parser.add_argument('--no-blocks', action='store_true', help='Skip raw block structures')
    parser.add_argument('--no-registers', action='store_true', help='Skip raw register structures')
    parser.add_argument('--no-fields', action='store_true', help='Skip raw field structures')
    parser.add_argument('--no-indices', action='store_true', help='Skip index arrays')
    parser.add_argument('--no-strings', action='store_true', help='Skip string table')
    args = parser.parse_args()

    try:
        with rw.RegisterFile(args.regfile) as rf:
            dump_file_header(rf)
            dump_memory_layout(rf)

            if not args.no_blocks:
                dump_blocks_raw(rf)

            if not args.no_registers:
                dump_registers_raw(rf)

            if not args.no_fields:
                dump_fields_raw(rf)

            if not args.no_indices:
                dump_indices(rf)

            if not args.no_strings:
                dump_strings(rf)

    except Exception as e:
        print(f'Error: {e}')
        return 1

    return 0


if __name__ == '__main__':
    exit(main())
