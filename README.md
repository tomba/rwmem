[![Build Status](https://github.com/tomba/rwmem/actions/workflows/c-cpp.yml/badge.svg)](https://github.com/tomba/rwmem/actions/workflows/c-cpp.yml)
[![Build Status](https://github.com/tomba/rwmem/actions/workflows/py-ci.yml/badge.svg)](https://github.com/tomba/rwmem/actions/workflows/py-ci.yml)

# rwmem - A small tool to read & write device registers

Copyright 2013-2025 Tomi Valkeinen

## Intro

**_WARNING: rwmem can break your hardware, use only if you know what you are doing._**

rwmem is a small tool for reading and writing device registers. rwmem supports
memory-mapped access and I2C device communication.

In mmap mode rwmem accesses a file by memory mapping it. Using /dev/mem as the
memory mapped file makes rwmem access memory and can thus be used to access
devices which have memory mapped registers.

In i2c mode rwmem accesses an i2c peripheral by sending i2c messages to it.

rwmem features:

* addressing with 8/16/32/64 bit addresses
* accessing 8/16/24/32/40/48/56/64 bit memory locations
* little and big endian addressess and accesses
* bitfields
* address ranges
* register description database

For detailed command line usage, see [docs/cmdline.md](docs/cmdline.md).

## Build Dependencies

- meson
- ninja
- inih (optional)

## Build Instructions

```
git clone https://github.com/tomba/rwmem.git
cd rwmem
meson build
ninja -C build
```

## Cross Compiling Instructions:

**Directions for cross compiling depend on your environment.**

```
meson build --cross-file=<path-to-meson-cross-file>
ninja -C build
```

Here is my cross file for arm32 (where ${BROOT} is path to my buildroot output dir):

```
[binaries]
c = ['ccache', '${BROOT}/host/bin/arm-buildroot-linux-gnueabihf-gcc']
cpp = ['ccache', '${BROOT}/host/bin/arm-buildroot-linux-gnueabihf-g++']
ar = '${BROOT}/host/bin/arm-buildroot-linux-gnueabihf-ar'
strip = '${BROOT}/host/bin/arm-buildroot-linux-gnueabihf-strip'
pkgconfig = '${BROOT}/host/bin/pkg-config'

[host_machine]
system = 'linux'
cpu_family = 'arm'
cpu = 'arm'
endian = 'little'
```

### Build a static rwmem

You can build a static rwmem executable e.g. with:

```
meson setup -Dinih=disabled -Dtests=false -Dbuildtype=minsize -Db_lto=true -Ddefault_library=static -Dprefer_static=true -Dc_link_args="-s -static" -Dcpp_link_args="-s -static" build
ninja -C build
```

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

        $ rwmem mmap edid.bin -d 8 0x10

Set /dev/fb0 to red

        $ rwmem mmap /dev/fb0 -p q 0x0..$((800*4*480))=0xff0000

Read a byte from i2c device 0x50 on bus 4, address 0x20

        $ rwmem i2c 4:0x50 -d 8 0x20

Read a 32 bit big endian value from 16 bit big endian address 0x800 from i2c device 0x50 on bus 4

        $ rwmem i2c 4:0x50 -a 16be -d 32be 0x800

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

        $ rwmem list

List registers in DISPC

        $ rwmem list DISPC

List registers in DISPC

        $ rwmem list DISPC.*

List registers in DISPC starting with VID

        $ rwmem list DISPC.VID*

List fields in DISPC SYSCONFIG

        $ rwmem list DISPC.SYSCONFIG:*

Read binary dump of DISPC to dispc.bin file

        $ rwmem -R DISPC > dispc.bin

Show SYSCONFIG register, as defined in dispc.regs, in file dispc.bin

        $ rwmem mmap dispc.bin -r dispc.regs --ignore-base DISPC.SYSCONFIG

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

## Size and Endianness

You can set the size and endianness for data and for address with -d and -a
options. The size and endianness for address is used only for i2c. The size is
in number of bits, and endianness is "be", "le", "bes" or "les".

In addition to the normal big (be) and little endian (le), rwmem supports
"swapped" modification for endianness (bes and les). In swapped endianness, 16
bit words of a 32 bit value are swapped, and similarly 32 bit words of a 64
bit value are swapped.

## Register description file

A register description file is a binary register database. See
[docs/regdb-v3.md](docs/regdb-v3.md) for the low-level binary format details.

Register description files can be generated using the pyrwmem library. See
[py/docs/regdb-generation.md](py/docs/regdb-generation.md) for a generation guide.

## Bash completion

examples/bash_completion/rwmem is an example bash completion script for rwmem.

## rwmem.ini file format

rwmem will look for configuration options from `~/.rwmem/rwmem.ini` file.
`examples/rwmem.ini` has an example rwmem.ini file.

`main.detect` entry can be set to point to a script which should echo the name
of the platform rwmem is running on. The name of the platform is then used to
look for "platform" entries in the rwmem.ini, which can be used to define
platform specific rwmem configuration (mainline regfile for the time being).
