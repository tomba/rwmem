#!/usr/bin/env python3
"""Tests for rwmem.convert."""

import io
import os
import unittest

from rwmem.convert import registerfile_to_unpacked
from rwmem.enums import Endianness
from rwmem.gen import UnpackedField, UnpackedRegBlock, UnpackedRegFile, UnpackedRegister
from rwmem.registerfile import RegisterFile

REGDB_PATH = os.path.dirname(os.path.abspath(__file__)) + '/test.regdb'


def pack(regfile: UnpackedRegFile) -> bytes:
    buf = io.BytesIO()
    regfile.pack_to(buf)
    return buf.getvalue()


def dump(regfile: UnpackedRegFile):
    """Everything the file format can hold, as plain tuples."""
    return (
        regfile.name,
        [
            (
                b.name,
                b.offset,
                b.size,
                b.addr_endianness,
                b.addr_size,
                b.data_endianness,
                b.data_size,
                b.description,
                [
                    (
                        r.name,
                        r.offset,
                        r.description,
                        r.reset_value,
                        r.data_endianness,
                        r.data_size,
                        [(f.name, f.high, f.low, f.description) for f in r.fields],
                    )
                    for r in b.regs
                ],
            )
            for b in regfile.blocks
        ],
    )


def make_regfile() -> UnpackedRegFile:
    # Fields in file order: the format stores them from the high bit down.
    status = UnpackedRegister(
        'STATUS',
        0x0,
        [UnpackedField('MODE', 3, 1), UnpackedField('ENABLE', 0, 0, 'Enable bit')],
        description='Status register',
        reset_value=0x5,
    )
    wide = UnpackedRegister(
        'WIDE', 0x4, [UnpackedField('BIT', 0, 0)], data_endianness=Endianness.Big, data_size=2
    )
    block_a = UnpackedRegBlock(
        'BLOCK_A',
        0x1000,
        0x100,
        [status, wide],
        Endianness.Little,
        1,
        Endianness.Little,
        4,
        description='Block A',
    )
    block_b = UnpackedRegBlock(
        'BLOCK_B', 0x2000, 0x10, [UnpackedRegister('R', 0)], Endianness.Big, 2, Endianness.Big, 1
    )
    return UnpackedRegFile('TEST', [block_a, block_b])


class ConvertTests(unittest.TestCase):
    def test_roundtrip(self):
        original = make_regfile()

        with RegisterFile(pack(original)) as rf:
            converted = registerfile_to_unpacked(rf)
        # rf is closed here, so the result must not reference it.

        self.assertEqual(dump(converted), dump(original))
        self.assertEqual(pack(converted), pack(original))

    def test_register_overrides(self):
        # The Register accessors distinguish an override from inheritance.
        with RegisterFile(pack(make_regfile())) as rf:
            self._check_overrides(rf)

    def _check_overrides(self, rf: RegisterFile):
        status = rf['BLOCK_A']['STATUS']
        self.assertIsNone(status.data_size)
        self.assertIsNone(status.data_endianness)
        self.assertEqual(status.effective_data_size, 4)
        self.assertEqual(status.effective_data_endianness, Endianness.Little)

        wide = rf['BLOCK_A']['WIDE']
        self.assertEqual(wide.data_size, 2)
        self.assertEqual(wide.data_endianness, Endianness.Big)
        self.assertEqual(wide.effective_data_size, 2)
        self.assertEqual(wide.effective_data_endianness, Endianness.Big)

    def test_load_test_regdb(self):
        with RegisterFile(REGDB_PATH) as rf:
            converted = registerfile_to_unpacked(rf)

        self.assertEqual(converted.name, 'TEST_V3')
        self.assertEqual(
            [b.name for b in converted.blocks], ['SENSOR_A', 'SENSOR_B', 'MEMORY_CTRL']
        )
        self.assertEqual(len(converted.blocks[0].regs), 9)

        # Packing the result and converting it again reproduces the result.
        # (The file itself is not compared byte for byte: it predates the
        # packer's deduplication of identical registers.)
        with RegisterFile(pack(converted)) as rf:
            again = registerfile_to_unpacked(rf)
        self.assertEqual(dump(again), dump(converted))


if __name__ == '__main__':
    unittest.main()
