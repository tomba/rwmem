#!/usr/bin/python3

import pyrwmem as rw

map = rw.MMapTarget("py/tests/test.bin")
map.map(0, 32, rw.Endianness.Default, 4, rw.Endianness.Big, 4, rw.MapMode.Read)

assert(map.read(0, 1) == 0x00)
assert(map.read(1, 1) == 0x11)
assert(map.read(2, 1) == 0x22)
assert(map.read(3, 1) == 0x33)

assert(map.read(0, 2) == 0x0011)
assert(map.read(2, 2) == 0x2233)

assert(map.read(0, 4) == 0x00112233)
assert(map.read(4, 4) == 0x44556677)

assert(map.read(8, 4) == 0xf00dbaad)
assert(map.read(12, 4) == 0xabbaaabb)
assert(map.read(16, 4) == 0x00560078)

assert(map.read(20, 4) == 0x00112233)
assert(map.read(24, 4) == 0x44556677)
assert(map.read(28, 4) == 0xdeadbeef)

assert(map.read(0, 8) == 0x0011223344556677)
assert(map.read(24, 8) == 0x44556677deadbeef)
