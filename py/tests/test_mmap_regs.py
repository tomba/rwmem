#!/usr/bin/env python3

import io
import os
import shutil
import stat
import tempfile
import unittest
import rwmem as rw
import rwmem.gen as gen

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


class TargetMappedRegsTests(unittest.TestCase):
    """MappedRegisterBlock given an already opened Target instead of a file name."""

    def setUp(self):
        self.rf = rw.RegisterFile(REGS_PATH)
        # A big-endian block, so that a target opened with another
        # endianness is not the same thing as the block's.
        self.block = self.rf['MEMORY_CTRL']

        self.tmpdir = tempfile.mkdtemp()
        self.bin_path = os.path.join(self.tmpdir, 'test.bin')
        shutil.copy(BIN_PATH, self.bin_path)
        os.chmod(self.bin_path, stat.S_IREAD | stat.S_IWRITE)

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def _target(self, mode=rw.MapMode.ReadWrite):
        # Opened with Little, unlike the block, which is Big.
        return rw.MMapTarget(
            self.bin_path,
            self.block.offset,
            self.block.size,
            rw.Endianness.Little,
            self.block.data_size,
            mode,
        )

    def _read_all(self, map):
        return {name: int(map[name]) for name in map}

    def test_reads_do_not_depend_on_the_targets_endianness(self):
        with rw.MappedRegisterBlock(self.bin_path, self.block, mode=rw.MapMode.Read) as m:
            expected = self._read_all(m)

        with rw.MappedRegisterBlock(self._target(), self.block) as m:
            self.assertEqual(self._read_all(m), expected)

    def test_writes_do_not_depend_on_the_targets_endianness(self):
        with rw.MappedRegisterBlock(self._target(), self.block) as m:
            m['STATUS_REG'].set_value(0x12345678)
            m['CONFIG_REG'].set_value({'THRESHOLD': 0xAB, 'GAIN': 0xCD, 'OFFSET': 0xEF})
            m['DATA_LO_REG']['DATA'] = 0xDEADBEEF

        # The file path is how the block is meant to be accessed.
        with rw.MappedRegisterBlock(self.bin_path, self.block, mode=rw.MapMode.Read) as m:
            self.assertEqual(int(m['STATUS_REG']), 0x12345678)
            self.assertEqual(int(m['CONFIG_REG']), 0xABCDEF)
            self.assertEqual(int(m['DATA_LO_REG']), 0xDEADBEEF)

    def test_register_endianness_override(self):
        # A register that overrides its block's endianness must read the
        # same through both paths, and the other way round from the block.
        regs = [
            gen.UnpackedRegister('LE_REG', 0x0, [gen.UnpackedField('VALUE', 31, 0)], data_size=4),
            gen.UnpackedRegister(
                'BE_REG',
                0x4,
                [gen.UnpackedField('VALUE', 31, 0)],
                data_size=4,
                data_endianness=rw.Endianness.Big,
            ),
        ]
        block = gen.UnpackedRegBlock(
            'B', 0x0, 0x8, regs, rw.Endianness.Little, 1, rw.Endianness.Little, 4
        )
        buf = io.BytesIO()
        gen.UnpackedRegFile('OVERRIDE', [block]).pack_to(buf)

        path = os.path.join(self.tmpdir, 'override.bin')
        with open(path, 'wb') as f:
            f.write(bytes.fromhex('11223344') * 2)

        with rw.RegisterFile(buf.getvalue()) as rf:
            b = rf['B']

            with rw.MappedRegisterBlock(path, b, mode=rw.MapMode.Read) as m:
                self.assertEqual(int(m['LE_REG']), 0x44332211)
                self.assertEqual(int(m['BE_REG']), 0x11223344)

            target = rw.MMapTarget(path, 0, 0x8, rw.Endianness.Big, 4, rw.MapMode.Read)
            with rw.MappedRegisterBlock(target, b) as m:
                self.assertEqual(int(m['LE_REG']), 0x44332211)
                self.assertEqual(int(m['BE_REG']), 0x11223344)

            del b, m

    def test_mode_with_a_target_raises(self):
        with self._target(mode=rw.MapMode.Read) as target:
            with self.assertRaises(ValueError):
                rw.MappedRegisterBlock(target, self.block, mode=rw.MapMode.Read)
            with self.assertRaises(ValueError):
                rw.MappedRegisterBlock(target, self.block, mode=rw.MapMode.ReadWrite)

    def test_read_only_target_does_not_write(self):
        with rw.MappedRegisterBlock(self._target(mode=rw.MapMode.Read), self.block) as m:
            with self.assertRaises(RuntimeError):
                m['STATUS_REG'].set_value(0)

    def test_close_is_idempotent(self):
        m = rw.MappedRegisterBlock(self._target(), self.block)
        m.close()
        m.close()


class MappedRegisterFileCloseTests(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.bin_path = os.path.join(self.tmpdir, 'test.bin')
        shutil.copy(BIN_PATH, self.bin_path)
        os.chmod(self.bin_path, stat.S_IREAD | stat.S_IWRITE)

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def _factory(self, rb):
        return rw.MMapTarget(self.bin_path, rb.offset, rb.size, rb.data_endianness, rb.data_size)

    def test_closing_the_register_file_after_the_mapped_file(self):
        # The mapped blocks hold views into the register file's mmap.
        # Without closing them the RegisterFile cannot close its mmap, and
        # raises BufferError. No helper method hides the objects here.
        with rw.RegisterFile(REGS_PATH) as rf:
            with rw.MappedRegisterFile(rf, target_factory=self._factory) as mrf:
                self.assertEqual(int(mrf['SENSOR_A']['STATUS_REG']), 0x39)
                self.assertEqual(len(mrf), len(rf))

    def test_close_is_idempotent(self):
        with rw.RegisterFile(REGS_PATH) as rf:
            mrf = rw.MappedRegisterFile(rf, target_factory=self._factory)
            self.assertEqual(int(mrf['SENSOR_A']['STATUS_REG']), 0x39)

            mrf.close()
            mrf.close()

            # The blocks are gone with it.
            self.assertEqual(len(mrf), 0)
            with self.assertRaises(KeyError):
                mrf['SENSOR_A']
