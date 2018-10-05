#!/usr/bin/python3

import sys
sys.path.append("../../scripts")

from struct import *
from regfile_writer import regfile_write, Endianness

regs = [
	[ "REG1", 0x00, [
		[ "REG11", 31, 16 ],
		[ "REG12", 15, 0 ],
		]],
	[ "REG2", 0x04, [
		[ "REG21", 31, 24 ],
		[ "REG22", 23, 16 ],
		[ "REG23", 15, 8 ],
		[ "REG24", 7, 0 ],
		]],
	[ "REG3", 0x08, [
		[ "REG31", 24, 16 ],
		[ "REG32", 7, 0 ],
		]],
]

def conv(src):
	dst = []

	for r in src:
		reg = { "name": r[0], "offset": r[1], "fields": [] }

		if len(r) == 3:
			for f in r[2]:
				if len(f) == 2:
					reg["fields"].append({ "name": f[0], "high": f[1], "low": f[1] })
				else:
					reg["fields"].append({ "name": f[0], "high": f[1], "low": f[2] })
		dst.append(reg)

	return dst

regs = conv(regs)

blocks = []

blocks.append({ "name": "BLOCK1", "offset": 0x8, "size": 0x10, "regs": regs,
                "addr_endianness": Endianness.DEFAULT, "addr_size": 4,
                "data_endianness": Endianness.BIG, "data_size": 4})

regfile_write("test.regs", "TEST", blocks)


fmt = ">IIIIIIII"

with open('test.bin', "wb") as f:
	f.write(pack(fmt,
	             0x00112233, 0x44556677, 0xf00dbaad, 0xabbaaabb,
	             0x00560078, 0x00112233, 0x44556677, 0xdeadbeef))
