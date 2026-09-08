# rwmem-shell

A Python shell with a register target already opened: IPython when it is
installed, the plain Python REPL otherwise. It is for poking at registers by
hand and for the small loops and experiments that are awkward on a command
line but not worth a script. The registers can be on the machine running
the shell or on another device over ssh, using `rwmem.remote`.

## Installation

```
pip install rwmem[shell]
```

Without IPython the standard REPL is used, with tab completion but without
IPython's history, magics and object introspection.

## Usage

```
rwmem-shell [options] mmap [FILE] [options]
rwmem-shell [options] i2c BUS:ADDR [options]

options: -r REGDB  --host HOST  --installed  --env K=V  --python PY  --ssh CMD
         -d SIZE[ENDIAN]  -a SIZE[ENDIAN]
```

The options may be given before or after the mode, as with rwmem and
rwmem-tui. Nothing but the mode is required: registers are accessed by
address, and with a register database (`-r`) also by name. `-d` and `-a`
set the data size and endianness, and for I2C the register address size,
of accesses by address; without them the database's blocks decide, see
below.

With `--host`, every access runs on that device through
`rwmem.remote.RemoteConnection`; see [remote-access.md](remote-access.md).
By default pyrwmem is shipped to the device, which then needs only python3.
`--installed` uses the copy on the device instead, with `--env` to point at
it when it is not installed system-wide. `--python` and `--ssh` override the
interpreter and the ssh command.

## In the shell

| name                 | what it is                                                  |
|----------------------|-------------------------------------------------------------|
| `rd(addr)`           | read a value; `rd(addr, d)` gives its size, see below       |
| `wr(addr, value)`    | write a value, with the same `d`                            |
| `dump(addr, length)` | print the values in a range, one per line as rwmem does     |
| `opts`               | the session's `-d`, settable as `opts.d = '16be'`, and `-a` |
| `mrf`                | a `MappedRegisterFile` over `-r`, keyed by register path    |
| `rf`                 | the `RegisterFile` itself, for names, offsets and fields    |
| `conn`               | the `RemoteConnection` with `--host`, else `None`           |
| `rw`                 | the `rwmem` package, e.g. `rw.Endianness.Big`               |

Integers are displayed in hex.

```
$ rwmem-shell --host mydevice mmap -r dss.regdb
rwmem-shell: mmap /dev/mem on mydevice, d=None, blocks: DSS, DISPC, DSI, ...

In [1]: rd(0x3022a000)
Out[1]: 0x40000000

In [2]: mrf['DSS.SYSCONFIG:SOFTRESET']
Out[2]: 0x0

In [3]: mrf['DSS.SYSCONFIG:SOFTRESET'] = 1

In [4]: dump(0x3022a000, 0x10)
0x3022a000 = 0x40000000
0x3022a004 = 0x00000000
0x3022a008 = 0x00000001
0x3022a00c = 0x00000000

In [5]: [rd(0x3022a040 + i * 4) & 0xff for i in range(4)]
Out[5]: [0x0, 0x1, 0x1, 0x0]

In [6]: %timeit rd(0x3022a000)
1.21 ms ± 12 µs per loop (mean ± std. dev. of 7 runs, 1,000 loops each)
```

`mrf` works as in scripts: `mrf['DSS.REVISION']` reads a register,
`mrf['DSS.REVISION:MAJOR'] = 4` writes a field, and `mrf['DSS.*']` reads a
whole block; see [register-access.md](register-access.md). For tab
completion one level at a time, use attribute navigation:
`mrf.DSS.REVISION.read()`, with `mrf.DSS.` completing registers and
`mrf.DSS.REVISION.` fields. Each block is opened on the target the first
time it is used.

The data size of an access by address is given as `-d` takes it:
`rd(0x160, 16)` reads 16 bits, `rd(0x160, '16be')` big-endian ones, and
`wr(0x160, 0x0a83, 'be')` writes big-endian at the size in effect. Size
and endianness are taken separately: what the call does not give comes
from `opts.d`, which starts as `-d` and can be changed in the shell; then,
with a register database, from the block containing the address; and
failing that is the default, 32-bit native data or 8-bit for I2C. For a
device with registers of several widths, `partial(rd, d=16)` is a reader
for one of them.

The register address size of an I2C device does not change within a
session: it is `-a`, else the database's when its blocks share one, else
8-bit, and `opts.a` shows it. So on an I2C sensor described by its
database, `rd(0)` needs no options.

The address helpers work on the target named on the command line. An I2C
device is opened once. An mmap file is mapped in windows opened as needed,
each covering exactly the accessed range, as rwmem's do, and kept for the
later accesses that fall inside it; a new address outside the open windows
costs a mapping, which on a remote device is a round trip. `dump` reads its
range in one round trip.

On a remote target, `conn.agent_info`, `conn.dead` and `conn.agent_stderr`
tell what the agent on the device is up to, and if it died, why.

Leaving the shell closes the targets and the connection. The register file
stays mapped if a register or block looked up from it is still referenced,
for example by IPython's output history; that is harmless.
