#!/usr/bin/env python3
"""Tests for rwmem-remote.

The accesses run through an agent started as a local subprocess, on a copy
of the test binary.
"""

import contextlib
import io
import os
import shutil
import sys
import tempfile
import unittest
from unittest import mock

import rwmem as rw
from rwmem import remotecmd
from rwmem.remote import RemoteConnection, RemoteError
from rwmem.remotecmd import Op, UsageError, parse_op, parse_rwmem_args

TEST_DIR = os.path.dirname(os.path.abspath(__file__))
BIN_PATH = TEST_DIR + '/test.bin'


def local_agent(ns):
    """Stands in for rwmem.cli.connect(): an agent running as a local subprocess."""
    return RemoteConnection(
        None, python=sys.executable, env={'PYTHONPATH': os.path.dirname(TEST_DIR)}
    )


class ParseTests(unittest.TestCase):
    def test_op(self):
        self.assertEqual(parse_op('0x100', 4), Op(0x100, 4, 31, 0, False, None))
        self.assertEqual(parse_op('0x100+0x10', 4), Op(0x100, 0x10, 31, 0, False, None))
        self.assertEqual(parse_op('0x100-0x110', 4), Op(0x100, 0x10, 31, 0, False, None))
        self.assertEqual(parse_op('0x100=0x12', 2), Op(0x100, 2, 15, 0, False, 0x12))
        self.assertEqual(parse_op('0x100:7:4=0xa', 4), Op(0x100, 4, 7, 4, True, 0xA))
        self.assertEqual(parse_op('0x100:3', 1), Op(0x100, 1, 3, 3, True, None))

        bad = [
            '',
            'x',
            '0x100=',
            '0x100:',
            '0x100+',
            '0x100-',
            '0x100-0x100',  # end not after start
            '0x100:32',  # bit beyond the register
            '0x100:3:7',  # high below low
            '0x100:1:2:3',
            '0x100=0x100000000',  # value beyond the register
            '0x100:3:0=0x10',  # value beyond the field
        ]
        for s in bad:
            with self.assertRaises(UsageError, msg=s):
                parse_op(s, 4)

    def test_rwmem_args(self):
        # The default mode is mmap /dev/mem.
        o = parse_rwmem_args(['0x100'])
        self.assertEqual((o.mode, o.file), ('mmap', '/dev/mem'))
        self.assertEqual((o.data_size, o.data_endianness), (4, rw.Endianness.Default))
        self.assertEqual((o.write_mode, o.print_mode, o.fmt), ('rwr', 'rf', 'x'))
        self.assertEqual(o.ops, [Op(0x100, 4, 31, 0, False, None)])

        o = parse_rwmem_args(
            ['mmap', '/dev/mem0', '-d', '16be', '0x100+8', '-w', 'w', '-p', 'q', '-f', 'd', '0x200']
        )
        self.assertEqual((o.mode, o.file), ('mmap', '/dev/mem0'))
        self.assertEqual((o.data_size, o.data_endianness), (2, rw.Endianness.Big))
        self.assertEqual((o.write_mode, o.print_mode, o.fmt), ('w', 'q', 'd'))
        self.assertEqual(
            o.ops, [Op(0x100, 8, 15, 0, False, None), Op(0x200, 2, 15, 0, False, None)]
        )

        o = parse_rwmem_args(['i2c', '1:0x45', '-a', '16be', '-d', '8', '0x0+4'])
        self.assertEqual((o.mode, o.i2c_bus, o.i2c_addr), ('i2c', 1, 0x45))
        self.assertEqual((o.addr_size, o.addr_endianness), (2, rw.Endianness.Big))
        self.assertEqual((o.data_size, o.data_endianness), (1, rw.Endianness.Default))

        bad = [
            ['-d', '16', 'mmap', '/dev/mem0', '0x0'],  # the mode comes first, as in rwmem
            ['mmap'],  # file required
            ['i2c'],
            ['i2c', '1', '0x0'],
            ['list'],  # needs a register database
            ['-a', '8', '0x0'],  # -a is i2c only
            ['-d', '12', '0x0'],
            ['-d', '16bes', '0x0'],
            ['-r', 'x.regdb', '0x0'],
            ['-R', '0x0'],
            ['--ignore-base', '0x0'],
            ['-v', '0x0'],
        ]
        for args in bad:
            with self.assertRaises(UsageError, msg=args):
                parse_rwmem_args(args)
        with self.assertRaises(SystemExit), contextlib.redirect_stderr(io.StringIO()):
            parse_rwmem_args([])  # no address


class MainTests(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.bin_path = os.path.join(self.tmpdir, 'test.bin')
        shutil.copy(BIN_PATH, self.bin_path)

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def rwmem(self, *args):
        """Run rwmem-remote on the copy of the test binary: (exit code, stdout, stderr)."""
        out, err = io.StringIO(), io.StringIO()
        with (
            mock.patch.object(remotecmd.rwmem.cli, 'connect', local_agent),
            contextlib.redirect_stdout(out),
            contextlib.redirect_stderr(err),
        ):
            rc = remotecmd.main(['h', 'mmap', self.bin_path, *args])
        return rc, out.getvalue(), err.getvalue()

    def data(self):
        with open(self.bin_path, 'rb') as f:
            return f.read()

    def test_reads(self):
        # test.bin at 0x10: d6 70 e5 8e 03 51 d8 ae
        rc, out, err = self.rwmem('-d', '32le', '0x10')
        self.assertEqual((rc, err, out), (0, '', '0x10 (+0x0) = 0x8ee570d6\n'))

        _, out, _ = self.rwmem('-d', '32be', '0x10+8')
        self.assertEqual(out, '0x10 (+0x0) = 0xd670e58e\n0x14 (+0x4) = 0x0351d8ae\n')

        _, out, _ = self.rwmem('-d', '16le', '0x10-0x18')
        self.assertEqual(
            out,
            '0x10 (+0x0) = 0x70d6\n0x12 (+0x2) = 0x8ee5\n'
            '0x14 (+0x4) = 0x5103\n0x16 (+0x6) = 0xaed8\n',
        )

        # Address 0 has no offset column, as in rwmem.
        _, out, _ = self.rwmem('-d', '8', '0x0+3')
        self.assertEqual(out, '0x00 = 0x39\n0x01 = 0x0c\n0x02 = 0x8c\n')

        # Number formats, and the field line of a bit range.
        _, out, _ = self.rwmem('-d', '32le', '-f', 'd', '0x10')
        self.assertEqual(out, '0x10 (+0x0) =  2397401302\n')
        _, out, _ = self.rwmem('-d', '8', '-f', 'b', '0x10')
        self.assertEqual(out, '0x10 (+0x0) = 0b11010110\n')
        _, out, _ = self.rwmem('-d', '32le', '0x10:3')
        self.assertEqual(out, '0x10 (+0x0) = 0x8ee570d6\n     3  = 0x00000000 \n')

    def test_default_data_size(self):
        _, out, _ = self.rwmem('0x10')
        v = int.from_bytes(self.data()[0x10:0x14], sys.byteorder)
        self.assertEqual(out, f'0x10 (+0x0) = {v:#010x}\n')

    def test_writes(self):
        rc, out, err = self.rwmem('-d', '32le', '0x10:7:4=0xa')
        self.assertEqual((rc, err), (0, ''))
        self.assertEqual(
            out,
            '0x10 (+0x0) = 0x8ee570d6 := 0x8ee570a6 -> 0x8ee570a6\n'
            '   7:4  = 0x0000000d := 0x0000000a -> 0x0000000a \n',
        )
        self.assertEqual(self.data()[0x10:0x14], bytes.fromhex('a670e58e'))

        # -w w writes without reading, -w rw without reading back, and -p r
        # drops the field line.
        _, out, _ = self.rwmem('-d', '32le', '-w', 'w', '0x14=1')
        self.assertEqual(out, '0x14 (+0x0)  := 0x00000001\n')
        _, out, _ = self.rwmem('-d', '32le', '-w', 'rw', '0x14=2')
        self.assertEqual(out, '0x14 (+0x0) = 0x00000001 := 0x00000002\n')
        _, out, _ = self.rwmem('-d', '32le', '-p', 'r', '0x14:3=1')
        self.assertEqual(out, '0x14 (+0x0) = 0x00000002 := 0x0000000a -> 0x0000000a\n')
        self.assertEqual(self.data()[0x14:0x18], bytes.fromhex('0a000000'))

        # -p q prints nothing but still writes.
        rc, out, _ = self.rwmem('-d', '32le', '-p', 'q', '0x14=3')
        self.assertEqual((rc, out), (0, ''))
        self.assertEqual(self.data()[0x14:0x18], bytes.fromhex('03000000'))

    def test_errors(self):
        rc, out, err = self.rwmem('-d', '12', '0x0')
        self.assertEqual((rc, out), (1, ''))
        self.assertTrue(err.startswith('Error: bad size'), err)

        # A failing access on the device is reported the same way.
        rc, out, err = self.rwmem('0x2f0+0x20')
        self.assertEqual((rc, out), (1, ''))
        self.assertTrue(err.startswith('Error: '), err)

    def test_connection_failure(self):
        def no_connection(ns):
            raise RemoteError('no way')

        err = io.StringIO()
        with (
            mock.patch.object(remotecmd.rwmem.cli, 'connect', no_connection),
            contextlib.redirect_stderr(err),
        ):
            self.assertEqual(remotecmd.main(['h', '0x0']), 1)
        self.assertEqual(err.getvalue(), 'Error: no way\n')

    def test_remote_options(self):
        seen = {}

        def connect(ns):
            seen.update(vars(ns))
            raise RemoteError('stop')

        argv = ['--installed', '--env', 'A=1', '--python', 'py', '--ssh', 'ssh -p 2222']
        with (
            mock.patch.object(remotecmd.rwmem.cli, 'connect', connect),
            contextlib.redirect_stderr(io.StringIO()),
        ):
            remotecmd.main([*argv, 'h', '-d', '8', '0x0'])
        self.assertEqual(
            (seen['host'], seen['installed'], seen['env'], seen['python'], seen['ssh']),
            ('h', True, [('A', '1')], 'py', 'ssh -p 2222'),
        )
        self.assertEqual(seen['rwmem_args'], ['-d', '8', '0x0'])


if __name__ == '__main__':
    unittest.main()
