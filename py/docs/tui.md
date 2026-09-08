# rwmem-tui

An interactive register browser built on pyrwmem and
[Textual](https://textual.textualize.io/). It shows the blocks, registers
and fields of a register database as a tree, reads and writes them, and
polls them for changes. The registers can be on the machine running the
TUI or on another device over ssh, using `rwmem.remote`.

## Installation

```
pip install rwmem[tui]
```

## Usage

```
rwmem-tui [options] mmap [FILE] [options]
rwmem-tui [options] i2c BUS:ADDR [options]

options: -r REGDB  --host HOST  --installed  --env K=V  --python PY  --ssh CMD
         -i SECONDS  --base [BLOCK=]ADDR  --ignore-base  -d SIZE[ENDIAN]
         -a SIZE[ENDIAN]  --range ADDR+LEN|ADDR-END
```

The options may be given before or after the mode, as with rwmem.
Registers come from a register database (`-r`), from ad-hoc `--range`
blocks, or both. A range shows a raw address range as a block with one
register per data word, which is enough to look at a peripheral without
writing a database first. `-d` sets the data size of range blocks, and for
I2C `-a` the register address size.

`--base BLOCK=ADDR` accesses a block at a different address than its
offset in the database, for example to use a database written for another
SoC whose peripheral sits elsewhere; `BLOCK=` may be left out when the
database has a single block. `--ignore-base` accesses every block at
address 0, as rwmem does, which is what a register dump file needs. The
tree shows the address actually used, with the database offset next to it
when they differ.

With `--host`, every access runs on that device through
`rwmem.remote.RemoteConnection`; see [remote-access.md](remote-access.md).
By default pyrwmem is shipped to the device, which then needs only python3.
`--installed` uses the copy on the device instead, with `--env` to point at
it when it is not installed system-wide. `--python` and `--ssh` override the
interpreter and the ssh command.

```sh
# a register database, registers on the local machine
rwmem-tui mmap -r dss.regdb

# the same registers on a board over ssh
rwmem-tui -r dss.regdb --host mydevice mmap

# no database: a raw block, on the board
rwmem-tui --host mydevice mmap --range 0x3022a000+0x100

# an I2C device on the board, 16-bit big-endian register addresses
rwmem-tui --host mydevice i2c 1:0x45 -a 16be --range 0x0+0x40
```

## The screen

The left pane is the tree: blocks, their registers, and each register's
fields as collapsed children. Registers and fields show their last value
once read, in green, or in yellow when it changed since the previous read.
Read errors are shown in red on the register. `[poll]` marks what is being
polled.

The right pane follows the tree cursor:

- **root**: the target, totals, and the key bindings
- **block**: offset, size, sizes and endianness, and how many registers
  have been read
- **register**: address, the value in hex, decimal and binary, a bit layout
  with each field in its own colour, and a table of the field values
- **field**: as for the register, with the field highlighted and the other
  bits dimmed

## Keys

| Key | Action |
|-----|--------|
| `r` | read the selected register, all registers of the selected block, or everything |
| `w` | write the selected register, or the selected field with a read-modify-write |
| `p` | toggle polling of the selected register, block, or everything |
| `P` | set the poll interval; 0 disables polling |
| `f` | cycle the value format: hex, decimal, binary |
| `q` | quit |

Reading a block or everything is one batched request, so a whole block over
ssh costs about the same as a single register.

## Polling

Anything marked with `p` is re-read every interval (`-i`, default 0.5 s)
in one batched request, and the tree marks the values that changed. A tick
that finds the previous poll still in progress is skipped, so a slow device
degrades to a slower poll rate rather than a backlog. Polling stops by
itself when nothing is marked, and when the connection to the device is
lost. A register that fails while polled shows the error on its row rather
than raising a notice on every tick; a read asked for with `r` reports it.

## Notes

- All register access runs in worker threads, so a slow or hung access
  does not freeze the display. Reads and writes are serialised: a request
  issued while another is in flight waits for it, so a write made during a
  long poll batch goes through once the batch is done. Only a poll tick
  that finds the previous poll still running is skipped.
  A request has no timeout, but quitting does not wait for one: the TUI
  closes the connection on its way out, which ends the agent and with it
  the hung request.
- Each block gets its own target, opened the first time it is accessed.
  A block whose target cannot be opened, for example because its range is
  outside the file, shows the error on each of its registers and does not
  affect the other blocks. Opening it is tried once per read, not once per
  register, and again on the next read.
- When the agent on the device dies, the whole read fails instead of each
  register on its own: the error is shown once, the header shows
  CONNECTION LOST and polling stops. There is no reconnect; restart the TUI.
- The register database is not editable in the TUI.
