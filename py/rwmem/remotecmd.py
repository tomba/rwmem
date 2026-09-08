"""rwmem-remote: a stripped-down rwmem that accesses registers on another device over ssh.

    rwmem-remote [remote options] HOST <rwmem arguments>

Everything after the host is parsed like the rwmem command, without register
database support: numeric addresses only, in default, mmap and i2c modes.

    rwmem-remote buildroot 0x3022a000
    rwmem-remote buildroot -d 16 0x3022a000-0x3022a020
    rwmem-remote buildroot 0x3022a05c:10:0=0x123
    rwmem-remote buildroot i2c 1:0x45 -a 8 -d 8 0x0+4
    rwmem-remote --installed --env PYTHONPATH=/path/to/rwmem/py buildroot 0x3022a000

Remote options go before the host. By default pyrwmem is shipped to the
device, so it needs only python3; --installed uses the copy on the device
instead. --env K=V sets the agent's environment (e.g. PYTHONPATH), --python
and --ssh override the interpreter and the ssh command.
"""

from __future__ import annotations

import argparse
import sys
from collections.abc import Callable
from dataclasses import dataclass, field

import rwmem as rw
import rwmem.cli
from rwmem.remote import RemoteConnection, RemoteError


class UsageError(Exception):
    pass


def parse_int(s: str) -> int:
    try:
        return int(s, 0)
    except ValueError:
        raise UsageError(f"Invalid number '{s}'") from None


def parse(fn: Callable, s: str):
    """Run one of rwmem.cli's parsers, reporting its error as a UsageError."""
    try:
        return fn(s)
    except argparse.ArgumentTypeError as e:
        raise UsageError(str(e)) from None


@dataclass
class Op:
    base: int
    range: int
    high: int
    low: int
    custom_field: bool
    value: int | None


def parse_op(s: str, data_size: int) -> Op:
    """Parse ADDR[-END|+LEN][:HIGH[:LOW]][=VALUE], the same way rwmem does."""
    value_str = field_str = range_str = None
    range_is_len = False

    if '=' in s:
        s, value_str = s.split('=', 1)
        if not value_str:
            raise UsageError('Empty value not allowed')

    if ':' in s:
        s, field_str = s.split(':', 1)
        if not field_str:
            raise UsageError('Empty field not allowed')

    if '+' in s:
        s, range_str = s.split('+', 1)
        range_is_len = True
        if not range_str:
            raise UsageError('Empty range not allowed')
    elif '-' in s:
        s, range_str = s.split('-', 1)
        if not range_str:
            raise UsageError('Empty range not allowed')

    if not s:
        raise UsageError('Empty address not allowed')

    base = parse_int(s)

    if range_str is not None:
        rng = parse_int(range_str)
        if not range_is_len:
            if rng <= base:
                raise UsageError(f"range '{range_str}' is <= 0")
            rng -= base
    else:
        rng = data_size

    bits = data_size * 8

    if field_str is not None:
        parts = field_str.split(':')
        if len(parts) == 1:
            high = low = parse_int(parts[0])
        elif len(parts) == 2:
            high, low = parse_int(parts[0]), parse_int(parts[1])
        else:
            raise UsageError(f"Field not found '{field_str}'")
        # A negative bit number is a huge unsigned value in rwmem, so it
        # fails this same check there.
        if not 0 <= high < bits or not 0 <= low < bits:
            raise UsageError('Field bits higher than register size')
        if high < low:
            raise UsageError(f"Field high bit below low bit in '{field_str}'")
        custom_field = True
    else:
        high, low = bits - 1, 0
        custom_field = False

    value = None
    if value_str is not None:
        value = parse_int(value_str)
        if value >> bits:
            raise UsageError('Value does not fit into the register size')
        if value >> (high - low + 1):
            raise UsageError('Value does not fit into the field')

    return Op(base, rng, high, low, custom_field, value)


@dataclass
class Opts:
    mode: str
    file: str = '/dev/mem'
    i2c_bus: int = 0
    i2c_addr: int = 0
    data_size: int = 4
    data_endianness: rw.Endianness = rw.Endianness.Default
    addr_size: int = 1
    addr_endianness: rw.Endianness = rw.Endianness.Default
    write_mode: str = 'rwr'
    print_mode: str = 'rf'
    fmt: str = 'x'
    ops: list[Op] = field(default_factory=list)


def parse_rwmem_args(args: list[str]) -> Opts:
    # Default mode is shorthand for "mmap /dev/mem".
    for a in args:
        if not a.startswith('-'):
            if a not in ('mmap', 'i2c', 'list'):
                args = ['mmap', '/dev/mem', *args]
            break
    else:
        args = ['mmap', '/dev/mem', *args]

    mode = args[0]
    if mode == 'list':
        raise UsageError('list mode needs a register database, which is not supported')
    if len(args) < 2 or args[1].startswith('-'):
        raise UsageError(f'{mode} requires {"file" if mode == "mmap" else "bus:addr"} argument')
    param = args[1]

    p = argparse.ArgumentParser(
        prog='rwmem-remote [remote options] HOST [mmap FILE | i2c BUS:ADDR]',
        description='Options and addresses after the host follow the rwmem command.',
    )
    p.add_argument('-d', '--data', metavar='SIZE[ENDIAN]', help='data size, e.g. 32, 16be, 8le')
    p.add_argument('-a', '--addr', metavar='SIZE[ENDIAN]', help='address size (i2c only)')
    p.add_argument('-w', '--write', choices=['w', 'rw', 'rwr'], default='rwr', help='write mode')
    p.add_argument('-p', '--print', dest='print_mode', choices=['q', 'r', 'rf'], default='rf')
    p.add_argument('-f', '--format', choices=['x', 'd', 'b'], default='x', help='number format')
    # Accepted so that they fail with a clear message rather than a parse error.
    p.add_argument('-r', '--regs', metavar='FILE', help=argparse.SUPPRESS)
    p.add_argument('-R', '--raw', action='store_true', help=argparse.SUPPRESS)
    p.add_argument('--ignore-base', action='store_true', help=argparse.SUPPRESS)
    p.add_argument('-v', '--verbose', action='store_true', help=argparse.SUPPRESS)
    p.add_argument('ops', nargs='+', metavar='ADDR[-END|+LEN][:HIGH[:LOW]][=VALUE]')
    ns = p.parse_intermixed_args(args[2:])

    if ns.regs or ns.raw or ns.ignore_base or ns.verbose:
        raise UsageError('-r, -R, --ignore-base and -v are not supported')

    opts = Opts(mode)

    if mode == 'mmap':
        opts.file = param
        if ns.addr:
            raise UsageError('-a is only valid in i2c mode')
    else:
        opts.i2c_bus, opts.i2c_addr = parse(rwmem.cli.parse_bus_addr, param)

    if ns.data:
        opts.data_size, opts.data_endianness = parse(rwmem.cli.parse_size_endian, ns.data)
    if ns.addr:
        opts.addr_size, opts.addr_endianness = parse(rwmem.cli.parse_size_endian, ns.addr)
    opts.write_mode = ns.write
    opts.print_mode = ns.print_mode
    opts.fmt = ns.format
    opts.ops = [parse_op(s, opts.data_size) for s in ns.ops]

    return opts


# --- output, matching rwmem's formatting ------------------------------------


def value_chars(size: int, fmt: str) -> int:
    if fmt == 'x':
        return size * 2 + 2
    if fmt == 'b':
        return size * 8 + 2
    return int(size * 8 * 0.30103) + 2


def fmt_value(v: int, chars: int, fmt: str, left: bool = False) -> str:
    if fmt == 'x':
        return f'{v:#0{chars}x}'
    if fmt == 'b':
        return f'{v:#0{chars}b}'
    return f'{v:<{chars}}' if left else f'{v:{chars}}'


class Output:
    """Prints progressively, so a hanging access leaves the partial line visible."""

    def __init__(self, quiet: bool) -> None:
        self.quiet = quiet
        self.line_open = False

    def __call__(self, s: str) -> None:
        if self.quiet:
            return
        print(s, end='', flush=True)
        self.line_open = not s.endswith('\n')


def do_op(op: Op, target: rw.Target, o: Opts, out: Output) -> None:
    address_chars = o.addr_size * 2 + 2
    # rwmem's DIV_ROUND_UP(fls(range), 4), where fls() is bit_length() - 1.
    offset_chars = -(-(op.range.bit_length() - 1) // 4)
    vchars = value_chars(o.data_size, o.fmt)
    mask = ((1 << (op.high - op.low + 1)) - 1) << op.low

    off = 0
    while off < op.range:
        paddr = op.base + off

        out(f'{paddr:#0{address_chars}x} ')
        if off != paddr:
            out(f'(+{off:#0{offset_chars}x}) ')

        old = new = 0
        if o.write_mode != 'w':
            old = target.read(paddr)
            out('= ' + fmt_value(old, vchars, o.fmt))
            new = old

        if op.value is not None:
            new = (old & ~mask) | (op.value << op.low)
            out(' := ' + fmt_value(new, vchars, o.fmt))
            target.write(paddr, new)
            if o.write_mode == 'rwr':
                new = target.read(paddr)
                out(' -> ' + fmt_value(new, vchars, o.fmt))

        out('\n')

        if o.print_mode == 'rf' and op.custom_field:
            s = '  '
            if op.high == op.low:
                s += f'   {op.low:<2} = '
            else:
                s += f'{op.high:2}:{op.low:<2} = '
            if o.write_mode != 'w':
                s += fmt_value((old & mask) >> op.low, vchars, o.fmt, left=True) + ' '
            if op.value is not None:
                s += ':= ' + fmt_value(op.value, vchars, o.fmt, left=True) + ' '
                if o.write_mode == 'rwr':
                    s += '-> ' + fmt_value((new & mask) >> op.low, vchars, o.fmt, left=True) + ' '
            out(s + '\n')

        off += o.data_size


def run(conn: RemoteConnection, o: Opts, out: Output) -> None:
    for op in o.ops:
        mode = rw.MapMode.Read if op.value is None else rw.MapMode.ReadWrite
        if o.mode == 'mmap':
            target = conn.open_mmap(o.file, op.base, op.range, o.data_endianness, o.data_size, mode)
        else:
            target = conn.open_i2c(
                o.i2c_bus,
                o.i2c_addr,
                op.base,
                op.range,
                o.addr_endianness,
                o.addr_size,
                o.data_endianness,
                o.data_size,
                mode,
            )
        with target:
            do_op(op, target, o, out)


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(
        prog='rwmem-remote',
        description=__doc__,
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    rwmem.cli.add_remote_options(p)
    p.add_argument('host', help='ssh host')
    p.add_argument('rwmem_args', nargs=argparse.REMAINDER, metavar='rwmem-args')
    ns = p.parse_args(argv)
    if not ns.host:
        p.error('HOST must not be empty')

    try:
        opts = parse_rwmem_args(ns.rwmem_args)
    except UsageError as e:
        print(f'Error: {e}', file=sys.stderr)
        return 1

    out = Output(quiet=opts.print_mode == 'q')

    try:
        with rwmem.cli.connect(ns) as conn:
            run(conn, opts, out)
    except RemoteError as e:
        if out.line_open:
            print(flush=True)
        print(f'Error: {e}', file=sys.stderr)
        return 1

    return 0


if __name__ == '__main__':
    sys.exit(main())
