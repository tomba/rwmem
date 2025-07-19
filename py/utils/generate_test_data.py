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
import struct
import sys

# Add parent directory to path to import rwmem modules
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..'))

import rwmem as rw
import rwmem.gen as gen


def generate_test_bin(output_path: str):
    """Generate test.bin binary data file.

    Creates a 32-byte binary file with:
    - Sequential pattern: 00 11 22 33 44 55 66 77
    - Test register values at specific offsets:
      - REG1 @ 8:  0xf00dbaad
      - REG2 @ 12: 0xabbaaabb
      - REG3 @ 16: 0x00560078
    - Additional test data to fill 32 bytes
    """
    # Create 32-byte binary data
    data = bytearray(32)

    # Fill first 8 bytes with sequential pattern
    for i in range(8):
        data[i] = i * 0x11

    # REG1 @ offset 8: 0xf00dbaad (big endian)
    struct.pack_into('>I', data, 8, 0xf00dbaad)

    # REG2 @ offset 12: 0xabbaaabb (big endian)
    struct.pack_into('>I', data, 12, 0xabbaaabb)

    # REG3 @ offset 16: 0x00560078 (big endian)
    struct.pack_into('>I', data, 16, 0x00560078)

    # Fill remaining bytes with additional test pattern
    # Bytes 20-23: 00 11 22 33
    # Bytes 24-27: 44 55 66 77
    # Bytes 28-31: de ad be ef
    for i in range(4):
        data[20 + i] = i * 0x11
        data[24 + i] = (i + 4) * 0x11
    struct.pack_into('>I', data, 28, 0xdeadbeef)

    # Write binary data to file
    with open(output_path, 'wb') as f:
        f.write(data)

    print(f'Generated {output_path} ({len(data)} bytes)')


def generate_test_regs(output_path: str):
    """Generate test.regdb register database file.

    Creates a register database with:
    - TEST register file containing BLOCK1
    - BLOCK1 with REG1, REG2, REG3 registers
    - Each register has sub-fields matching test expectations
    """

    # Define register fields
    reg1_fields = [
        ('REG11', 31, 16),  # Upper 16 bits: 0xf00d
        ('REG12', 15, 0),   # Lower 16 bits: 0xbaad
    ]

    reg2_fields = [
        ('REG21', 31, 24),  # Byte 3: 0xab
        ('REG22', 23, 16),  # Byte 2: 0xba
        ('REG23', 15, 8),   # Byte 1: 0xaa
        ('REG24', 7, 0),    # Byte 0: 0xbb
    ]

    reg3_fields = [
        ('REG31', 23, 16),  # Byte 2: 0x56
        ('REG32', 7, 0),    # Byte 0: 0x78
    ]

    # Define registers with their offsets and fields
    block1_regs = [
        gen.UnpackedRegister('REG1', 8, reg1_fields),
        gen.UnpackedRegister('REG2', 12, reg2_fields),
        gen.UnpackedRegister('REG3', 16, reg3_fields),
    ]

    # Define register block
    # BLOCK1: offset 0, size 32, big endian, 4-byte addresses and data
    block1 = gen.UnpackedRegBlock(
        name='BLOCK1',
        offset=0,
        size=32,
        regs=block1_regs,
        addr_endianness=rw.Endianness.Big,
        addr_size=4,
        data_endianness=rw.Endianness.Big,
        data_size=4
    )

    # Create register file
    regfile = gen.UnpackedRegFile('TEST', [block1])

    # Pack and write to file
    with open(output_path, 'wb') as f:
        regfile.pack_to(f)

    print(f'Generated {output_path}')


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

    print(f'\n{regs_path} contains TEST register file with BLOCK1')


if __name__ == '__main__':
    main()
