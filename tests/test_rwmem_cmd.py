#!/usr/bin/env python3

import os
import shutil
import stat
import subprocess
import tempfile
import unittest

RWMEM_CMD_PATH = os.path.dirname(os.path.abspath(__file__)) + '/../build/rwmem/rwmem'
DATA_BIN_PATH = os.path.dirname(os.path.abspath(__file__)) + '/test.bin'
TEST_REGDB_PATH = os.path.dirname(os.path.abspath(__file__)) + '/test.regdb'

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
                          '0x00 = 0x7d8c0c39\n')

        self.assertOutput(['0x10'],
                          '0x10 (+0x0) = 0x8ee570d6\n')

        self.assertOutput(['-s8', '0'],
                          '0x00 = 0x39\n')

        self.assertOutput(['-s16', '0'],
                          '0x00 = 0x0c39\n')

        self.assertOutput(['-s16', '0'],
                          '0x00 = 0x0c39\n')

        self.assertOutput(['-s32', '0'],
                          '0x00 = 0x7d8c0c39\n')

        self.assertOutput(['-s24', '0'],
                          '0x00 = 0x8c0c39\n')

        self.assertOutput(['-s24be', '0'],
                          '0x00 = 0x390c8c\n')

    def test_numeric_reads_ranges(self):
        self.assertOutput(['0x0-0x10'],
                          '0x00 = 0x7d8c0c39\n' +
                          '0x04 = 0x2c344772\n' +
                          '0x08 = 0x2f0f10d8\n' +
                          '0x0c = 0x650d776f\n')

        self.assertOutput(['0x0+0x10'],
                          '0x00 = 0x7d8c0c39\n' +
                          '0x04 = 0x2c344772\n' +
                          '0x08 = 0x2f0f10d8\n' +
                          '0x0c = 0x650d776f\n')

        self.assertOutput(['0x10-0x20'],
                           '0x10 (+0x0) = 0x8ee570d6\n' +
                           '0x14 (+0x4) = 0xaed85103\n' +
                           '0x18 (+0x8) = 0xac6e4f8e\n' +
                           '0x1c (+0xc) = 0x31c22f34\n')

        self.assertOutput(['0x10+0x10'],
                           '0x10 (+0x0) = 0x8ee570d6\n' +
                           '0x14 (+0x4) = 0xaed85103\n' +
                           '0x18 (+0x8) = 0xac6e4f8e\n' +
                           '0x1c (+0xc) = 0x31c22f34\n')


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
                          '0x00 = 0x7d8c0c39 := 0x00000000 -> 0x00000000\n')

        self.assertOutput(['0xa0=0'],
                          '0xa0 (+0x0) = 0x24a91022 := 0x00000000 -> 0x00000000\n')

        self.assertOutput(['-s24', '0xb0=0x123456'],
                          '0xb0 (+0x0) = 0xd8b5dc := 0x123456 -> 0x123456\n')

    def test_numeric_writes_ranges(self):
        self.assertOutput(['0x10+0x10=0x1234'],
                           '0x10 (+0x0) = 0x8ee570d6 := 0x00001234 -> 0x00001234\n' +
                           '0x14 (+0x4) = 0xaed85103 := 0x00001234 -> 0x00001234\n' +
                           '0x18 (+0x8) = 0xac6e4f8e := 0x00001234 -> 0x00001234\n' +
                           '0x1c (+0xc) = 0x31c22f34 := 0x00001234 -> 0x00001234\n')


class RwmemRegisterDatabaseTests(RwmemTestBase):
    def setUp(self):
        super().setUp()

        self.rwmem_common_opts = ['--regs=' + TEST_REGDB_PATH, '--mmap=' + DATA_BIN_PATH]

    def test_regdb_list(self):
        # Test register database listing
        res = subprocess.run([self.rwmem_cmd, '--regs=' + TEST_REGDB_PATH, '--list'],
                           capture_output=True, encoding='ASCII', check=False)

        self.assertEqual(res.returncode, 0, res)
        self.assertIn('TEST_V3: total 3/14/24', res.stdout)
        self.assertIn('SENSOR_A:', res.stdout)
        self.assertIn('SENSOR_B:', res.stdout)
        self.assertIn('MEMORY_CTRL:', res.stdout)

    def test_regdb_list_search_sensor_a(self):
        # Test listing with SENSOR_A pattern
        res = subprocess.run([self.rwmem_cmd, '--regs=' + TEST_REGDB_PATH, '--list', 'SENSOR_A'],
                           capture_output=True, encoding='ASCII', check=False)

        self.assertEqual(res.returncode, 0, res)
        self.assertEqual(res.stdout, 'SENSOR_A\n')

    def test_regdb_list_search_sens_wildcard(self):
        # Test listing with SENS* wildcard pattern
        res = subprocess.run([self.rwmem_cmd, '--regs=' + TEST_REGDB_PATH, '--list', 'SENS*'],
                           capture_output=True, encoding='ASCII', check=False)

        self.assertEqual(res.returncode, 0, res)
        self.assertEqual(res.stdout, 'SENSOR_A\nSENSOR_B\n')

    def test_regdb_list_search_sensor_a_dot_wildcard(self):
        # Test listing with SENSOR_A.* pattern
        res = subprocess.run([self.rwmem_cmd, '--regs=' + TEST_REGDB_PATH, '--list', 'SENSOR_A.*'],
                           capture_output=True, encoding='ASCII', check=False)

        self.assertEqual(res.returncode, 0, res)
        expected = 'SENSOR_A.STATUS_REG\nSENSOR_A.CONTROL_REG\nSENSOR_A.DATA_REG\nSENSOR_A.CONFIG_REG\nSENSOR_A.COUNTER_REG\nSENSOR_A.BIG_REG\nSENSOR_A.HUGE_REG\nSENSOR_A.GIANT_REG\nSENSOR_A.MAX_REG\n'
        self.assertEqual(res.stdout, expected)

    def test_regdb_list_search_sensor_a_stat_wildcard(self):
        # Test listing with SENSOR_A.STAT* pattern
        res = subprocess.run([self.rwmem_cmd, '--regs=' + TEST_REGDB_PATH, '--list', 'SENSOR_A.STAT*'],
                           capture_output=True, encoding='ASCII', check=False)

        self.assertEqual(res.returncode, 0, res)
        self.assertEqual(res.stdout, 'SENSOR_A.STATUS_REG\n')

    def test_regdb_byte_register(self):
        # Test 8-bit register access
        self.assertOutput(['SENSOR_A.STATUS_REG'],
                          'SENSOR_A.STATUS_REG            0x00 = 0x00000039\n' +
                          '  MODE                            7:3  = 0x00000007 \n' +
                          '  ERROR                           2:1  = 0x00000000 \n' +
                          '  READY                             0  = 0x00000001 \n')

        self.assertOutput(['SENSOR_A.CONTROL_REG'],
                          'SENSOR_A.CONTROL_REG           0x01 = 0x0000000c\n' +
                          '  MODE                            7:3  = 0x00000001 \n' +
                          '  ERROR                           2:1  = 0x00000002 \n' +
                          '  ENABLE                            0  = 0x00000000 \n')

    def test_regdb_word_register(self):
        # Test 16-bit register access
        self.assertOutput(['SENSOR_A.DATA_REG'],
                          'SENSOR_A.DATA_REG              0x02 = 0x00007d8c\n' +
                          '  VALUE                          15:0  = 0x00007d8c \n')

    def test_regdb_dword_register(self):
        # Test 32-bit register access
        self.assertOutput(['SENSOR_A.COUNTER_REG'],
                          'SENSOR_A.COUNTER_REG           0x08 = 0x2f0f10d8\n' +
                          '  COUNT                          31:0  = 0x2f0f10d8 \n')

    def test_regdb_tbyte_register(self):
        # Test 24-bit register access (3-byte)
        self.assertOutput(['SENSOR_A.CONFIG_REG'],
                          'SENSOR_A.CONFIG_REG            0x04 = 0x00344772\n' +
                          '  THRESHOLD                      23:16 = 0x00000034 \n' +
                          '  GAIN                           15:8  = 0x00000047 \n' +
                          '  OFFSET                          7:0  = 0x00000072 \n')

    def test_regdb_qword_register(self):
        # Test 64-bit register access
        self.assertOutput(['SENSOR_A.MAX_REG'],
                          'SENSOR_A.MAX_REG               0x24 = 0x2362b99628c13feb\n' +
                          '  MAX_DATA                       63:0  = 0x2362b99628c13feb \n')

    def test_regdb_field_access(self):
        # Test specific field access
        self.assertOutput(['SENSOR_A.CONFIG_REG:THRESHOLD'],
                          'SENSOR_A.CONFIG_REG            0x04 = 0x00344772\n' +
                          '  THRESHOLD                      23:16 = 0x00000034 \n')

        self.assertOutput(['SENSOR_A.STATUS_REG:MODE'],
                          'SENSOR_A.STATUS_REG            0x00 = 0x00000039\n' +
                          '  MODE                            7:3  = 0x00000007 \n')


if __name__ == '__main__':
    unittest.main()
