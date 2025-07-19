#!/usr/bin/env python3

import os
import unittest
import rwmem as rw

REGS_PATH = os.path.dirname(os.path.abspath(__file__)) + '/test.regdb'


class ContextManagerTests(unittest.TestCase):
    def test(self):
        with rw.RegisterFile(REGS_PATH) as rf:
            self.assertEqual(rf.name, 'TEST_V3')
            self.assertIn('SENSOR_A', rf)


class RegisterFileBasicTests(unittest.TestCase):
    def setUp(self):
        self.rf = rw.RegisterFile(REGS_PATH)

    def test_registerfile_properties(self):
        """Test basic RegisterFile properties and structure."""
        rf = self.rf

        # Test RegisterFile name and basic properties
        self.assertEqual(rf.name, 'TEST_V3')
        self.assertEqual(len(rf), 3)  # 3 blocks

        # Test block access
        expected_blocks = ['SENSOR_A', 'SENSOR_B', 'MEMORY_CTRL']
        self.assertEqual(list(rf.keys()), expected_blocks)

        for block_name in expected_blocks:
            self.assertIn(block_name, rf)
            self.assertTrue(hasattr(rf[block_name], 'offset'))
            self.assertTrue(hasattr(rf[block_name], 'size'))

    def test_sensor_a_block(self):
        """Test SENSOR_A block structure and properties."""
        sensor_a = self.rf['SENSOR_A']

        # Block properties
        self.assertEqual(sensor_a.offset, 0x0)
        self.assertEqual(sensor_a.size, 0x100)
        self.assertEqual(sensor_a.data_endianness, rw.Endianness.Little)
        self.assertEqual(sensor_a.addr_endianness, rw.Endianness.Little)
        self.assertEqual(sensor_a.data_size, 4)
        self.assertEqual(sensor_a.addr_size, 1)

        # Expected registers
        expected_regs = ['STATUS_REG', 'CONTROL_REG', 'DATA_REG', 'CONFIG_REG',
                        'COUNTER_REG', 'BIG_REG', 'HUGE_REG', 'GIANT_REG', 'MAX_REG']
        self.assertEqual(list(sensor_a.keys()), expected_regs)
        self.assertEqual(len(sensor_a), 9)

    def test_memory_ctrl_block(self):
        """Test MEMORY_CTRL block with different endianness."""
        memory_ctrl = self.rf['MEMORY_CTRL']

        # Block properties (big endian, different from sensors)
        self.assertEqual(memory_ctrl.offset, 0x200)
        self.assertEqual(memory_ctrl.size, 0x100)
        self.assertEqual(memory_ctrl.data_endianness, rw.Endianness.Big)
        self.assertEqual(memory_ctrl.addr_endianness, rw.Endianness.Big)
        self.assertEqual(memory_ctrl.data_size, 4)
        self.assertEqual(memory_ctrl.addr_size, 4)

        # Expected registers
        expected_regs = ['ADDR_REG', 'CONFIG_REG', 'STATUS_REG', 'DATA_LO_REG', 'DATA_HI_REG']
        self.assertEqual(list(memory_ctrl.keys()), expected_regs)


class RegisterTests(unittest.TestCase):
    def setUp(self):
        self.rf = rw.RegisterFile(REGS_PATH)
        self.sensor_a = self.rf['SENSOR_A']
        self.memory_ctrl = self.rf['MEMORY_CTRL']

    def test_register_properties(self):
        """Test register properties and data sizes."""
        # Test various data sizes
        status_reg = self.sensor_a['STATUS_REG']
        self.assertEqual(status_reg.offset, 0x0)
        self.assertEqual(status_reg.effective_data_size, 1)  # 8-bit register
        self.assertEqual(status_reg.reset_value, 0x80)

        data_reg = self.sensor_a['DATA_REG']
        self.assertEqual(data_reg.offset, 0x2)
        self.assertEqual(data_reg.effective_data_size, 2)  # 16-bit register
        self.assertEqual(data_reg.reset_value, 0x1234)

        config_reg = self.sensor_a['CONFIG_REG']
        self.assertEqual(config_reg.offset, 0x4)
        self.assertEqual(config_reg.effective_data_size, 3)  # 24-bit register
        self.assertEqual(config_reg.reset_value, 0x123456)

        counter_reg = self.sensor_a['COUNTER_REG']
        self.assertEqual(counter_reg.offset, 0x8)
        self.assertEqual(counter_reg.effective_data_size, 4)  # 32-bit register

        max_reg = self.sensor_a['MAX_REG']
        self.assertEqual(max_reg.offset, 0x24)
        self.assertEqual(max_reg.effective_data_size, 8)  # 64-bit register
        self.assertEqual(max_reg.reset_value, 0x123456789abcdef0)

    def test_register_reset_values(self):
        """Test register reset values."""
        # Memory controller status reset value
        mem_status = self.memory_ctrl['STATUS_REG']
        self.assertEqual(mem_status.reset_value, 0x80000000)


class FieldTests(unittest.TestCase):
    def setUp(self):
        self.rf = rw.RegisterFile(REGS_PATH)
        self.sensor_a = self.rf['SENSOR_A']
        self.memory_ctrl = self.rf['MEMORY_CTRL']

    def test_field_access(self):
        """Test field access and properties."""
        status_reg = self.sensor_a['STATUS_REG']

        # Test field existence
        expected_fields = ['MODE', 'ERROR', 'READY']
        self.assertEqual(list(status_reg.keys()), expected_fields)

        # Test individual field properties
        mode_field = status_reg['MODE']
        self.assertEqual(mode_field.high, 7)
        self.assertEqual(mode_field.low, 3)

        error_field = status_reg['ERROR']
        self.assertEqual(error_field.high, 2)
        self.assertEqual(error_field.low, 1)

        ready_field = status_reg['READY']
        self.assertEqual(ready_field.high, 0)
        self.assertEqual(ready_field.low, 0)

    def test_shared_fields(self):
        """Test that shared fields work correctly across registers."""
        # ERROR and MODE fields are shared between STATUS_REG and CONTROL_REG
        status_reg = self.sensor_a['STATUS_REG']
        control_reg = self.sensor_a['CONTROL_REG']

        # Both should have ERROR and MODE fields with same properties
        self.assertIn('ERROR', status_reg)
        self.assertIn('ERROR', control_reg)
        self.assertIn('MODE', status_reg)
        self.assertIn('MODE', control_reg)

        # Field properties should be identical
        self.assertEqual(status_reg['ERROR'].high, control_reg['ERROR'].high)
        self.assertEqual(status_reg['ERROR'].low, control_reg['ERROR'].low)
        self.assertEqual(status_reg['MODE'].high, control_reg['MODE'].high)
        self.assertEqual(status_reg['MODE'].low, control_reg['MODE'].low)

    def test_wide_fields(self):
        """Test fields in wide registers."""
        # Test 64-bit register field
        addr_reg = self.memory_ctrl['ADDR_REG']
        address_field = addr_reg['ADDRESS']
        self.assertEqual(address_field.high, 63)
        self.assertEqual(address_field.low, 0)

        # Test 32-bit data fields
        data_lo = self.memory_ctrl['DATA_LO_REG']
        data_field = data_lo['DATA']
        self.assertEqual(data_field.high, 31)
        self.assertEqual(data_field.low, 0)


class DeduplicationTests(unittest.TestCase):
    def setUp(self):
        self.rf = rw.RegisterFile(REGS_PATH)

    def test_identical_blocks(self):
        """Test that SENSOR_A and SENSOR_B have identical register structures."""
        sensor_a = self.rf['SENSOR_A']
        sensor_b = self.rf['SENSOR_B']

        # Should have same register names
        self.assertEqual(list(sensor_a.keys()), list(sensor_b.keys()))

        # Check a few registers have same structure
        for reg_name in ['STATUS_REG', 'CONFIG_REG', 'MAX_REG']:
            reg_a = sensor_a[reg_name]
            reg_b = sensor_b[reg_name]

            self.assertEqual(reg_a.offset, reg_b.offset)
            self.assertEqual(reg_a.effective_data_size, reg_b.effective_data_size)
            self.assertEqual(reg_a.reset_value, reg_b.reset_value)
            self.assertEqual(list(reg_a.keys()), list(reg_b.keys()))


class ErrorHandlingTests(unittest.TestCase):
    def setUp(self):
        self.rf = rw.RegisterFile(REGS_PATH)

    def test_invalid_block_access(self):
        """Test error handling for invalid block names."""
        with self.assertRaises(KeyError):
            _ = self.rf['NONEXISTENT_BLOCK']

        self.assertNotIn('NONEXISTENT_BLOCK', self.rf)

    def test_invalid_register_access(self):
        """Test error handling for invalid register names."""
        sensor_a = self.rf['SENSOR_A']

        with self.assertRaises(KeyError):
            _ = sensor_a['NONEXISTENT_REG']

        self.assertNotIn('NONEXISTENT_REG', sensor_a)

    def test_invalid_field_access(self):
        """Test error handling for invalid field names."""
        status_reg = self.rf['SENSOR_A']['STATUS_REG']

        with self.assertRaises(KeyError):
            _ = status_reg['NONEXISTENT_FIELD']

        self.assertNotIn('NONEXISTENT_FIELD', status_reg)
