#!/usr/bin/env python3

import io
import unittest

import rwmem as rw
import rwmem.gen as gen
from rwmem.registerfile import RegisterFile


class DeduplicationTests(unittest.TestCase):
    def test_identical_blocks_share_register_data(self):
        """Test that blocks with identical register definitions share underlying data structures."""

        # Define identical VP register sets - same names, offsets, and fields
        VP_REGS = (
            (
                'CTRL',
                0x00,
                (
                    ('ENABLE', 0, 0),
                    ('MODE', 3, 1),
                ),
            ),
            (
                'STATUS',
                0x04,
                (
                    ('READY', 0, 0),
                    ('ERROR', 1, 1),
                ),
            ),
            ('CONFIG', 0x08, (('THRESHOLD', 7, 0),)),
        )

        # Define UART register set (different from VP registers to test group separation)
        UART_REGS = (
            ('DATA', 0x00, (('VALUE', 7, 0),)),
            ('BAUD', 0x04, (('RATE', 15, 0),)),
        )

        # Create blocks: 4 identical VP blocks + 2 identical UART blocks
        BLOCKS = (
            (
                'VP0',
                0x10000000,
                0x1000,
                VP_REGS,
                rw.Endianness.Default,
                4,
                rw.Endianness.Default,
                4,
            ),
            (
                'VP1',
                0x10001000,
                0x1000,
                VP_REGS,
                rw.Endianness.Default,
                4,
                rw.Endianness.Default,
                4,
            ),
            (
                'VP2',
                0x10002000,
                0x1000,
                VP_REGS,
                rw.Endianness.Default,
                4,
                rw.Endianness.Default,
                4,
            ),
            (
                'VP3',
                0x10003000,
                0x1000,
                VP_REGS,
                rw.Endianness.Default,
                4,
                rw.Endianness.Default,
                4,
            ),
            (
                'UART0',
                0x20000000,
                0x1000,
                UART_REGS,
                rw.Endianness.Default,
                4,
                rw.Endianness.Default,
                4,
            ),
            (
                'UART1',
                0x20001000,
                0x1000,
                UART_REGS,
                rw.Endianness.Default,
                4,
                rw.Endianness.Default,
                4,
            ),
        )

        # Generate and load register file
        urf = gen.create_register_file('SoC', BLOCKS)

        with io.BytesIO() as f:
            urf.pack_to(f)
            data = f.getvalue()

        rf = RegisterFile(data)

        # Test 1: Functional correctness - all blocks should be accessible
        self.assertEqual(rf.name, 'SoC')
        self.assertEqual(rf.num_blocks, 6)

        # All VP blocks should have identical register structure
        for vp_name in ['VP0', 'VP1', 'VP2', 'VP3']:
            vp = rf[vp_name]
            self.assertEqual(vp.num_registers, 3)
            self.assertEqual(vp['CTRL'].name, 'CTRL')
            self.assertEqual(vp['CTRL']['ENABLE'].name, 'ENABLE')
            self.assertEqual(vp['CTRL']['MODE'].high, 3)
            self.assertEqual(vp['CTRL']['MODE'].low, 1)

        # UART blocks should have different structure from VP blocks
        for uart_name in ['UART0', 'UART1']:
            uart = rf[uart_name]
            self.assertEqual(uart.num_registers, 2)
            self.assertEqual(uart['DATA'].name, 'DATA')
            self.assertEqual(uart['BAUD']['RATE'].high, 15)

        # Test 2: Deduplication verification - check internal structure
        vp0_block = rf['VP0']
        vp1_block = rf['VP1']
        vp2_block = rf['VP2']
        vp3_block = rf['VP3']
        uart0_block = rf['UART0']
        uart1_block = rf['UART1']

        # In v3, identical blocks share RegisterData entries through RegisterIndex indirection
        # VP blocks should have their RegisterIndex entries pointing to the same RegisterData entries
        import ctypes
        from rwmem._structs import RegisterIndexV3

        def get_register_indices(block):
            """Get the list of RegisterData indices this block references."""
            indices = []
            for i in range(block.rbd.num_regs):
                reg_index_offset = rf.register_indices_offset + ctypes.sizeof(RegisterIndexV3) * (
                    block.rbd.first_reg_list_index + i
                )
                reg_index_data = RegisterIndexV3.from_buffer(rf._map, reg_index_offset)
                indices.append(reg_index_data.register_index)
            return indices

        vp0_indices = get_register_indices(vp0_block)
        vp1_indices = get_register_indices(vp1_block)
        vp2_indices = get_register_indices(vp2_block)
        vp3_indices = get_register_indices(vp3_block)

        self.assertEqual(
            vp1_indices, vp0_indices, 'VP1 should reference same RegisterData entries as VP0'
        )
        self.assertEqual(
            vp2_indices, vp0_indices, 'VP2 should reference same RegisterData entries as VP0'
        )
        self.assertEqual(
            vp3_indices, vp0_indices, 'VP3 should reference same RegisterData entries as VP0'
        )

        # UART blocks should share with each other but not with VP blocks
        uart0_indices = get_register_indices(uart0_block)
        uart1_indices = get_register_indices(uart1_block)

        self.assertEqual(
            uart1_indices,
            uart0_indices,
            'UART1 should reference same RegisterData entries as UART0',
        )
        self.assertNotEqual(
            uart0_indices,
            vp0_indices,
            'UART and VP blocks should reference different RegisterData entries',
        )

        # Test 3: Efficiency verification - deduplication should reduce total unique data structures

        # Register deduplication
        total_logical_registers = (
            4 * 3 + 2 * 2
        )  # Without dedup: 4 VP blocks × 3 regs + 2 UART blocks × 2 regs = 16
        total_actual_registers = rf.num_regs
        expected_unique_registers = 3 + 2  # With perfect dedup: 3 VP regs + 2 UART regs = 5

        self.assertEqual(
            total_actual_registers,
            expected_unique_registers,
            f'Expected {expected_unique_registers} unique registers, got {total_actual_registers}',
        )
        self.assertLess(
            total_actual_registers,
            total_logical_registers,
            f'Deduplication should reduce {total_logical_registers} logical registers to {expected_unique_registers}',
        )

        # Field deduplication
        total_logical_fields = 4 * (2 + 2 + 1) + 2 * (
            1 + 1
        )  # VP: 4 × (CTRL:2 + STATUS:2 + CONFIG:1), UART: 2 × (DATA:1 + BAUD:1) = 24
        total_actual_fields = rf.num_fields
        expected_unique_fields = (2 + 2 + 1) + (
            1 + 1
        )  # With perfect dedup: VP fields + UART fields = 7

        self.assertEqual(
            total_actual_fields,
            expected_unique_fields,
            f'Expected {expected_unique_fields} unique fields, got {total_actual_fields}',
        )
        self.assertLess(
            total_actual_fields,
            total_logical_fields,
            f'Deduplication should reduce {total_logical_fields} logical fields to {expected_unique_fields}',
        )

        # String deduplication verification
        # Expected unique strings: 'SoC' + VP block names (4) + UART block names (2) + VP reg names (3) + VP field names (5) + UART reg names (2) + UART field names (2) = 19
        # All strings in this test are unique, so no string deduplication is expected
        # The string pool should contain exactly these 19 unique strings
        # Note: We can't easily count strings in the binary format, but deduplication ensures shared register/field names use same string offsets


if __name__ == '__main__':
    unittest.main()
