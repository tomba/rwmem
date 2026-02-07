"""Command-line interface for rwmem-tui."""

from __future__ import annotations

import argparse
import sys


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        prog='rwmem-tui',
        description='Interactive register browser and editor',
    )
    parser.add_argument('-r', '--regdb', metavar='REGDB', help='Path to .regdb file')

    subparsers = parser.add_subparsers(dest='mode', required=True)

    mmap_parser = subparsers.add_parser('mmap', help='Memory-mapped target')
    mmap_parser.add_argument(
        'file', nargs='?', default='/dev/mem', help='File to map (default: /dev/mem)'
    )

    i2c_parser = subparsers.add_parser('i2c', help='I2C target')
    i2c_parser.add_argument(
        'bus_addr', metavar='bus:addr', help='I2C bus and device address (e.g. 1:0x48)'
    )

    return parser.parse_args(argv)


def parse_i2c_bus_addr(bus_addr: str) -> tuple[int, int]:
    parts = bus_addr.split(':')
    if len(parts) != 2:
        print(f'Error: invalid I2C bus:addr format: {bus_addr!r}', file=sys.stderr)
        sys.exit(1)
    try:
        bus = int(parts[0], 0)
        addr = int(parts[1], 0)
    except ValueError:
        print(f'Error: invalid I2C bus:addr values: {bus_addr!r}', file=sys.stderr)
        sys.exit(1)
    return bus, addr


def main(argv: list[str] | None = None):
    args = parse_args(argv)

    from .app import RwmemTuiApp

    if args.mode == 'mmap':
        app = RwmemTuiApp(
            target_mode='mmap',
            mmap_file=args.file,
            regdb_path=args.regdb,
        )
    elif args.mode == 'i2c':
        bus, addr = parse_i2c_bus_addr(args.bus_addr)
        app = RwmemTuiApp(
            target_mode='i2c',
            i2c_bus=bus,
            i2c_addr=addr,
            regdb_path=args.regdb,
        )
    else:
        print(f'Error: unknown mode {args.mode!r}', file=sys.stderr)
        sys.exit(1)

    app.run()
