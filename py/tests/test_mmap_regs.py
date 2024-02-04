#!/usr/bin/python3

import os
import shutil
import stat
import tempfile
import unittest
import rwmem as rw

REGS_PATH = os.path.dirname(os.path.abspath(__file__)) + '/test.regs'
BIN_PATH = os.path.dirname(os.path.abspath(__file__)) + '/test.bin'

class MmapRegsTests(unittest.TestCase):
    def setUp(self):
        self.rf = rw.RegisterFile(REGS_PATH)
        self.map = rw.MappedRegisterBlock(BIN_PATH, self.rf["BLOCK1"], mode=rw.MapMode.Read)

    def tests(self):
        m = self.map

        self.assertTrue("REG1" in m)
        self.assertTrue("REG11" in m.reg1)

        self.assertEqual(m["REG1"].value, 0xf00dbaad)
        self.assertEqual(m.reg1.value, 0xf00dbaad)

        self.assertEqual(m.reg1[0:7], 0xad)
        self.assertEqual(m.reg1[31:16], 0xf00d)

        self.assertEqual(m["REG1"]["REG11"], 0xf00d)
        self.assertEqual(m["REG1"]["REG12"], 0xbaad)

        self.assertEqual(m.reg1.reg11, 0xf00d)
        self.assertEqual(m.reg1.reg12, 0xbaad)

        self.assertEqual(m.reg2.value, 0xabbaaabb)
        self.assertEqual(m.reg2.reg21, 0xab)
        self.assertEqual(m.reg2.reg22, 0xba)
        self.assertEqual(m.reg2.reg23, 0xaa)
        self.assertEqual(m.reg2.reg24, 0xbb)

        self.assertEqual(m.reg3.value, 0x00560078)
        self.assertEqual(m.reg3.reg31, 0x56)
        self.assertEqual(m.reg3.reg32, 0x78)


class WriteMmapRegsTests(unittest.TestCase):
    def setUp(self):
        self.rf = rw.RegisterFile(REGS_PATH)

        self.tmpfile = tempfile.NamedTemporaryFile(mode='w+b', suffix='.bin', delete=True)
        self.tmpfile_path = self.tmpfile.name

        shutil.copy2(BIN_PATH, self.tmpfile_path)
        os.chmod(self.tmpfile_path, stat.S_IREAD | stat.S_IWRITE)

        self.map = rw.MappedRegisterBlock(self.tmpfile_path, self.rf["BLOCK1"], mode=rw.MapMode.ReadWrite)

    def tests(self):
        m = self.map

        self.assertEqual(m["reg1"].value, 0xf00dbaad)

        m["reg1"] = 0x12345678
        m["reg1"][0:7] = 0xda
        m["reg1"][15:8] = 0x01
        m["reg1"]["reg11"] = 0xbade;

        self.assertEqual(m["reg1"].value, 0xbade01da)
        self.assertEqual(m._map.read(8, 4), 0xbade01da)

        m = self.map

        m["reg1"] = 0xf00dbaad
        self.assertEqual(m["reg1"].value, 0xf00dbaad)

        m.reg1 = 0x12345678
        m.reg1[0:7] = 0xda
        m.reg1[15:8] = 0x01
        m.reg1.reg11 = 0xbade;

        self.assertEqual(m.reg1.value, 0xbade01da)
        self.assertEqual(m._map.read(8, 4), 0xbade01da)


        m.reg3 = { "reg31": 0x56, "reg32": 0x78 }
        self.assertEqual(m.reg3.value, 0x00560078)
        self.assertEqual(m._map.read(16, 4), 0x00560078)

        m.sync()

        import difflib
        with (open(BIN_PATH, 'rb') as f1,
              open(self.tmpfile_path, 'rb') as f2):
            x = f1.read()
            y = f2.read()

            s = difflib.SequenceMatcher(None, x, y)
            ref = ((0, 0, 8), (10, 8, 1), (12, 12, 20), (32, 32, 0))
            matching = list(s.get_matching_blocks())

            self.assertEqual(len(ref), len(matching))

            for i in range(len(matching)):
                #print(matching[i])
                self.assertEqual(ref[i], matching[i])
