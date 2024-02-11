#!/usr/bin/python3

import difflib
import io
import os
import unittest

import rwmem as rw
import rwmem.gen as gen

BIN_PATH = os.path.dirname(os.path.abspath(__file__)) + '/gen.bin'

OVR_REGS = [
    ( 'ATTRIBUTES_0', 0x20, [
        ( 'POSY', 30, 19 ),
        ( 'POSX', 17, 6 ),
        ( 'CHANNELIN', 4, 1 ),
        ( 'ENABLE', 0, 0 ),
    ] ),
    ( 'ATTRIBUTES_1', 0x24, [
        ( 'POSY', 30, 19 ),
        ( 'POSX', 17, 6 ),
        ( 'CHANNELIN', 4, 1 ),
        ( 'ENABLE', 0, 0 ),
    ] ),
    ( 'ATTRIBUTES_2', 0x28, [
        ( 'POSY', 30, 19 ),
        ( 'POSX', 17, 6 ),
        ( 'CHANNELIN', 4, 1 ),
        ( 'ENABLE', 0, 0 ),
    ] ),
    ( 'ATTRIBUTES_3', 0x2c, [
        ( 'POSY', 30, 19 ),
        ( 'POSX', 17, 6 ),
        ( 'CHANNELIN', 4, 1 ),
        ( 'ENABLE', 0, 0 ),
    ] ),
]

VP_REGS = [
    ( 'CONTROL', 0x4, [
        ( 'GOBIT', 5, 5 ),
        ( 'ENABLE', 0, 0 ),
    ] ),
]

class MmapTests(unittest.TestCase):
    def test_gen(self):
        urf = gen.UnpackedRegFile(
            'DSS', [
                ( 'VP1', 0x3020a000, 0x1000, VP_REGS, rw.Endianness.Default, 4, rw.Endianness.Default, 4 ),
                ( 'VP2', 0x3020b000, 0x1000, VP_REGS, rw.Endianness.Default, 4, rw.Endianness.Default, 4 ),
                ( 'OVR2', 0x30208000, 0x1000, OVR_REGS, rw.Endianness.Default, 4, rw.Endianness.Default, 4 ),
                ( 'OVR1', 0x30207000, 0x1000, OVR_REGS, rw.Endianness.Default, 4, rw.Endianness.Default, 4 ),
            ]
        )

        with io.BytesIO() as f:
            urf.pack_to(f)
            data1 = f.getvalue()

        with io.FileIO(BIN_PATH, 'r') as f:
            data2 = f.readall()

        s = difflib.SequenceMatcher(None, data1, data2)

        ref = ((0, 0, 684), (684, 684, 0))
        matching = list(s.get_matching_blocks())

        self.assertEqual(len(ref), len(matching))

        for i in range(len(matching)):
            self.assertEqual(ref[i], matching[i])
