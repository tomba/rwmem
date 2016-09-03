#!/usr/bin/python3

import pyrwmem

#mem = pyrwmem.mem("omap5")
#dss = mem["dss"]
#reg = dss["revision"]


#mem = pyrwmem.MemMap("LICENSE", 0x80, 0x1000, True)
#v = mem.read32(0x10)
#print(format(v, "#0x"))

rf = pyrwmem.RegisterFile("/home/tomba/work-lappy/rwmem-db/k2g.bin")
print("RF {} blocks:{} regs:{} fields:{}".format(rf.name, rf.num_blocks, rf.num_regs, rf.num_fields))

rb = rf.block(0)
print("RB {} offset:{:#x} size:{} regs:{}".format(rb.name, rb.offset, rb.size, rb.num_regs))

r = rb.reg(0)
print("R {} offset:{:#x} size:{} regs:{}".format(r.name, r.offset, r.size, r.num_fields))

f = r.field(0)
print("F {} low:{} high:{}".format(f.name, f.low, f.high))
