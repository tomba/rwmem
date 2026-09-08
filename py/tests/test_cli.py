#!/usr/bin/env python3
"""Tests for rwmem.cli, the command line pieces shared by the interactive tools."""

import argparse
import contextlib
import io
import unittest
from unittest import mock

from rwmem import cli
from rwmem.cli import (
    DEFAULT_ADDR,
    DEFAULT_DATA,
    add_remote_options,
    build_parser,
    connect,
    parse_args,
    parse_bus_addr,
    parse_env,
    parse_size_endian,
)
from rwmem.enums import Endianness
from rwmem.remote import DEFAULT_SSH


def parse(argv):
    return parse_args(build_parser('prog', 'test'), argv)


class ParserTests(unittest.TestCase):
    def test_size_endian(self):
        self.assertEqual(parse_size_endian('32'), (4, Endianness.Default))
        self.assertEqual(parse_size_endian('16be'), (2, Endianness.Big))
        self.assertEqual(parse_size_endian('8le'), (1, Endianness.Little))
        for bad in ('', 'x', '12', '72', '32bes'):
            with self.assertRaises(argparse.ArgumentTypeError):
                parse_size_endian(bad)

    def test_bus_addr(self):
        self.assertEqual(parse_bus_addr('1:0x45'), (1, 0x45))
        with self.assertRaises(argparse.ArgumentTypeError):
            parse_bus_addr('1')

    def test_env(self):
        self.assertEqual(parse_env('PYTHONPATH=/x'), ('PYTHONPATH', '/x'))
        self.assertEqual(parse_env('A=b=c'), ('A', 'b=c'))
        self.assertEqual(parse_env('A='), ('A', ''))
        for bad in ('', 'A', '=1'):
            with self.assertRaises(argparse.ArgumentTypeError):
                parse_env(bad)

    def test_parser(self):
        ns = parse(['--host', 'h', '--env', 'A=1', 'mmap'])
        self.assertEqual(ns.host, 'h')
        self.assertEqual(ns.env, [('A', '1')])
        self.assertEqual(ns.file, '/dev/mem')
        # Not given: the program applies the defaults where it needs them.
        self.assertEqual((ns.data, ns.addr), (None, None))
        self.assertEqual(DEFAULT_DATA['mmap'], (4, Endianness.Default))
        self.assertEqual(DEFAULT_DATA['i2c'], (1, Endianness.Default))
        self.assertEqual(DEFAULT_ADDR, (1, Endianness.Default))

        ns = parse(['-r', 'x.regdb', 'i2c', '1:0x45', '-a', '16be'])
        self.assertEqual(ns.regdb, 'x.regdb')
        self.assertEqual(ns.bus_addr, (1, 0x45))
        self.assertEqual(ns.addr, (2, Endianness.Big))
        self.assertIsNone(ns.data)

    def test_options_before_and_after_mode(self):
        # The options work on either side of the mode; the later one wins.
        ns = parse(['mmap', '-r', 'x.regdb', '--host', 'h'])
        self.assertEqual((ns.regdb, ns.host, ns.file), ('x.regdb', 'h', '/dev/mem'))
        self.assertEqual((ns.installed, ns.env, ns.python), (False, [], 'python3'))

        ns = parse(['-r', 'a', '--host', 'h', 'mmap', 'f', '-r', 'b'])
        self.assertEqual((ns.regdb, ns.host, ns.file), ('b', 'h', 'f'))

        ns = parse(['i2c', '1:0x45', '--installed', '--env', 'A=1'])
        self.assertEqual((ns.installed, ns.env, ns.regdb), (True, [('A', '1')], None))

        # The repeatable options keep the values given on both sides.
        ns = parse(['--env', 'A=1', 'mmap', '--env', 'B=2'])
        self.assertEqual(ns.env, [('A', '1'), ('B', '2')])

    def test_own_options(self):
        # A program's own options work on either side of the mode too.
        p = build_parser('prog', 'test')
        p.add_argument('-i', '--interval', type=float, default=1.0)
        p.add_argument('--base', action='append', default=[])
        ns = parse_args(p, ['--base', 'X=1', 'mmap', '-i', '2', '--base', 'Y=2'])
        self.assertEqual((ns.interval, ns.base), (2.0, ['X=1', 'Y=2']))

    def test_mode_arguments(self):
        self.assertEqual(parse(['mmap']).file, '/dev/mem')
        ns = parse(['mmap', '/dev/mem0'])
        self.assertEqual((ns.file, ns.bus_addr), ('/dev/mem0', None))
        self.assertEqual(parse(['i2c', '1:0x45']).bus_addr, (1, 0x45))

        bad = [
            [],  # no mode
            ['-r', 'x'],
            ['spi'],  # unknown mode
            ['i2c'],  # bus:addr required
            ['i2c', '1'],
            ['mmap', '-a', '8'],  # -a is i2c only
        ]
        for args in bad:
            with self.assertRaises(SystemExit, msg=args), contextlib.redirect_stderr(io.StringIO()):
                parse(args)


class ConnectTests(unittest.TestCase):
    def test_local(self):
        with mock.patch.object(cli, 'RemoteConnection') as rc:
            self.assertIsNone(connect(parse(['mmap'])))
        rc.assert_not_called()

    def test_remote(self):
        argv = ['--host', 'h', '--installed', '--python', 'py', '--env', 'A=1']
        ns = parse([*argv, '--ssh', 'ssh -p 2222', 'mmap'])
        with mock.patch.object(cli, 'RemoteConnection') as rc:
            self.assertIs(connect(ns), rc.return_value)
        rc.assert_called_once_with(
            'h', deploy=False, ssh=['ssh', '-p', '2222'], python='py', env={'A': '1'}
        )

        with mock.patch.object(cli, 'RemoteConnection') as rc:
            connect(parse(['--host', 'h', 'mmap']))
        rc.assert_called_once_with(
            'h', deploy=True, ssh=list(DEFAULT_SSH), python='python3', env={}
        )

    def test_positional_host(self):
        # rwmem-remote takes the host as a positional; connect() reads it the same way.
        p = argparse.ArgumentParser()
        add_remote_options(p)
        p.add_argument('host')
        ns = p.parse_args(['--env', 'A=1', 'h'])
        with mock.patch.object(cli, 'RemoteConnection') as rc:
            connect(ns)
        rc.assert_called_once_with(
            'h', deploy=True, ssh=list(DEFAULT_SSH), python='python3', env={'A': '1'}
        )


if __name__ == '__main__':
    unittest.main()
