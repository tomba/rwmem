#!/usr/bin/python3

import pyrwmem as rw

rf = rw.RegisterFile("py/tests/test.regs")

b1 = rw.MappedRegisterBlock("py/tests/test.bin", rf["BLOCK1"])

def check():
	assert("REG1" in b1)
	assert("REG11" in b1.reg1)

	assert(b1["REG1"].value == 0xf00dbaad)
	assert(b1.reg1.value == 0xf00dbaad)

	assert(b1.reg1[0:7] == 0xad)
	assert(b1.reg1[31:16] == 0xf00d)

	assert(b1["REG1"]["REG11"] == 0xf00d)
	assert(b1["REG1"]["REG12"] == 0xbaad)

	assert(b1.reg1.reg11 == 0xf00d)
	assert(b1.reg1.reg12 == 0xbaad)

	assert(b1.reg2.reg21 == 0xab)
	assert(b1.reg2.reg22 == 0xba)
	assert(b1.reg2.reg23 == 0xaa)
	assert(b1.reg2.reg24 == 0xbb)

	assert(b1.reg3.reg31 == 0x56)
	assert(b1.reg3.reg32 == 0x78)

check()

b1.reg1[0:7] = 0xad
b1.reg1[31:16] = 0xf00d

b1.reg2.reg21 = 0xab
b1.reg2 = b1.reg2.fields
b1.reg3 = { "reg31": 0x56, "reg32": 0x78 }

check()
