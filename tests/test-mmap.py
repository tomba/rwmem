#!/usr/bin/python3

import os
import unittest
import tempfile
import shutil
import stat
import pyrwmem as rw

class MmapTests(unittest.TestCase):
    def setUp(self):
        path = os.path.dirname(os.path.abspath(__file__)) + '/test.bin'
        self.map = rw.MMapTarget(path)
        self.map.map(0, 32, rw.Endianness.Default, 4, rw.Endianness.Big, 4, rw.MapMode.Read)

    def tests(self):
        map = self.map

        self.assertEqual(map.read(0, 1), 0x00)
        self.assertEqual(map.read(1, 1), 0x11)
        self.assertEqual(map.read(2, 1), 0x22)
        self.assertEqual(map.read(3, 1), 0x33)

        self.assertEqual(map.read(0, 2), 0x0011)
        self.assertEqual(map.read(0, 2, rw.Endianness.Big), 0x0011)
        self.assertEqual(map.read(0, 2, rw.Endianness.Little), 0x1100)
        self.assertEqual(map.read(2, 2), 0x2233)

        self.assertEqual(map.read(0, 4), 0x00112233)
        self.assertEqual(map.read(4, 4), 0x44556677)

        self.assertEqual(map.read(8, 4), 0xf00dbaad)
        self.assertEqual(map.read(12, 4), 0xabbaaabb)
        self.assertEqual(map.read(16, 4), 0x00560078)

        self.assertEqual(map.read(20, 4), 0x00112233)
        self.assertEqual(map.read(24, 4), 0x44556677)
        self.assertEqual(map.read(28, 4), 0xdeadbeef)

        self.assertEqual(map.read(0, 8), 0x0011223344556677)
        self.assertEqual(map.read(24, 8), 0x44556677deadbeef)


class WriteMmapTests(unittest.TestCase):
    def setUp(self):
        path = os.path.dirname(os.path.abspath(__file__)) + '/test.bin'

        self.tmpfile = tempfile.NamedTemporaryFile(mode='w+b', suffix='.bin', delete=True)
        self.tmpfile_name = self.tmpfile.name

        shutil.copy2(path, self.tmpfile_name)
        os.chmod(self.tmpfile_name, stat.S_IREAD | stat.S_IWRITE)

        self.map = rw.MMapTarget(self.tmpfile_name)
        self.map.map(0, 32, rw.Endianness.Default, 4, rw.Endianness.Big, 4, rw.MapMode.ReadWrite)

    def tests(self):
        map = self.map

        self.assertEqual(map.read(0, 1), 0x00)
        self.assertEqual(map.read(1, 1), 0x11)
        self.assertEqual(map.read(2, 1), 0x22)
        self.assertEqual(map.read(3, 1), 0x33)

        self.assertEqual(map.read(0, 2), 0x0011)
        self.assertEqual(map.read(0, 2, rw.Endianness.Big), 0x0011)
        self.assertEqual(map.read(0, 2, rw.Endianness.Little), 0x1100)
        self.assertEqual(map.read(2, 2), 0x2233)

        self.assertEqual(map.read(0, 4), 0x00112233)
        self.assertEqual(map.read(4, 4), 0x44556677)

        self.assertEqual(map.read(8, 4), 0xf00dbaad)
        self.assertEqual(map.read(12, 4), 0xabbaaabb)
        self.assertEqual(map.read(16, 4), 0x00560078)

        self.assertEqual(map.read(20, 4), 0x00112233)
        self.assertEqual(map.read(24, 4), 0x44556677)
        self.assertEqual(map.read(28, 4), 0xdeadbeef)

        self.assertEqual(map.read(0, 8), 0x0011223344556677)
        self.assertEqual(map.read(24, 8), 0x44556677deadbeef)

        map.write(0, 0x12345678, 8)
        self.assertEqual(map.read(0, 8), 0x12345678)


if __name__ == '__main__':
    unittest.main()
