#!/usr/bin/python3

import pyrwmem as rw

rf = rw.RegisterFile("py/tests/test.regs")
print("{}: blocks {}, regs {}, fields {}".format(rf.name, rf.num_blocks, rf.num_regs, rf.num_fields))

for rb in rf:
	print("{} {:#x} {:#x}".format(rb.name, rb.offset, rb.size))
	for r in rb:
		print("  {} {:#x} {:#x}".format(r.name, r.offset, r.size))
		for f in r:
			print("    {} {}:{}".format(f.name, f.low, f.high))
