#!/usr/bin/env python3
"""
Pyrwmem Example: Register File Loading

This example shows how to load and explore register database files (.regdb)
using pyrwmem's RegisterFile class. Register files contain metadata about
hardware registers organized in a hierarchical structure.
"""

import os
import sys
import rwmem as rw

# Use test files from the test directory
SCRIPT_DIR = os.path.dirname(os.path.abspath(__file__))
REGDB_PATH = os.path.join(SCRIPT_DIR, '..', 'tests', 'test.regdb')

def explore_register_file(rf: rw.RegisterFile):
        # 1. Register File level
        print(f'Register File: {rf.name}')
        print(f'Blocks: {list(rf.keys())}')

        # 2. Register Block level
        first_block_name = list(rf.keys())[0]
        block = rf[first_block_name]
        print(f'\nBlock: {block.name} @ 0x{block.offset:x}')
        print(f'Registers: {list(block.keys())}')

        # 3. Register level
        first_reg_name = list(block.keys())[0]
        register = block[first_reg_name]
        print(f'\nRegister: {register.name} @ 0x{register.offset:x}')
        print(f'Size: {register.effective_data_size} bytes')
        print(f'Reset: 0x{register.reset_value:x}')

        # 4. Field level (if fields exist)
        if len(register) > 0:
            print(f'Fields: {list(register.keys())}')

            first_field_name = list(register.keys())[0]
            field = register[first_field_name]
            bit_range = f'{field.high}:{field.low}' if field.high != field.low else str(field.low)
            print(f'\nField: {field.name} [{bit_range}]')
        else:
            print('Fields: none')


def main():
    """Load and explore the hierarchy: file → blocks → registers → fields."""
    print(f'Loading: {REGDB_PATH}')

    with rw.RegisterFile(REGDB_PATH) as rf:
        explore_register_file(rf)


if __name__ == '__main__':
    sys.exit(main())
