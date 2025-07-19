#!/usr/bin/env python3

"""
Generate test data files for pyrwmem tests.

This script generates:
- test.bin: Binary data file with specific test values
- test.regdb: Register database file defining register layout

The generated files match the existing test data structure used by
pyrwmem tests in py/tests/.
"""

import os
import random
import sys

# Add parent directory to path to import rwmem modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import rwmem as rw
import rwmem.gen as gen


def generate_test_bin(output_path: str):
    """Generate test.bin binary data file.

    Creates a 768-byte binary file with random data for comprehensive testing:
    - Address space: 0x000-0x2FF (768 bytes total)
    - Three 256-byte blocks: SENSOR_A (0x000), SENSOR_B (0x100), MEMORY_CTRL (0x200)
    - Uses fixed random seed for reproducible test data
    """
    # Use fixed seed for reproducible test data
    random.seed(42)

    # Create 768-byte binary data (3 blocks × 256 bytes each)
    data = bytearray(768)

    # Fill with random data
    for i in range(len(data)):
        data[i] = random.randint(0, 255)

    # Write binary data to file
    with open(output_path, 'wb') as f:
        f.write(data)

    print(f'Generated {output_path} ({len(data)} bytes)')


def generate_test_regs(output_path: str):
    """Generate test.regdb register database file.

    Creates a comprehensive v3 register database with:
    - TEST_V3 register file with three blocks
    - SENSOR_A block: 9 registers covering all data sizes 1-8 bytes
    - SENSOR_B block: identical to SENSOR_A for register deduplication testing
    - MEMORY_CTRL block: demonstrates field sharing across different registers
    - Full v3 feature coverage: descriptions, reset values, sharing
    """

    # Shared field definitions for deduplication testing
    error_field = gen.UnpackedField('ERROR', 2, 1, 'Error status bits')
    mode_field = gen.UnpackedField('MODE', 7, 3, 'Operating mode')
    threshold_field = gen.UnpackedField('THRESHOLD', 23, 16, 'Threshold value')
    gain_field = gen.UnpackedField('GAIN', 15, 8, 'Gain setting')
    offset_field = gen.UnpackedField('OFFSET', 7, 0, 'Offset value')
    data_field = gen.UnpackedField('DATA', 31, 0, 'Data value')

    # SENSOR_A block registers - covering all data sizes 1-8 bytes
    sensor_a_regs = [
        # 1-byte register
        gen.UnpackedRegister('STATUS_REG', 0x00, [
            gen.UnpackedField('READY', 0, 0, 'Ready flag'),
            error_field,  # Shared field
            mode_field,   # Shared field
        ], 'Device status register', reset_value=0x80, data_size=1),

        # 1-byte register (shares fields with STATUS_REG)
        gen.UnpackedRegister('CONTROL_REG', 0x01, [
            gen.UnpackedField('ENABLE', 0, 0, 'Enable flag'),
            error_field,  # Shared field
            mode_field,   # Shared field
        ], 'Device control register', reset_value=0x00, data_size=1),

        # 2-byte register
        gen.UnpackedRegister('DATA_REG', 0x02, [
            gen.UnpackedField('VALUE', 15, 0, '16-bit data value'),
        ], 'Data register', reset_value=0x1234, data_size=2),

        # 3-byte register (shares fields with MEMORY_CTRL CONFIG_REG)
        gen.UnpackedRegister('CONFIG_REG', 0x04, [
            threshold_field,  # Shared field
            gain_field,       # Shared field
            offset_field,     # Shared field
        ], 'Configuration register', reset_value=0x123456, data_size=3),

        # 4-byte register
        gen.UnpackedRegister('COUNTER_REG', 0x08, [
            gen.UnpackedField('COUNT', 31, 0, 'Counter value'),
        ], 'Counter register', reset_value=0x00000000, data_size=4),

        # 5-byte register
        gen.UnpackedRegister('BIG_REG', 0x0C, [
            gen.UnpackedField('BIG_DATA', 39, 0, '40-bit data value'),
        ], 'Big data register', reset_value=0x123456789A, data_size=5),

        # 6-byte register
        gen.UnpackedRegister('HUGE_REG', 0x14, [
            gen.UnpackedField('HUGE_DATA', 47, 0, '48-bit data value'),
        ], 'Huge data register', reset_value=0x123456789ABC, data_size=6),

        # 7-byte register
        gen.UnpackedRegister('GIANT_REG', 0x1C, [
            gen.UnpackedField('GIANT_DATA', 55, 0, '56-bit data value'),
        ], 'Giant data register', reset_value=0x123456789ABCDE, data_size=7),

        # 8-byte register
        gen.UnpackedRegister('MAX_REG', 0x24, [
            gen.UnpackedField('MAX_DATA', 63, 0, '64-bit data value'),
        ], 'Maximum size register', reset_value=0x123456789ABCDEF0, data_size=8),
    ]

    # SENSOR_A block: I2C-style, little endian, 1-byte addressing, 4-byte default data
    sensor_a_block = gen.UnpackedRegBlock(
        name='SENSOR_A',
        offset=0x000,
        size=0x100,  # 256 bytes
        regs=sensor_a_regs,
        addr_endianness=rw.Endianness.Little,
        addr_size=1,
        data_endianness=rw.Endianness.Little,
        data_size=4,
        description='Sensor A device registers (I2C-style)'
    )

    # SENSOR_B block: identical to SENSOR_A for register deduplication testing
    sensor_b_regs = [
        # Create identical registers but at different offsets for SENSOR_B
        gen.UnpackedRegister('STATUS_REG', 0x00, [
            gen.UnpackedField('READY', 0, 0, 'Ready flag'),
            error_field,  # Shared field
            mode_field,   # Shared field
        ], 'Device status register', reset_value=0x80, data_size=1),

        gen.UnpackedRegister('CONTROL_REG', 0x01, [
            gen.UnpackedField('ENABLE', 0, 0, 'Enable flag'),
            error_field,  # Shared field
            mode_field,   # Shared field
        ], 'Device control register', reset_value=0x00, data_size=1),

        gen.UnpackedRegister('DATA_REG', 0x02, [
            gen.UnpackedField('VALUE', 15, 0, '16-bit data value'),
        ], 'Data register', reset_value=0x1234, data_size=2),

        gen.UnpackedRegister('CONFIG_REG', 0x04, [
            threshold_field,  # Shared field
            gain_field,       # Shared field
            offset_field,     # Shared field
        ], 'Configuration register', reset_value=0x123456, data_size=3),

        gen.UnpackedRegister('COUNTER_REG', 0x08, [
            gen.UnpackedField('COUNT', 31, 0, 'Counter value'),
        ], 'Counter register', reset_value=0x00000000, data_size=4),

        gen.UnpackedRegister('BIG_REG', 0x0C, [
            gen.UnpackedField('BIG_DATA', 39, 0, '40-bit data value'),
        ], 'Big data register', reset_value=0x123456789A, data_size=5),

        gen.UnpackedRegister('HUGE_REG', 0x14, [
            gen.UnpackedField('HUGE_DATA', 47, 0, '48-bit data value'),
        ], 'Huge data register', reset_value=0x123456789ABC, data_size=6),

        gen.UnpackedRegister('GIANT_REG', 0x1C, [
            gen.UnpackedField('GIANT_DATA', 55, 0, '56-bit data value'),
        ], 'Giant data register', reset_value=0x123456789ABCDE, data_size=7),

        gen.UnpackedRegister('MAX_REG', 0x24, [
            gen.UnpackedField('MAX_DATA', 63, 0, '64-bit data value'),
        ], 'Maximum size register', reset_value=0x123456789ABCDEF0, data_size=8),
    ]

    sensor_b_block = gen.UnpackedRegBlock(
        name='SENSOR_B',
        offset=0x100,
        size=0x100,  # 256 bytes
        regs=sensor_b_regs,
        addr_endianness=rw.Endianness.Little,
        addr_size=1,
        data_endianness=rw.Endianness.Little,
        data_size=4,
        description='Sensor B device registers (identical to SENSOR_A)'
    )

    # MEMORY_CTRL block: memory-mapped style with field sharing
    memory_ctrl_regs = [
        # 8-byte register
        gen.UnpackedRegister('ADDR_REG', 0x00, [
            gen.UnpackedField('ADDRESS', 63, 0, 'Memory address'),
        ], 'Address register', reset_value=0x0000000000000000, data_size=8),

        # 3-byte register (shares fields with SENSOR CONFIG_REG)
        gen.UnpackedRegister('CONFIG_REG', 0x08, [
            threshold_field,  # Shared field
            gain_field,       # Shared field
            offset_field,     # Shared field
        ], 'Memory controller configuration', reset_value=0xABCDEF, data_size=3),

        # 4-byte register (shares ERROR field)
        gen.UnpackedRegister('STATUS_REG', 0x0C, [
            gen.UnpackedField('BUSY', 0, 0, 'Memory busy flag'),
            error_field,  # Shared field
            gen.UnpackedField('READY', 31, 31, 'Memory ready flag'),
        ], 'Memory controller status', reset_value=0x80000000, data_size=4),

        # 4-byte register (shares layout with DATA_HI_REG)
        gen.UnpackedRegister('DATA_LO_REG', 0x10, [
            data_field,  # Shared field
        ], 'Lower 32-bit data', reset_value=0x12345678, data_size=4),

        # 4-byte register (shares layout with DATA_LO_REG)
        gen.UnpackedRegister('DATA_HI_REG', 0x14, [
            data_field,  # Shared field
        ], 'Upper 32-bit data', reset_value=0x9ABCDEF0, data_size=4),
    ]

    memory_ctrl_block = gen.UnpackedRegBlock(
        name='MEMORY_CTRL',
        offset=0x200,
        size=0x100,  # 256 bytes
        regs=memory_ctrl_regs,
        addr_endianness=rw.Endianness.Big,
        addr_size=4,
        data_endianness=rw.Endianness.Big,
        data_size=4,
        description='Memory controller registers (memory-mapped style)'
    )

    # Create comprehensive v3 register file
    regfile = gen.UnpackedRegFile(
        'TEST_V3',
        [sensor_a_block, sensor_b_block, memory_ctrl_block],
        'Comprehensive v3 test register database'
    )

    # Pack and write to file
    with open(output_path, 'wb') as f:
        regfile.pack_to(f)

    print(f'Generated {output_path} (v3 format with comprehensive features)')


def main():
    """Generate both test.bin and test.regdb files."""

    # Determine output directory (py/tests/)
    script_dir = os.path.dirname(os.path.abspath(__file__))
    tests_dir = os.path.join(script_dir, '..', 'tests')

    bin_path = os.path.join(tests_dir, 'test.bin')
    regs_path = os.path.join(tests_dir, 'test.regdb')

    print('Generating test data files...')
    print(f'Output directory: {tests_dir}')

    # Generate files
    generate_test_bin(bin_path)
    generate_test_regs(regs_path)

    print('\nTest data generation complete!')
    print('\nGenerated file contents:')

    # Show binary file contents using od-like format
    with open(bin_path, 'rb') as f:
        data = f.read()

    print(f'\n{bin_path} (hexdump):')
    for i in range(0, len(data), 16):
        chunk = data[i:i+16]
        offset = f'{i:06x}'
        hex_part = ' '.join(f'{b:02x}' for b in chunk)
        print(f'{offset} {hex_part}')

    print(f'\n{regs_path} contains TEST_V3 register file with three blocks:')
    print('  - SENSOR_A: 9 registers covering all data sizes 1-8 bytes')
    print('  - SENSOR_B: identical to SENSOR_A (register deduplication)')
    print('  - MEMORY_CTRL: field sharing demonstration')


if __name__ == '__main__':
    main()
