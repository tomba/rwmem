#!/usr/bin/python3

import rwmem as rw

# Read EDID one byte at a time from the monitor at i2c-adapter 12

i2c_adapter = 12
i2c_addr = 0x50
i2c_addr_len = 1
i2c_data_len = 1

target = rw.I2CTarget(i2c_adapter, i2c_addr, 0, 0x100, rw.Endianness.Big, i2c_addr_len, rw.Endianness.Big, i2c_data_len)

for i in range(256):
    v = target.read(i, 1)
    print("{:3} = {:02x} {}".format(i, v, chr(v)))
