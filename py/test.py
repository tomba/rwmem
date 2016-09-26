#!/usr/bin/python3

import pyrwmem

map = pyrwmem.MappedRegisterBlock("LICENSE", 0, "/home/tomba/work-lappy/rwmem-db/k2g.regs", "DSS")
map.read32("REVISION")

r = map.find_register("REVISION")
r.read32()

v = r.read32value()
v.field_value("REV")



map = pyrwmem.MappedRegisterBlock("LICENSE", 0x0, 0x1000)
map.read32(0x10)

r = map.get_register(0x10)
r.read32()


#map.modify32(0x10, [2, 1, 0x10], [4, 3, 0x20])
#map.modify32("DSS_CONFIG", ["KALA", 0x10], ["KISSA", 0x20])

#mem = pyrwmem.MemMap("LICENSE", 0x80, 0x1000, True)
#v = mem.read32(0x10)
#print(format(v, "#0x"))

rf = pyrwmem.RegisterFile("/home/tomba/work-lappy/rwmem-db/k2g.regs")
print("RF {} blocks:{} regs:{} fields:{}".format(rf.name, rf.num_blocks, rf.num_regs, rf.num_fields))

rb = rf[0]
rb = rf["DSS"]
print("RB {} offset:{:#x} size:{} regs:{}".format(rb.name, rb.offset, rb.size, rb.num_regs))

r = rb.reg(0)
print("R {} offset:{:#x} size:{} fields:{}".format(r.name, r.offset, r.size, r.num_fields))

f = r.field(0)
print("F {} low:{} high:{}".format(f.name, f.low, f.high))


r = rf.find_reg("DSS_REVISION")
print("R {} offset:{:#x} size:{} fields:{}".format(r.name, r.offset, r.size, r.num_fields))


# XXX i2c?
