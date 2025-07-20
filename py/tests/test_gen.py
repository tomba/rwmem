#!/usr/bin/env python3

import io
import unittest

import rwmem as rw
import rwmem.gen as gen
from rwmem.registerfile import RegisterFile


class V3GenerationTests(unittest.TestCase):
    """Test v3 register database generation with comprehensive v3 features."""

    def test_basic_v2_compatibility(self):
        """Test that basic v2-style definitions still work (backward compatibility)."""
        # Simple block with basic registers (v2-style, no v3 features)
        basic_regs = [
            gen.UnpackedRegister('CONFIG', 0x00, [
                gen.UnpackedField('ENABLE', 0, 0),
                gen.UnpackedField('MODE', 3, 1),
            ]),
            gen.UnpackedRegister('STATUS', 0x04, [
                gen.UnpackedField('READY', 0, 0),
                gen.UnpackedField('ERROR', 7, 4),
            ]),
        ]

        basic_blocks = [
            gen.UnpackedRegBlock('BASIC', 0x1000, 0x100, basic_regs,
                               rw.Endianness.Little, 4, rw.Endianness.Little, 4)
        ]

        urf = gen.UnpackedRegFile('BASIC_TEST', basic_blocks)

        # Pack and verify
        with io.BytesIO() as f:
            urf.pack_to(f)
            data = f.getvalue()

        rf = RegisterFile(data)
        self.assertEqual(rf.name, 'BASIC_TEST')

        block = rf['BASIC']
        self.assertEqual(block.name, 'BASIC')
        self.assertEqual(block.offset, 0x1000)
        self.assertEqual(block.size, 0x100)
        self.assertIsNone(block.description)  # No description in v2-style

        reg = block['CONFIG']
        self.assertEqual(reg.name, 'CONFIG')
        self.assertEqual(reg.offset, 0x00)
        self.assertEqual(reg.reset_value, 0)  # Default when not specified
        self.assertIsNone(reg.description)

        field = reg['ENABLE']
        self.assertEqual(field.name, 'ENABLE')
        self.assertEqual(field.high, 0)
        self.assertEqual(field.low, 0)
        self.assertIsNone(field.description)

    def test_comprehensive_v3_features(self):
        """Test all v3 features: descriptions, reset values, per-register sizing."""

        # GPU-style register block with comprehensive v3 features
        gpu_regs = [
            # Main control register
            gen.UnpackedRegister(
                'CTRL', 0x00,
                description='Main GPU control register',
                reset_value=0x80000000,  # READY bit set by default
                fields=[
                    gen.UnpackedField('ENABLE', 0, 0,
                                    description='GPU enable bit'),
                    gen.UnpackedField('RESET', 1, 1,
                                    description='Soft reset trigger'),
                    gen.UnpackedField('IRQ_MASK', 7, 4,
                                    description='Interrupt mask bits'),
                    gen.UnpackedField('MODE', 11, 8,
                                    description='Operating mode'),
                    gen.UnpackedField('ERROR', 19, 16,
                                    description='Error status'),
                    gen.UnpackedField('READY', 31, 31,
                                    description='GPU ready flag'),
                ]
            ),

            # 16-bit status register (per-register data size override)
            gen.UnpackedRegister(
                'STATUS', 0x04,
                description='GPU status register',
                reset_value=0x0001,  # IDLE bit set
                data_size=2,  # Override to 16-bit
                fields=[
                    gen.UnpackedField('IDLE', 0, 0,
                                    description='GPU idle state'),
                    gen.UnpackedField('BUSY', 1, 1,
                                    description='GPU busy flag'),
                    gen.UnpackedField('TEMP', 15, 8,
                                    description='Temperature reading'),
                ]
            ),

            # 8-bit interrupt register with endianness override
            gen.UnpackedRegister(
                'IRQ', 0x06,
                description='Interrupt control',
                reset_value=0x00,
                data_size=1,  # 8-bit register
                data_endianness=rw.Endianness.Big,  # Override endianness
                fields=[
                    gen.UnpackedField('VSYNC_EN', 0, 0,
                                    description='VSync interrupt enable'),
                    gen.UnpackedField('HSYNC_EN', 1, 1,
                                    description='HSync interrupt enable'),
                    gen.UnpackedField('ERR_EN', 2, 2,
                                    description='Error interrupt enable'),
                    gen.UnpackedField('PEND', 7, 7,
                                    description='Interrupt pending'),
                ]
            ),

            # 64-bit framebuffer address register
            gen.UnpackedRegister(
                'FB_ADDR', 0x08,
                description='Framebuffer base address',
                reset_value=0x0000000000000000,
                data_size=8,  # 64-bit register
                fields=[
                    gen.UnpackedField('ADDR_LOW', 31, 0,
                                    description='Lower address bits'),
                    gen.UnpackedField('ADDR_HIGH', 63, 32,
                                    description='Upper address bits'),
                ]
            ),
        ]

        # I2C sensor block with different addressing
        i2c_regs = [
            gen.UnpackedRegister(
                'SENSOR_CTRL', 0x00,
                description='Sensor control register',
                reset_value=0x08,  # Default sample rate
                addr_size=1,  # 8-bit I2C addressing
                fields=[
                    gen.UnpackedField('SAMPLE_RATE', 3, 0,
                                    description='Sample rate setting'),
                    gen.UnpackedField('POWER_DOWN', 7, 7,
                                    description='Power down mode'),
                ]
            ),
            gen.UnpackedRegister(
                'SENSOR_DATA', 0x01,
                description='Sensor data register',
                reset_value=0x00,
                addr_size=1,  # 8-bit I2C addressing
                fields=[
                    gen.UnpackedField('TEMP_DATA', 7, 0,
                                    description='Temperature data'),
                ]
            ),
        ]

        # Create blocks with descriptions
        blocks = [
            gen.UnpackedRegBlock(
                'GPU', 0x40000000, 0x1000, gpu_regs,
                rw.Endianness.Little, 4, rw.Endianness.Little, 4,
                description='Graphics processing unit registers'
            ),
            gen.UnpackedRegBlock(
                'I2C_SENSOR', 0x48, 0x10, i2c_regs,
                rw.Endianness.Big, 1, rw.Endianness.Big, 1,
                description='I2C temperature sensor'
            ),
        ]

        # Create register file with description
        urf = gen.UnpackedRegFile('GPU_SYSTEM', blocks, description='GPU system with I2C sensors')

        # Pack and test
        with io.BytesIO() as f:
            urf.pack_to(f)
            data = f.getvalue()

        rf = RegisterFile(data)

        # Test register file properties
        self.assertEqual(rf.name, 'GPU_SYSTEM')
        # Note: RegisterFile description property not yet implemented in step 2

        # Test GPU block
        gpu_block = rf['GPU']
        self.assertEqual(gpu_block.name, 'GPU')
        self.assertEqual(gpu_block.description, 'Graphics processing unit registers')
        self.assertEqual(gpu_block.offset, 0x40000000)
        self.assertEqual(gpu_block.addr_endianness, rw.Endianness.Little)
        self.assertEqual(gpu_block.data_size, 4)

        # Test CTRL register (32-bit)
        ctrl_reg = gpu_block['CTRL']
        self.assertEqual(ctrl_reg.name, 'CTRL')
        self.assertEqual(ctrl_reg.description, 'Main GPU control register')
        self.assertEqual(ctrl_reg.reset_value, 0x80000000)
        self.assertEqual(ctrl_reg.effective_data_size, 4)  # Inherits from block
        self.assertEqual(ctrl_reg.effective_data_endianness, rw.Endianness.Little)

        # Test CTRL register fields
        enable_field = ctrl_reg['ENABLE']
        self.assertEqual(enable_field.description, 'GPU enable bit')

        reset_field = ctrl_reg['RESET']
        self.assertEqual(reset_field.description, 'Soft reset trigger')

        ready_field = ctrl_reg['READY']
        self.assertEqual(ready_field.description, 'GPU ready flag')

        # Test STATUS register (16-bit override)
        status_reg = gpu_block['STATUS']
        self.assertEqual(status_reg.description, 'GPU status register')
        self.assertEqual(status_reg.reset_value, 0x0001)
        self.assertEqual(status_reg.effective_data_size, 2)  # Per-register override

        # Test field
        idle_field = status_reg['IDLE']
        self.assertEqual(idle_field.description, 'GPU idle state')

        # Test IRQ register (8-bit with endianness override)
        irq_reg = gpu_block['IRQ']
        self.assertEqual(irq_reg.description, 'Interrupt control')
        self.assertEqual(irq_reg.effective_data_size, 1)  # 8-bit override
        self.assertEqual(irq_reg.effective_data_endianness, rw.Endianness.Big)  # Endianness override

        pend_field = irq_reg['PEND']
        self.assertEqual(pend_field.description, 'Interrupt pending')

        # Test FB_ADDR register (64-bit)
        fb_reg = gpu_block['FB_ADDR']
        self.assertEqual(fb_reg.description, 'Framebuffer base address')
        self.assertEqual(fb_reg.effective_data_size, 8)  # 64-bit override
        self.assertEqual(fb_reg.reset_value, 0x0000000000000000)

        # Test I2C block
        i2c_block = rf['I2C_SENSOR']
        self.assertEqual(i2c_block.description, 'I2C temperature sensor')
        self.assertEqual(i2c_block.addr_size, 1)  # 8-bit addressing
        self.assertEqual(i2c_block.data_endianness, rw.Endianness.Big)

        # Test I2C register with address size override
        sensor_ctrl = i2c_block['SENSOR_CTRL']
        self.assertEqual(sensor_ctrl.effective_addr_size, 1)  # Per-register override
        self.assertEqual(sensor_ctrl.reset_value, 0x08)

        sample_rate_field = sensor_ctrl['SAMPLE_RATE']
        self.assertEqual(sample_rate_field.description, 'Sample rate setting')

    def test_validation_errors(self):
        """Test that validation catches v3-specific errors."""

        # Test reset value too large for register size
        with self.assertRaises(gen.RegisterValidationError) as cm:
            reg = gen.UnpackedRegister('BAD_REG', 0x00, reset_value=0x1FF, data_size=1)
            # Validation happens during block creation
            gen.UnpackedRegBlock('TEST', 0x1000, 0x100, [reg],
                               rw.Endianness.Little, 4, rw.Endianness.Little, 4)
        self.assertIn('reset_value', str(cm.exception))

        # Test field bit position validation
        with self.assertRaises(gen.FieldValidationError) as cm:
            gen.UnpackedField('BAD_FIELD', 5, 7)  # high < low should fail
        self.assertIn('high bit (5) must be >= low bit (7)', str(cm.exception))

    def test_inheritance_behavior(self):
        """Test register property inheritance from blocks."""

        # Block with specific defaults
        block_regs = [
            # Register that inherits everything from block
            gen.UnpackedRegister('INHERIT_ALL', 0x00, fields=[
                gen.UnpackedField('DATA', 7, 0),
            ]),

            # Register that overrides some properties
            gen.UnpackedRegister('OVERRIDE_SOME', 0x04,
                               data_size=2,  # Override size
                               addr_endianness=rw.Endianness.Big,  # Override endianness
                               fields=[
                                   gen.UnpackedField('DATA', 15, 0),
                               ]),
        ]

        block = gen.UnpackedRegBlock(
            'INHERIT_TEST', 0x2000, 0x100, block_regs,
            rw.Endianness.Little, 4, rw.Endianness.Little, 4,
            description='Inheritance test block'
        )

        urf = gen.UnpackedRegFile('INHERIT_TEST', [block])

        with io.BytesIO() as f:
            urf.pack_to(f)
            data = f.getvalue()

        rf = RegisterFile(data)
        test_block = rf['INHERIT_TEST']

        # Test full inheritance
        inherit_reg = test_block['INHERIT_ALL']
        self.assertEqual(inherit_reg.effective_addr_size, 4)  # From block
        self.assertEqual(inherit_reg.effective_data_size, 4)  # From block
        self.assertEqual(inherit_reg.effective_addr_endianness, rw.Endianness.Little)  # From block
        self.assertEqual(inherit_reg.effective_data_endianness, rw.Endianness.Little)  # From block

        # Test partial override
        override_reg = test_block['OVERRIDE_SOME']
        self.assertEqual(override_reg.effective_addr_size, 4)  # From block (not overridden)
        self.assertEqual(override_reg.effective_data_size, 2)  # Overridden
        self.assertEqual(override_reg.effective_addr_endianness, rw.Endianness.Big)  # Overridden
        self.assertEqual(override_reg.effective_data_endianness, rw.Endianness.Little)  # From block (not overridden)

    def test_field_sharing_optimization(self):
        """Test that field sharing optimization works correctly."""

        # Create two registers with overlapping field definitions
        shared_fields = [
            gen.UnpackedField('ENABLE', 0, 0, description='Enable bit'),
            gen.UnpackedField('STATUS', 7, 4, description='Status bits'),
        ]

        reg1 = gen.UnpackedRegister('REG1', 0x00, fields=shared_fields + [
            gen.UnpackedField('UNIQUE1', 15, 8, description='Unique to reg1'),
        ])

        reg2 = gen.UnpackedRegister('REG2', 0x04, fields=shared_fields + [
            gen.UnpackedField('UNIQUE2', 15, 8, description='Unique to reg2'),
        ])

        block = gen.UnpackedRegBlock('SHARING_TEST', 0x3000, 0x100, [reg1, reg2],
                                   rw.Endianness.Little, 4, rw.Endianness.Little, 4)

        urf = gen.UnpackedRegFile('SHARING_TEST', [block])

        with io.BytesIO() as f:
            urf.pack_to(f)
            data = f.getvalue()

        rf = RegisterFile(data)

        # Verify both registers can access shared fields
        test_block = rf['SHARING_TEST']
        reg1 = test_block['REG1']
        reg2 = test_block['REG2']

        # Both should have the shared fields
        self.assertEqual(reg1['ENABLE'].description, 'Enable bit')
        self.assertEqual(reg2['ENABLE'].description, 'Enable bit')
        self.assertEqual(reg1['STATUS'].description, 'Status bits')
        self.assertEqual(reg2['STATUS'].description, 'Status bits')

        # And their unique fields
        self.assertEqual(reg1['UNIQUE1'].description, 'Unique to reg1')
        self.assertEqual(reg2['UNIQUE2'].description, 'Unique to reg2')

    def test_tuple_approach_conversion(self):
        """Test that tuple specifications are correctly converted to objects."""

        # Define register file using pure tuple approach
        tuple_blocks_spec = [
            # Block tuple: (name, offset, size, regs_spec, addr_endianness, addr_size, data_endianness, data_size, description)
            ('CTRL_BLOCK', 0x1000, 0x100, [
                # Register tuple: (name, offset, fields_spec)
                ('CONFIG', 0x00, [
                    # Field tuples: (name, high, low, description)
                    ('ENABLE', 0, 0, 'Enable bit'),
                    ('MODE', 3, 1, 'Operation mode'),
                ]),
                ('STATUS', 0x04, [
                    ('READY', 0, 0, 'Ready flag'),
                    ('ERROR', 7, 4, 'Error status'),
                ]),
            ], rw.Endianness.Little, 4, rw.Endianness.Little, 4, 'Control block'),

            ('DATA_BLOCK', 0x2000, 0x200, [
                ('DATA_REG', 0x00, [
                    ('VALUE', 31, 0, 'Data value'),
                ]),
            ], rw.Endianness.Big, 4, rw.Endianness.Big, 4, 'Data block'),
        ]

        # Create register file using tuple approach
        tuple_rf = gen.create_register_file('TUPLE_TEST', tuple_blocks_spec, 'Test register file')

        # Create equivalent register file using explicit objects
        obj_blocks = [
            gen.UnpackedRegBlock(
                'CTRL_BLOCK', 0x1000, 0x100, [
                    gen.UnpackedRegister('CONFIG', 0x00, [
                        gen.UnpackedField('ENABLE', 0, 0, 'Enable bit'),
                        gen.UnpackedField('MODE', 3, 1, 'Operation mode'),
                    ]),
                    gen.UnpackedRegister('STATUS', 0x04, [
                        gen.UnpackedField('READY', 0, 0, 'Ready flag'),
                        gen.UnpackedField('ERROR', 7, 4, 'Error status'),
                    ]),
                ], rw.Endianness.Little, 4, rw.Endianness.Little, 4, 'Control block'
            ),
            gen.UnpackedRegBlock(
                'DATA_BLOCK', 0x2000, 0x200, [
                    gen.UnpackedRegister('DATA_REG', 0x00, [
                        gen.UnpackedField('VALUE', 31, 0, 'Data value'),
                    ]),
                ], rw.Endianness.Big, 4, rw.Endianness.Big, 4, 'Data block'
            ),
        ]

        obj_rf = gen.UnpackedRegFile('TUPLE_TEST', obj_blocks, 'Test register file')

        # Pack both and compare binary output
        with io.BytesIO() as tuple_out, io.BytesIO() as obj_out:
            tuple_rf.pack_to(tuple_out)
            obj_rf.pack_to(obj_out)

            tuple_data = tuple_out.getvalue()
            obj_data = obj_out.getvalue()

            self.assertEqual(tuple_data, obj_data, 'Tuple approach should produce identical binary output')

        # Verify both can be read and produce same results
        tuple_regfile = RegisterFile(tuple_data)
        obj_regfile = RegisterFile(obj_data)

        self.assertEqual(tuple_regfile.name, obj_regfile.name)
        self.assertEqual(len(tuple_regfile), len(obj_regfile))

        # Test specific block/register/field access
        tuple_ctrl = tuple_regfile['CTRL_BLOCK']
        obj_ctrl = obj_regfile['CTRL_BLOCK']
        self.assertEqual(tuple_ctrl.description, obj_ctrl.description)
        self.assertEqual(tuple_ctrl.offset, obj_ctrl.offset)

        tuple_config = tuple_ctrl['CONFIG']
        obj_config = obj_ctrl['CONFIG']
        self.assertEqual(tuple_config.name, obj_config.name)
        self.assertEqual(tuple_config.offset, obj_config.offset)

        tuple_enable = tuple_config['ENABLE']
        obj_enable = obj_config['ENABLE']
        self.assertEqual(tuple_enable.description, obj_enable.description)

    def test_tuple_approach_mixed_objects(self):
        """Test that tuples and objects can be mixed in specifications."""

        # Mix objects and tuples at different levels
        mixed_blocks_spec = [
            # Use object for first block
            gen.UnpackedRegBlock(
                'OBJ_BLOCK', 0x1000, 0x100, [
                    # Use tuple for register
                    ('REG1', 0x00, [
                        # Use object for field
                        gen.UnpackedField('FIELD1', 7, 0, 'Test field'),
                    ]),
                ], rw.Endianness.Little, 4, rw.Endianness.Little, 4, 'Object block'
            ),
            # Use tuple for second block
            ('TUPLE_BLOCK', 0x2000, 0x100, [
                # Use object for register
                gen.UnpackedRegister('REG2', 0x00, [
                    # Use tuple for field
                    ('FIELD2', 7, 0, 'Another field'),
                ]),
            ], rw.Endianness.Little, 4, rw.Endianness.Little, 4, 'Tuple block'),
        ]

        mixed_rf = gen.create_register_file('MIXED_TEST', mixed_blocks_spec)

        # Should work without errors
        with io.BytesIO() as f:
            mixed_rf.pack_to(f)
            data = f.getvalue()

        rf = RegisterFile(data)
        self.assertEqual(rf.name, 'MIXED_TEST')
        self.assertEqual(len(rf), 2)

        # Verify both blocks are accessible
        obj_block = rf['OBJ_BLOCK']
        tuple_block = rf['TUPLE_BLOCK']
        self.assertEqual(obj_block.description, 'Object block')
        self.assertEqual(tuple_block.description, 'Tuple block')

    def test_tuple_approach_error_handling(self):
        """Test that invalid tuple specifications raise appropriate errors."""

        # Test invalid block specification
        with self.assertRaises(TypeError) as cm:
            gen.create_register_file('ERROR_TEST', [
                'invalid_block_spec'  # Neither tuple nor UnpackedRegBlock
            ])
        self.assertIn('Block specification must be UnpackedRegBlock or tuple', str(cm.exception))

        # Test invalid register specification in tuple block
        with self.assertRaises(TypeError) as cm:
            gen.create_register_file('ERROR_TEST', [
                ('BLOCK', 0x1000, 0x100, [
                    123  # Neither tuple nor UnpackedRegister
                ], rw.Endianness.Little, 4, rw.Endianness.Little, 4)
            ])
        self.assertIn('Register specification must be UnpackedRegister or tuple', str(cm.exception))

        # Test invalid field specification
        with self.assertRaises(TypeError) as cm:
            gen.create_register_file('ERROR_TEST', [
                ('BLOCK', 0x1000, 0x100, [
                    ('REG', 0x00, [
                        {'invalid': 'field'}  # Neither tuple nor UnpackedField
                    ])
                ], rw.Endianness.Little, 4, rw.Endianness.Little, 4)
            ])
        self.assertIn('Field specification must be UnpackedField or tuple', str(cm.exception))


if __name__ == '__main__':
    unittest.main()
