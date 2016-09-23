#!/usr/bin/python3

import xml.etree.ElementTree as ET

def ipxact_parse(file, given_name, given_address):
	tree = ET.parse(file)

	root = tree.getroot()

	ns = {'spirit': 'http://www.spiritconsortium.org/XMLSchema/SPIRIT/1685-2009',
	      'socns': 'http://www.duolog.com/2011/05/socrates'}

	if len(root.findall('.//spirit:memoryMap', ns)) != 1:
		print("Error: requires a single memorymap")
		exit(1)

	if len(root.findall('.//spirit:addressBlock/spirit:dim', ns)) > 0:
		print("addressBlock dim not supported")
		exit(1)

	REGSIZE = 4

	regs = []

	for abElem in root.findall('.//spirit:addressBlock', ns):
		abName = abElem.find('spirit:name', ns).text
		abOffset = int(abElem.find('spirit:baseAddress', ns).text)

		for regElem in abElem.findall('spirit:register', ns):
			e = regElem.find('spirit:dim', ns)
			regDim = int(e.text) if e != None else 1

			for idx in range(0, regDim):
				regname = regElem.find('spirit:name', ns).text
				if regDim > 1:
					regname += "_" + str(idx)

				regoffset = int(regElem.find('spirit:addressOffset', ns).text) + abOffset + idx * REGSIZE

				fields = []

				for fieldElem in regElem.findall('spirit:field', ns):
					fname = fieldElem.find('spirit:name', ns).text
					fshift = int(fieldElem.find('spirit:bitOffset', ns).text)
					fwidth = int(fieldElem.find('spirit:bitWidth', ns).text)
					freserved = False

					e1 = fieldElem.find('spirit:vendorExtensions', ns)
					if e1 != None:
						e2 = e1.find('socns:reserved', ns)
						if e2 != None:
							if e2.text.lower() == "true":
								fname = "Reserved"

					fields.append({ "name": fname, "high": fshift + fwidth - 1, "low": fshift })

				reg = { "name": regname, "offset": regoffset, "size": REGSIZE, "fields": fields }

				regs.append(reg)

	return { "name": given_name, "offset": given_address, "size": 0, "regs": regs }

