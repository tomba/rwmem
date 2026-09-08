# Remote register access

`rwmem.remote` lets a program on a PC read and write registers on another
device over ssh. It is not imported by the `rwmem` package itself, because its
dependencies are slow to import on small devices and the agent never needs it;
import it explicitly with `from rwmem.remote import RemoteConnection`. The device runs a small agent (`rwmem.agent`); the PC side
talks to it through the ssh session's stdin and stdout. No TCP port is
opened, no daemon is left running, and ssh provides the authentication.

`RemoteTarget` implements the same `Target` interface as `MMapTarget` and
`I2CTarget`, so anything that takes a `Target` works unchanged over the
connection, including `MappedRegisterBlock` and `MappedRegisterFile`.

## Requirements on the device

- `python3`, 3.10 or newer, in both modes, the same as pyrwmem requires
- an ssh server with key-based login (the PC side runs ssh with
  `BatchMode=yes`, so password prompts fail instead of hanging)
- for installed mode only: pyrwmem importable, either installed or reachable
  through `PYTHONPATH`

## Starting the agent

There are two ways to get the agent running on the device.

**Deploy mode** (default) needs nothing but `python3` on the device. From its
own copy of the package the PC zips the few modules the agent needs, in
memory, and streams them to a bootstrap on the device, which imports them
straight from memory and starts the agent. Nothing is written to the device's
filesystem, and the device always runs exactly the PC's version of the code.

```python
import rwmem as rw
from rwmem.remote import RemoteConnection

with RemoteConnection('buildroot') as conn:
    with conn.open_mmap('/dev/mem', 0x3022a000, 0x100, rw.Endianness.Little, 4) as t:
        print(hex(t.read(0x3022a000)))
        t.write(0x3022a05c, 0x01230456)
```

**Installed mode** (`deploy=False`) runs `python3 -m rwmem.agent` on the
device, so pyrwmem must be importable there. If it is not installed
system-wide, pass its location in `env`. This skips the transfer and the
compile, which saves a few hundred milliseconds per connection on a small
device, and it is the fallback for debugging deploy mode against a known
on-disk copy.

```python
with RemoteConnection('buildroot', deploy=False, env={'PYTHONPATH': '/path/to/rwmem/py'}) as conn:
    with conn.open_i2c(1, 0x45, 0, 0x100, rw.Endianness.Big, 1, rw.Endianness.Big, 1) as t:
        print(hex(t.read(0)))
```

Other `RemoteConnection` arguments: `ssh` is the ssh command prefix
(default `ssh -o BatchMode=yes`), `python` is the interpreter to run on the
device (default `python3`). With `host=None` the agent runs as a local
subprocess instead of over ssh, which is how the tests exercise both modes
without hardware.

## Register files over a connection

A register file describes many blocks at different addresses, and each
block gets its own target the first time it is used. On a connection that
target is opened on the device:

```python
with rw.RegisterFile('dss.regdb') as rf, RemoteConnection('buildroot') as conn:
    with conn.mapped_register_file(rf, '/dev/mem') as mrf:
        print(mrf['DSS.REVISION'])
```

The inner `with` matters: the mapped blocks hold views into the register
file's mmap, and `MappedRegisterFile.close()` (which its `with` calls) closes
the blocks and drops those views. Closing the `RegisterFile` while they are
still alive raises `BufferError: cannot close exported pointers exist`.

`MappedRegisterFile` is keyed by register path, so `mrf['DSS.REVISION']`
reads and `mrf['DSS.REVISION:MAJOR'] = 4` writes on the device; see
[register-access.md](register-access.md). Under the hood it takes a
`target_factory`, a callable that is given a `RegisterBlock` and returns a
`Target` covering it. The default factory maps blocks from the local
`/dev/mem`; `RemoteConnection.mmap_factory()` returns one that opens them on
the device, and `mapped_register_file()` is shorthand for passing it.

`RemoteConnection.i2c_factory(bus, addr)` returns the factory for an I2C
device: `MappedRegisterFile(rf, conn.i2c_factory(1, 0x45))` opens each
block as an I2C target on the device, with the register address size and
endianness the database gives the block. Register files over mmap and over
I2C can share one connection.

`MappedRegisterBlock` accepts a ready `Target` in place of a file name. The
target must cover the block's address range, and the block closes it on
exit, as it does with its own `MMapTarget`. The target was opened with its
own mode, so passing `mode` as well is an error.

## How deploy mode works

1. The PC runs `python3 -c '<stage one>'` on the device. Stage one is a
   single quote-free line that reads a length-prefixed blob from stdin and
   execs it.
2. The blob is `rwmem/_bootstrap.py`. It reads a second length-prefixed blob,
   the zipped modules, and installs a meta path finder that serves
   `rwmem.*` modules from that in-memory zip. Tracebacks still show source
   lines because the sources are registered with `linecache`.
3. The bootstrap imports `rwmem.agent` and starts it. From here on both modes
   behave identically.

The bundle holds only what the agent imports from the package: `agent`,
`target`, `mmaptarget`, `i2ctarget` and `enums`, listed in
`rwmem.remote.AGENT_MODULES`, plus a stub `__init__.py` in place of the real
one, which imports the whole package. So the device neither compiles nor runs
anything the agent does not use.

Because those modules are shipped as source and compiled on the device, they
must parse and run under the device's Python version, which must be 3.10 or
newer, as for pyrwmem as a whole.

## Protocol

Newline-delimited JSON, one request line and one reply line, strictly in
turn. Enum arguments are sent as their integer values. Ops on a target carry
its handle in `t`; handles are returned by the open ops.

`RemoteConnection` holds a lock for the length of a request, so a
connection can be used from several threads and by any number of targets
and register files. Closing it from another thread ends a request in
flight.

| op          | arguments                                                   | reply value          |
|-------------|-------------------------------------------------------------|----------------------|
| `info`      |                                                             | python, byteorder, origin |
| `open_mmap` | `MMapTarget` constructor arguments by name                  | handle               |
| `open_i2c`  | `I2CTarget` constructor arguments by name                   | handle               |
| `read`      | `t`, `Target.read` arguments by name                        | the value            |
| `read_many` | `reads`: list of `read` argument objects                    | list of `{"value"}` or `{"error"}`, one per read |
| `write`     | `t`, `Target.write` arguments by name                       | null                 |
| `close`     | `t`                                                         | null                 |
| `quit`      |                                                             | null, then agent exits |

A reply is `{"value": ...}` or `{"error": "<ExceptionType>: <message>"}`.
Errors are raised on the PC as `RemoteError`, a `RuntimeError` subclass.
The agent's stdout carries only replies: at startup the agent moves them to a
private duplicate of stdout and points fd 1 at stderr, so a stray `print()`
on the device cannot corrupt the protocol. Its stderr, and ssh's, is captured
by the PC side: the last lines are available as `RemoteConnection.agent_stderr`
and are included in the `RemoteError` raised when the agent exits unexpectedly,
for example because pyrwmem is not importable on the device. Connecting
performs an `info` request as a handshake, so such failures are raised by
the `RemoteConnection` constructor; the reply is kept as `agent_info`.

A register access that faults on the device, for example a read from an
unmapped address or a powered-down peripheral, kills the agent with SIGBUS.
The agent runs with `faulthandler` enabled, so the error for that request
carries the Python traceback naming the access. The connection remembers
the death: every later request fails with the same message, `dead` is
true, and closing targets or the connection does not raise.

## rwmem-remote

`rwmem-remote` is a stripped-down rwmem command that runs its accesses on a
remote device. Everything after the host is parsed like the rwmem command
line, with the same output format, but only numeric addresses are
supported: no register database, and no `list`, `-r`, `-R`, `-v` or
`--ignore-base`. Address ranges, bitfields, writes, the `-d` and `-a` size
and endianness options, the write modes and the print and number formats all
work as in rwmem.

```sh
# read one register, default mode is "mmap /dev/mem"; pyrwmem is shipped to the device
rwmem-remote buildroot 0x3022a000

# a 16-bit range, a bitfield write, and an i2c read
rwmem-remote buildroot -d 16 0x3022a000-0x3022a020
rwmem-remote buildroot 0x3022a05c:10:0=0x123
rwmem-remote buildroot i2c 1:0x45 -a 8 -d 8 0x0+4

# use the copy of pyrwmem on the device instead
rwmem-remote --installed --env PYTHONPATH=/path/to/rwmem/py buildroot 0x3022a000
```

Remote options (`--installed`, `--env`, `--python`, `--ssh`) go before the host.

## Current limitations

- One request in flight at a time: requests from other threads wait, so a
  slow one delays them all. `read_many` batches reads across any targets of
  a connection into one round trip; there is no batched write.
- Deploy mode re-sends the agent's modules on every connection. They are
  about 6 KB, so this only matters if connections are opened often.
- Errors arrive as `RemoteError` with the original type in the message
  rather than as the original exception type.
- There is no timeout on requests; a hung agent hangs the caller.
