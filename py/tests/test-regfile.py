#!/usr/bin/python3

import pyrwmem as rw

rf = rw.RegisterFile("py/tests/test.regs")

assert(rf["BLOCK1"])
assert(rf["BLOCK1"]["REG1"])
assert(rf["BLOCK1"]["REG1"]["REG11"])

# test __getitem__ with int
assert(rf[0][0][0].name == "REG11")

# test __getitem__ with string
assert(rf["BLOCK1"]["REG1"]["REG11"].name == "REG11")

# test __getitem__ with slice
assert(rf["BLOCK1"]["REG1"][0:15].name == "REG12")

assert("BLOCK1" in rf)
assert("REG1" in rf["BLOCK1"])
assert("REG11" in rf["BLOCK1"]["REG1"])
