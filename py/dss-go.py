#!/usr/bin/python3

import pyrwmem

map = pyrwmem.MappedRegisterBlock("LICENSE", 0, "/home/tomba/work-lappy/rwmem-db/omap5.regs", "DISPC")

rv = map.read_value("CONTROL1")

if rv.field_value("LCDENABLE"):
	rv.set_field_value("GOLCD", 1)

if rv.field_value("TVENABLE"):
	rv.set_field_value("GOTV", 1)

rv.write()


rv = map.read_value("CONTROL2")
if rv.field_value("LCDENABLE"):
	rv.set_field_value("GOLCD", 1)
rv.write()

rv = map.read_value("CONTROL3")
if rv.field_value("LCDENABLE"):
	rv.set_field_value("GOLCD", 1)
rv.write()
