#!/usr/bin/python3

from regfile_writer import Endianness
import xml.etree.ElementTree as ET

def ipxact_parse(file):
	tree = ET.parse(file)

	root = tree.getroot()

	ns = {'spirit': 'http://www.spiritconsortium.org/XMLSchema/SPIRIT/1685-2009',
	      'socns': 'http://www.duolog.com/2011/05/socrates'}

	if len(root.findall('.//spirit:addressBlock/spirit:dim', ns)) > 0:
		print("addressBlock dim not supported")
		exit(1)

	REGSIZE = 4

	mmaps = []

	for memMap in root.findall('.//spirit:memoryMap', ns):
		memMapName = memMap.find('spirit:name', ns).text

		if len(memMap.findall('.//spirit:addressBlock', ns)) > 1:
			print("multiple addressBlocks not supported")
			exit(1)

		regs = []

		for abElem in memMap.findall('.//spirit:addressBlock', ns):
			abName = abElem.find('spirit:name', ns).text
			abOffset = int(abElem.find('spirit:baseAddress', ns).text, 0)
			abOffset = 0

			for regElem in abElem.findall('spirit:register', ns):
				e = regElem.find('spirit:dim', ns)
				regDim = int(e.text) if e != None else 1

				for idx in range(0, regDim):
					regname = regElem.find('spirit:name', ns).text
					if regDim > 1:
						regname += "_" + str(idx)

					regoffset = int(regElem.find('spirit:addressOffset', ns).text, 0) + abOffset + idx * REGSIZE

					fields = []

					for fieldElem in regElem.findall('spirit:field', ns):
						fname = fieldElem.find('spirit:name', ns).text
						fshift = int(fieldElem.find('spirit:bitOffset', ns).text, 0)
						fwidth = int(fieldElem.find('spirit:bitWidth', ns).text, 0)
						freserved = False

						e1 = fieldElem.find('spirit:vendorExtensions', ns)
						if e1 != None:
							e2 = e1.find('socns:reserved', ns)
							if e2 != None:
								if e2.text.lower() == "true":
									fname = "Reserved"

						fields.append({ "name": fname, "high": fshift + fwidth - 1, "low": fshift })

					reg = { "name": regname, "offset": regoffset, "fields": fields }

					regs.append(reg)

		mmaps.append({ "name": memMapName, "offset": 0, "size": 0, "regs": regs,
		             "addr_endianness": Endianness.DEFAULT, "addr_size": 4,
		             "data_endianness": Endianness.DEFAULT, "data_size": 4})

	return mmaps
