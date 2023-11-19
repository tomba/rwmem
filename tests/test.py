#!/usr/bin/python3

import unittest
import subprocess
import os


class RwmemTests(unittest.TestCase):

    def setUp(self):
        if 'RWMEM_CMD' in os.environ:
            self.rwmem_cmd =  os.environ['RWMEM_CMD']
        else:
            self.rwmem_cmd = '../build/rwmem/rwmem'

        self.rwmem_common_opts = []

    def assertOutput(self, rwmemopts, expected):
        opts = self.rwmem_common_opts + rwmemopts

        res = subprocess.run([self.rwmem_cmd, *opts],
                             capture_output=True,
                             encoding='ASCII')

        self.assertEqual(res.returncode, 0, res)
        self.assertEqual(res.stdout, expected, res)

        return

    def test_numeric_reads(self):
        self.rwmem_common_opts = ['--mmap=data.bin']

        self.assertOutput(['0'],
                          '0x00 = 0x0f7216c2\n')

        self.assertOutput(['-s8', '0'],
                          '0x00 = 0xc2\n')

        self.assertOutput(['-s16', '0'],
                          '0x00 = 0x16c2\n')

        self.assertOutput(['-s16', '0'],
                          '0x00 = 0x16c2\n')

        self.assertOutput(['-s32', '0'],
                          '0x00 = 0x0f7216c2\n')


if __name__ == '__main__':
    unittest.main()
