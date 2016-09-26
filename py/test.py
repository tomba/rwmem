#!/usr/bin/python3

import pyrwmem

map = pyrwmem.MappedRegisterBlock("LICENSE", 0, "/home/tomba/work-lappy/rwmem-db/k2g.regs", "DSS")
v = map.read32("REVISION")
print("Tuli {:x}".format(v))

r = map.find_register("REVISION")
v = r.read32()

print("Tuli {:x}".format(v))

rv = r.read32value()
v = rv.field_value("REV")

print("Tuli {:x}".format(v))
