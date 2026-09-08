#!/usr/bin/env python3

import io
import os
import shutil
import stat
import tempfile
import unittest

import rwmem as rw
import rwmem.gen as gen
from rwmem import MappedRegisterBlock, MappedRegisterFile, RegisterValue

REGS_PATH = os.path.dirname(os.path.abspath(__file__)) + '/test.regdb'
BIN_PATH = os.path.dirname(os.path.abspath(__file__)) + '/test.bin'


def _le(data, off, size):
    return int.from_bytes(data[off : off + size], 'little')


class KeyParsingTests(unittest.TestCase):
    """The path syntax, exercised on a read-only block."""

    def setUp(self):
        self.rf = rw.RegisterFile(REGS_PATH)
        self.block = MappedRegisterBlock(BIN_PATH, self.rf['SENSOR_A'], mode=rw.MapMode.Read)
        with open(BIN_PATH, 'rb') as f:
            self.data = f.read()

    def tearDown(self):
        self.block.close()
        self.rf.close()

    def test_register_and_field_paths(self):
        m = self.block
        self.assertEqual(m['STATUS_REG'], 0x39)
        self.assertEqual(m['STATUS_REG:MODE'], 0x7)  # bits 7:3
        self.assertEqual(m['STATUS_REG:ERROR'], 0x0)  # bits 2:1
        self.assertEqual(m['STATUS_REG:READY'], 0x1)  # bit 0
        self.assertEqual(m['STATUS_REG:7:3'], 0x7)  # by bit range
        self.assertEqual(m['STATUS_REG:3'], 0x1)  # single bit (bit 3 of 0x39)
        self.assertEqual(m['DATA_REG'], 0x7D8C)  # 16-bit little endian
        self.assertEqual(m['CONFIG_REG'], 0x344772)  # 24-bit little endian
        self.assertEqual(m['CONFIG_REG:THRESHOLD'], 0x34)

    def test_bad_paths_raise(self):
        with self.assertRaises(KeyError):
            self.block['NOPE']
        with self.assertRaises(KeyError):
            self.block['STATUS_REG:NOPE']  # not a field, not a number
        with self.assertRaises(ValueError):
            self.block['STATUS_REG:40']  # bit out of range, no clamping
        with self.assertRaises(ValueError):
            self.block['STATUS_REG:40:32']

    def test_iteration_is_metadata_only(self):
        self.assertEqual(list(self.block), list(self.rf['SENSOR_A']))
        self.assertIn('STATUS_REG', self.block)
        self.assertEqual(len(self.block), self.rf['SENSOR_A'].num_registers)


class RegisterValueTests(unittest.TestCase):
    def setUp(self):
        self.rf = rw.RegisterFile(REGS_PATH)
        self.block = MappedRegisterBlock(BIN_PATH, self.rf['SENSOR_A'], mode=rw.MapMode.Read)

    def tearDown(self):
        self.block.close()
        self.rf.close()

    def test_is_int_and_decodes(self):
        v = self.block['STATUS_REG']
        self.assertIsInstance(v, RegisterValue)
        self.assertIsInstance(v, int)
        self.assertEqual(v, 0x39)
        self.assertEqual(v & 0xFF, 0x39)
        self.assertEqual(v['MODE'], 0x7)
        self.assertEqual(v[7:3], 0x7)
        self.assertEqual(v[0], 0x1)
        self.assertEqual(v.fields, {'MODE': 0x7, 'ERROR': 0x0, 'READY': 0x1})

    def test_repr(self):
        self.assertEqual(repr(self.block['STATUS_REG']), '0x39  MODE=0x7 ERROR=0x0 READY=0x1')

    def test_is_read_only(self):
        v = self.block['STATUS_REG']
        with self.assertRaises(TypeError):
            v['MODE'] = 1

    def test_outlives_register_file(self):
        # The value copies its layout, so it survives closing everything.
        v = self.block['STATUS_REG']
        self.block.close()
        self.rf.close()
        self.assertEqual(v['MODE'], 0x7)
        self.assertEqual(v.fields['READY'], 0x1)


class WriteTests(unittest.TestCase):
    def setUp(self):
        self.rf = rw.RegisterFile(REGS_PATH)
        self.tmpdir = tempfile.mkdtemp()
        self.bin_path = os.path.join(self.tmpdir, 'test.bin')
        shutil.copy(BIN_PATH, self.bin_path)
        os.chmod(self.bin_path, stat.S_IREAD | stat.S_IWRITE)
        self.block = MappedRegisterBlock(self.bin_path, self.rf['SENSOR_A'])

    def tearDown(self):
        self.block.close()
        self.rf.close()
        shutil.rmtree(self.tmpdir)

    def test_register_write(self):
        self.block['STATUS_REG'] = 0xAB
        self.assertEqual(self.block['STATUS_REG'], 0xAB)

    def test_field_writes(self):
        m = self.block
        m['STATUS_REG'] = 0x00
        m['STATUS_REG:MODE'] = 0x1F
        m['STATUS_REG:ERROR'] = 0x3
        m['STATUS_REG:READY'] = 0x1
        self.assertEqual(m['STATUS_REG'], 0xFF)

    def test_bit_range_write(self):
        m = self.block
        m['STATUS_REG'] = 0x07
        m['STATUS_REG:7:3'] = 0x10
        self.assertEqual(m['STATUS_REG:MODE'], 0x10)
        self.assertEqual(m['STATUS_REG'], 0x87)

    def test_dict_write(self):
        self.block['CONFIG_REG'] = {'THRESHOLD': 0xAB, 'GAIN': 0xCD, 'OFFSET': 0xEF}
        self.assertEqual(self.block['CONFIG_REG'], 0xABCDEF)
        self.assertEqual(self.block['CONFIG_REG'].fields['GAIN'], 0xCD)

    def test_reaches_the_file(self):
        self.block['DATA_REG'] = 0x1234  # 16-bit little endian at offset 2
        self.block.close()
        with open(self.bin_path, 'rb') as f:
            data = f.read()
        self.assertEqual(_le(data, 2, 2), 0x1234)


class HandleTests(unittest.TestCase):
    def setUp(self):
        self.rf = rw.RegisterFile(REGS_PATH)
        self.tmpdir = tempfile.mkdtemp()
        self.bin_path = os.path.join(self.tmpdir, 'test.bin')
        shutil.copy(BIN_PATH, self.bin_path)
        os.chmod(self.bin_path, stat.S_IREAD | stat.S_IWRITE)
        self.mrf = MappedRegisterFile(
            self.rf,
            target_factory=lambda rb: rw.MMapTarget(
                self.bin_path, rb.offset, rb.size, rb.data_endianness, rb.data_size
            ),
        )

    def tearDown(self):
        self.mrf.close()
        self.rf.close()
        shutil.rmtree(self.tmpdir)

    def test_register_handle(self):
        reg = self.mrf.reg('SENSOR_A.DATA_REG')
        self.assertEqual(reg.name, 'DATA_REG')
        self.assertEqual(reg.offset, 0x2)
        self.assertEqual(reg.address, 0x2)
        self.assertEqual(reg.bits, 16)
        reg.write(0x1234)
        self.assertEqual(reg.read(), 0x1234)
        self.assertIsInstance(reg.read(), RegisterValue)
        self.assertEqual(reg['VALUE'], 0x1234)
        reg['VALUE'] = 0x4321
        self.assertEqual(reg.read(), 0x4321)

    def test_handle_is_cached(self):
        self.assertIs(self.mrf.reg('SENSOR_A.DATA_REG'), self.mrf.reg('SENSOR_A.DATA_REG'))
        self.assertIs(self.mrf['SENSOR_A'].reg('DATA_REG'), self.mrf.reg('SENSOR_A.DATA_REG'))

    def test_register_handle_address_with_base(self):
        block = MappedRegisterBlock(self.bin_path, self.rf['SENSOR_A'], offset=0x40)
        try:
            self.assertEqual(block.address, 0x40)
            self.assertEqual(block.reg('DATA_REG').address, 0x42)
        finally:
            block.close()

    def test_field_handle(self):
        reg = self.mrf.reg('SENSOR_A.CONFIG_REG')
        fld = reg.field('THRESHOLD')
        self.assertEqual((fld.high, fld.low, fld.width), (23, 16, 8))
        self.assertEqual(fld.mask, 0xFF0000)
        self.assertIs(fld.register, reg)
        reg.write(0)
        fld.write(0xAB)
        self.assertEqual(fld.read(), 0xAB)
        self.assertEqual(reg['THRESHOLD'], 0xAB)

    def test_anonymous_field_handle(self):
        reg = self.mrf.reg('SENSOR_A.CONFIG_REG')
        reg.write(0x00AB0000)
        fld = reg.field(23, 16)
        self.assertIsNone(fld.name)
        self.assertEqual(fld.read(), 0xAB)

    def test_field_handle_from_file(self):
        fld = self.mrf.field('SENSOR_A.CONFIG_REG:GAIN')
        self.assertEqual((fld.high, fld.low), (15, 8))
        fld = self.mrf.field('SENSOR_A.CONFIG_REG:15:8')
        self.assertEqual((fld.high, fld.low), (15, 8))

    def test_reg_and_field_reject_wrong_paths(self):
        with self.assertRaises(KeyError):
            self.mrf.reg('SENSOR_A.DATA_REG:VALUE')  # a field path
        with self.assertRaises(KeyError):
            self.mrf.field('SENSOR_A.DATA_REG')  # no field


class AttributeNavigationTests(unittest.TestCase):
    def setUp(self):
        self.rf = rw.RegisterFile(REGS_PATH)
        self.tmpdir = tempfile.mkdtemp()
        self.bin_path = os.path.join(self.tmpdir, 'test.bin')
        shutil.copy(BIN_PATH, self.bin_path)
        os.chmod(self.bin_path, stat.S_IREAD | stat.S_IWRITE)
        self.mrf = MappedRegisterFile(
            self.rf,
            target_factory=lambda rb: rw.MMapTarget(
                self.bin_path, rb.offset, rb.size, rb.data_endianness, rb.data_size
            ),
        )

    def tearDown(self):
        self.mrf.close()
        self.rf.close()
        shutil.rmtree(self.tmpdir)

    def test_navigation_returns_handles(self):
        from rwmem import MappedField, MappedRegister, MappedRegisterBlock

        self.assertIsInstance(self.mrf.SENSOR_A, MappedRegisterBlock)
        self.assertIsInstance(self.mrf.SENSOR_A.STATUS_REG, MappedRegister)
        self.assertIsInstance(self.mrf.SENSOR_A.STATUS_REG.MODE, MappedField)

    def test_read_and_write_through_attributes(self):
        self.assertEqual(self.mrf.SENSOR_A.STATUS_REG.read(), 0x39)
        self.assertEqual(self.mrf.SENSOR_A.STATUS_REG.MODE.read(), 0x7)
        self.mrf.SENSOR_A.STATUS_REG.MODE.write(0x1F)
        self.assertEqual(self.mrf['SENSOR_A.STATUS_REG:MODE'], 0x1F)

    def test_handles_are_the_cached_ones(self):
        self.assertIs(self.mrf.SENSOR_A, self.mrf['SENSOR_A'])
        self.assertIs(self.mrf.SENSOR_A.STATUS_REG, self.mrf.reg('SENSOR_A.STATUS_REG'))

    def test_dir_lists_children(self):
        self.assertIn('SENSOR_A', dir(self.mrf))
        self.assertIn('STATUS_REG', dir(self.mrf.SENSOR_A))
        self.assertIn('MODE', dir(self.mrf.SENSOR_A.STATUS_REG))

    def test_unknown_names_raise_attribute_error(self):
        with self.assertRaises(AttributeError):
            self.mrf.NOPE
        with self.assertRaises(AttributeError):
            self.mrf.SENSOR_A.NOPE
        with self.assertRaises(AttributeError):
            self.mrf.SENSOR_A.STATUS_REG.NOPE
        # Dunder and private lookups must not be intercepted.
        self.assertFalse(hasattr(self.mrf, '__wrapped__'))
        with self.assertRaises(AttributeError):
            self.mrf._not_a_thing

    def test_real_attributes_win_over_navigation(self):
        # A method name is found before __getattr__, so a register named
        # like one would be shadowed; reg() always reaches it.
        self.assertTrue(callable(self.mrf.block))
        self.assertTrue(callable(self.mrf.SENSOR_A.reg))


class MappedRegisterFileTests(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.bin_path = os.path.join(self.tmpdir, 'test.bin')
        shutil.copy(BIN_PATH, self.bin_path)
        os.chmod(self.bin_path, stat.S_IREAD | stat.S_IWRITE)
        with open(BIN_PATH, 'rb') as f:
            self.data = f.read()

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def _mrf(self, rf):
        return MappedRegisterFile(
            rf,
            target_factory=lambda rb: rw.MMapTarget(
                self.bin_path, rb.offset, rb.size, rb.data_endianness, rb.data_size
            ),
        )

    def test_scope_vs_value(self):
        with rw.RegisterFile(REGS_PATH) as rf:
            mrf = self._mrf(rf)
            self.assertIsInstance(mrf['SENSOR_A'], MappedRegisterBlock)  # no I/O
            self.assertIsInstance(mrf['SENSOR_A.STATUS_REG'], RegisterValue)  # a read
            self.assertEqual(mrf['SENSOR_A']['STATUS_REG:MODE'], mrf['SENSOR_A.STATUS_REG:MODE'])
            mrf.close()

    def test_block_read_one_pass(self):
        with rw.RegisterFile(REGS_PATH) as rf:
            mrf = self._mrf(rf)
            allregs = mrf['SENSOR_A.*']
            self.assertEqual(list(allregs), list(rf['SENSOR_A']))
            self.assertEqual(allregs['STATUS_REG'], 0x39)
            subset = mrf['SENSOR_A'].read(['STATUS_REG', 'DATA_REG'])
            self.assertEqual(list(subset), ['STATUS_REG', 'DATA_REG'])
            mrf.close()

    def test_file_read_groups_by_block(self):
        with rw.RegisterFile(REGS_PATH) as rf:
            mrf = self._mrf(rf)
            out = mrf.read(['SENSOR_A.DATA_REG', 'MEMORY_CTRL.ADDR_REG'])
            self.assertEqual(set(out), {'SENSOR_A.DATA_REG', 'MEMORY_CTRL.ADDR_REG'})
            self.assertIsInstance(out['SENSOR_A.DATA_REG'], RegisterValue)
            mrf.close()

    def test_assign_to_bare_block_raises(self):
        with rw.RegisterFile(REGS_PATH) as rf:
            mrf = self._mrf(rf)
            with self.assertRaises(KeyError):
                mrf['SENSOR_A'] = 5
            mrf.close()

    def test_iteration_and_completions(self):
        with rw.RegisterFile(REGS_PATH) as rf:
            mrf = self._mrf(rf)
            self.assertEqual(list(mrf), list(rf))
            keys = mrf._ipython_key_completions_()
            self.assertIn('SENSOR_A', keys)
            self.assertIn('SENSOR_A.*', keys)
            self.assertIn('SENSOR_A.STATUS_REG', keys)
            self.assertIn('SENSOR_A.STATUS_REG:MODE', keys)
            mrf.close()

    def test_owns_register_file_from_path(self):
        mrf = MappedRegisterFile(
            REGS_PATH,
            target_factory=lambda rb: rw.MMapTarget(
                self.bin_path, rb.offset, rb.size, rb.data_endianness, rb.data_size
            ),
        )
        self.assertEqual(mrf['SENSOR_A.STATUS_REG'], 0x39)
        mrf.close()  # closes the RegisterFile it opened
        mrf.close()

    def test_does_not_close_a_borrowed_register_file(self):
        with rw.RegisterFile(REGS_PATH) as rf:
            mrf = self._mrf(rf)
            self.assertEqual(mrf['SENSOR_A.STATUS_REG'], 0x39)
            mrf.close()
            # rf is still usable, and closing it here (via with) must work.
            self.assertEqual(rf['SENSOR_A'].name, 'SENSOR_A')


class EndiannessTests(unittest.TestCase):
    """A block, and a register, must read the same regardless of the
    target's own endianness."""

    def setUp(self):
        self.rf = rw.RegisterFile(REGS_PATH)
        self.block = self.rf['MEMORY_CTRL']  # big-endian block
        self.tmpdir = tempfile.mkdtemp()
        self.bin_path = os.path.join(self.tmpdir, 'test.bin')
        shutil.copy(BIN_PATH, self.bin_path)
        os.chmod(self.bin_path, stat.S_IREAD | stat.S_IWRITE)

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def _le_target(self, mode=rw.MapMode.ReadWrite):
        # Opened Little, unlike the block, which is Big.
        return rw.MMapTarget(
            self.bin_path,
            self.block.offset,
            self.block.size,
            rw.Endianness.Little,
            self.block.data_size,
            mode,
        )

    def test_reads_ignore_target_endianness(self):
        with MappedRegisterBlock(self.bin_path, self.block, mode=rw.MapMode.Read) as m:
            expected = dict(m.read())
        with MappedRegisterBlock(self._le_target(), self.block) as m:
            self.assertEqual(dict(m.read()), expected)

    def test_writes_ignore_target_endianness(self):
        with MappedRegisterBlock(self._le_target(), self.block) as m:
            m['STATUS_REG'] = 0x12345678
            m['CONFIG_REG'] = {'THRESHOLD': 0xAB, 'GAIN': 0xCD, 'OFFSET': 0xEF}
            m['DATA_LO_REG:DATA'] = 0xDEADBEEF
        with MappedRegisterBlock(self.bin_path, self.block, mode=rw.MapMode.Read) as m:
            self.assertEqual(m['STATUS_REG'], 0x12345678)
            self.assertEqual(m['CONFIG_REG'], 0xABCDEF)
            self.assertEqual(m['DATA_LO_REG'], 0xDEADBEEF)

    def test_register_endianness_override(self):
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
            with MappedRegisterBlock(path, b, mode=rw.MapMode.Read) as m:
                self.assertEqual(m['LE_REG'], 0x44332211)
                self.assertEqual(m['BE_REG'], 0x11223344)
            target = rw.MMapTarget(path, 0, 0x8, rw.Endianness.Big, 4, rw.MapMode.Read)
            with MappedRegisterBlock(target, b) as m:
                self.assertEqual(m['LE_REG'], 0x44332211)
                self.assertEqual(m['BE_REG'], 0x11223344)
            del b, m


class TargetAndCloseTests(unittest.TestCase):
    def setUp(self):
        self.rf = rw.RegisterFile(REGS_PATH)
        self.tmpdir = tempfile.mkdtemp()
        self.bin_path = os.path.join(self.tmpdir, 'test.bin')
        shutil.copy(BIN_PATH, self.bin_path)
        os.chmod(self.bin_path, stat.S_IREAD | stat.S_IWRITE)

    def tearDown(self):
        self.rf.close()
        shutil.rmtree(self.tmpdir)

    def _target(self, mode=rw.MapMode.ReadWrite):
        b = self.rf['SENSOR_A']
        return rw.MMapTarget(self.bin_path, b.offset, b.size, b.data_endianness, b.data_size, mode)

    def test_mode_with_a_target_raises(self):
        with self._target(mode=rw.MapMode.Read) as target:
            with self.assertRaises(ValueError):
                MappedRegisterBlock(target, self.rf['SENSOR_A'], mode=rw.MapMode.Read)

    def test_read_only_target_does_not_write(self):
        with MappedRegisterBlock(self._target(mode=rw.MapMode.Read), self.rf['SENSOR_A']) as m:
            with self.assertRaises(Exception):
                m['STATUS_REG'] = 0

    def test_block_close_is_idempotent(self):
        m = MappedRegisterBlock(self._target(), self.rf['SENSOR_A'])
        m.close()
        m.close()

    def test_closing_the_register_file_needs_the_mapped_file_closed_first(self):
        # The mapped blocks hold views into the register file's mmap; a
        # borrowed RegisterFile is closed by its own with-block afterwards.
        with rw.RegisterFile(REGS_PATH) as rf:
            with MappedRegisterFile(
                rf,
                target_factory=lambda rb: rw.MMapTarget(
                    self.bin_path, rb.offset, rb.size, rb.data_endianness, rb.data_size
                ),
            ) as mrf:
                self.assertEqual(mrf['SENSOR_A.STATUS_REG'], 0x39)


if __name__ == '__main__':
    unittest.main()
