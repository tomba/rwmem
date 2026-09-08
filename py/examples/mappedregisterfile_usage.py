#!/usr/bin/env python3
"""
Pyrwmem Example: MappedRegisterFile Usage

Register access by name, combining a register database with a memory
mapping. String keys are the short form and do I/O; register and field
handles are looked up once and reused.
"""

import os
import shutil
import tempfile

import rwmem as rw


def demonstrate(bin_path, regdb_path):
    # A MappedRegisterFile opens and owns the RegisterFile when given a path.
    # Point its blocks at the copy of test.bin instead of /dev/mem.
    with rw.MappedRegisterFile(
        regdb_path,
        target_factory=lambda rb: rw.MMapTarget(
            bin_path, rb.offset, rb.size, rb.data_endianness, rb.data_size
        ),
    ) as mrf:
        print('=== Reading by path ===')
        print(f'  STATUS_REG:      0x{mrf["SENSOR_A.STATUS_REG"]:02x}')
        print(f'  STATUS_REG:MODE: 0x{mrf["SENSOR_A.STATUS_REG:MODE"]:x}')
        print(f'  bits [7:3]:      0x{mrf["SENSOR_A.STATUS_REG:7:3"]:x}')

        # A read returns a value that can decode its own fields.
        value = mrf['SENSOR_A.STATUS_REG']
        print(f'  decoded:         {value.fields}')

        print('\n=== Writing by path ===')
        mrf['SENSOR_A.STATUS_REG:MODE'] = 0x10  # read-modify-write of one field
        print(f'  after MODE=0x10: 0x{mrf["SENSOR_A.STATUS_REG"]:02x}')
        mrf['SENSOR_A.CONFIG_REG'] = {'THRESHOLD': 0xAB, 'GAIN': 0xCD, 'OFFSET': 0xEF}
        print(f'  CONFIG_REG:      0x{mrf["SENSOR_A.CONFIG_REG"]:06x}')

        print('\n=== Handles ===')
        # A block scope drops the block prefix; a register handle is reused.
        sensor = mrf['SENSOR_A']
        reg = sensor.reg('DATA_REG')
        reg.write(0x1234)
        print(f'  {reg.name} @0x{reg.address:x} = 0x{reg.read():04x}')

        print('\n=== Whole block in one read ===')
        for name, value in mrf['SENSOR_A.*'].items():
            print(f'  {name} = 0x{value:x}')


def main():
    script_dir = os.path.dirname(os.path.abspath(__file__))
    regdb_path = os.path.join(script_dir, '..', 'tests', 'test.regdb')
    src_bin = os.path.join(script_dir, '..', 'tests', 'test.bin')

    # Work on a writable copy of the test data.
    with tempfile.NamedTemporaryFile(delete=False, suffix='.bin') as tmp:
        bin_path = tmp.name
    shutil.copy(src_bin, bin_path)
    try:
        demonstrate(bin_path, regdb_path)
    finally:
        os.unlink(bin_path)


if __name__ == '__main__':
    main()
