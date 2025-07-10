#!/usr/bin/env python3

import os
import shutil
import stat
import subprocess
import tempfile
import unittest

RWMEM_CMD_PATH = os.path.dirname(os.path.abspath(__file__)) + '/../build/rwmem/rwmem'
DATA_BIN_PATH = os.path.dirname(os.path.abspath(__file__)) + '/data.bin'
TEST_REGDB_PATH = os.path.dirname(os.path.abspath(__file__)) + '/data.regdb'

class RwmemTestBase(unittest.TestCase):
    def setUp(self):
        if 'RWMEM_CMD' in os.environ:
            self.rwmem_cmd =  os.environ['RWMEM_CMD']
        else:
            self.rwmem_cmd = RWMEM_CMD_PATH

        self.rwmem_common_opts = []

    def assertOutput(self, rwmemopts, expected):
        opts = self.rwmem_common_opts + rwmemopts

        res = subprocess.run([self.rwmem_cmd, *opts],
                             capture_output=True,
                             encoding='ASCII', check=False)

        self.assertEqual(res.returncode, 0, res)
        self.assertEqual(res.stdout, expected, res)


class RwmemNumericReadTests(RwmemTestBase):
    def setUp(self):
        super().setUp()

        self.rwmem_common_opts = ['--mmap=' + DATA_BIN_PATH]

    def test_numeric_reads_single(self):
        self.assertOutput(['0'],
                          '0x00 = 0x0f7216c2\n')

        self.assertOutput(['0x10'],
                          '0x10 (+0x0) = 0xfbf9f1c4\n')

        self.assertOutput(['-s8', '0'],
                          '0x00 = 0xc2\n')

        self.assertOutput(['-s16', '0'],
                          '0x00 = 0x16c2\n')

        self.assertOutput(['-s16', '0'],
                          '0x00 = 0x16c2\n')

        self.assertOutput(['-s32', '0'],
                          '0x00 = 0x0f7216c2\n')

        self.assertOutput(['-s24', '0'],
                          '0x00 = 0x7216c2\n')

        self.assertOutput(['-s24be', '0'],
                          '0x00 = 0xc21672\n')

    def test_numeric_reads_ranges(self):
        self.assertOutput(['0x0-0x10'],
                          '0x00 = 0x0f7216c2\n' +
                          '0x04 = 0x7d12d37b\n' +
                          '0x08 = 0x5e1721ec\n' +
                          '0x0c = 0x3b0eb509\n')

        self.assertOutput(['0x0+0x10'],
                          '0x00 = 0x0f7216c2\n' +
                          '0x04 = 0x7d12d37b\n' +
                          '0x08 = 0x5e1721ec\n' +
                          '0x0c = 0x3b0eb509\n')

        self.assertOutput(['0x10-0x20'],
                           '0x10 (+0x0) = 0xfbf9f1c4\n' +
                           '0x14 (+0x4) = 0x85f114a9\n' +
                           '0x18 (+0x8) = 0xa4edffdd\n' +
                           '0x1c (+0xc) = 0x2ecde8ff\n')

        self.assertOutput(['0x10+0x10'],
                           '0x10 (+0x0) = 0xfbf9f1c4\n' +
                           '0x14 (+0x4) = 0x85f114a9\n' +
                           '0x18 (+0x8) = 0xa4edffdd\n' +
                           '0x1c (+0xc) = 0x2ecde8ff\n')


class RwmemNumericWriteTests(RwmemTestBase):
    def setUp(self):
        super().setUp()

        self.tmpfile = tempfile.NamedTemporaryFile(mode='w+b', suffix='.bin', delete=True)
        self.tmpfile_name = self.tmpfile.name

        shutil.copy2(DATA_BIN_PATH, self.tmpfile_name)
        os.chmod(self.tmpfile_name, stat.S_IREAD | stat.S_IWRITE)

        self.rwmem_common_opts = ['--mmap=' + self.tmpfile_name]

    def test_numeric_writes_single(self):
        self.assertOutput(['0x0=0'],
                          '0x00 = 0x0f7216c2 := 0x00000000 -> 0x00000000\n')

        self.assertOutput(['0xa0=0'],
                          '0xa0 (+0x0) = 0xc4f32790 := 0x00000000 -> 0x00000000\n')

        self.assertOutput(['-s24', '0xb0=0x123456'],
                          '0xb0 (+0x0) = 0x62ce25 := 0x123456 -> 0x123456\n')

    def test_numeric_writes_ranges(self):
        self.assertOutput(['0x10+0x10=0x1234'],
                           '0x10 (+0x0) = 0xfbf9f1c4 := 0x00001234 -> 0x00001234\n' +
                           '0x14 (+0x4) = 0x85f114a9 := 0x00001234 -> 0x00001234\n' +
                           '0x18 (+0x8) = 0xa4edffdd := 0x00001234 -> 0x00001234\n' +
                           '0x1c (+0xc) = 0x2ecde8ff := 0x00001234 -> 0x00001234\n')


class RwmemRegisterDatabaseTests(RwmemTestBase):
    def setUp(self):
        super().setUp()

        self.rwmem_common_opts = ['--regs=' + TEST_REGDB_PATH, '--mmap=' + DATA_BIN_PATH]

    def test_regdb_list(self):
        # Test register database listing
        res = subprocess.run([self.rwmem_cmd, '--regs=' + TEST_REGDB_PATH, '--list'],
                           capture_output=True, encoding='ASCII', check=False)

        self.assertEqual(res.returncode, 0, res)
        self.assertIn('TestChip: total 4/9/18', res.stdout)
        self.assertIn('ByteRegs:', res.stdout)
        self.assertIn('WordRegs:', res.stdout)
        self.assertIn('DwordRegs:', res.stdout)
        self.assertIn('QwordRegs:', res.stdout)

    def test_regdb_byte_register(self):
        # Test 8-bit register access
        self.assertOutput(['ByteRegs.BYTE0'],
                          'ByteRegs.BYTE0                 0x00000000 = 0xc2\n' +
                          '  VAL                             7:0  = 0xc2 \n')

        self.assertOutput(['ByteRegs.BYTE1'],
                          'ByteRegs.BYTE1                 0x00000001 = 0x16\n' +
                          '  VAL                             7:0  = 0x16 \n')

    def test_regdb_word_register(self):
        # Test 16-bit register access
        self.assertOutput(['WordRegs.WORD0'],
                          'WordRegs.WORD0                 0x00000020 (+0x10) = 0x175b\n' +
                          '  HIGH                           15:8  = 0x0017 \n' +
                          '  LOW                             7:0  = 0x005b \n')

    def test_regdb_dword_register(self):
        # Test 32-bit register access
        self.assertOutput(['DwordRegs.DWORD0'],
                          'DwordRegs.DWORD0               0x00000040 (+0x20) = 0x39a3ab9b\n' +
                          '  BITS31_24                      31:24 = 0x00000039 \n' +
                          '  BITS23_16                      23:16 = 0x000000a3 \n' +
                          '  BITS15_8                       15:8  = 0x000000ab \n' +
                          '  BITS7_0                         7:0  = 0x0000009b \n')

    def test_regdb_qword_register(self):
        # Test 64-bit register access
        self.assertOutput(['QwordRegs.QWORD0'],
                          'QwordRegs.QWORD0               0x00000080 (+0x40) = 0x195626529f41411b\n' +
                          '  HIGH32                         63:32 = 0x0000000019562652 \n' +
                          '  LOW32                          31:0  = 0x000000009f41411b \n')

    def test_regdb_field_access(self):
        # Test specific field access
        self.assertOutput(['DwordRegs.CONTROL:VALUE'],
                          'DwordRegs.CONTROL              0x00000044 (+0x24) = 0x0038e625\n' +
                          '  VALUE                          23:0  = 0x0038e625 \n')

        self.assertOutput(['DwordRegs.CONTROL:ENABLE'],
                          'DwordRegs.CONTROL              0x00000044 (+0x24) = 0x0038e625\n' +
                          '  ENABLE                            31 = 0x00000000 \n')


if __name__ == '__main__':
    unittest.main()
