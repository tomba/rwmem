"""Command line for rwmem-tui.

    rwmem-tui [options] mmap [FILE] [options]
    rwmem-tui [options] i2c BUS:ADDR [options]

Registers come from a register database (-r), from ad-hoc --range blocks,
or both. With --host, all accesses run on that device over ssh. The options
may be given before or after the mode, as with rwmem.
"""

from __future__ import annotations

import argparse
import sys

import rwmem.cli
from rwmem.convert import registerfile_to_unpacked
from rwmem.enums import Endianness
from rwmem.gen import UnpackedRegBlock, UnpackedRegFile, UnpackedRegister
from rwmem.registerfile import RegisterFile
from rwmem.remote import RemoteError


def parse_range(s: str) -> tuple[int, int]:
    """'ADDR+LEN' or 'ADDR-END' -> (addr, length)."""
    try:
        if '+' in s:
            a, b = s.split('+', 1)
            addr, length = int(a, 0), int(b, 0)
        elif '-' in s:
            a, b = s.split('-', 1)
            addr, end = int(a, 0), int(b, 0)
            length = end - addr
        else:
            raise ValueError
    except ValueError:
        raise argparse.ArgumentTypeError(
            f"bad range '{s}', expected ADDR+LEN or ADDR-END"
        ) from None
    if length <= 0:
        raise argparse.ArgumentTypeError(f"bad range '{s}', length must be positive")
    return addr, length


def range_block_name(addr: int) -> str:
    return f'{addr:#x}'


def range_block(
    addr: int,
    length: int,
    data_size: int,
    data_endianness: Endianness,
    addr_size: int,
    addr_endianness: Endianness,
) -> UnpackedRegBlock:
    """A block covering a raw range, one register per data word."""
    width = max(2, ((length - 1).bit_length() + 3) // 4)
    regs = [UnpackedRegister(f'0x{off:0{width}x}', off) for off in range(0, length, data_size)]
    return UnpackedRegBlock(
        range_block_name(addr),
        addr,
        length,
        regs,
        addr_endianness,
        addr_size,
        data_endianness,
        data_size,
    )


def build_parser() -> argparse.ArgumentParser:
    p = rwmem.cli.build_parser(
        'rwmem-tui',
        'Interactive register browser. Registers come from a register database '
        '(-r), from --range blocks, or both; with --host they are accessed on another '
        'device over ssh. The options may be given before or after the mode.',
    )
    p.add_argument(
        '-i',
        '--interval',
        type=float,
        default=0.5,
        help='poll interval in seconds (default 0.5)',
    )
    p.add_argument(
        '--base',
        action='append',
        default=[],
        metavar='[BLOCK=]ADDR',
        help='access BLOCK at ADDR instead of its regdb offset (repeatable); '
        'BLOCK may be omitted when there is only one block',
    )
    p.add_argument(
        '--ignore-base',
        action='store_true',
        help='access every block at address 0, e.g. on a register dump file',
    )
    p.add_argument(
        '--range',
        action='append',
        default=[],
        type=parse_range,
        metavar='ADDR+LEN|ADDR-END',
        help='show a raw address range as a block (repeatable)',
    )

    return p


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    p = build_parser()
    ns = rwmem.cli.parse_args(p, argv)

    if not ns.regdb and not ns.range:
        p.error('give a register database (-r) and/or at least one --range')

    return ns


def build_regfile(ns: argparse.Namespace) -> UnpackedRegFile:
    name = 'ranges'
    blocks: list[UnpackedRegBlock] = []

    if ns.regdb:
        with RegisterFile(ns.regdb) as rf:
            regfile = registerfile_to_unpacked(rf)
        name = regfile.name
        blocks.extend(regfile.blocks)

    data_size, data_endianness = ns.data or rwmem.cli.DEFAULT_DATA[ns.mode]
    addr_size, addr_endianness = ns.addr or rwmem.cli.DEFAULT_ADDR

    for addr, length in ns.range:
        blocks.append(
            range_block(addr, length, data_size, data_endianness, addr_size, addr_endianness)
        )

    return UnpackedRegFile(name, blocks)


def parse_bases(specs: list[str], regfile: UnpackedRegFile) -> dict[str, int]:
    """'[BLOCK=]ADDR' specs -> {block name: address}."""
    bases: dict[str, int] = {}
    for spec in specs:
        name, sep, addr_str = spec.rpartition('=')
        if not sep:
            if len(regfile.blocks) != 1:
                raise ValueError(f'--base {spec!r}: give BLOCK=ADDR, there are several blocks')
            name = regfile.blocks[0].name
        try:
            bases[name] = int(addr_str, 0)
        except ValueError:
            raise ValueError(f'--base {spec!r}: bad address {addr_str!r}') from None
    return bases


def main(argv: list[str] | None = None) -> int:
    ns = parse_args(argv)

    # Import the app, and with it textual, before opening a connection: a
    # missing dependency must not leave an ssh connection and an agent
    # behind. After parsing, so that --help does not need textual.
    try:
        from .app import RwmemTui
        from .model import Model
        from .session import Session
    except ImportError as e:
        print(f'Error: {e}\nrwmem-tui needs Textual: pip install rwmem[tui]', file=sys.stderr)
        return 1

    try:
        regfile = build_regfile(ns)
        bases = parse_bases(ns.base, regfile)
        if ns.ignore_base:
            # --ignore-base is about database offsets; a --range is an
            # address given by the user and stays where it is.
            for addr, _ in ns.range:
                bases.setdefault(range_block_name(addr), addr)
        model = Model(regfile, bases=bases, ignore_base=ns.ignore_base)
    except Exception as e:  # noqa: BLE001 - any load or validation error is fatal here
        print(f'Error: {e}', file=sys.stderr)
        return 1

    try:
        conn = rwmem.cli.connect(ns)
    except RemoteError as e:
        print(f'Error: {e}', file=sys.stderr)
        return 1

    if ns.mode == 'mmap':
        session = Session('mmap', file=ns.file, conn=conn)
    else:
        bus, addr = ns.bus_addr
        session = Session('i2c', i2c_bus=bus, i2c_addr=addr, conn=conn)

    try:
        RwmemTui(session, model, ns.interval).run()
    finally:
        session.close()

    return 0


if __name__ == '__main__':
    sys.exit(main())
