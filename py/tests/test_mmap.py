#!/usr/bin/python3

import difflib
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

        # Test different read positions, sizes and endiannesses

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

        self.assertEqual(map.read(0, 8), 0x0011223344556677)
        map.write(0, 0x8899aabbccddeeff, 8)
        self.assertEqual(map.read(0, 8), 0x8899aabbccddeeff)

        with (open(BIN_PATH, 'rb') as f1,
              open(self.tmpfile_path, 'rb') as f2):
            x = f1.read()
            y = f2.read()

            s = difflib.SequenceMatcher(None, x, y)
            ref = ((8, 8, 24), (32, 32, 0))
            matching = list(s.get_matching_blocks())

            self.assertEqual(len(ref), len(matching))

            for i in range(len(matching)):
                #print(matching[i])
                self.assertEqual(ref[i], matching[i])
