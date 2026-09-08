"""rwmem-shell: a Python shell with a register target opened.

    rwmem-shell [options] mmap [FILE] [options]
    rwmem-shell [options] i2c BUS:ADDR [options]

The target is on this machine or, with --host, on another device over ssh.
IPython starts with these names defined, or the plain Python REPL when
IPython is not installed:

    rw                   the rwmem package
    conn                 the RemoteConnection with --host, else None
    rf                   the RegisterFile given with -r, else None
    mrf                  a MappedRegisterFile over rf: mrf['DSS.REVISION']
    opts                 the session's -d, settable, and its -a
    rd(addr)             read a value
    wr(addr, value)      write a value
    dump(addr, length)   print the values in a range

The address helpers take absolute addresses on the target named on the
command line. The data size of an access is given as -d takes it, for
one call (rd(0x160, '16be')) or for the session in opts; what neither
gives comes from the register database's block at the address, else
from -d's default. The register address size of an I2C device is the
session's: -a, else the database's, else 8-bit. Integers are displayed
in hex.
"""

from __future__ import annotations

import argparse
import builtins
import code
import itertools
import sys
from collections.abc import Sequence
from typing import Any

import rwmem as rw
import rwmem.cli
from rwmem.enums import Endianness
from rwmem.i2ctarget import I2CTarget
from rwmem.mappedregisterfile import MappedRegisterFile
from rwmem.mmaptarget import MMapTarget
from rwmem.registerfile import RegisterBlock, RegisterFile
from rwmem.remote import RemoteConnection, RemoteError
from rwmem.target import Target

# --- sizes --------------------------------------------------------------

# A size as -d and -a take it: '16be', '16', 'be', the bits as an int, or
# a parsed (size, endianness) pair. None is nothing given.
Spec = str | int | tuple[int, Endianness] | None

# A parsed spec that gives neither a size nor an endianness.
NOTHING: tuple[int | None, Endianness] = (None, Endianness.Default)


def parse_spec(spec: Spec) -> tuple[int | None, Endianness]:
    """(size in bytes, endianness) for ``spec``; None and Default for what
    it does not give, so that a size and an endianness can be given apart."""
    if spec is None:
        return NOTHING
    if isinstance(spec, tuple):
        return spec
    if isinstance(spec, int):
        spec = str(spec)
    digits = ''.join(itertools.takewhile(str.isdigit, spec))
    ending = spec[len(digits) :]
    if not spec or ending not in rwmem.cli.ENDIANNESS:
        raise ValueError(f"bad size '{spec}', expected e.g. 32, 16be, 8le or be")
    if not digits:
        return None, rwmem.cli.ENDIANNESS[ending]
    try:
        return rwmem.cli.parse_size_endian(spec)
    except argparse.ArgumentTypeError as e:
        raise ValueError(str(e)) from None


def format_spec(size: int | None, endianness: Endianness) -> str | None:
    """The inverse of ``parse_spec``: '16be', '16', 'be', or None for nothing."""
    s = '' if size is None else str(size * 8)
    s += next(k for k, v in rwmem.cli.ENDIANNESS.items() if v == endianness)
    return s or None


def resolve(*tiers: tuple[int | None, Endianness]) -> tuple[int, Endianness]:
    """The first size and the first endianness given, each on its own;
    the last tier must give both."""
    size = next(size for size, _ in tiers if size is not None)
    endianness = next((e for _, e in tiers if e != Endianness.Default), Endianness.Default)
    return size, endianness


class Opts:
    """The session's -d, changeable in the shell as ``opts.d = '16be'``,
    and its -a, which is not.

    ``d`` is None until given, on the command line or here. A size given
    in a call wins over it; what neither gives comes from the register
    database's block containing the address, and failing that is the
    default: 32-bit native data, 8-bit for i2c. ``a`` is the register
    address size of an I2C session: -a, else the database's when its
    blocks share one, else 8-bit.
    """

    def __init__(self, data: Spec, addr: tuple[int, Endianness] | None) -> None:
        self._d = parse_spec(data)
        self._a = addr

    @property
    def d(self) -> str | None:
        """The data size and endianness, as -d takes them."""
        return format_spec(*self._d)

    @d.setter
    def d(self, spec: Spec) -> None:
        self._d = parse_spec(spec)

    @property
    def a(self) -> str | None:
        """The register address size and endianness of the session; None for mmap."""
        return None if self._a is None else format_spec(*self._a)

    def __repr__(self) -> str:
        s = f'd={self.d}'
        if self._a is not None:
            s += f' a={self.a}'
        return s


# --- the shell ----------------------------------------------------------


class Shell:
    """The targets behind the shell's names.

    Targets are opened on first use: a register database block when it is
    first accessed through ``mrf``, and for the address helpers the I2C
    device, or for mmap a window covering the accessed range when no open
    one does. A window covers exactly what was asked for, as rwmem's do,
    since a register dump file smaller than a page cannot be mapped past
    its end.
    """

    def __init__(
        self,
        ns: argparse.Namespace,
        conn: RemoteConnection | None = None,
        rf: RegisterFile | None = None,
    ) -> None:
        self.mode: str = ns.mode
        self.file: str = ns.file
        self.bus_addr: tuple[int, int] | None = ns.bus_addr
        self.regdb: str | None = ns.regdb
        self.conn = conn
        self._default_data = rwmem.cli.DEFAULT_DATA[ns.mode]

        self.rf = rf
        self.mrf = MappedRegisterFile(rf, self._block_target) if rf is not None else None

        # (start, end, block) of the database's blocks, for the sizes of an
        # access by address inside one.
        self._blocks = (
            [(b.offset, b.offset + b.size, b) for b in rf.values()] if rf is not None else []
        )

        addr = None
        if ns.mode == 'i2c':
            addr = ns.addr or self._regdb_addressing() or rwmem.cli.DEFAULT_ADDR
        self.opts = Opts(ns.data, addr)

        # The targets opened by the address helpers: the I2C device, or
        # (start, end, target) of the mmap windows.
        self._device: Target | None = None
        self._targets: list[tuple[int, int, Target]] = []

    def _regdb_addressing(self) -> tuple[int, Endianness] | None:
        """The register address size of the database's blocks, when they
        all share one."""
        sizes = {(b.addr_size, b.addr_endianness) for _, _, b in self._blocks}
        return sizes.pop() if len(sizes) == 1 else None

    def description(self) -> str:
        if self.mode == 'mmap':
            s = f'mmap {self.file}'
        else:
            assert self.bus_addr is not None
            bus, dev = self.bus_addr
            s = f'i2c {bus}:{dev:#x}'
        if self.conn is not None:
            s += f' on {self.conn.host}'
        return s

    # --- targets --------------------------------------------------------

    def _open(
        self,
        offset: int,
        length: int,
        data_endianness: Endianness,
        data_size: int,
        addr_endianness: Endianness,
        addr_size: int,
    ) -> Target:
        if self.mode == 'mmap':
            if self.conn is not None:
                return self.conn.open_mmap(self.file, offset, length, data_endianness, data_size)
            return MMapTarget(self.file, offset, length, data_endianness, data_size)

        assert self.bus_addr is not None
        bus, dev = self.bus_addr
        args = (bus, dev, offset, length, addr_endianness, addr_size, data_endianness, data_size)
        if self.conn is not None:
            return self.conn.open_i2c(*args)
        return I2CTarget(*args)

    def _block_target(self, block: RegisterBlock) -> Target:
        """Target factory for ``mrf``: a block is accessed with its own sizes."""
        return self._open(
            block.offset,
            block.size,
            block.data_endianness,
            block.data_size,
            block.addr_endianness,
            block.addr_size,
        )

    def _target(self, addr: int, length: int) -> Target:
        """The Target for ``[addr, addr + length)``, opened on first use.

        The I2C device is one target, addressed as the session is and
        covering its whole address space. An mmap window covers exactly
        the range it was opened for, and serves the later accesses that
        fall inside it. The targets are opened with the default data
        endianness, so that Default in an access means native.
        """
        if addr < 0:
            raise ValueError(f'address must not be negative, got {addr:#x}')
        if length <= 0:
            raise ValueError(f'length must be positive, got {length}')

        data_size, data_endianness = self._default_data

        if self.mode == 'i2c':
            if self._device is None:
                assert self.opts._a is not None
                addr_size, addr_endianness = self.opts._a
                self._device = self._open(
                    0, 1 << (8 * addr_size), data_endianness, data_size, addr_endianness, addr_size
                )
            return self._device

        end = addr + length
        for start, stop, t in self._targets:
            if start <= addr and end <= stop:
                return t

        t = self._open(addr, length, data_endianness, data_size, Endianness.Default, 0)
        self._targets.append((addr, end, t))
        return t

    # --- access ---------------------------------------------------------

    def _block_at(self, addr: int) -> RegisterBlock | None:
        """The database's block containing ``addr``, if any."""
        for start, end, block in self._blocks:
            if start <= addr < end:
                return block
        return None

    def _data(self, addr: int, d: Spec) -> tuple[int, Endianness]:
        """The data size and endianness of an access at ``addr``: what the
        call gives, then ``opts.d``, then the block containing the address,
        then the default, size and endianness each on its own."""
        block = self._block_at(addr)
        block_data = (block.data_size, block.data_endianness) if block else NOTHING
        return resolve(parse_spec(d), self.opts._d, block_data, self._default_data)

    def rd(self, addr: int, d: Spec = None) -> int:
        """Read the value at ``addr``.

        ``d`` is the data size as -d takes it, for this access:
        ``rd(0x160, 16)``, ``rd(0x160, '16be')``, ``rd(0x160, 'be')``.
        """
        size, endianness = self._data(addr, d)
        return self._target(addr, size).read(addr, size, endianness)

    def wr(self, addr: int, value: int, d: Spec = None) -> None:
        """Write ``value`` at ``addr``; ``d`` as for ``rd``."""
        size, endianness = self._data(addr, d)
        self._target(addr, size).write(addr, value, size, endianness)

    def dump(self, addr: int, length: int, d: Spec = None) -> None:
        """Print the values in ``[addr, addr + length)``, one per line.

        ``d`` as for ``rd``. On a remote target this is one round trip. A
        trailing part shorter than the data size is left out.
        """
        size, endianness = self._data(addr, d)
        t = self._target(addr, length)
        addrs = range(addr, addr + length - size + 1, size)
        values = t.read_many([(x, size, endianness) for x in addrs])

        addr_chars = 2 + 2 * (4 if self.opts._a is None else self.opts._a[0])
        addr_chars = max(addr_chars, len(f'{addr + length - 1:#x}'))
        for x, v in zip(addrs, values, strict=True):
            print(f'{x:#0{addr_chars}x} = {v:#0{2 + 2 * size}x}')

    def close(self) -> None:
        # The mapped blocks hold views into the register file's mmap, so
        # they go first.
        if self.mrf is not None:
            self.mrf.close()
        if self.rf is not None:
            try:
                self.rf.close()
            except BufferError:
                # A register or block the user looked up is still referenced,
                # for example from IPython's output history. The file stays
                # mapped until the process exits, which is harmless.
                pass
        if self._device is not None:
            self._device.close()
            self._device = None
        for _, _, t in self._targets:
            t.close()
        self._targets.clear()
        if self.conn is not None:
            self.conn.close()


def namespace(shell: Shell) -> dict[str, Any]:
    """The names the user gets."""
    return {
        'rw': rw,
        'conn': shell.conn,
        'rf': shell.rf,
        'mrf': shell.mrf,
        'opts': shell.opts,
        'rd': shell.rd,
        'wr': shell.wr,
        'dump': shell.dump,
    }


def block_names(names: Sequence[str], width: int = 60) -> str:
    """The names that fit in ``width`` characters, then ', ...' for the rest."""
    shown: list[str] = []
    for name in names:
        if shown and len(', '.join([*shown, name])) > width:
            return ', '.join(shown) + ', ...'
        shown.append(name)
    return ', '.join(shown)


def banner(shell: Shell) -> str:
    """One line: the target, the sizes in effect, and the database's blocks."""
    s = f'rwmem-shell: {shell.description()}, {shell.opts!r}'
    if shell.rf is not None:
        s += f', blocks: {block_names(list(shell.rf))}'
    return s


# --- the REPLs ----------------------------------------------------------


def hex_displayhook(value: Any) -> None:
    """``sys.displayhook`` that shows plain ints in hex."""
    if type(value) is int:
        builtins._ = None
        print(hex(value))
        builtins._ = value
    else:
        sys.__displayhook__(value)


def _pretty_hex(n: int, p: Any, cycle: bool) -> None:
    """IPython pretty printer for int: hex, except for subclasses such as enums."""
    p.text(hex(n) if type(n) is int else repr(n))


def run_ipython(ns: dict[str, Any], banner: str) -> bool:
    """Run IPython over ``ns``. False when IPython is not installed."""
    try:
        from IPython.terminal.ipapp import TerminalIPythonApp
    except ImportError:
        return False

    # argv=[] keeps IPython away from this program's command line. Its own
    # banner is replaced by ours.
    app = TerminalIPythonApp.instance(user_ns=ns, display_banner=False)
    app.initialize(argv=[])
    app.shell.display_formatter.formatters['text/plain'].for_type(int, _pretty_hex)
    print(banner)
    app.start()
    return True


def run_plain(ns: dict[str, Any], banner: str) -> None:
    """Run the standard Python REPL over ``ns``, with tab completion."""
    try:
        import readline
        import rlcompleter
    except ImportError:
        pass
    else:
        readline.set_completer(rlcompleter.Completer(ns).complete)
        readline.parse_and_bind('tab: complete')

    # code.interact() would write the banner to stderr.
    print(banner)
    displayhook = sys.displayhook
    sys.displayhook = hex_displayhook
    try:
        code.interact(banner='', local=ns, exitmsg='')
    finally:
        sys.displayhook = displayhook


def run(ns: dict[str, Any], banner: str) -> None:
    if not run_ipython(ns, banner):
        run_plain(ns, banner + '\n(plain Python REPL: IPython is not installed)')


# --- command line -------------------------------------------------------


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = rwmem.cli.build_parser(
        'rwmem-shell',
        'Python shell with a register target opened: IPython when installed, the plain REPL '
        'otherwise. Registers are read and written by address, and by name with a register '
        'database (-r); with --host they are accessed on another device over ssh. The options '
        'may be given before or after the mode.',
    )
    return rwmem.cli.parse_args(p, argv)


def main(argv: list[str] | None = None) -> int:
    ns = parse_args(argv)

    try:
        rf = RegisterFile(ns.regdb) if ns.regdb else None
    except Exception as e:  # noqa: BLE001 - any load error is fatal here
        print(f'Error: {e}', file=sys.stderr)
        return 1

    try:
        conn = rwmem.cli.connect(ns)
    except RemoteError as e:
        print(f'Error: {e}', file=sys.stderr)
        if rf is not None:
            rf.close()
        return 1

    shell = Shell(ns, conn, rf)
    try:
        run(namespace(shell), banner(shell))
    finally:
        shell.close()

    return 0


if __name__ == '__main__':
    sys.exit(main())
