# rwmem Command Line Interface

This document describes the command line interface for rwmem, a tool for reading and writing device registers through memory-mapped access or I2C devices.

## Overview

rwmem supports three main modes of operation:

1. **Default mode** - Simplified mmap access to `/dev/mem`
2. **Explicit mmap mode** - Memory-mapped access to a specified file
3. **I2C mode** - I2C device communication
4. **List mode** - List registers from a register database

## Command Structure

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

## Address Syntax

All modes support the same address syntax:

- `0x1000` - Single address
- `0x1000-0x1040` - Address range (from start to end)
- `0x1000+0x40` - Address range (start + length)
- `0x1000:7` - Single bit access (bit 7)
- `0x1000:7:4` - Bitfield access (bits 7 down to 4)
- `0x1000:7:4=0xf` - Bitfield write (set bits 7-4 to 0xf)
- `DISPC.SYSCONFIG:MIDLEMODE=0x1` - Register database access

## Common Options

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
- Address sizes: `8`, `16`, `32`, `64` bits
- Endianness: `be` (big), `le` (little), `bes` (big swapped), `les` (little swapped)

## Mode Details

### Default Mode

Shorthand for mmap mode using `/dev/mem`:

```bash
rwmem 0x1000                    # Read 32-bit native endian value at 0x1000
rwmem -d 16 0x1000              # Read 16-bit value (native endian)
rwmem -d 32be 0x1000            # Read 32-bit big-endian value
rwmem 0x1000=0x12345678         # Write value
rwmem -w rw 0x1000=0x1234       # Read-write (show before and after)
rwmem 0x1000:7:4=0xf            # Set bitfield
```

This is equivalent to `rwmem mmap /dev/mem [options] <address>` but more convenient for the common case.

Uses all common options.

### mmap Mode

For memory-mapped access to any file:

```bash
rwmem mmap /dev/mem 0x1000           # Equivalent to default mode
rwmem mmap /sys/class/uio/uio0/maps/map0/addr -d 32 0x0
rwmem mmap my_device.bin -d 16le 0x100
```

**Additional parameter:**
- `<file>` - File to open for memory mapping (required)

Uses all common options.

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

Uses all common options.

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

## Write Modes

- **`w` (write only)** - Writes the register directly without reading first
  - CAUTION: For bitfield operations like `0x1000:5=1`, this sets bit 5 to 1 but all other bits to 0
  - Only safe for writing complete register values
  - Use when you want to set the entire register to a known value

- **`rw` (read-write)** - Reads current value, modifies specified bits/fields, then writes
  - Safe for bitfield operations: `0x1000:5=1` preserves other bits
  - Shows: original value and intended write value
  - Does NOT read back after writing (assumes write succeeded)

- **`rwr` (read-write-read, default)** - Like `rw` but also reads back after writing
  - Safe for bitfield operations with verification
  - Shows: original value, intended write value, and actual final value
  - Recommended for verification since some registers have side effects or read-only bits

**Examples:**
```bash
# Safe bitfield modification (preserves other bits)
rwmem 0x1000:7:4=0xa                    # Uses rwr (default)
rwmem -w rw 0x1000:7:4=0xa               # Uses rw (no verification)

# Dangerous: sets bits 7:4 to 0xa, all other bits to 0!
rwmem -w w 0x1000:7:4=0xa                # Uses w (destructive)

# Safe: writing complete register value
rwmem -w w 0x1000=0x12345678             # Uses w (appropriate here)
```

## Print Modes

- `q` - Quiet (only show values)
- `r` - Register (show register name and value)
- `rf` - Register+fields (show register, value, and field breakdown)

## Number Formats

- `x` - Hexadecimal (default, shows as 0x1234)
- `d` - Decimal (shows as 1234)
- `b` - Binary (shows as 0b10110010)

Note: Format only applies to register display modes (`-p r` and `-p rf`). Ignored in quiet (`-p q`) and raw (`-R`) modes.

## Examples

### Basic Memory Access
```bash
# Read 32-bit register
rwmem 0x48004000

# Write and verify
rwmem 0x48004000=0x12345678

# Read bitfield
rwmem 0x48004000:31:16

# Set specific bits
rwmem 0x48004000:7:4=0xa
```

### Using Register Database
```bash
# With register file
rwmem -r omap4.regdb DISPC.CONTROL

# Set field using name
rwmem -r omap4.regdb DISPC.CONTROL:ENABLE=1

# List all DISPC registers
rwmem list -r omap4.regdb DISPC.*
```

### I2C Device Access
```bash
# Read EEPROM
rwmem i2c 1:0x50 -a 16be -d 8 0x0000

# Write to RTC
rwmem i2c 0:0x68 -a 8 -d 8 0x00=0x12
```

### Different Data Formats
```bash
# 16-bit little-endian
rwmem -d 16le 0x1000

# 32-bit big-endian with binary output
rwmem -d 32be -f b 0x1000

# Quiet mode (values only)
rwmem -p q 0x1000-0x1010
```
