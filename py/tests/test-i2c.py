#!/usr/bin/python3

import pyrwmem as rw

i2c_adapter = 4
i2c_addr = 0x50
i2c_addr_len = 1

map = rw.I2CTarget(i2c_adapter, i2c_addr, i2c_addr_len, rw.Endianness.Big, rw.Endianness.Big)

for i in range(10):
	print("{:x}".format(map.read(i, 1)))
