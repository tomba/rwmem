#!/usr/bin/env python3

import os
import shutil
import stat
import tempfile
import unittest
import rwmem as rw

REGS_PATH = os.path.dirname(os.path.abspath(__file__)) + '/test.regdb'
BIN_PATH = os.path.dirname(os.path.abspath(__file__)) + '/test.bin'


class ContextManagerTests(unittest.TestCase):
    def test(self):
        with rw.RegisterFile(REGS_PATH) as rf:
            with rw.MappedRegisterBlock(BIN_PATH, rf['SENSOR_A'], mode=rw.MapMode.Read) as map:
                self.assertEqual(map['STATUS_REG'].value, 0x39)


class MmapRegsTests(unittest.TestCase):
    def setUp(self):
        self.rf = rw.RegisterFile(REGS_PATH)
        self.map = rw.MappedRegisterBlock(BIN_PATH, self.rf['SENSOR_A'], mode=rw.MapMode.Read)

    def tests(self):
        m = self.map

        # Test register existence
        self.assertTrue('STATUS_REG' in m)
        self.assertTrue('MODE' in m['STATUS_REG'])

        # Test STATUS_REG (0x39 = 0011 1001 binary)
        self.assertEqual(m['STATUS_REG'].value, 0x39)

        # Test field access: MODE[7:3]=0x7, ERROR[2:1]=0x0, READY[0:0]=0x1
        self.assertEqual(m['STATUS_REG']['MODE'], 0x7)  # bits 7:3 = 0111
        self.assertEqual(m['STATUS_REG']['ERROR'], 0x0)  # bits 2:1 = 00
        self.assertEqual(m['STATUS_REG']['READY'], 0x1)  # bit 0 = 1

        # Test bit slicing on STATUS_REG
        self.assertEqual(m['STATUS_REG'][7:3], 0x7)  # MODE field
        self.assertEqual(m['STATUS_REG'][2:1], 0x0)  # ERROR field
        self.assertEqual(m['STATUS_REG'][0:0], 0x1)  # READY field

        # Test DATA_REG (16-bit little endian)
        self.assertEqual(m['DATA_REG'].value, 0x7D8C)
        self.assertEqual(m['DATA_REG']['VALUE'], 0x7D8C)

        # Test CONFIG_REG (24-bit little endian: 0x344772)
        self.assertEqual(m['CONFIG_REG'].value, 0x344772)
        self.assertEqual(m['CONFIG_REG']['THRESHOLD'], 0x34)  # bits 23:16
        self.assertEqual(m['CONFIG_REG']['GAIN'], 0x47)  # bits 15:8
        self.assertEqual(m['CONFIG_REG']['OFFSET'], 0x72)  # bits 7:0


class WriteMmapRegsTests(unittest.TestCase):
    def setUp(self):
        self.rf = rw.RegisterFile(REGS_PATH)

        self.tmpfile = tempfile.NamedTemporaryFile(mode='w+b', suffix='.bin', delete=True)
        self.tmpfile_path = self.tmpfile.name

        shutil.copy2(BIN_PATH, self.tmpfile_path)
        os.chmod(self.tmpfile_path, stat.S_IREAD | stat.S_IWRITE)

        self.map = rw.MappedRegisterBlock(
            self.tmpfile_path, self.rf['SENSOR_A'], mode=rw.MapMode.ReadWrite
        )

    def tests(self):
        m = self.map

        # Verify initial STATUS_REG value
        self.assertEqual(m['STATUS_REG'].value, 0x39)

        # Test writing full register value
        m['STATUS_REG'].set_value(0xAB)
        self.assertEqual(m['STATUS_REG'].value, 0xAB)
        self.assertEqual(m._map.read(0, 1), 0xAB)

        # Test writing individual fields
        m['STATUS_REG'].set_value(0x00)  # Reset to known state
        m['STATUS_REG']['MODE'] = 0x1F  # Set MODE to max value (5 bits)
        m['STATUS_REG']['ERROR'] = 0x3  # Set ERROR to max value (2 bits)
        m['STATUS_REG']['READY'] = 0x1  # Set READY bit

        # Verify field writes: MODE[7:3]=0x1F, ERROR[2:1]=0x3, READY[0:0]=0x1
        # Expected: 1111 1111 = 0xFF
        self.assertEqual(m['STATUS_REG'].value, 0xFF)
        self.assertEqual(m['STATUS_REG']['MODE'], 0x1F)
        self.assertEqual(m['STATUS_REG']['ERROR'], 0x3)
        self.assertEqual(m['STATUS_REG']['READY'], 0x1)

        # Test bit slice writes
        m['STATUS_REG'][7:3] = 0x10  # Set MODE field via bit slice
        self.assertEqual(m['STATUS_REG']['MODE'], 0x10)
        self.assertEqual(m['STATUS_REG'].value, 0x87)  # 1000 0111

        # Test DATA_REG (16-bit register)
        m['DATA_REG'].set_value(0x1234)
        self.assertEqual(m['DATA_REG'].value, 0x1234)
        self.assertEqual(m['DATA_REG']['VALUE'], 0x1234)
        # Verify little-endian write to offset 0x2
        self.assertEqual(m._map.read(2, 2, rw.Endianness.Little), 0x1234)

        # Test CONFIG_REG field writes using dict
        m['CONFIG_REG'].set_value({'THRESHOLD': 0xAB, 'GAIN': 0xCD, 'OFFSET': 0xEF})
        self.assertEqual(m['CONFIG_REG']['THRESHOLD'], 0xAB)
        self.assertEqual(m['CONFIG_REG']['GAIN'], 0xCD)
        self.assertEqual(m['CONFIG_REG']['OFFSET'], 0xEF)
        self.assertEqual(m['CONFIG_REG'].value, 0xABCDEF)

        # Verify changes are written to file
        import difflib

        with open(BIN_PATH, 'rb') as f1, open(self.tmpfile_path, 'rb') as f2:
            x = f1.read()
            y = f2.read()

            s = difflib.SequenceMatcher(None, x, y)
            matching = list(s.get_matching_blocks())

            # Files should differ (we made changes)
            self.assertNotEqual(x, y)
            # But should have some unchanged regions
            self.assertGreater(len(matching), 1)
