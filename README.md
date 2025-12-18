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

## Command Line Reference

### Command Structure

rwmem supports three main modes of operation:

```bash
# Default mode (simplified mmap /dev/mem)
rwmem [OPTIONS] <address>[:field][=value] ...

# Explicit mmap mode
rwmem mmap <file> [OPTIONS] <address>[:field][=value] ...

# I2C mode
rwmem i2c <bus:addr> [OPTIONS] <address>[:field][=value] ...

# List mode
rwmem list [OPTIONS] [pattern] ...
```

### Address Syntax

All modes support the same address syntax:

- `0x1000` - Single address
- `0x1000-0x1040` - Address range (from start to end)
- `0x1000+0x40` - Address range (start + length)
- `0x1000:7` - Single bit access (bit 7)
- `0x1000:7:4` - Bitfield access (bits 7 down to 4)
- `0x1000:7:4=0xf` - Bitfield write (set bits 7-4 to 0xf)
- `DISPC.SYSCONFIG:MIDLEMODE=0x1` - Register database access

### Common Options

Most options are shared across default, mmap, and i2c modes:

- `-d, --data <size>[endian]` - Data size and endianness
- `-w, --write <mode>` - Write mode: w, rw, rwr (default)
- `-p, --print <mode>` - Print mode: q (quiet), r (register), rf (register+fields, default)
- `-f, --format <fmt>` - Number format: x (hex, default), b (binary), d (decimal)
- `-r, --regs <file>` - Register description file
- `-R, --raw` - Raw output mode
- `--ignore-base` - Ignore base from register file
- `-v, --verbose` - Verbose output

**Size Formats:**
- Data sizes: `8`, `16`, `24`, `32`, `40`, `48`, `56`, `64` bits (any multiple of 8)
- Address sizes (I2C only): `8`, `16`, `32`, `64` bits
- Endianness: `be` (big), `le` (little), `bes` (big swapped), `les` (little swapped)

### Default Mode

Shorthand for mmap mode using `/dev/mem`:

```bash
rwmem 0x1000                    # Read 32-bit native endian value at 0x1000
rwmem -d 16 0x1000              # Read 16-bit value (native endian)
rwmem -d 32be 0x1000            # Read 32-bit big-endian value
rwmem 0x1000=0x12345678         # Write value
rwmem 0x1000:7:4=0xf            # Set bitfield
```

This is equivalent to `rwmem mmap /dev/mem [options] <address>`.

### mmap Mode

For memory-mapped access to any file:

```bash
rwmem mmap /dev/mem 0x1000           # Equivalent to default mode
rwmem mmap /sys/class/uio/uio0/maps/map0/addr -d 32 0x0
rwmem mmap my_dump.bin -d 16le 0x100
```

**Additional parameter:**
- `<file>` - File to open for memory mapping (required)

### I2C Mode

For communicating with I2C devices:

```bash
rwmem i2c 1:0x50 0x10                    # Read from I2C bus 1, device 0x50, register 0x10
rwmem i2c 1:0x50 -a 16 -d 8 0x1000      # 16-bit address, 8-bit data
rwmem i2c 2:0x48 -a 8le -d 16be 0x80=0x1234  # Little-endian address, big-endian data
```

**Additional parameter:**
- `<bus:addr>` - I2C bus number and device address (required)

**Additional option:**
- `-a, --addr <size>[endian]` - Address size and endianness (I2C only)

### List Mode

For listing registers from a register database:

```bash
rwmem list                               # List all registers
rwmem list -r my.regdb                   # Use specific register file
rwmem list DISPC.*                       # List DISPC registers
rwmem list DISPC.SYSCONFIG               # List specific register
rwmem list DISPC.SYSCONFIG:MIDLEMODE     # List specific field
```

**Options:**
- `-r, --regs <file>` - Register description file
- `-p, --print <mode>` - Print mode: r (register), rf (register+fields, default)
- `-v, --verbose` - Verbose output

**Pattern Format:**
- `BLOCK.*` - All registers in block
- `BLOCK.REGISTER` - Specific register
- `BLOCK.REGISTER:FIELD` - Specific field
- Supports shell wildcards (`*`, `?`)

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

## Write Modes

The write mode parameter (`-w, --write`) affects how rwmem handles writing:

- **`w` (write only)** - Writes the register directly without reading first
  - CAUTION: For bitfield operations like `0x1000:5=1`, this sets bit 5 to 1 but all other bits to 0

- **`rw` (read-write)** - Reads current value, modifies specified bits/fields, then writes
  - Safe for bitfield operations: `0x1000:5=1` preserves other bits
  - Shows: original value and intended write value
  - Does NOT read back after writing (assumes write succeeded)

- **`rwr` (read-write-read, default)** - Like `rw` but also reads back after writing
  - Safe for bitfield operations with verification
  - Shows: original value, intended write value, and actual final value

**Examples:**
```bash
# Safe bitfield modification (preserves other bits)
rwmem 0x1000:7:4=0xa                     # Uses rwr (default)
rwmem -w rw 0x1000:7:4=0xa               # Uses rw (no verification)

# Dangerous: sets bits 7:4 to 0xa, all other bits to 0!
rwmem -w w 0x1000:7:4=0xa                # Uses w (destructive)

# Safe: writing complete register value
rwmem -w w 0x1000=0x12345678             # Uses w (appropriate here)
```

## Print Modes

The print mode parameter (`-p, --print`) affects what rwmem will output:

- `q` - Quiet
- `r` - Register (show register name and value)
- `rf` - Register+fields (show register, value, and field breakdown) - default

## Number Formats

The format parameter (`-f, --format`) controls how numbers are displayed:

- `x` - Hexadecimal (default, shows as 0x1234)
- `d` - Decimal (shows as 1234)
- `b` - Binary (shows as 0b10110010)

Note: Format only applies to register display modes (`-p r` and `-p rf`). It is ignored in quiet (`-p q`) and raw (`-R`) modes.

## Raw Output Mode

In raw output mode (`-R, --raw`) rwmem will copy the values it reads to stdout without any
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
