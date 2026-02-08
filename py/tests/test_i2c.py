#!/usr/bin/env python3

import os
import unittest

import rwmem as rw
from rwmem.enums import Endianness

DRM_PATH = '/sys/devices/pci0000:00/0000:00:02.0/drm/card1/card1-DP-2'


class I2CTests(unittest.TestCase):
    def setUp(self):
        if os.geteuid() != 0:
            self.skipTest('Not root')

        self.map = rw.I2CTarget(
            12,
            0x50,
            0,
            256,
            addr_endianness=rw.Endianness.Big,
            addr_size=1,
            data_endianness=rw.Endianness.Big,
            data_size=1,
            mode=rw.MapMode.ReadWrite,
        )

        with open(DRM_PATH + '/status') as f:
            self.assertEqual(f.read(), 'connected\n')

        with open(DRM_PATH + '/edid', 'rb') as f:
            self.edid = f.read()

    def get_edid_u8(self, addr):
        return int.from_bytes(self.edid[addr : addr + 1], 'little')

    def get_edid_u16(self, addr):
        return int.from_bytes(self.edid[addr : addr + 2], 'little')

    def get_edid_u32(self, addr):
        return int.from_bytes(self.edid[addr : addr + 4], 'little')

    def tests(self):
        map = self.map

        for addr in range(256):
            self.assertEqual(map.read(addr), self.get_edid_u8(addr))

        for addr in range(0, 256, 4):
            v1 = map.read(addr, data_size=4, data_endianness=Endianness.Little)
            v2 = self.get_edid_u32(addr)
            self.assertEqual(v1, v2)


if __name__ == '__main__':
    unittest.main()
