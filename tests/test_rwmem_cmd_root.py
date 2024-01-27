#!/usr/bin/python3

import os
import subprocess
import unittest

RWMEM_CMD_PATH = os.path.dirname(os.path.abspath(__file__)) + '/../build/rwmem/rwmem'

DRM_PATH = '/sys/devices/pci0000:00/0000:00:02.0/drm/card0/card0-DP-2'

class RwmemTestI2C(unittest.TestCase):
    def setUp(self):
        if os.geteuid() != 0:
            self.skipTest('Not root')

        if 'RWMEM_CMD' in os.environ:
            self.rwmem_cmd =  os.environ['RWMEM_CMD']
        else:
            self.rwmem_cmd = RWMEM_CMD_PATH

        self.rwmem_common_opts = ['--i2c=12:0x50']

        with open(DRM_PATH + '/status') as f:
            self.assertEqual(f.read(), 'connected\n')

        with open(DRM_PATH + '/edid', 'rb') as f:
            self.edid = f.read()

    def assertOutput(self, rwmemopts, expected):
        opts = self.rwmem_common_opts + rwmemopts

        res = subprocess.run([self.rwmem_cmd, *opts],
                             capture_output=True,
                             encoding='ASCII')

        self.assertEqual(res.returncode, 0, res)
        self.assertEqual(res.stdout, expected, res)

    def get_edid_u8(self, addr):
        return '0x{:02x}'.format(int.from_bytes(self.edid[addr:addr+1], 'little', signed=False))

    def get_edid_u16(self, addr):
        return '0x{:04x}'.format(int.from_bytes(self.edid[addr:addr+2], 'little', signed=False))

    def get_edid_u32(self, addr):
        return '0x{:08x}'.format(int.from_bytes(self.edid[addr:addr+4], 'little', signed=False))

    def test_i2c(self):
        self.assertOutput(['0'],
                          f'0x00 = {self.get_edid_u32(0)}\n')

        self.assertOutput(['4'],
                          f'0x04 (+0x0) = {self.get_edid_u32(4)}\n')

        self.assertOutput(['-s8', '0x10'],
                          f'0x10 (+0x0) = {self.get_edid_u8(0x10)}\n')

        self.assertOutput(['-s16le', '0x10'],
                          f'0x10 (+0x0) = {self.get_edid_u16(0x10)}\n')

        self.assertOutput(['-s32le', '0x10'],
                          f'0x10 (+0x0) = {self.get_edid_u32(0x10)}\n')
