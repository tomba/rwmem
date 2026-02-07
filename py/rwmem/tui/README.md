# rwmem-tui

An interactive terminal UI for browsing and editing hardware registers, built
on top of the `rwmem` Python module using [Textual](https://textual.textualize.io/).

## Installation

```
pip install rwmem[tui]
```

## Usage

```
rwmem-tui [-r <regdb>] mmap [<file>]
rwmem-tui [-r <regdb>] i2c <bus>:<addr>
```

- **mmap mode**: Memory-mapped access. `<file>` defaults to `/dev/mem`.
- **i2c mode**: I2C access. `<bus>:<addr>` specifies adapter and device
  address (e.g. `1:0x48`).
- **`-r <regdb>`**: Optional `.regdb` file. Without one, the register
  database is built interactively.

## Features

### Register Browser

The left pane shows a collapsible tree of register blocks, registers, and
fields. Fields appear as children of their register node (collapsed by
default) with labels showing `name [high:low]` and optionally the current
value.

The right pane shows a context-sensitive detail view depending on what is
selected in the tree:

- **Root**: Target info (type, file/bus, poll interval), totals (blocks,
  registers, fields), and a block summary table.
- **Block**: Block metadata (offset, size, data size, endianness) and live
  state (registers read, errors, polling count).
- **Register**: Bit diagram with colored fields and a field value table.
- **Field**: Bit diagram with the selected field highlighted and all other
  fields dimmed, plus the field value shown simultaneously in hex, decimal,
  and binary formats.

### Reading and Writing

Press `r` to read the selected register or all registers in a block. When
a field is selected, `r` reads the parent register. Press `w` to write a
value, either to the full register or to an individual field
(read-modify-write). When a field is selected, the write dialog opens
pre-selected to that field.

### Polling

Registers can be watched for changes. Press `p` to toggle polling on the
selected register, block, or all registers. When a field is selected, `p`
toggles polling on the parent register. Press `P` to configure the poll
interval. For mmap targets, polling defaults to 100ms. For I2C targets,
polling is disabled by default due to bus overhead.

When values change during polling, the affected tree nodes are updated
in-place (without rebuilding the tree) and briefly highlighted in yellow.

### Register Database Editing

The register database can be built or modified interactively. Press
`Ctrl+a` to add blocks, registers, or fields (context-sensitive: when a
field is selected, `Ctrl+a` adds a sibling field to the parent register).
Press `Ctrl+d` to delete the selected block, register, or field. Press
`Ctrl+s` to save the database as a `.regdb` file.

### Key Bindings

| Key      | Action                                    |
|----------|-------------------------------------------|
| `r`      | Read selected register/block/field        |
| `w`      | Write register or field value              |
| `Ctrl+a` | Add block, register, or field              |
| `Ctrl+d` | Delete selected item                       |
| `Ctrl+s` | Save register database                     |
| `p`      | Toggle polling on selection                |
| `P`      | Set poll interval                          |
| `f`      | Cycle value format (hex/dec/bin)           |
| `v`      | Toggle value display in tree               |
| `q`      | Quit                                       |
