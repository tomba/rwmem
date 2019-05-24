#!/usr/bin/python3

from regfile_writer import Endianness
import xml.etree.ElementTree as ET


REGSIZE = 4

ns = {'spirit': 'http://www.spiritconsortium.org/XMLSchema/SPIRIT/1685-2009',
      'socns': 'http://www.duolog.com/2011/05/socrates'}

def parse_fields(regElem):
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

	return fields

def parse_regs(abElem, abOffset, prefix=""):
	regs = []

	for regElem in abElem.findall('spirit:register', ns):
		regDim = int(regElem.findtext("spirit:dim", "1", ns))

		for idx in range(0, regDim):
			regname = prefix + regElem.find('spirit:name', ns).text
			if regDim > 1:
				regname += "_" + str(idx)

			regoffset = int(regElem.find('spirit:addressOffset', ns).text, 0) + abOffset + idx * REGSIZE

			fields = parse_fields(regElem)

			reg = { "name": regname, "offset": regoffset, "fields": fields }

			regs.append(reg)

	return regs

def ipxact_parse(file):
	tree = ET.parse(file)

	root = tree.getroot()

	if len(root.findall('.//spirit:addressBlock/spirit:dim', ns)) > 0:
		print("addressBlock dim not supported")
		exit(1)

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
			e = abElem.find('spirit:dim', ns)
			assert(e == None)

			regs += parse_regs(abElem, abOffset)

			for rfElem in abElem.findall('.//spirit:registerFile', ns):
				rfOffset = int(rfElem.findtext('spirit:addressOffset', "0", ns), 0)
				rfDim = int(rfElem.findtext("spirit:dim", "1", ns))
				rfRange = int(rfElem.findtext("spirit:range", str(REGSIZE), ns))

				for idx in range(0, rfDim):
					rfName = rfElem.find('spirit:name', ns).text
					if rfDim > 1:
						rfName += str(idx)

					rfOffset = int(rfElem.find('spirit:addressOffset', ns).text, 0) + idx * rfRange

					regs += parse_regs(rfElem, rfOffset, rfName + "_")

		mmaps.append({ "name": memMapName, "offset": 0, "size": 0, "regs": regs,
		             "addr_endianness": Endianness.DEFAULT, "addr_size": 4,
		             "data_endianness": Endianness.DEFAULT, "data_size": 4})

	return mmaps
