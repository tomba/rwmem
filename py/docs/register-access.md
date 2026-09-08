# Register access by name

`rwmem.MappedRegisterFile` binds a register database to memory, so registers
and fields are read and written by name instead of by address. It is what
`rwmem-tui` and `rwmem-shell` use, and it works locally or on a device over
ssh (see [remote-access.md](remote-access.md)).

There are two ways to reach a register, over the same handles underneath.
String keys are the short form and do I/O; methods return handles you look
up once and reuse.

## Opening

```python
import rwmem as rw

# Owns the RegisterFile it opens from a path; blocks map /dev/mem lazily.
mrf = rw.MappedRegisterFile('dss.regdb')

# Or pass a RegisterFile you keep yourself, and a factory for the targets.
with rw.RegisterFile('dss.regdb') as rf:
    mrf = rw.MappedRegisterFile(rf, target_factory=my_factory)
    ...
    mrf.close()
```

`target_factory` is called with a `RegisterBlock` and returns a `Target`
covering it. Without one, blocks are mapped from `/dev/mem`. A
`RemoteConnection` supplies factories that open blocks on the device:
`conn.mapped_register_file(rf)` is the shorthand for mmap, and
`conn.i2c_factory(bus, addr)` the factory for an I2C device.

## String keys: the short form

A key is an rwmem register path. Indexing does I/O.

```python
mrf['DSS.REVISION']            # read a register -> a value
mrf['DSS.REVISION'] = 0x10     # write a register
mrf['DSS.REVISION:MAJOR']      # read a field
mrf['DSS.REVISION:MAJOR'] = 4  # write a field (read-modify-write)
mrf['DSS.REVISION:7:3']        # a bit range, high:low inclusive
mrf['DSS.REVISION:7:3'] = 2
mrf['DSS.REVISION:3']          # a single bit
mrf['DSS.REVISION'] = {'MAJOR': 4, 'MINOR': 0}   # several fields, one read-modify-write
mrf['DSS.*']                   # the whole block -> {name: value}, one round trip
```

Indexing a bare block name gives a block scope and does no I/O. Its keys
drop the block prefix:

```python
dss = mrf['DSS']
dss['REVISION:MAJOR'] = 4
dss['*']
```

`mrf.read([...])` reads several register paths at once, one round trip per
block, which matters over ssh:

```python
mrf.read(['DSS.REVISION', 'DISPC.CONTROL'])   # {path: value}
```

## Values decode their own fields

Reading a register returns a `RegisterValue`, an `int` that also carries the
register's field layout. It behaves as an ordinary integer, and in addition
decodes fields from the value already read, with no further access:

```python
v = mrf['DSS.REVISION']
v == 0x40000011                # True; it is an int
hex(v), v & 0xff               # ordinary int operations
v['MAJOR'], v[7:3], v[3]       # decode a field, a range, a bit
v.fields                       # {'MAJOR': 0x4, 'MINOR': 0x11}
```

Because the layout is copied, a value stays valid after the
`MappedRegisterFile` and its `RegisterFile` are closed. A value is a
read-only copy: assigning to `v['MAJOR']` raises. To write, use a path or a
handle.

In IPython, `mrf['` and `dss['` complete block names, register paths and
`BLOCK.REG:FIELD` paths, and a value prints its fields decoded.

## Handles: looked up once

Methods return handles that read and write without parsing a path again.

```python
reg = mrf.reg('DSS.REVISION')          # or mrf['DSS'].reg('REVISION')
reg.read()                             # a RegisterValue
reg.write(0x10)
reg.write({'MAJOR': 4, 'MINOR': 0})    # one read-modify-write
reg['MAJOR']                           # brackets on a handle are I/O: read the field
reg['MAJOR'] = 4                       # read-modify-write
reg[7:3] = 2
reg.name, reg.address, reg.offset, reg.bits, reg.reset_value, reg.description

fld = reg.field('MAJOR')               # or reg.field(31, 28); or mrf.field('DSS.REVISION:MAJOR')
fld.read()
fld.write(4)
fld.high, fld.low, fld.width, fld.mask, fld.register
```

A block scope and its register handles are created on first use and then
cached, so `mrf.reg('DSS.REVISION')` returns the same handle each time and
opens the block's target only once.

## Attribute navigation

Blocks, registers and fields are also reachable as attributes, one level
at a time, which reads naturally for a fixed path and lets `dir()` and tab
completion show what the next level holds.

```python
mrf.DSS                       # the block scope, same as mrf['DSS']
mrf.DSS.REVISION              # the register handle, same as mrf.reg('DSS.REVISION')
mrf.DSS.REVISION.MAJOR        # the field handle
mrf.DSS.REVISION.read()       # attributes navigate; read() and write() do the I/O
mrf.DSS.REVISION.MAJOR.write(4)
```

Attribute access only navigates to handles and never reads or writes on its
own, so `mrf.DSS.REVISION` is the register handle, not its value; use
`mrf['DSS.REVISION']` or `.read()` for that. It returns the same cached
handles as the methods. Two limits follow from Python attributes: a block,
register or field whose name is not a valid identifier, or clashes with a
method or property (`read`, `name`, `block`, ...), is reachable only through
the string keys or `reg()`/`field()`; and a stray assignment such as
`mrf.DSS = 1` raises rather than writing, since writes go through the keys
and handles above.

## Iteration and metadata

Iterating touches no hardware. A `MappedRegisterFile` iterates block names,
a block scope iterates register names, and `in` tests membership. It is not
a full mapping: there is no `values()`, since that would read every
register one at a time; use `mrf['BLOCK.*']` or `block.read()` for that.

Bit positions, offsets, descriptions and the like come from the database
tree, `rw.RegisterFile`, reached through the handles above or directly.

## Blocks and targets

`MappedRegisterBlock` is the block scope. It can be built directly on a file
name or on an already opened `Target`, with an optional `offset` to access
the block somewhere other than its database offset:

```python
with rw.RegisterFile('dss.regdb') as rf:
    with rw.MappedRegisterBlock('/dev/mem', rf['DSS'], offset=0xfed90000) as dss:
        dss['REVISION']
```

A `Target` given this way must cover the block's range; the block closes it
on exit, as it does its own `MMapTarget`. The target was opened with its own
mode, so passing `mode` as well is an error.

## Lifetime

The mapped blocks hold views into the `RegisterFile`'s mmap, so close the
`MappedRegisterFile` (or let its `with` do it) before closing a
`RegisterFile` you own; otherwise closing the file raises `BufferError:
cannot close exported pointers exist`. A `MappedRegisterFile` opened from a
path owns its `RegisterFile` and closes it for you, tolerating a handle you
kept alive.
