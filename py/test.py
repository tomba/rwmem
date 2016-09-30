#!/usr/bin/python3

import pyrwmem

map = pyrwmem.MappedRegisterBlock("LICENSE", 0, "/home/tomba/work-lappy/rwmem-db/omap5.regs", "DISPC")

v = map.read("REVISION")
print("Tuli {:x}".format(v))

rv = map.read_value("REVISION")
v = rv.field_value("REV")
print("Tuli {:x}".format(v))

r = map.find_register("REVISION")
v = r.read()
print("Tuli {:x}".format(v))

rv = r.read_value()
v = rv.field_value("REV")
print("Tuli {:x}".format(v))
