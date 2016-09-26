# rwmem - A small tool to read & write device registers

Copyright 2013-2016 Tomi Valkeinen

## Intro

rwmem is a small tool for reading and writing device registers. rwmem supports
two modes: mmap mode and i2c mode.

In mmap mode rwmem accesses a file by memory mapping it. Using /dev/mem as the
memory mapped file makes rwmem access memory and can thus be used to access
devices which have memory mapped registers.

In i2c mode rwmem accesses an i2c peripheral by sending i2c messages to it.

rwmem features:

* addressing with 8/16/32/64 bit addresses
* accessing 8/16/32/64 bit memory locations
* little and big endian addressess and accesses
* bitfields
* address ranges
* register description database

## Examples without register file

Show what's in memory location 0x58001000

        $ rwmem 0x58001000

Show what's in memory locations between 0x58001000 to 0x58001040

        $ rwmem 0x58001000-0x58001040

Show what's in memory locations between 0x58001000 to 0x58001040

        $ rwmem 0x58001000+0x40

Show what's in memory location 0x58001000's bit 7 (i.e. 8th bit)

        $ rwmem 0x58001000:7

Show what's in memory location 0x58001000's bits 7-4 (i.e. bits 4, 5, 6, 7)

        $ rwmem 0x58001000:7:4

Write 0x12345678 to memory location 0x58001000

        $ rwmem 0x58001000=0x12345678

Modify memory location 0x58001000's bits 7-4 to 0xf

        $ rwmem 0x58001000:7:4=0xf

Show the byte at location 0x10 in file edid.bin

        $ rwmem --mmap edid.bin -s 8 0x10

Set /dev/fb0 to red

        $ rwmem -p q --mmap /dev/fb0 0x0..$((800*4*480))=0xff0000

Read a byte from i2c device 0x50 on bus 4, address 0x20

        $ rwmem -s 8 --i2c=4:0x50 0x20

Read a 32 bit big endian register with swapped 16-bit words from i2c device 0x50 on bus 4, address 0x800

        $ rwmem -s 32bes -S 16 --i2c=4:0x50 0x800

## Examples with register file

Show the whole DISPC address space

        $ rwmem DISPC

Show the known registers in DISPC address space

        $ rwmem DISPC.*

Show SYSCONFIG register in DISPC

        $ rwmem DISPC.SYSCONFIG

Modify MIDLEMODE field in DISPC's SYSCONFIG register to 0x1

        $ rwmem DISPC.SYSCONFIG:MIDLEMODE=0x1

List all registers in the register file

        $ rwmem --list

List registers in DISPC

        $ rwmem --list DISPC

List registers in DISPC

        $ rwmem --list DISPC.*

List fields in DISPC SYSCONFIG

        $ rwmem --list DISPC.SYSCONFIG:*

Read binary dump of DISPC to dispc.bin file

        $ rwmem --raw DISPC > dispc.bin

Show SYSCONFIG register, as defined in dispc.regs, in file dispc.bin

        $ rwmem --mmap dispc.bin --regs dispc.regs --ignore-base DISPC.SYSCONFIG

## Write mode

The write mode parameter affects how rwmem handles writing.

Write mode 'w' means write-only. In this mode rwmem never reads from the
address. This means that if you modify only certain bits with the bitfield
operator, the rest of the bits will be set to 0.

Write mode 'rw' means read-write. In this mode rwmem reads from the address,
modifies the value, and writes it back.

Write mode 'rwr' means read-write-read. This is the same as 'rw' except rwmem
reads from the address again after writing for the purpose of showing the new
value. This is the default mode.

## Print mode

The print mode parameter affects what rwmem will output.

'q'  - quiet
'r'  - print only register value, not individual fields
'rf' - print register and fields (when available).

## Raw output mode

In raw output mode rwmem will copy the values it reads to stdout without any
formatting. This can be used to get binary dumps of memory areas.

## Register description file

A register description file is a binary register database. See the code and
the included python scripts to see the details of the format.

It is easy to generate register description files using the regfile_writer.py
python script.

## rwmem.cfg file format

TODO
