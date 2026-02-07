"""Tests for registerfile_to_unpacked conversion."""

from __future__ import annotations

import io
import unittest

from rwmem.convert import registerfile_to_unpacked
from rwmem.enums import Endianness
from rwmem.gen import UnpackedField, UnpackedRegBlock, UnpackedRegFile, UnpackedRegister
from rwmem.registerfile import RegisterFile


class ConvertTests(unittest.TestCase):
    def test_roundtrip(self):
        """Test that UnpackedRegFile -> pack -> RegisterFile -> unpack produces equivalent data."""
        field1 = UnpackedField('ENABLE', 0, 0)
        field2 = UnpackedField('MODE', 3, 1)
        reg = UnpackedRegister('STATUS', 0x00, fields=[field1, field2])
        block = UnpackedRegBlock(
            name='BLOCK_A',
            offset=0x1000,
            size=0x100,
            regs=[reg],
            addr_endianness=Endianness.Little,
            addr_size=1,
            data_endianness=Endianness.Little,
            data_size=4,
        )
        original = UnpackedRegFile(name='TEST', blocks=[block])

        buf = io.BytesIO()
        original.pack_to(buf)
        buf.seek(0)

        rf = RegisterFile(buf.read())
        converted = registerfile_to_unpacked(rf)

        self.assertEqual(converted.name, 'TEST')
        self.assertEqual(len(converted.blocks), 1)

        cblock = converted.blocks[0]
        self.assertEqual(cblock.name, 'BLOCK_A')
        self.assertEqual(cblock.offset, 0x1000)
        self.assertEqual(cblock.size, 0x100)
        self.assertEqual(cblock.addr_endianness, Endianness.Little)
        self.assertEqual(cblock.addr_size, 1)
        self.assertEqual(cblock.data_endianness, Endianness.Little)
        self.assertEqual(cblock.data_size, 4)

        self.assertEqual(len(cblock.regs), 1)
        creg = cblock.regs[0]
        self.assertEqual(creg.name, 'STATUS')
        self.assertEqual(creg.offset, 0x00)
        self.assertIsNone(creg.data_endianness)
        self.assertIsNone(creg.data_size)

        self.assertEqual(len(creg.fields), 2)
        field_names = {f.name for f in creg.fields}
        self.assertEqual(field_names, {'ENABLE', 'MODE'})

    def test_load_test_regdb(self):
        """Test loading the test.regdb file."""
        rf = RegisterFile('py/tests/test.regdb')
        converted = registerfile_to_unpacked(rf)

        self.assertEqual(converted.name, 'TEST_V3')
        self.assertEqual(len(converted.blocks), 3)

        block_names = {b.name for b in converted.blocks}
        self.assertEqual(block_names, {'SENSOR_A', 'SENSOR_B', 'MEMORY_CTRL'})

        # SENSOR_A has 9 registers
        sensor_a = next(b for b in converted.blocks if b.name == 'SENSOR_A')
        self.assertEqual(len(sensor_a.regs), 9)

    def test_register_with_overrides(self):
        """Test that register-level data_endianness/data_size overrides are preserved."""
        field = UnpackedField('BIT', 0, 0)
        reg = UnpackedRegister(
            'REG_OVERRIDE',
            0x00,
            fields=[field],
            data_endianness=Endianness.Big,
            data_size=2,
        )
        block = UnpackedRegBlock(
            name='BLK',
            offset=0,
            size=0x10,
            regs=[reg],
            addr_endianness=Endianness.Little,
            addr_size=1,
            data_endianness=Endianness.Little,
            data_size=4,
        )
        original = UnpackedRegFile(name='TEST2', blocks=[block])

        buf = io.BytesIO()
        original.pack_to(buf)
        buf.seek(0)

        rf = RegisterFile(buf.read())
        converted = registerfile_to_unpacked(rf)

        creg = converted.blocks[0].regs[0]
        self.assertEqual(creg.data_endianness, Endianness.Big)
        self.assertEqual(creg.data_size, 2)


if __name__ == '__main__':
    unittest.main()
