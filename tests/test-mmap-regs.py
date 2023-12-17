#!/usr/bin/python3

import os
import unittest
import rwmem as rw

class MmapTests(unittest.TestCase):
    def setUp(self):
        path = os.path.dirname(os.path.abspath(__file__)) + '/test.regs'
        self.rf = rw.RegisterFile(path)

        path = os.path.dirname(os.path.abspath(__file__)) + '/test.bin'
        self.map = rw.MappedRegisterBlock(path, self.rf["BLOCK1"])

    def __check(self):
        b1 = self.map

        self.assertTrue("REG1" in b1)
        self.assertTrue("REG11" in b1.reg1)

        self.assertEqual(b1["REG1"].value, 0xf00dbaad)
        self.assertEqual(b1.reg1.value, 0xf00dbaad)

        self.assertEqual(b1.reg1[0:7], 0xad)
        self.assertEqual(b1.reg1[31:16], 0xf00d)

        self.assertEqual(b1["REG1"]["REG11"], 0xf00d)
        self.assertEqual(b1["REG1"]["REG12"], 0xbaad)

        self.assertEqual(b1.reg1.reg11, 0xf00d)
        self.assertEqual(b1.reg1.reg12, 0xbaad)

        self.assertEqual(b1.reg2.reg21, 0xab)
        self.assertEqual(b1.reg2.reg22, 0xba)
        self.assertEqual(b1.reg2.reg23, 0xaa)
        self.assertEqual(b1.reg2.reg24, 0xbb)

        self.assertEqual(b1.reg3.reg31, 0x56)
        self.assertEqual(b1.reg3.reg32, 0x78)

    def test(self):
        self.__check()

        b1 = self.map

        b1.reg1[0:7] = 0xad
        b1.reg1[31:16] = 0xf00d

        b1.reg2.reg21 = 0xab
        b1.reg2 = b1.reg2.fields
        b1.reg3 = { "reg31": 0x56, "reg32": 0x78 }

        self.__check()


if __name__ == '__main__':
    unittest.main()
