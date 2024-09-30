#!/usr/bin/python3

import os
import unittest
import rwmem as rw

REGS_PATH = os.path.dirname(os.path.abspath(__file__)) + '/test.regs'

#class ContextManagerTests(unittest.TestCase):
#    def test(self):
#        with rw.RegisterFile(REGS_PATH) as rf:
#            pass

class MmapRegsTests(unittest.TestCase):
    def setUp(self):
        self.rf = rw.RegisterFile(REGS_PATH)

    def tests(self):
        rf = self.rf

        self.assertTrue('BLOCK1' in rf)
        self.assertTrue('REG1' in rf['BLOCK1'])
        self.assertTrue('REG11' in rf['BLOCK1']['REG1'])
