#!/usr/bin/env python3

import io
import unittest

import rwmem as rw
import rwmem.gen as gen
from rwmem.registerfile import Register, RegisterBlock, RegisterFile

# Define register blocks without fields

OVR_REGS = (
    ( 'ATTRIBUTES_0', 0x20 ),
    ( 'ATTRIBUTES_1', 0x24 ),
    ( 'ATTRIBUTES_2', 0x28 ),
    ( 'ATTRIBUTES_3', 0x2c ),
)

VP_REGS = (
    ( 'CONTROL', 0x4 ),
)

BLOCKS = (
    ( 'VP1', 0x3020a000, 0x1000, VP_REGS, rw.Endianness.Default, 4, rw.Endianness.Default, 4 ),
    ( 'VP2', 0x3020b000, 0x1000, VP_REGS, rw.Endianness.Default, 4, rw.Endianness.Default, 4 ),
    ( 'OVR2', 0x30208000, 0x1000, OVR_REGS, rw.Endianness.Default, 4, rw.Endianness.Default, 4 ),
    ( 'OVR1', 0x30207000, 0x1000, OVR_REGS, rw.Endianness.Default, 4, rw.Endianness.Default, 4 ),
)

# Define register blocks with fields

OVR_REGS_FIELDS = (
    ( 'ATTRIBUTES_0', 0x20, (
        ( 'POSY', 30, 19 ),
        ( 'POSX', 17, 6 ),
        ( 'CHANNELIN', 4, 1 ),
        ( 'ENABLE', 0, 0 ),
    ) ),
    ( 'ATTRIBUTES_1', 0x24, (
        ( 'POSY', 30, 19 ),
        ( 'POSX', 17, 6 ),
        ( 'CHANNELIN', 4, 1 ),
        ( 'ENABLE', 0, 0 ),
    ) ),
    ( 'ATTRIBUTES_2', 0x28, (
        ( 'POSY', 30, 19 ),
        ( 'POSX', 17, 6 ),
        ( 'CHANNELIN', 4, 1 ),
        ( 'ENABLE', 0, 0 ),
    ) ),
    ( 'ATTRIBUTES_3', 0x2c, (
        ( 'POSY', 30, 19 ),
        ( 'POSX', 17, 6 ),
        ( 'CHANNELIN', 4, 1 ),
        ( 'ENABLE', 0, 0 ),
    ) ),
)

VP_REGS_FIELDS = (
    ( 'CONTROL', 0x4, (
        ( 'GOBIT', 5, 5 ),
        ( 'ENABLE', 0, 0 ),
    ) ),
)

BLOCKS_FIELDS = (
    ( 'VP1', 0x3020a000, 0x1000, VP_REGS_FIELDS, rw.Endianness.Default, 4, rw.Endianness.Default, 4 ),
    ( 'VP2', 0x3020b000, 0x1000, VP_REGS_FIELDS, rw.Endianness.Default, 4, rw.Endianness.Default, 4 ),
    ( 'OVR2', 0x30208000, 0x1000, OVR_REGS_FIELDS, rw.Endianness.Default, 4, rw.Endianness.Default, 4 ),
    ( 'OVR1', 0x30207000, 0x1000, OVR_REGS_FIELDS, rw.Endianness.Default, 4, rw.Endianness.Default, 4 ),
)

class MmapTests(unittest.TestCase):
    def test_gen(self):
        # Create an unpacked register file
        urf = gen.UnpackedRegFile('DSS', BLOCKS)

        # Pack the unpacked register file into a memory stream.
        # Normally this would be written to a file.
        with io.BytesIO() as f:
            urf.pack_to(f)
            data = f.getvalue()

        # Create a RegisterFile from the packed data.
        # Normally this would be read from a file.
        rf = RegisterFile(data)

        # Test that the register file contains the correct data
        self.assertEqual(rf.name, 'DSS')

        self.compare_blocks(rf, BLOCKS)

    def test_gen_fields(self):
        # Create an unpacked register file
        urf = gen.UnpackedRegFile('DSS', BLOCKS_FIELDS)

        # Pack the unpacked register file into a memory stream.
        # Normally this would be written to a file.
        with io.BytesIO() as f:
            urf.pack_to(f)
            data = f.getvalue()

        # Create a RegisterFile from the packed data.
        # Normally this would be read from a file.
        rf = RegisterFile(data)

        # Test that the register file contains the correct data
        self.assertEqual(rf.name, 'DSS')

        self.compare_blocks(rf, BLOCKS_FIELDS)


    def compare_blocks(self, rf: RegisterFile, ref_blocks):
        for ref_name, ref_offset, ref_size, ref_regs, ref_ae, ref_as, ref_de, ref_ds in ref_blocks:
            rb = rf[ref_name]
            self.assertEqual(rb.name, ref_name)
            self.assertEqual(rb.offset, ref_offset)
            self.assertEqual(rb.size, ref_size)
            self.assertEqual(rb.addr_endianness, ref_ae)
            self.assertEqual(rb.addr_size, ref_as)
            self.assertEqual(rb.data_endianness, ref_de)
            self.assertEqual(rb.data_size, ref_ds)

            self.compare_registers(rb, ref_regs)

    def compare_registers(self, block: RegisterBlock, ref_regs):
        for ref_name, ref_offset, *ref_fields in ref_regs:
            if ref_fields:
                ref_fields_data = ref_fields[0]
            else:
                ref_fields_data = None

            reg = block[ref_name]
            self.assertEqual(reg.name, ref_name)
            self.assertEqual(reg.offset, ref_offset)

            self.compare_fields(reg, ref_fields_data)

    def compare_fields(self, reg: Register, ref_fields):
        if ref_fields is None:
            return
        for ref_name, ref_high, ref_low in ref_fields:
            field = reg[ref_name]
            self.assertEqual(field.name, ref_name)
            self.assertEqual(field.high, ref_high)
            self.assertEqual(field.low, ref_low)
