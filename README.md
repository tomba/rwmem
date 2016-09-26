# rwmem - A small tool to read/write memory

Copyright 2013-2016 Tomi Valkeinen

## Intro

rwmem is a small tool to read and write arbitrary locations in a file.
Normally, this file is /dev/mem, so the tool reads/writes memory, but the file
can be any file that can be memory mapped (e.g. a normal file, /dev/fb0, etc.).

rwmem supports accessing 32/64 bit addresses, and accessing 8/16/32/64 bit
memory locations.

rwmem also supports bitfields (i.e. accessing only a subset of the memory
location), and operations on address ranges.

rwmem has support for using symbolic names for addresses and bitfields.

## Usage

usage: rwmem [options] <address>[:field][=value]

	address		address to access:
			<address>	single address
			<start-end>	range with end address
			<start+len>	range with length

	field		bitfield (inclusive, start from 0):
			<bit>		single bit
			<high>:<low>	bitfield from high to low

	value		value to be written

	-h		show this help
	-s <size>	size of the memory access: 8/16/32/64 (default: 32)
	-w <mode>	write mode: w, rw or rwr (default)
	-p <mode>	print mode: q, r or rf (default)
	-b <address>	base address
	-R		raw output mode
	--file <file>	file to open (default: /dev/mem)
	--conf <file>	config file (default: ~/.rwmem/rwmemrc)
	--regs <file>	register set file

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

        $ rwmem --raw DISPC 0x0..0x1000 > dispc.bin

Show SYSCONFIG register, as defined in dispc.regs, in file dispc.bin

        $ rwmem --file dispc.bin --regs dispc.regs --ignore-base DISPC.SYSCONFIG


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

## Register set files

TODO

## Register set file format

TODO

## rwmem.cfg file format

TODO
