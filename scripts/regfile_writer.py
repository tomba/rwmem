#!/usr/bin/python3

from struct import *
from enum import IntEnum
import os

RWMEM_MAGIC = 0x00e11554
RWMEM_VERSION = 2

class Endianness(IntEnum):
	DEFAULT = 0
	BIG = 1
	LITTLE = 2
	BIGSWAPPED = 3
	LITTLESWAPPED = 4

def regfile_write(file, name, blocks):

	fmt_regfile = ">IIIIII"
	fmt_block = ">IQQIIBBBB"
	fmt_reg = ">IQII"
	fmt_field = ">IBB"

	blocks = sorted(blocks, key=lambda x: x["offset"])

	num_blocks = len(blocks)
	num_regs = 0
	num_fields = 0

	# Remove common prefix
	for block in blocks:
		names = []
		for reg in block["regs"]:
			names += [ reg["name"] ]

		prefix = os.path.commonprefix(names)

		if prefix != "" and prefix.endswith("_"):
			for reg in block["regs"]:
				reg["name"] = reg["name"][len(prefix):]

	for block in blocks:
		block["regs"] = sorted(block["regs"], key=lambda x: x["offset"])
		block["regs_offset"] = num_regs

		if block["size"] == 0:
			reg = max(block["regs"], key=lambda x: x["offset"])
			block["size"] = reg["offset"] + block.get("data_size", 4)

		num_regs += len(block["regs"])

	for block in blocks:
		for reg in block["regs"]:
			reg["fields"] = sorted(reg["fields"], key=lambda x: x["high"], reverse=True)
			reg["fields_offset"] = num_fields
			num_fields += len(reg["fields"])

	strs = { "": 0 }
	str_idx = 1

	def get_str_idx(str):
		nonlocal str_idx
		nonlocal strs

		if str not in strs:
			strs[str] = str_idx
			str_idx += len(str) + 1

		return strs[str]

	out = open(file, "wb")

	out.write(pack(fmt_regfile, RWMEM_MAGIC, RWMEM_VERSION, get_str_idx(name), num_blocks, num_regs, num_fields))

	for block in blocks:
		addr_e = block.get("addr_endianness", Endianness.DEFAULT)
		addr_s = block.get("addr_size", 4)
		data_e = block.get("data_endianness", Endianness.DEFAULT)
		data_s = block.get("data_size", 4)

		out.write(pack(fmt_block, get_str_idx(block["name"]), block["offset"], block["size"], len(block["regs"]), block["regs_offset"],
		               addr_e, addr_s, data_e, data_s))

#  reg["size"],
	for block in blocks:
		for reg in block["regs"]:
			out.write(pack(fmt_reg, get_str_idx(reg["name"]), reg["offset"], len(reg["fields"]), reg["fields_offset"]))

	for block in blocks:
		for reg in block["regs"]:
			for field in reg["fields"]:
				out.write(pack(fmt_field, get_str_idx(field["name"]), field["high"], field["low"]))

	for str, idx in sorted(strs.items(), key=lambda x: x[1]):
		out.write(bytes(str, "ascii"))
		out.write(b"\0")

	out.close()
