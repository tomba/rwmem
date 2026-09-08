"""Command line pieces shared by rwmem-remote, rwmem-tui and rwmem-shell.

rwmem-tui and rwmem-shell describe their target the same way:

    prog [options] mmap [FILE] [options]
    prog [options] i2c BUS:ADDR [options]

with -r for a register database, --host and its companions for access
over ssh, and -d and -a for the data and address sizes of accesses
outside a database. Each program adds its own options on top.
rwmem-remote takes rwmem's own command line after the host, and shares
the remote options and the size and address parsers.
"""

from __future__ import annotations

import argparse
import itertools
import shlex

from rwmem.enums import Endianness
from rwmem.remote import DEFAULT_SSH, RemoteConnection

ENDIANNESS = {'': Endianness.Default, 'be': Endianness.Big, 'le': Endianness.Little}

# What -d and -a stand for when they are not given, per mode: 32-bit data,
# 8-bit for i2c, and 8-bit register addresses.
DEFAULT_DATA = {'mmap': (4, Endianness.Default), 'i2c': (1, Endianness.Default)}
DEFAULT_ADDR = (1, Endianness.Default)


def parse_size_endian(s: str) -> tuple[int, Endianness]:
    """'32', '16be', '8le' -> (size in bytes, endianness)."""
    digits = ''.join(itertools.takewhile(str.isdigit, s))
    ending = s[len(digits) :]
    if not digits or ending not in ENDIANNESS:
        raise argparse.ArgumentTypeError(f"bad size '{s}', expected e.g. 32, 16be, 8le")
    bits = int(digits)
    if bits == 0 or bits > 64 or bits % 8:
        raise argparse.ArgumentTypeError(f"bad size '{s}', must be 8-64 bits, multiple of 8")
    return bits // 8, ENDIANNESS[ending]


def parse_bus_addr(s: str) -> tuple[int, int]:
    parts = s.split(':')
    try:
        if len(parts) != 2:
            raise ValueError
        return int(parts[0], 0), int(parts[1], 0)
    except ValueError:
        raise argparse.ArgumentTypeError(f"bad I2C target '{s}', expected BUS:ADDR") from None


def parse_env(s: str) -> tuple[str, str]:
    """'K=V' -> (K, V)."""
    key, sep, value = s.partition('=')
    if not sep or not key:
        raise argparse.ArgumentTypeError(f"bad environment '{s}', expected K=V")
    return key, value


def add_remote_options(p: argparse.ArgumentParser) -> None:
    """Add the options of a connection to a device, all but the host itself.

    The host is the caller's, a positional in rwmem-remote and --host in
    the others; ``connect`` reads it as ``host`` along with these.
    """
    p.add_argument(
        '--installed',
        action='store_true',
        help='use pyrwmem installed on the host instead of shipping it',
    )
    p.add_argument(
        '--env',
        action='append',
        default=[],
        type=parse_env,
        metavar='K=V',
        help='agent environment (repeatable)',
    )
    p.add_argument('--python', default='python3', help='python executable on the host')
    p.add_argument('--ssh', default=' '.join(DEFAULT_SSH), metavar='CMD', help='ssh command prefix')


def build_parser(prog: str, description: str) -> argparse.ArgumentParser:
    """A parser with the shared options and the mode and target positionals.

    The caller adds its own options to it, and parses with ``parse_args``.
    """
    p = argparse.ArgumentParser(
        prog=prog,
        usage='%(prog)s [options] mmap [FILE] [options]\n'
        '       %(prog)s [options] i2c BUS:ADDR [options]',
        description=description,
    )
    p.add_argument('-r', '--regdb', metavar='FILE', help='register database (.regdb)')
    p.add_argument('--host', metavar='HOST', help='run the accesses on HOST over ssh')
    add_remote_options(p)
    p.add_argument(
        '-a',
        '--addr',
        type=parse_size_endian,
        metavar='SIZE[ENDIAN]',
        help='register address size for accesses outside a register database, i2c only (default 8)',
    )
    p.add_argument(
        '-d',
        '--data',
        type=parse_size_endian,
        metavar='SIZE[ENDIAN]',
        help='data size for accesses outside a register database, e.g. 32, 16be, 8le '
        '(default 32, 8 for i2c)',
    )
    p.add_argument('mode', choices=('mmap', 'i2c'), help='memory-mapped or I2C target')
    p.add_argument(
        'target',
        nargs='?',
        metavar='FILE|BUS:ADDR',
        help='file to map (mmap, default /dev/mem) or the I2C target (i2c)',
    )

    return p


def parse_args(p: argparse.ArgumentParser, argv: list[str] | None = None) -> argparse.Namespace:
    """Parse the command line and fill in what depends on the mode.

    Sets ``file`` (mmap) and ``bus_addr`` (i2c). ``data`` and ``addr`` stay
    None when -d and -a are not given, so that a program can tell; what
    they stand for then is ``DEFAULT_DATA[mode]`` and ``DEFAULT_ADDR``.
    """
    # Intermixed, so that the options work on either side of the mode.
    ns = p.parse_intermixed_args(argv)

    ns.file = '/dev/mem'
    ns.bus_addr = None

    if ns.mode == 'i2c':
        if ns.target is None:
            p.error('i2c needs a BUS:ADDR argument')
        try:
            ns.bus_addr = parse_bus_addr(ns.target)
        except argparse.ArgumentTypeError as e:
            p.error(str(e))
    else:
        if ns.addr is not None:
            p.error('-a is only valid in i2c mode')
        if ns.target is not None:
            ns.file = ns.target

    return ns


def connect(ns: argparse.Namespace) -> RemoteConnection | None:
    """The connection for ``host``, or None when it is not set. Raises RemoteError."""
    if not ns.host:
        return None
    return RemoteConnection(
        ns.host,
        deploy=not ns.installed,
        ssh=shlex.split(ns.ssh),
        python=ns.python,
        env=dict(ns.env),
    )
