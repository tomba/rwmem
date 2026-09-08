#!/usr/bin/env python3

"""Tests for rwmem-shell.

The shell's helpers are tested on a copy of test.bin, locally and through
an agent subprocess. The REPLs are driven with scripted input; IPython
itself is not started here.
"""

import builtins
import contextlib
import io
import os
import shutil
import sys
import tempfile
import unittest
from typing import ClassVar
from unittest import mock

import rwmem as rw
from rwmem import gen, shell
from rwmem.enums import Endianness
from rwmem.remote import RemoteConnection, RemoteError
from rwmem.shell import (
    Shell,
    banner,
    format_spec,
    hex_displayhook,
    namespace,
    parse_args,
    parse_spec,
    resolve,
)
from rwmem.target import Target

TEST_DIR = os.path.dirname(os.path.abspath(__file__))
BIN_PATH = TEST_DIR + '/test.bin'
REGDB_PATH = TEST_DIR + '/test.regdb'
PY_DIR = os.path.dirname(TEST_DIR)


class CliTests(unittest.TestCase):
    def test_parser(self):
        ns = parse_args(['mmap'])
        self.assertEqual((ns.file, ns.regdb, ns.host), ('/dev/mem', None, None))
        self.assertIsNone(ns.data)

        ns = parse_args(['-r', 'x.regdb', '--host', 'h', 'mmap', '/dev/mem0', '-d', '16be'])
        self.assertEqual((ns.file, ns.regdb, ns.host), ('/dev/mem0', 'x.regdb', 'h'))
        self.assertEqual(ns.data, (2, Endianness.Big))

        ns = parse_args(['i2c', '1:0x45', '-a', '16be'])
        self.assertEqual(ns.bus_addr, (1, 0x45))
        self.assertEqual(ns.addr, (2, Endianness.Big))
        self.assertIsNone(ns.data)

        for args in ([], ['i2c'], ['mmap', '-a', '8']):
            with self.assertRaises(SystemExit, msg=args), contextlib.redirect_stderr(io.StringIO()):
                parse_args(args)


class Base:
    # Nested so that discovery does not run the shared tests on the base
    # itself; only the two concrete subclasses below are collected.

    class ShellTests(unittest.TestCase):
        remote = False

        def setUp(self):
            self.tmpdir = tempfile.mkdtemp()
            self.bin_path = os.path.join(self.tmpdir, 'test.bin')
            shutil.copy(BIN_PATH, self.bin_path)
            with open(BIN_PATH, 'rb') as f:
                self.data = f.read()

            argv = ['mmap', self.bin_path, '-r', REGDB_PATH, '-d', '32le']
            self.conn = None
            if self.remote:
                # The agent is a local subprocess; the host only shows in the banner.
                argv = ['--host', 'h'] + argv
                self.conn = RemoteConnection(
                    None, python=sys.executable, env={'PYTHONPATH': PY_DIR}
                )
            self.shell = Shell(parse_args(argv), self.conn, rw.RegisterFile(REGDB_PATH))

        def tearDown(self):
            self.shell.close()
            shutil.rmtree(self.tmpdir)

        def _le(self, off, size):
            return int.from_bytes(self.data[off : off + size], 'little')

        def _be(self, off, size):
            return int.from_bytes(self.data[off : off + size], 'big')

        def _file_bytes(self, off, size):
            with open(self.bin_path, 'rb') as f:
                f.seek(off)
                return f.read(size)

        def test_rd(self):
            self.assertEqual(self.shell.rd(0), self._le(0, 4))
            self.assertEqual(self.shell.rd(0x10, 8), self.data[0x10])
            self.assertEqual(self.shell.rd(0x10, '16be'), self._be(0x10, 2))
            self.assertEqual(self.shell.rd(0x100, 64), self._le(0x100, 8))
            # Only the endianness: the size stays -d's.
            self.assertEqual(self.shell.rd(0x10, 'be'), self._be(0x10, 4))

            with self.assertRaises(ValueError):
                self.shell.rd(0, 12)

        def test_wr(self):
            self.shell.wr(0x20, 0x12345678)
            self.assertEqual(self.shell.rd(0x20), 0x12345678)
            self.assertEqual(self._file_bytes(0x20, 4), bytes.fromhex('78563412'))

            self.shell.wr(0x24, 0xABCD, '16be')
            self.assertEqual(self._file_bytes(0x24, 2), bytes.fromhex('abcd'))

        def test_opts(self):
            opts = self.shell.opts
            self.assertEqual((opts.d, opts.a), ('32le', None))
            self.assertEqual(repr(opts), 'd=32le')

            opts.d = '16be'
            self.assertEqual(opts.d, '16be')
            self.assertEqual(self.shell.rd(0x10), self._be(0x10, 2))
            opts.d = 8
            self.assertEqual(self.shell.rd(0x10), self.data[0x10])
            # The call's endianness goes with the session's size.
            self.assertEqual(self.shell.rd(0x10, 'be'), self.data[0x10])
            opts.d = None
            self.assertIsNone(opts.d)
            # Now the block's sizes: SENSOR_A is 32-bit little-endian.
            self.assertEqual(self.shell.rd(0), self._le(0, 4))

            with self.assertRaises(ValueError):
                opts.d = 'x'
            # The address size is the session's, and mmap has none.
            self.assertIsNone(opts.a)
            with self.assertRaises(AttributeError):
                opts.a = '16be'

        def test_windows_are_reused(self):
            def window(addr, length):
                return self.shell._target(addr, length)

            t = window(0x100, 0x10)
            self.assertIs(window(0x100, 4), t)
            self.assertIs(window(0x10C, 4), t)
            self.assertIs(window(0x104, 8), t)
            # These reach past the end of it.
            self.assertIsNot(window(0x10E, 4), t)
            self.assertIsNot(window(0x100, 0x20), t)
            self.assertIsNot(window(0x200, 4), t)

            with self.assertRaises(ValueError):
                window(-1, 4)
            with self.assertRaises(ValueError):
                window(0, 0)

        def test_dump(self):
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                self.shell.dump(0x100, 0x10)
            expected = ''.join(
                f'{a:#010x} = {self._le(a, 4):#010x}\n' for a in range(0x100, 0x110, 4)
            )
            self.assertEqual(out.getvalue(), expected)

            # 16-bit big-endian words; the trailing byte does not make a word.
            out = io.StringIO()
            with contextlib.redirect_stdout(out):
                self.shell.dump(0x200, 7, '16be')
            expected = ''.join(
                f'{a:#010x} = {self._be(a, 2):#06x}\n' for a in range(0x200, 0x206, 2)
            )
            self.assertEqual(out.getvalue(), expected)

        def test_mrf(self):
            mrf = self.shell.mrf
            self.assertEqual(list(mrf), list(self.shell.rf))
            self.assertEqual(mrf['SENSOR_A.STATUS_REG'], self.data[0])
            # A register with its own size and endianness, from the database.
            self.assertEqual(mrf['MEMORY_CTRL.ADDR_REG'], self._be(0x200, 8))

            mrf['SENSOR_A.CONTROL_REG'] = 0x5A
            self.assertEqual(self.shell.rd(1, 8), 0x5A)

        def test_namespace_and_banner(self):
            ns = namespace(self.shell)
            self.assertEqual(sorted(ns), ['conn', 'dump', 'mrf', 'opts', 'rd', 'rf', 'rw', 'wr'])
            self.assertIs(ns['rw'], rw)
            self.assertIs(ns['conn'], self.conn)
            self.assertIs(ns['rf'], self.shell.rf)
            self.assertIs(ns['mrf'], self.shell.mrf)
            self.assertIs(ns['opts'], self.shell.opts)
            self.assertEqual(ns['rd'](0), self._le(0, 4))

            # The test agent is local, so the host it reports is None.
            host = f' on {self.conn.host}' if self.remote else ''
            self.assertEqual(
                banner(self.shell),
                f'rwmem-shell: mmap {self.bin_path}{host}, d=32le, '
                'blocks: SENSOR_A, SENSOR_B, MEMORY_CTRL',
            )

        def test_block_names(self):
            self.assertEqual(shell.block_names([]), '')
            self.assertEqual(shell.block_names(['A', 'B']), 'A, B')
            names = [f'BLOCK_{i:02}' for i in range(20)]
            self.assertEqual(shell.block_names(names, 30), 'BLOCK_00, BLOCK_01, BLOCK_02, ...')
            # A first name longer than the width is shown whole.
            self.assertEqual(shell.block_names(['X' * 40, 'Y'], 30), 'X' * 40 + ', ...')

        def test_close(self):
            self.shell.rd(0)
            # A reference the user keeps, as IPython's output history does.
            r = self.shell.mrf.reg('SENSOR_A.STATUS_REG')

            self.shell.close()
            self.shell.close()
            self.assertEqual(self.shell._targets, [])
            if self.conn is not None:
                self.assertTrue(self.conn.closed)

            del r


class LocalShellTests(Base.ShellTests):
    remote = False


class RemoteShellTests(Base.ShellTests):
    remote = True


class RegdbDefaultsTests(unittest.TestCase):
    """Without -d, the block containing the address gives the sizes."""

    def setUp(self):
        with open(BIN_PATH, 'rb') as f:
            self.data = f.read()
        self.shell = Shell(
            parse_args(['mmap', BIN_PATH, '-r', REGDB_PATH]), None, rw.RegisterFile(REGDB_PATH)
        )
        self.addCleanup(self.shell.close)

    def _le(self, off, size):
        return int.from_bytes(self.data[off : off + size], 'little')

    def _be(self, off, size):
        return int.from_bytes(self.data[off : off + size], 'big')

    def test_block_sizes(self):
        sh = self.shell
        # SENSOR_A is 32-bit little-endian, MEMORY_CTRL 32-bit big-endian.
        self.assertEqual(sh.rd(0), self._le(0, 4))
        self.assertEqual(sh.rd(0x200), self._be(0x200, 4))
        self.assertEqual(sh.rd(0x2FC), self._be(0x2FC, 4))
        # The call's size with the block's endianness, and the other way round.
        self.assertEqual(sh.rd(0x200, 16), self._be(0x200, 2))
        self.assertEqual(sh.rd(0x200, 'le'), self._le(0x200, 4))

        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            sh.dump(0x200, 8)
        self.assertEqual(
            out.getvalue(),
            f'0x00000200 = {self._be(0x200, 4):#010x}\n0x00000204 = {self._be(0x204, 4):#010x}\n',
        )

    def test_opts_win(self):
        sh = self.shell
        sh.opts.d = '8'
        self.assertEqual(sh.rd(0x200), self.data[0x200])
        sh.opts.d = 'le'
        self.assertEqual(sh.rd(0x200), self._le(0x200, 4))
        sh.opts.d = None
        self.assertEqual(sh.rd(0x200), self._be(0x200, 4))


class ShellWithoutRegdbTests(unittest.TestCase):
    def test_no_regdb(self):
        with open(BIN_PATH, 'rb') as f:
            data = f.read()
        sh = Shell(parse_args(['mmap', BIN_PATH, '-d', '8']))
        try:
            self.assertIsNone(sh.rf)
            self.assertIsNone(sh.mrf)
            self.assertEqual(sh.rd(3), data[3])
            self.assertEqual(sh.rd(4, '32le'), int.from_bytes(data[4:8], 'little'))
            self.assertEqual(banner(sh), f'rwmem-shell: mmap {BIN_PATH}, d=8')
        finally:
            sh.close()


class FakeI2CTarget(Target):
    """Stands in for I2CTarget, which needs a bus: records how it was opened
    and what was accessed, and reads back a constant."""

    instances: ClassVar[list] = []

    def __init__(
        self, bus, dev, offset, length, addr_endianness, addr_size, data_endianness, data_size
    ):
        self.args = (
            bus,
            dev,
            offset,
            length,
            addr_endianness,
            addr_size,
            data_endianness,
            data_size,
        )
        self.calls = []
        self.closed = False
        FakeI2CTarget.instances.append(self)

    def read(
        self,
        addr,
        data_size=None,
        data_endianness=Endianness.Default,
        addr_size=None,
        addr_endianness=Endianness.Default,
    ):
        self.calls.append(('read', addr, data_size, data_endianness, addr_size, addr_endianness))
        return 0x5A

    def write(
        self,
        addr,
        value,
        data_size=None,
        data_endianness=Endianness.Default,
        addr_size=None,
        addr_endianness=Endianness.Default,
    ):
        self.calls.append(
            ('write', addr, value, data_size, data_endianness, addr_size, addr_endianness)
        )

    def close(self):
        self.closed = True


class I2CShellTests(unittest.TestCase):
    def setUp(self):
        FakeI2CTarget.instances = []
        patcher = mock.patch.object(shell, 'I2CTarget', FakeI2CTarget)
        patcher.start()
        self.addCleanup(patcher.stop)

    def test_one_device_target(self):
        sh = Shell(parse_args(['i2c', '3:0x10', '-a', '16be']))
        try:
            self.assertEqual(sh.rd(0), 0x5A)
            sh.wr(0x160, 0x12, '16be')
            sh.rd(0xFFFF)

            # The device is opened once, addressed as the session is and
            # covering its whole address space.
            self.assertEqual(len(FakeI2CTarget.instances), 1)
            t = FakeI2CTarget.instances[0]
            self.assertEqual(
                t.args, (3, 0x10, 0, 1 << 16, Endianness.Big, 2, Endianness.Default, 1)
            )
            self.assertEqual(
                t.calls,
                [
                    ('read', 0, 1, Endianness.Default, None, Endianness.Default),
                    ('write', 0x160, 0x12, 2, Endianness.Big, None, Endianness.Default),
                    ('read', 0xFFFF, 1, Endianness.Default, None, Endianness.Default),
                ],
            )
            self.assertIs(sh._target(0, 1), t)

            self.assertEqual(repr(sh.opts), 'd=None a=16be')
            with self.assertRaises(AttributeError):
                sh.opts.a = '8'
            self.assertEqual(banner(sh), 'rwmem-shell: i2c 3:0x10, d=None a=16be')
        finally:
            sh.close()
        self.assertTrue(t.closed)
        self.assertIsNone(sh._device)

    def test_addressing(self):
        def opened():
            return FakeI2CTarget.instances[-1].args[2:6]

        # Without -a and a database: 8-bit addresses.
        sh = Shell(parse_args(['i2c', '3:0x10']))
        try:
            self.assertEqual(sh.opts.a, '8')
            sh.rd(0)
            self.assertEqual(opened(), (0, 1 << 8, Endianness.Default, 1))
        finally:
            sh.close()

        # A database whose blocks share an address size supplies it, and
        # the block's data size applies as well.
        block = gen.UnpackedRegBlock(
            'SENSOR',
            0,
            0x10000,
            [gen.UnpackedRegister('ID', 0)],
            Endianness.Big,
            2,
            Endianness.Big,
            1,
        )
        with io.BytesIO() as f:
            gen.UnpackedRegFile('SENSOR', [block]).pack_to(f)
            regdb = f.getvalue()
        argv = ['i2c', '3:0x10', '-r', 'sensor.regdb']
        sh = Shell(parse_args(argv), None, rw.RegisterFile(regdb))
        try:
            self.assertEqual(sh.opts.a, '16be')
            sh.rd(0)
            self.assertEqual(opened(), (0, 1 << 16, Endianness.Big, 2))
            self.assertEqual(
                FakeI2CTarget.instances[-1].calls,
                [('read', 0, 1, Endianness.Big, None, Endianness.Default)],
            )
        finally:
            sh.close()

        # -a wins over the database.
        sh = Shell(parse_args(argv + ['-a', '8']), None, rw.RegisterFile(regdb))
        try:
            self.assertEqual(sh.opts.a, '8')
        finally:
            sh.close()

        # test.regdb's blocks disagree on the address size, so the default
        # applies; the data sizes still come from the block at the address.
        sh = Shell(
            parse_args(['i2c', '3:0x10', '-r', REGDB_PATH]), None, rw.RegisterFile(REGDB_PATH)
        )
        try:
            self.assertEqual(sh.opts.a, '8')
            sh.rd(0x200)
            sh.rd(0)
            self.assertEqual(opened(), (0, 1 << 8, Endianness.Default, 1))
            self.assertEqual(
                FakeI2CTarget.instances[-1].calls,
                [
                    ('read', 0x200, 4, Endianness.Big, None, Endianness.Default),
                    ('read', 0, 4, Endianness.Little, None, Endianness.Default),
                ],
            )
        finally:
            sh.close()

    def test_dump(self):
        sh = Shell(parse_args(['i2c', '3:0x10', '-a', '16be']))
        out = io.StringIO()
        try:
            with contextlib.redirect_stdout(out):
                sh.dump(0x100, 3)
        finally:
            sh.close()
        # Addresses are shown at the width of -a.
        self.assertEqual(out.getvalue(), '0x0100 = 0x5a\n0x0101 = 0x5a\n0x0102 = 0x5a\n')


class SpecTests(unittest.TestCase):
    def test_parse_spec(self):
        D, B, L = Endianness.Default, Endianness.Big, Endianness.Little
        self.assertEqual(parse_spec(None), (None, D))
        self.assertEqual(parse_spec(32), (4, D))
        self.assertEqual(parse_spec('16be'), (2, B))
        self.assertEqual(parse_spec('8le'), (1, L))
        self.assertEqual(parse_spec('be'), (None, B))
        self.assertEqual(parse_spec((2, B)), (2, B))
        for bad in ('', 'x', '12', '0', '128', '16BE', 12):
            with self.assertRaises(ValueError, msg=bad):
                parse_spec(bad)

    def test_format_spec(self):
        self.assertEqual(format_spec(4, Endianness.Default), '32')
        self.assertEqual(format_spec(2, Endianness.Big), '16be')
        self.assertEqual(format_spec(None, Endianness.Little), 'le')
        self.assertIsNone(format_spec(None, Endianness.Default))

    def test_resolve(self):
        D, B = Endianness.Default, Endianness.Big
        self.assertEqual(resolve((None, D), (2, D), (4, D)), (2, D))
        self.assertEqual(resolve((None, B), (2, D), (4, D)), (2, B))
        self.assertEqual(resolve((None, D), (None, D), (4, D)), (4, D))


def scripted_input(lines):
    """A replacement for input() that hands out lines, then EOF."""
    it = iter(lines)

    def read(prompt=''):
        try:
            return next(it)
        except StopIteration:
            raise EOFError from None

    return read


class ReplTests(unittest.TestCase):
    def test_hex_displayhook(self):
        out = io.StringIO()
        with contextlib.redirect_stdout(out):
            for value in (255, -1, True, None, 'x', Endianness.Big, [1]):
                hex_displayhook(value)
        self.assertEqual(out.getvalue(), "0xff\n-0x1\nTrue\n'x'\n<Endianness.Big: 1>\n[1]\n")
        self.assertEqual(builtins._, [1])

    def test_pretty_hex(self):
        texts = []

        class P:
            def text(self, s):
                texts.append(s)

        shell._pretty_hex(255, P(), False)
        shell._pretty_hex(True, P(), False)
        shell._pretty_hex(Endianness.Big, P(), False)
        self.assertEqual(texts, ['0xff', 'True', '<Endianness.Big: 1>'])

    def test_run_plain(self):
        ns = {'x': 0x1234}
        out = io.StringIO()
        displayhook = sys.displayhook
        with (
            mock.patch('builtins.input', scripted_input(['x', 'x + 1', "'s'"])),
            contextlib.redirect_stdout(out),
            contextlib.redirect_stderr(io.StringIO()),
        ):
            shell.run_plain(ns, 'hello')
        self.assertIs(sys.displayhook, displayhook)
        self.assertEqual(out.getvalue(), "hello\n0x1234\n0x1235\n's'\n")

    def test_run_falls_back_without_ipython(self):
        out = io.StringIO()
        with (
            mock.patch.dict(sys.modules, {'IPython.terminal.ipapp': None}),
            mock.patch('builtins.input', scripted_input(['1'])),
            contextlib.redirect_stdout(out),
            contextlib.redirect_stderr(io.StringIO()),
        ):
            shell.run({}, 'hello')
        self.assertEqual(
            out.getvalue(),
            'hello\n(plain Python REPL: IPython is not installed)\n0x1\n',
        )


class MainTests(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.bin_path = os.path.join(self.tmpdir, 'test.bin')
        shutil.copy(BIN_PATH, self.bin_path)

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def test_main(self):
        seen = {}

        def fake_run(ns, banner):
            seen['ns'] = ns
            seen['banner'] = banner
            seen['value'] = ns['rd'](0)

        with mock.patch.object(shell, 'run', fake_run):
            self.assertEqual(shell.main(['mmap', self.bin_path, '-r', REGDB_PATH]), 0)

        self.assertEqual(
            sorted(seen['ns']), ['conn', 'dump', 'mrf', 'opts', 'rd', 'rf', 'rw', 'wr']
        )
        self.assertIn('rwmem-shell: mmap', seen['banner'])
        with open(BIN_PATH, 'rb') as f:
            self.assertEqual(seen['value'], int.from_bytes(f.read(4), sys.byteorder))

        # Everything was closed after the REPL returned.
        sh = seen['ns']['rd'].__self__
        self.assertEqual(sh._targets, [])
        self.assertIsNone(sh.rf._map)

    def test_bad_regdb(self):
        err = io.StringIO()
        with mock.patch.object(shell, 'run') as run, contextlib.redirect_stderr(err):
            self.assertEqual(shell.main(['mmap', self.bin_path, '-r', '/nonexistent.regdb']), 1)
        run.assert_not_called()
        self.assertIn('Error:', err.getvalue())

    def test_connection_failure(self):
        def no_connection(ns):
            raise RemoteError('no way')

        err = io.StringIO()
        with (
            mock.patch.object(shell.rwmem.cli, 'connect', no_connection),
            mock.patch.object(shell, 'run') as run,
            contextlib.redirect_stderr(err),
        ):
            self.assertEqual(
                shell.main(['--host', 'h', 'mmap', self.bin_path, '-r', REGDB_PATH]), 1
            )
        run.assert_not_called()
        self.assertIn('Error: no way', err.getvalue())


if __name__ == '__main__':
    unittest.main()
