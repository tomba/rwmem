#!/usr/bin/env python3

import os
import random
import shutil
import stat
import tempfile
import unittest

import rwmem as rw

BIN_PATH = os.path.dirname(os.path.abspath(__file__)) + '/test.bin'


def generate_test_data():
    """Generate the same test data as in generate_test_data.py.

    Creates a 768-byte binary data with random data using fixed seed 42.
    This ensures tests stay in sync with the actual test.bin file.
    """
    random.seed(42)
    data = bytearray(768)
    for i in range(len(data)):
        data[i] = random.randint(0, 255)
    return data


def extract_value(data, offset, size, endianness=rw.Endianness.Big):
    """Extract a value from test data at given offset with specified size and endianness."""
    chunk = data[offset:offset + size]
    if endianness == rw.Endianness.Little:
        chunk = chunk[::-1]  # Reverse for little endian

    value = 0
    for byte in chunk:
        value = (value << 8) | byte
    return value


# Generate test data once at module level
TEST_DATA = generate_test_data()


class ContextManagerTests(unittest.TestCase):
    def test(self):
        with rw.MMapTarget(BIN_PATH, 0, 32, rw.Endianness.Big, 4, rw.MapMode.Read) as map:
            expected = extract_value(TEST_DATA, 8, 4, rw.Endianness.Big)
            self.assertEqual(map.read(8, 4), expected)


class MmapTests(unittest.TestCase):
    def setUp(self):
        self.map = rw.MMapTarget(BIN_PATH, 0, 32, rw.Endianness.Big, 4, rw.MapMode.Read)

    def test_reads(self):
        map = self.map

        # Test 8-bit reads (1 byte)
        self.assertEqual(map.read(0, 1), extract_value(TEST_DATA, 0, 1))
        self.assertEqual(map.read(1, 1), extract_value(TEST_DATA, 1, 1))
        self.assertEqual(map.read(2, 1), extract_value(TEST_DATA, 2, 1))
        self.assertEqual(map.read(3, 1), extract_value(TEST_DATA, 3, 1))
        self.assertEqual(map.read(4, 1), extract_value(TEST_DATA, 4, 1))
        self.assertEqual(map.read(8, 1), extract_value(TEST_DATA, 8, 1))

        # Test 16-bit reads (2 bytes)
        self.assertEqual(map.read(0, 2), extract_value(TEST_DATA, 0, 2, rw.Endianness.Big))
        self.assertEqual(map.read(0, 2, rw.Endianness.Big), extract_value(TEST_DATA, 0, 2, rw.Endianness.Big))
        self.assertEqual(map.read(0, 2, rw.Endianness.Little), extract_value(TEST_DATA, 0, 2, rw.Endianness.Little))
        self.assertEqual(map.read(2, 2), extract_value(TEST_DATA, 2, 2, rw.Endianness.Big))
        self.assertEqual(map.read(2, 2, rw.Endianness.Big), extract_value(TEST_DATA, 2, 2, rw.Endianness.Big))
        self.assertEqual(map.read(4, 2), extract_value(TEST_DATA, 4, 2, rw.Endianness.Big))
        self.assertEqual(map.read(4, 2, rw.Endianness.Big), extract_value(TEST_DATA, 4, 2, rw.Endianness.Big))

        # Test 24-bit reads (3 bytes)
        self.assertEqual(map.read(0, 3), extract_value(TEST_DATA, 0, 3, rw.Endianness.Big))
        self.assertEqual(map.read(0, 3, rw.Endianness.Big), extract_value(TEST_DATA, 0, 3, rw.Endianness.Big))
        self.assertEqual(map.read(0, 3, rw.Endianness.Little), extract_value(TEST_DATA, 0, 3, rw.Endianness.Little))
        self.assertEqual(map.read(1, 3), extract_value(TEST_DATA, 1, 3, rw.Endianness.Big))
        self.assertEqual(map.read(1, 3, rw.Endianness.Big), extract_value(TEST_DATA, 1, 3, rw.Endianness.Big))
        self.assertEqual(map.read(4, 3), extract_value(TEST_DATA, 4, 3, rw.Endianness.Big))
        self.assertEqual(map.read(4, 3, rw.Endianness.Big), extract_value(TEST_DATA, 4, 3, rw.Endianness.Big))

        # Test 32-bit reads (4 bytes)
        self.assertEqual(map.read(0, 4), extract_value(TEST_DATA, 0, 4, rw.Endianness.Big))
        self.assertEqual(map.read(0, 4, rw.Endianness.Big), extract_value(TEST_DATA, 0, 4, rw.Endianness.Big))
        self.assertEqual(map.read(0, 4, rw.Endianness.Little), extract_value(TEST_DATA, 0, 4, rw.Endianness.Little))
        self.assertEqual(map.read(4, 4), extract_value(TEST_DATA, 4, 4, rw.Endianness.Big))
        self.assertEqual(map.read(4, 4, rw.Endianness.Big), extract_value(TEST_DATA, 4, 4, rw.Endianness.Big))
        self.assertEqual(map.read(8, 4), extract_value(TEST_DATA, 8, 4, rw.Endianness.Big))
        self.assertEqual(map.read(8, 4, rw.Endianness.Big), extract_value(TEST_DATA, 8, 4, rw.Endianness.Big))
        self.assertEqual(map.read(12, 4), extract_value(TEST_DATA, 12, 4, rw.Endianness.Big))
        self.assertEqual(map.read(16, 4), extract_value(TEST_DATA, 16, 4, rw.Endianness.Big))
        self.assertEqual(map.read(20, 4), extract_value(TEST_DATA, 20, 4, rw.Endianness.Big))
        self.assertEqual(map.read(24, 4), extract_value(TEST_DATA, 24, 4, rw.Endianness.Big))
        self.assertEqual(map.read(28, 4), extract_value(TEST_DATA, 28, 4, rw.Endianness.Big))

        # Test 40-bit reads (5 bytes)
        self.assertEqual(map.read(0, 5), extract_value(TEST_DATA, 0, 5, rw.Endianness.Big))
        self.assertEqual(map.read(0, 5, rw.Endianness.Big), extract_value(TEST_DATA, 0, 5, rw.Endianness.Big))
        self.assertEqual(map.read(0, 5, rw.Endianness.Little), extract_value(TEST_DATA, 0, 5, rw.Endianness.Little))
        self.assertEqual(map.read(1, 5), extract_value(TEST_DATA, 1, 5, rw.Endianness.Big))
        self.assertEqual(map.read(1, 5, rw.Endianness.Big), extract_value(TEST_DATA, 1, 5, rw.Endianness.Big))
        self.assertEqual(map.read(3, 5), extract_value(TEST_DATA, 3, 5, rw.Endianness.Big))
        self.assertEqual(map.read(3, 5, rw.Endianness.Big), extract_value(TEST_DATA, 3, 5, rw.Endianness.Big))

        # Test 48-bit reads (6 bytes)
        self.assertEqual(map.read(0, 6), extract_value(TEST_DATA, 0, 6, rw.Endianness.Big))
        self.assertEqual(map.read(0, 6, rw.Endianness.Big), extract_value(TEST_DATA, 0, 6, rw.Endianness.Big))
        self.assertEqual(map.read(0, 6, rw.Endianness.Little), extract_value(TEST_DATA, 0, 6, rw.Endianness.Little))
        self.assertEqual(map.read(1, 6), extract_value(TEST_DATA, 1, 6, rw.Endianness.Big))
        self.assertEqual(map.read(1, 6, rw.Endianness.Big), extract_value(TEST_DATA, 1, 6, rw.Endianness.Big))
        self.assertEqual(map.read(2, 6), extract_value(TEST_DATA, 2, 6, rw.Endianness.Big))
        self.assertEqual(map.read(2, 6, rw.Endianness.Big), extract_value(TEST_DATA, 2, 6, rw.Endianness.Big))

        # Test 56-bit reads (7 bytes)
        self.assertEqual(map.read(0, 7), extract_value(TEST_DATA, 0, 7, rw.Endianness.Big))
        self.assertEqual(map.read(0, 7, rw.Endianness.Big), extract_value(TEST_DATA, 0, 7, rw.Endianness.Big))
        self.assertEqual(map.read(0, 7, rw.Endianness.Little), extract_value(TEST_DATA, 0, 7, rw.Endianness.Little))
        self.assertEqual(map.read(1, 7), extract_value(TEST_DATA, 1, 7, rw.Endianness.Big))
        self.assertEqual(map.read(1, 7, rw.Endianness.Big), extract_value(TEST_DATA, 1, 7, rw.Endianness.Big))
        self.assertEqual(map.read(8, 7), extract_value(TEST_DATA, 8, 7, rw.Endianness.Big))
        self.assertEqual(map.read(8, 7, rw.Endianness.Big), extract_value(TEST_DATA, 8, 7, rw.Endianness.Big))

        # Test 64-bit reads (8 bytes)
        self.assertEqual(map.read(0, 8), extract_value(TEST_DATA, 0, 8, rw.Endianness.Big))
        self.assertEqual(map.read(0, 8, rw.Endianness.Big), extract_value(TEST_DATA, 0, 8, rw.Endianness.Big))
        self.assertEqual(map.read(0, 8, rw.Endianness.Little), extract_value(TEST_DATA, 0, 8, rw.Endianness.Little))
        self.assertEqual(map.read(24, 8), extract_value(TEST_DATA, 24, 8, rw.Endianness.Big))
        self.assertEqual(map.read(24, 8, rw.Endianness.Big), extract_value(TEST_DATA, 24, 8, rw.Endianness.Big))


class MMapTargetFailureTests(unittest.TestCase):
    def test_constructor_failures(self):
        # Non-existent file
        with self.assertRaises(FileNotFoundError):
            rw.MMapTarget('/nonexistent/file.bin', 0, 32, rw.Endianness.Big, 4)

        # Directory instead of file
        with self.assertRaises(OSError):
            rw.MMapTarget('/tmp', 0, 32, rw.Endianness.Big, 4)

        # Negative offset
        with self.assertRaises(OverflowError):
            rw.MMapTarget(BIN_PATH, -1, 32, rw.Endianness.Big, 4)

        # Zero length should be invalid
        with self.assertRaises(ValueError):
            rw.MMapTarget(BIN_PATH, 0, 0, rw.Endianness.Big, 4)

        # Negative length should be invalid
        with self.assertRaises(ValueError):
            rw.MMapTarget(BIN_PATH, 0, -1, rw.Endianness.Big, 4)

        # Zero data_size should be invalid
        with self.assertRaises(ValueError):
            rw.MMapTarget(BIN_PATH, 0, 32, rw.Endianness.Big, 0)

        # Negative data_size should be invalid
        with self.assertRaises(ValueError):
            rw.MMapTarget(BIN_PATH, 0, 32, rw.Endianness.Big, -1)

    def test_read_parameter_validation(self):
        map = rw.MMapTarget(BIN_PATH, 0, 32, rw.Endianness.Big, 4, rw.MapMode.Read)

        # Non-zero addr_size
        with self.assertRaises(RuntimeError):
            map.read(0, 4, rw.Endianness.Default, 4)

        # Non-Default addr_endianness
        with self.assertRaises(RuntimeError):
            map.read(0, 4, rw.Endianness.Default, 0, rw.Endianness.Big)

        # Zero data_size should be invalid when explicitly passed
        with self.assertRaises(ValueError):
            map.read(0, 0)

        # Negative data_size should be invalid
        with self.assertRaises(ValueError):
            map.read(0, -1)

        # Reading from Write-only map should fail (tested in test_mode_conflicts)

    def test_write_parameter_validation(self):
        tmpfile = tempfile.NamedTemporaryFile(mode='w+b', suffix='.bin', delete=True)
        shutil.copy2(BIN_PATH, tmpfile.name)
        os.chmod(tmpfile.name, stat.S_IREAD | stat.S_IWRITE)

        map = rw.MMapTarget(tmpfile.name, 0, 32, rw.Endianness.Big, 4, rw.MapMode.ReadWrite)

        # Non-zero addr_size
        with self.assertRaises(RuntimeError):
            map.write(0, 0x12345678, 4, rw.Endianness.Default, 4)

        # Non-Default addr_endianness
        with self.assertRaises(RuntimeError):
            map.write(0, 0x12345678, 4, rw.Endianness.Default, 0, rw.Endianness.Big)

        # Zero data_size should be invalid when explicitly passed
        with self.assertRaises(ValueError):
            map.write(0, 0x12345678, 0)

        # Negative data_size should be invalid
        with self.assertRaises(ValueError):
            map.write(0, 0x12345678, -1)

        # Writing to Read-only map
        read_map = rw.MMapTarget(BIN_PATH, 0, 32, rw.Endianness.Big, 4, rw.MapMode.Read)
        with self.assertRaises(RuntimeError):
            read_map.write(0, 0x12345678, 4)

        # Value too large for data_size (test 1-byte overflow)
        with self.assertRaises(OverflowError):
            map.write(0, 0x100, 1)

        # Value too large for data_size (test 2-byte overflow)
        with self.assertRaises(OverflowError):
            map.write(0, 0x10000, 2)

    def test_mode_conflicts(self):
        # Write-only mode doesn't work with regular files due to permission issues
        # Only test writing to Read-only map

        # Writing to Read-only map should fail
        read_map = rw.MMapTarget(BIN_PATH, 0, 32, rw.Endianness.Big, 4, rw.MapMode.Read)
        with self.assertRaises(RuntimeError):
            read_map.write(0, 0x12345678, 4)

    def test_address_boundary_violations(self):
        map = rw.MMapTarget(BIN_PATH, 0, 32, rw.Endianness.Big, 4, rw.MapMode.Read)

        # Read beyond end of mapped region
        with self.assertRaises(RuntimeError):
            map.read(32, 1)

        with self.assertRaises(RuntimeError):
            map.read(30, 4)

        # Read from negative address
        with self.assertRaises(RuntimeError):
            map.read(-1, 1)

        # Write tests with writable map
        tmpfile = tempfile.NamedTemporaryFile(mode='w+b', suffix='.bin', delete=True)
        shutil.copy2(BIN_PATH, tmpfile.name)
        os.chmod(tmpfile.name, stat.S_IREAD | stat.S_IWRITE)

        write_map = rw.MMapTarget(tmpfile.name, 0, 32, rw.Endianness.Big, 4, rw.MapMode.ReadWrite)

        # Write beyond end of mapped region
        with self.assertRaises(RuntimeError):
            write_map.write(32, 0x12345678, 1)

        with self.assertRaises(RuntimeError):
            write_map.write(30, 0x12345678, 4)

        # Write to negative address
        with self.assertRaises(RuntimeError):
            write_map.write(-1, 0x12345678, 1)

    def test_lifecycle_failures(self):
        map = rw.MMapTarget(BIN_PATH, 0, 32, rw.Endianness.Big, 4, rw.MapMode.Read)

        # Close the map explicitly
        map.close()

        # Operations after close should fail
        with self.assertRaises(ValueError):
            map.read(0, 4)

        # Test context manager
        with rw.MMapTarget(BIN_PATH, 0, 32, rw.Endianness.Big, 4, rw.MapMode.Read) as ctx_map:
            # Should work inside context
            ctx_map.read(0, 4)

        # Should fail after context exit
        with self.assertRaises(ValueError):
            ctx_map.read(0, 4)


class WriteMmapTests(unittest.TestCase):
    def setUp(self):
        self.tmpfile = tempfile.NamedTemporaryFile(mode='w+b', suffix='.bin', delete=True)
        self.tmpfile_path = self.tmpfile.name

        shutil.copy2(BIN_PATH, self.tmpfile_path)
        os.chmod(self.tmpfile_path, stat.S_IREAD | stat.S_IWRITE)

        self.map = rw.MMapTarget(
            self.tmpfile_path, 0, 32, rw.Endianness.Big, 4, rw.MapMode.ReadWrite
        )

    def test_writes(self):
        map = self.map

        # Test 8-bit writes (1 byte)
        map.write(16, 0xAB, 1)
        self.assertEqual(map.read(16, 1), 0xAB)
        map.write(17, 0xCD, 1, rw.Endianness.Big)
        self.assertEqual(map.read(17, 1, rw.Endianness.Big), 0xCD)
        map.write(18, 0xEF, 1, rw.Endianness.Little)
        self.assertEqual(map.read(18, 1, rw.Endianness.Little), 0xEF)

        # Test 16-bit writes (2 bytes)
        map.write(20, 0x1234, 2)
        self.assertEqual(map.read(20, 2), 0x1234)
        map.write(22, 0x5678, 2, rw.Endianness.Big)
        self.assertEqual(map.read(22, 2, rw.Endianness.Big), 0x5678)
        map.write(24, 0x9ABC, 2, rw.Endianness.Little)
        self.assertEqual(map.read(24, 2, rw.Endianness.Little), 0x9ABC)

        # Test 24-bit writes (3 bytes)
        map.write(16, 0xABCDEF, 3)
        self.assertEqual(map.read(16, 3), 0xABCDEF)
        map.write(19, 0x123456, 3, rw.Endianness.Big)
        self.assertEqual(map.read(19, 3, rw.Endianness.Big), 0x123456)
        map.write(22, 0xFEDCBA, 3, rw.Endianness.Little)
        self.assertEqual(map.read(22, 3, rw.Endianness.Little), 0xFEDCBA)

        # Test 32-bit writes (4 bytes)
        map.write(8, 0x12345678, 4)
        self.assertEqual(map.read(8, 4), 0x12345678)
        map.write(12, 0x9ABCDEF0, 4, rw.Endianness.Big)
        self.assertEqual(map.read(12, 4, rw.Endianness.Big), 0x9ABCDEF0)
        map.write(16, 0xFEDCBA98, 4, rw.Endianness.Little)
        self.assertEqual(map.read(16, 4, rw.Endianness.Little), 0xFEDCBA98)

        # Test 40-bit writes (5 bytes) - write to separate region
        map.write(25, 0x123456789A, 5)
        self.assertEqual(map.read(25, 5), 0x123456789A)
        map.write(25, 0xABCDEF0123, 5, rw.Endianness.Big)
        self.assertEqual(map.read(25, 5, rw.Endianness.Big), 0xABCDEF0123)
        map.write(25, 0x9876543210, 5, rw.Endianness.Little)
        self.assertEqual(map.read(25, 5, rw.Endianness.Little), 0x9876543210)

        # Test 48-bit writes (6 bytes) - write to separate region
        map.write(26, 0x123456789ABC, 6)
        self.assertEqual(map.read(26, 6), 0x123456789ABC)
        map.write(26, 0xABCDEF012345, 6, rw.Endianness.Big)
        self.assertEqual(map.read(26, 6, rw.Endianness.Big), 0xABCDEF012345)
        map.write(26, 0x987654321098, 6, rw.Endianness.Little)
        self.assertEqual(map.read(26, 6, rw.Endianness.Little), 0x987654321098)

        # Test 56-bit writes (7 bytes) - write to separate region
        map.write(25, 0x123456789ABCDE, 7)
        self.assertEqual(map.read(25, 7), 0x123456789ABCDE)
        map.write(25, 0xABCDEF01234567, 7, rw.Endianness.Big)
        self.assertEqual(map.read(25, 7, rw.Endianness.Big), 0xABCDEF01234567)
        map.write(25, 0x98765432109876, 7, rw.Endianness.Little)
        self.assertEqual(map.read(25, 7, rw.Endianness.Little), 0x98765432109876)

        # Test 64-bit writes (8 bytes)
        map.write(0, 0x8899AABBCCDDEEFF, 8)
        self.assertEqual(map.read(0, 8), 0x8899AABBCCDDEEFF)
        map.write(0, 0x1122334455667788, 8, rw.Endianness.Big)
        self.assertEqual(map.read(0, 8, rw.Endianness.Big), 0x1122334455667788)
        map.write(0, 0xFFEEDDCCBBAA9988, 8, rw.Endianness.Little)
        self.assertEqual(map.read(0, 8, rw.Endianness.Little), 0xFFEEDDCCBBAA9988)
