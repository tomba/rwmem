#!/usr/bin/env python3

import os
import shutil
import stat
import tempfile
import unittest

import rwmem as rw

BIN_PATH = os.path.dirname(os.path.abspath(__file__)) + '/test.bin'

class ContextManagerTests(unittest.TestCase):
    def test(self):
        with rw.MMapTarget(BIN_PATH, 0, 32,
                           rw.Endianness.Big, 4,
                           rw.MapMode.Read) as map:
            self.assertEqual(map.read(8, 4), 0xf00dbaad)

class MmapTests(unittest.TestCase):
    def setUp(self):
        self.map = rw.MMapTarget(BIN_PATH, 0, 32,
                                 rw.Endianness.Big, 4,
                                 rw.MapMode.Read)

    def tests(self):
        map = self.map

        # Test 8-bit reads (1 byte)
        self.assertEqual(map.read(0, 1), 0x00)
        self.assertEqual(map.read(1, 1), 0x11)
        self.assertEqual(map.read(2, 1), 0x22)
        self.assertEqual(map.read(3, 1), 0x33)
        self.assertEqual(map.read(4, 1), 0x44)
        self.assertEqual(map.read(8, 1), 0xf0)

        # Test 16-bit reads (2 bytes)
        self.assertEqual(map.read(0, 2), 0x0011)
        self.assertEqual(map.read(0, 2, rw.Endianness.Big), 0x0011)
        self.assertEqual(map.read(0, 2, rw.Endianness.Little), 0x1100)
        self.assertEqual(map.read(2, 2), 0x2233)
        self.assertEqual(map.read(2, 2, rw.Endianness.Big), 0x2233)
        self.assertEqual(map.read(4, 2), 0x4455)
        self.assertEqual(map.read(4, 2, rw.Endianness.Big), 0x4455)

        # Test 24-bit reads (3 bytes)
        self.assertEqual(map.read(0, 3), 0x001122)
        self.assertEqual(map.read(0, 3, rw.Endianness.Big), 0x001122)
        self.assertEqual(map.read(0, 3, rw.Endianness.Little), 0x221100)
        self.assertEqual(map.read(1, 3), 0x112233)
        self.assertEqual(map.read(1, 3, rw.Endianness.Big), 0x112233)
        self.assertEqual(map.read(4, 3), 0x445566)
        self.assertEqual(map.read(4, 3, rw.Endianness.Big), 0x445566)

        # Test 32-bit reads (4 bytes)
        self.assertEqual(map.read(0, 4), 0x00112233)
        self.assertEqual(map.read(0, 4, rw.Endianness.Big), 0x00112233)
        self.assertEqual(map.read(0, 4, rw.Endianness.Little), 0x33221100)
        self.assertEqual(map.read(4, 4), 0x44556677)
        self.assertEqual(map.read(4, 4, rw.Endianness.Big), 0x44556677)
        self.assertEqual(map.read(8, 4), 0xf00dbaad)
        self.assertEqual(map.read(8, 4, rw.Endianness.Big), 0xf00dbaad)
        self.assertEqual(map.read(12, 4), 0xabbaaabb)
        self.assertEqual(map.read(16, 4), 0x00560078)
        self.assertEqual(map.read(20, 4), 0x00112233)
        self.assertEqual(map.read(24, 4), 0x44556677)
        self.assertEqual(map.read(28, 4), 0xdeadbeef)

        # Test 40-bit reads (5 bytes)
        self.assertEqual(map.read(0, 5), 0x0011223344)
        self.assertEqual(map.read(0, 5, rw.Endianness.Big), 0x0011223344)
        self.assertEqual(map.read(0, 5, rw.Endianness.Little), 0x4433221100)
        self.assertEqual(map.read(1, 5), 0x1122334455)
        self.assertEqual(map.read(1, 5, rw.Endianness.Big), 0x1122334455)
        self.assertEqual(map.read(3, 5), 0x3344556677)
        self.assertEqual(map.read(3, 5, rw.Endianness.Big), 0x3344556677)

        # Test 48-bit reads (6 bytes)
        self.assertEqual(map.read(0, 6), 0x001122334455)
        self.assertEqual(map.read(0, 6, rw.Endianness.Big), 0x001122334455)
        self.assertEqual(map.read(0, 6, rw.Endianness.Little), 0x554433221100)
        self.assertEqual(map.read(1, 6), 0x112233445566)
        self.assertEqual(map.read(1, 6, rw.Endianness.Big), 0x112233445566)
        self.assertEqual(map.read(2, 6), 0x223344556677)
        self.assertEqual(map.read(2, 6, rw.Endianness.Big), 0x223344556677)

        # Test 56-bit reads (7 bytes)
        self.assertEqual(map.read(0, 7), 0x00112233445566)
        self.assertEqual(map.read(0, 7, rw.Endianness.Big), 0x00112233445566)
        self.assertEqual(map.read(0, 7, rw.Endianness.Little), 0x66554433221100)
        self.assertEqual(map.read(1, 7), 0x11223344556677)
        self.assertEqual(map.read(1, 7, rw.Endianness.Big), 0x11223344556677)
        self.assertEqual(map.read(8, 7), 0xf00dbaadabbaaa)
        self.assertEqual(map.read(8, 7, rw.Endianness.Big), 0xf00dbaadabbaaa)

        # Test 64-bit reads (8 bytes)
        self.assertEqual(map.read(0, 8), 0x0011223344556677)
        self.assertEqual(map.read(0, 8, rw.Endianness.Big), 0x0011223344556677)
        self.assertEqual(map.read(0, 8, rw.Endianness.Little), 0x7766554433221100)
        self.assertEqual(map.read(24, 8), 0x44556677deadbeef)
        self.assertEqual(map.read(24, 8, rw.Endianness.Big), 0x44556677deadbeef)

        # Test that writes fail

        with self.assertRaises(RuntimeError):
            map.write(0, 0x12345678, 8)

        # Test bad reads
        with self.assertRaises(RuntimeError):
            map.read(33, 1)

        with self.assertRaises(RuntimeError):
            map.read(30, 8)


class WriteMmapTests(unittest.TestCase):
    def setUp(self):
        self.tmpfile = tempfile.NamedTemporaryFile(mode='w+b', suffix='.bin', delete=True)
        self.tmpfile_path = self.tmpfile.name

        shutil.copy2(BIN_PATH, self.tmpfile_path)
        os.chmod(self.tmpfile_path, stat.S_IREAD | stat.S_IWRITE)

        self.map = rw.MMapTarget(self.tmpfile_path, 0, 32,
                                 rw.Endianness.Big, 4,
                                 rw.MapMode.ReadWrite)

    def tests(self):
        map = self.map

        # Test 8-bit writes (1 byte)
        map.write(16, 0xab, 1)
        self.assertEqual(map.read(16, 1), 0xab)
        map.write(17, 0xcd, 1, rw.Endianness.Big)
        self.assertEqual(map.read(17, 1, rw.Endianness.Big), 0xcd)
        map.write(18, 0xef, 1, rw.Endianness.Little)
        self.assertEqual(map.read(18, 1, rw.Endianness.Little), 0xef)

        # Test 16-bit writes (2 bytes)
        map.write(20, 0x1234, 2)
        self.assertEqual(map.read(20, 2), 0x1234)
        map.write(22, 0x5678, 2, rw.Endianness.Big)
        self.assertEqual(map.read(22, 2, rw.Endianness.Big), 0x5678)
        map.write(24, 0x9abc, 2, rw.Endianness.Little)
        self.assertEqual(map.read(24, 2, rw.Endianness.Little), 0x9abc)

        # Test 24-bit writes (3 bytes)
        map.write(16, 0xabcdef, 3)
        self.assertEqual(map.read(16, 3), 0xabcdef)
        map.write(19, 0x123456, 3, rw.Endianness.Big)
        self.assertEqual(map.read(19, 3, rw.Endianness.Big), 0x123456)
        map.write(22, 0xfedcba, 3, rw.Endianness.Little)
        self.assertEqual(map.read(22, 3, rw.Endianness.Little), 0xfedcba)

        # Test 32-bit writes (4 bytes)
        map.write(8, 0x12345678, 4)
        self.assertEqual(map.read(8, 4), 0x12345678)
        map.write(12, 0x9abcdef0, 4, rw.Endianness.Big)
        self.assertEqual(map.read(12, 4, rw.Endianness.Big), 0x9abcdef0)
        map.write(16, 0xfedcba98, 4, rw.Endianness.Little)
        self.assertEqual(map.read(16, 4, rw.Endianness.Little), 0xfedcba98)

        # Test 40-bit writes (5 bytes) - write to separate region
        map.write(25, 0x123456789a, 5)
        self.assertEqual(map.read(25, 5), 0x123456789a)
        map.write(25, 0xabcdef0123, 5, rw.Endianness.Big)
        self.assertEqual(map.read(25, 5, rw.Endianness.Big), 0xabcdef0123)
        map.write(25, 0x9876543210, 5, rw.Endianness.Little)
        self.assertEqual(map.read(25, 5, rw.Endianness.Little), 0x9876543210)

        # Test 48-bit writes (6 bytes) - write to separate region
        map.write(26, 0x123456789abc, 6)
        self.assertEqual(map.read(26, 6), 0x123456789abc)
        map.write(26, 0xabcdef012345, 6, rw.Endianness.Big)
        self.assertEqual(map.read(26, 6, rw.Endianness.Big), 0xabcdef012345)
        map.write(26, 0x987654321098, 6, rw.Endianness.Little)
        self.assertEqual(map.read(26, 6, rw.Endianness.Little), 0x987654321098)

        # Test 56-bit writes (7 bytes) - write to separate region
        map.write(25, 0x123456789abcde, 7)
        self.assertEqual(map.read(25, 7), 0x123456789abcde)
        map.write(25, 0xabcdef01234567, 7, rw.Endianness.Big)
        self.assertEqual(map.read(25, 7, rw.Endianness.Big), 0xabcdef01234567)
        map.write(25, 0x98765432109876, 7, rw.Endianness.Little)
        self.assertEqual(map.read(25, 7, rw.Endianness.Little), 0x98765432109876)

        # Test 64-bit writes (8 bytes)
        map.write(0, 0x8899aabbccddeeff, 8)
        self.assertEqual(map.read(0, 8), 0x8899aabbccddeeff)
        map.write(0, 0x1122334455667788, 8, rw.Endianness.Big)
        self.assertEqual(map.read(0, 8, rw.Endianness.Big), 0x1122334455667788)
        map.write(0, 0xffeeddccbbaa9988, 8, rw.Endianness.Little)
        self.assertEqual(map.read(0, 8, rw.Endianness.Little), 0xffeeddccbbaa9988)
