#!/usr/bin/python3

import pyrwmem as rw
import argparse

parser = argparse.ArgumentParser()
parser.add_argument("regfile")
parser.add_argument("--no-regs", action="store_true")
parser.add_argument("--no-fields", action="store_true")
args = parser.parse_args()

rf = rw.RegisterFile(args.regfile)
print("{}: blocks {}, regs {}, fields {}".format(rf.name, rf.num_blocks, rf.num_regs, rf.num_fields))

for rb in rf:
	print("{} {:#x} {:#x}".format(rb.name, rb.offset, rb.size))
	if not args.no_regs:
		for r in rb:
			print("  {} {:#x}".format(r.name, r.offset))
			if not args.no_fields:
				for f in r:
					print("    {} {}:{}".format(f.name, f.low, f.high))
