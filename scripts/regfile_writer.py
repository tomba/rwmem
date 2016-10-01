#!/usr/bin/python3

from struct import *
import os

RWMEM_MAGIC = 0x00e11554
RWMEM_VERSION = 1

ENDIAN_DEFAULT = 0
ENDIAN_BIG = 1
ENDIAN_LITTLE = 2
ENDIAN_BIGSWAPPED = 3
ENDIAN_LITTLESWAPPED = 4

def regfile_write(file, name, blocks, address_endianness = 0, data_endianness = 0):

	fmt_regfile = ">IIIIIIII"
	fmt_block = ">IQQII"
	fmt_reg = ">IQIII"
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
			block["size"] = reg["offset"] + reg["size"]

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

	out.write(pack(fmt_regfile, RWMEM_MAGIC, RWMEM_VERSION, get_str_idx(name), num_blocks, num_regs, num_fields, address_endianness, data_endianness))

	for block in blocks:
		out.write(pack(fmt_block, get_str_idx(block["name"]), block["offset"], block["size"], len(block["regs"]), block["regs_offset"]))

	for block in blocks:
		for reg in block["regs"]:
			out.write(pack(fmt_reg, get_str_idx(reg["name"]), reg["offset"], reg["size"], len(reg["fields"]), reg["fields_offset"]))

	for block in blocks:
		for reg in block["regs"]:
			for field in reg["fields"]:
				out.write(pack(fmt_field, get_str_idx(field["name"]), field["high"], field["low"]))

	for str, idx in sorted(strs.items(), key=lambda x: x[1]):
		out.write(bytes(str, "ascii"))
		out.write(b"\0")

	out.close()
