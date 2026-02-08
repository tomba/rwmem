#!/usr/bin/env python3
"""
Pyrwmem Example: MappedRegisterFile Usage

This example demonstrates high-level register access by combining register
database metadata with memory mapping. This provides register and field
access by name with automatic addressing and bit manipulation.
"""

import os
import shutil
import tempfile
import rwmem as rw

# Use test files from the test directory
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REGDB_PATH = os.path.join(SCRIPT_DIR, '..', 'tests', 'test.regdb')
BIN_PATH = os.path.join(SCRIPT_DIR, '..', 'tests', 'test.bin')


def access_registers(temp_bin_path, rf: rw.RegisterFile):
    # Use SENSOR_A block from test.regdb
    sensor_block = rf['SENSOR_A']

    with rw.MappedRegisterBlock(
        temp_bin_path, sensor_block, mode=rw.MapMode.ReadWrite
    ) as mapped_block:
        print('Reading registers:')

        # Read register values from test data
        status_reg = mapped_block['STATUS_REG']
        data_reg = mapped_block['DATA_REG']
        config_reg = mapped_block['CONFIG_REG']

        print(f'  STATUS_REG: 0x{status_reg.value:02x}')
        print(f'  DATA_REG:   0x{data_reg.value:04x}')
        print(f'  CONFIG_REG: 0x{config_reg.value:06x}')


def demonstrate_register_access():
    """Show basic register reading and writing."""
    print('=== Register Access ===')

    # Create a temporary copy of test.bin for modification
    with tempfile.NamedTemporaryFile(delete=False, suffix='.bin') as temp_file:
        temp_bin_path = temp_file.name

    shutil.copy(BIN_PATH, temp_bin_path)

    try:
        with rw.RegisterFile(REGDB_PATH) as rf:
            access_registers(temp_bin_path, rf)
    finally:
        os.unlink(temp_bin_path)


def access_fields(temp_bin_path, rf: rw.RegisterFile):
    sensor_block = rf['SENSOR_A']

    with rw.MappedRegisterBlock(
        temp_bin_path, sensor_block, mode=rw.MapMode.ReadWrite
    ) as mapped_block:
        status_reg = mapped_block['STATUS_REG']

        print('Reading STATUS_REG fields:')
        print(f'  READY: {status_reg["READY"]}')
        print(f'  ERROR: {status_reg["ERROR"]}')
        print(f'  MODE:  {status_reg["MODE"]}')

        print('\nModifying fields:')
        status_reg['MODE'] = 0x10  # Change MODE field
        print('  Set MODE to 0x10')
        print(f'  STATUS_REG value now: 0x{status_reg.value:02x}')

        # Bit slice operations
        print('\nBit slice operations:')
        print(f'  Bits [7:3]: 0x{status_reg[7:3]:x} (MODE field)')
        status_reg[2:1] = 0x2  # Set ERROR field
        print('  Set ERROR bits [2:1] to 0x2')
        print(f'  STATUS_REG value now: 0x{status_reg.value:02x}')

        # Demonstrate with CONFIG_REG fields
        print('\nCONFIG_REG field access:')
        config_reg = mapped_block['CONFIG_REG']
        print(f'  THRESHOLD: 0x{config_reg["THRESHOLD"]:02x}')
        print(f'  GAIN:      0x{config_reg["GAIN"]:02x}')
        print(f'  OFFSET:    0x{config_reg["OFFSET"]:02x}')


def demonstrate_field_access():
    """Show field-level operations."""
    print('\n=== Field Access ===')

    # Create a temporary copy of test.bin for modification
    with tempfile.NamedTemporaryFile(delete=False, suffix='.bin') as temp_file:
        temp_bin_path = temp_file.name

    shutil.copy(BIN_PATH, temp_bin_path)

    try:
        with rw.RegisterFile(REGDB_PATH) as rf:
            access_fields(temp_bin_path, rf)

    finally:
        os.unlink(temp_bin_path)


def main():
    """Run MappedRegisterFile demonstrations."""

    demonstrate_register_access()
    demonstrate_field_access()


if __name__ == '__main__':
    main()
