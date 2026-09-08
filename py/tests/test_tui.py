#!/usr/bin/env python3
"""Tests for rwmem-tui.

The session, model and command line parts need nothing beyond pyrwmem. The
application tests drive the Textual app headlessly and are skipped when
Textual is not installed.
"""

import argparse
import asyncio
import contextlib
import io
import os
import shutil
import sys
import tempfile
import threading
import time
import unittest
from unittest import mock

import rwmem as rw
from rwmem.enums import Endianness
from rwmem.gen import UnpackedRegBlock, UnpackedRegFile, UnpackedRegister
from rwmem.tui import cli as tui_cli
from rwmem.tui.cli import build_regfile, parse_args, parse_bases, parse_range
from rwmem.tui.model import Format, Model, field_value, format_value, set_field_value
from rwmem.tui.session import Session

try:
    import textual  # noqa: F401

    HAVE_TEXTUAL = True
except ImportError:
    HAVE_TEXTUAL = False

TEST_DIR = os.path.dirname(os.path.abspath(__file__))
BIN_PATH = TEST_DIR + '/test.bin'
REGDB_PATH = TEST_DIR + '/test.regdb'


def load_regfile():
    ns = parse_args(['-r', REGDB_PATH, 'mmap', BIN_PATH])
    return build_regfile(ns)


def make_block(name, offset, nregs=1):
    return UnpackedRegBlock(
        name,
        offset,
        4 * nregs,
        [UnpackedRegister(f'R{i}', 4 * i) for i in range(nregs)],
        Endianness.Default,
        1,
        Endianness.Little,
        4,
    )


def local_agent(env=None):
    """A RemoteConnection to an agent running as a local subprocess."""
    from rwmem.remote import RemoteConnection

    return RemoteConnection(
        None, python=sys.executable, env=env or {'PYTHONPATH': os.path.dirname(TEST_DIR)}
    )


class CliTests(unittest.TestCase):
    def test_range(self):
        self.assertEqual(parse_range('0x100+0x10'), (0x100, 0x10))
        self.assertEqual(parse_range('0x100-0x120'), (0x100, 0x20))
        for bad in ('0x100', '0x120-0x100', '0x100+0', 'x+1'):
            with self.assertRaises(argparse.ArgumentTypeError):
                parse_range(bad)

    def test_parser(self):
        ns = parse_args(
            ['--host', 'h', '--env', 'A=1', 'mmap', '--range', '0x0+0x10', '--range', '0x100-0x108']
        )
        self.assertEqual(ns.host, 'h')
        self.assertEqual(ns.env, [('A', '1')])
        self.assertEqual(ns.file, '/dev/mem')
        self.assertEqual(ns.range, [(0, 0x10), (0x100, 8)])
        self.assertIsNone(ns.data)

        ns = parse_args(['-r', 'x.regdb', 'i2c', '1:0x45', '-a', '16be'])
        self.assertEqual(ns.bus_addr, (1, 0x45))
        self.assertEqual(ns.addr, (2, Endianness.Big))
        self.assertIsNone(ns.data)

    def test_options_before_and_after_mode(self):
        # The TUI's options work on either side of the mode, like the shared ones.
        ns = parse_args(['mmap', '-r', 'x.regdb', '--host', 'h', '-i', '2'])
        self.assertEqual(
            (ns.regdb, ns.host, ns.interval, ns.file), ('x.regdb', 'h', 2.0, '/dev/mem')
        )

        ns = parse_args(['i2c', '1:0x45', '--installed', '--env', 'A=1', '--range', '0x0+0x10'])
        self.assertEqual((ns.installed, ns.env, ns.regdb), (True, [('A', '1')], None))

        # The repeatable options keep the values given on both sides.
        ns = parse_args(
            [
                '--env',
                'A=1',
                '--base',
                'X=1',
                '--range',
                '0x0+0x10',
                'mmap',
                '--env',
                'B=2',
                '--base',
                'Y=2',
                '--range',
                '0x100+0x10',
            ]
        )
        self.assertEqual(ns.env, [('A', '1'), ('B', '2')])
        self.assertEqual(ns.base, ['X=1', 'Y=2'])
        self.assertEqual(ns.range, [(0, 0x10), (0x100, 0x10)])

    def test_regdb_or_range_required(self):
        with self.assertRaises(SystemExit), contextlib.redirect_stderr(io.StringIO()):
            parse_args(['mmap', BIN_PATH])

    def test_missing_textual_does_not_connect(self):
        from rwmem import cli

        def no_connection(*args, **kwargs):
            raise AssertionError('a connection was opened before importing the app')

        argv = ['--host', 'h', 'mmap', '--range', '0x0+0x10']
        err = io.StringIO()
        with (
            mock.patch.dict(sys.modules, {'rwmem.tui.app': None}),
            mock.patch.object(cli, 'RemoteConnection', no_connection),
            contextlib.redirect_stderr(err),
        ):
            self.assertEqual(tui_cli.main(argv), 1)
        self.assertIn('Textual', err.getvalue())

    def test_bases(self):
        rf = load_regfile()
        self.assertEqual(parse_bases([], rf), {})
        self.assertEqual(parse_bases(['SENSOR_B=0x400'], rf), {'SENSOR_B': 0x400})
        with self.assertRaises(ValueError):
            parse_bases(['0x400'], rf)  # several blocks, name required
        with self.assertRaises(ValueError):
            parse_bases(['SENSOR_B=zz'], rf)

        ns = parse_args(['mmap', BIN_PATH, '--range', '0x0+0x10', '--base', '0x100'])
        one = build_regfile(ns)
        self.assertEqual(parse_bases(ns.base, one), {'0x0': 0x100})
        self.assertTrue(parse_args(['--ignore-base', '-r', REGDB_PATH, 'mmap']).ignore_base)
        self.assertTrue(parse_args(['-r', REGDB_PATH, 'mmap', '--ignore-base']).ignore_base)

    def test_build_regfile(self):
        rf = load_regfile()
        self.assertEqual([b.name for b in rf.blocks], ['SENSOR_A', 'SENSOR_B', 'MEMORY_CTRL'])

        ns = parse_args(['-r', REGDB_PATH, 'mmap', BIN_PATH, '-d', '16', '--range', '0x400+0x10'])
        rf = build_regfile(ns)
        block = rf.blocks[-1]
        self.assertEqual(block.name, '0x400')
        self.assertEqual(block.offset, 0x400)
        self.assertEqual(block.data_size, 2)
        self.assertEqual([r.name for r in block.regs], [f'0x{o:02x}' for o in range(0, 0x10, 2)])

        # Without -d, a range block gets the mode's default data size.
        ns = parse_args(['mmap', BIN_PATH, '--range', '0x0+0x10'])
        rf = build_regfile(ns)
        self.assertEqual(rf.name, 'ranges')
        self.assertEqual(rf.blocks[0].data_size, 4)


class ModelTests(unittest.TestCase):
    def test_format(self):
        self.assertEqual(format_value(0x1F, Format.HEX, 8), '0x1f')
        self.assertEqual(format_value(0x1F, Format.HEX, 12), '0x01f')
        self.assertEqual(format_value(5, Format.DEC, 8), '5')
        self.assertEqual(format_value(5, Format.BIN, 4), '0b0101')
        self.assertEqual(Format.HEX.next(), Format.DEC)
        self.assertEqual(Format.BIN.next(), Format.HEX)

    def test_fields(self):
        rf = load_regfile()
        reg = rf.blocks[0].regs[0]  # STATUS_REG: READY, ERROR, MODE
        mode = next(f for f in reg.fields if f.name == 'MODE')
        self.assertEqual((mode.high, mode.low), (7, 3))
        self.assertEqual(field_value(0b10101000, mode), 0b10101)
        self.assertEqual(set_field_value(0xFF, mode, 0), 0x07)
        self.assertEqual(set_field_value(0x00, mode, 0x1F), 0xF8)

    def test_model(self):
        m = Model(load_regfile())
        refs = m.refs_in()
        self.assertEqual(len(refs), sum(len(b.regs) for b in m.regfile.blocks))
        ref = refs[0]
        self.assertEqual(ref.key, ('SENSOR_A', 'STATUS_REG'))
        self.assertEqual(ref.addr, 0)

        self.assertFalse(m.apply(ref, 5))
        self.assertEqual(m.state(ref).value, 5)
        self.assertTrue(m.apply(ref, 6))
        self.assertTrue(m.state(ref).changed)
        self.assertFalse(m.apply(ref, 6))
        m.apply(ref, RuntimeError('boom'))
        self.assertEqual(m.state(ref).error, 'boom')

        self.assertEqual(m.watched_refs(), [])
        m.watched_regs.add(ref.key)
        self.assertEqual(m.watched_refs(), [ref])
        m.watched_blocks.add('SENSOR_B')
        self.assertEqual(len(m.watched_refs()), 1 + len(m.regfile.blocks[1].regs))
        m.watch_all = True
        self.assertEqual(len(m.watched_refs()), len(refs))

    def test_base_override(self):
        rf = load_regfile()
        m = Model(rf, bases={'SENSOR_B': 0x400})
        self.assertEqual(m.refs[('SENSOR_A', 'STATUS_REG')].addr, 0x0)
        self.assertEqual(m.refs[('SENSOR_B', 'STATUS_REG')].addr, 0x400)
        self.assertEqual(m.bases, {'SENSOR_A': 0x0, 'SENSOR_B': 0x400, 'MEMORY_CTRL': 0x200})

        m = Model(rf, ignore_base=True)
        self.assertEqual(m.refs[('MEMORY_CTRL', 'CONFIG_REG')].addr, 0x8)

        # An explicit base wins over ignore_base (how --range blocks keep theirs).
        m = Model(rf, bases={'SENSOR_B': 0x100}, ignore_base=True)
        self.assertEqual(m.refs[('SENSOR_A', 'STATUS_REG')].addr, 0x0)
        self.assertEqual(m.refs[('SENSOR_B', 'STATUS_REG')].addr, 0x100)

        with self.assertRaises(ValueError):
            Model(rf, bases={'NOPE': 0})


class SessionTests(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.bin_path = os.path.join(self.tmpdir, 'test.bin')
        shutil.copy(BIN_PATH, self.bin_path)
        self.model = Model(load_regfile())
        self.session = Session('mmap', file=self.bin_path)

    def tearDown(self):
        self.session.close()
        shutil.rmtree(self.tmpdir)

    def test_read_many_and_write(self):
        refs = self.model.refs_in()
        results = self.session.read_many(refs)
        self.assertEqual(len(results), len(refs))
        for ref, res in zip(refs, results, strict=True):
            self.assertIsInstance(res, int, ref.key)
            with rw.MMapTarget(
                self.bin_path, ref.block.offset, ref.block.size, ref.data_endianness, ref.data_size
            ) as t:
                self.assertEqual(res, t.read(ref.addr))

        ref = self.model.refs[('SENSOR_A', 'DATA_REG')]
        value = 0x1234 & ((1 << ref.bits) - 1)
        self.assertEqual(self.session.write(ref, value), value)
        self.assertEqual(self.session.read(ref), value)
        self.assertEqual(self.session.read_many([ref]), [value])

        # A masked write is a read-modify-write of the masked bits only.
        self.assertEqual(self.session.write(ref, 0xFF, 0xF0), (value & ~0xF0) | 0xF0)
        self.assertEqual(self.session.read(ref), (value & ~0xF0) | 0xF0)

    def test_closed_session_does_not_reopen(self):
        ref = self.model.refs_in()[0]
        self.session.read(ref)
        self.session.close()
        with self.assertRaises(RuntimeError):
            self.session.read(ref)
        with self.assertRaises(RuntimeError):
            self.session.write(ref, 0)
        self.assertIsInstance(self.session.read_many([ref])[0], RuntimeError)

    def test_base_override_reads(self):
        # SENSOR_B accessed at SENSOR_A's address reads SENSOR_A's memory.
        m = Model(load_regfile(), bases={'SENSOR_B': 0x0})
        a = m.refs[('SENSOR_A', 'STATUS_REG')]
        b = m.refs[('SENSOR_B', 'STATUS_REG')]
        self.assertEqual(self.session.read(b), self.session.read(a))
        self.assertEqual(b.addr, 0)

    def test_remote_session_death(self):
        from rwmem.remote import RemoteError

        conn = local_agent()
        self.addCleanup(conn.close)
        session = Session('mmap', file=self.bin_path, conn=conn)
        self.addCleanup(session.close)
        opened, never_opened = self.model.refs_in()[0], self.model.refs[('SENSOR_B', 'STATUS_REG')]
        self.assertIsInstance(session.read(opened), int)
        self.assertTrue(session.alive)

        assert conn._proc is not None
        conn._proc.kill()
        # A dead connection fails the whole batch; the app reports that once.
        with self.assertRaises(RemoteError):
            session.read_many([opened])
        self.assertFalse(session.alive)
        with self.assertRaises(RemoteError):
            session.read(opened)
        # Also for a block that was never opened: the failed open of its
        # target must not turn into a per-entry error either.
        with self.assertRaises(RemoteError):
            session.read_many([never_opened])
        with self.assertRaises(RemoteError):
            session.read_many([opened, never_opened])

        session.close()  # must not raise

    def test_open_failure_is_per_entry(self):
        model = Model(UnpackedRegFile('T', [make_block('G', 0), make_block('B', 0x10000)]))
        results = self.session.read_many(model.refs_in())
        self.assertIsInstance(results[0], int)
        self.assertIsInstance(results[1], Exception)
        self.assertEqual(self.session.description, f'mmap {self.bin_path}')

    def test_failing_open_is_tried_once_per_call(self):
        opens = []

        class CountingSession(Session):
            def _open(self, block, base):
                opens.append(block.name)
                return super()._open(block, base)

        session = CountingSession('mmap', file=self.bin_path)
        self.addCleanup(session.close)
        model = Model(UnpackedRegFile('T', [make_block('B', 0x10000, nregs=4)]))
        refs = model.refs_in()

        results = session.read_many(refs)
        self.assertEqual(opens, ['B'])
        # Every register of the block reports the same failure.
        self.assertTrue(all(r is results[0] for r in results))
        self.assertIsInstance(results[0], Exception)

        # The failure is not remembered across calls.
        session.read_many(refs)
        self.assertEqual(opens, ['B', 'B'])

    def test_close_does_not_wait_for_a_stuck_request(self):
        conn = local_agent()
        self.addCleanup(conn.close)
        session = Session('mmap', file=self.bin_path, conn=conn)

        # A worker stuck in a request holds the lock indefinitely. close()
        # must not wait for it; closing the connection is what ends the
        # request.
        session._lock.acquire()
        self.addCleanup(session._lock.release)
        done = threading.Event()

        def closer():
            session.close()
            done.set()

        thread = threading.Thread(target=closer)
        thread.start()
        self.assertTrue(done.wait(10), 'close() blocked on the lock')
        thread.join()
        self.assertTrue(conn.closed)


async def wait_until(pilot, predicate, timeout=10):
    """Let the app run until predicate() holds. Returns whether it does."""
    deadline = time.monotonic() + timeout
    while not predicate():
        if time.monotonic() > deadline:
            return False
        await pilot.pause(0.01)
    return True


def recording_tui(session, model, interval):
    """A RwmemTui that keeps the error notifications it showed."""
    from rwmem.tui.app import RwmemTui

    class RecordingTui(RwmemTui):
        def __init__(self, *args, **kwargs):
            super().__init__(*args, **kwargs)
            self.errors: list[str] = []

        def notify(
            self, message, *, title='', severity='information', timeout=None, markup=True
        ) -> None:
            if severity == 'error':
                self.errors.append(message)
            super().notify(message, title=title, severity=severity, timeout=timeout, markup=markup)

    return RecordingTui(session, model, interval)


@unittest.skipUnless(HAVE_TEXTUAL, 'textual not installed')
class AppTests(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()
        self.bin_path = os.path.join(self.tmpdir, 'test.bin')
        shutil.copy(BIN_PATH, self.bin_path)
        self.model = Model(load_regfile())
        self.session = Session('mmap', file=self.bin_path)

    def tearDown(self):
        self.session.close()
        shutil.rmtree(self.tmpdir)

    def test_app(self):
        asyncio.run(self._run())

    def test_registers_without_fields_are_leaves(self):
        asyncio.run(self._run_leaves())

    async def _run_leaves(self):
        from rwmem.tui.app import RwmemTui
        from rwmem.tui.widgets import RegisterTree

        ns = parse_args(['mmap', self.bin_path, '--range', '0x0+0x20'])
        model = Model(build_regfile(ns))
        app = RwmemTui(self.session, model, interval=0)
        async with app.run_test() as pilot:
            await pilot.pause()
            tree = app.query_one(RegisterTree)
            for key, node in tree._reg_nodes.items():
                self.assertEqual(node.allow_expand, bool(model.refs[key].reg.fields), key)
                self.assertFalse(node.allow_expand)
            self.assertEqual(len(tree._reg_nodes), 8)

    async def _run(self):
        from rwmem.tui.app import RwmemTui
        from rwmem.tui.widgets import FieldNode, RegisterTree

        app = RwmemTui(self.session, self.model, interval=0)
        async with app.run_test() as pilot:
            model = self.model
            refs = model.refs_in()

            # Nothing read yet; 'r' at the root reads everything in one go.
            self.assertTrue(all(model.state(r).value is None for r in refs))
            await pilot.press('r')
            await app.workers.wait_for_complete()
            await pilot.pause()
            self.assertTrue(all(model.state(r).value is not None for r in refs))
            self.assertEqual(app._read_count, 1)

            tree = app.query_one(RegisterTree)
            for key, node in tree._reg_nodes.items():
                self.assertEqual(node.allow_expand, bool(model.refs[key].reg.fields), key)

            # Select DATA_REG and write it through the dialog.
            ref = model.refs[('SENSOR_A', 'DATA_REG')]
            tree.move_cursor(tree._reg_nodes[ref.key])
            await pilot.pause()
            self.assertEqual(app._scope_refs(), [ref])

            await pilot.press('w')
            await pilot.pause()
            await pilot.press(*'0xabcd', 'enter')
            await app.workers.wait_for_complete()
            await pilot.pause()
            self.assertEqual(model.state(ref).value, 0xABCD)
            self.assertEqual(self.session.read(ref), 0xABCD)
            self.assertEqual(app._read_count, 2)

            # Field write is a read-modify-write.
            status = model.refs[('SENSOR_A', 'STATUS_REG')]
            node = tree._reg_nodes[status.key]
            node.expand()
            await pilot.pause()
            mode_node = next(
                c
                for c in node.children
                if isinstance(c.data, FieldNode) and c.data.field.name == 'MODE'
            )
            tree.move_cursor(mode_node)
            await pilot.pause()
            before = self.session.read(status)
            await pilot.press('w')
            await pilot.pause()
            await pilot.press(*'0x15', 'enter')
            await app.workers.wait_for_complete()
            await pilot.pause()
            after = self.session.read(status)
            self.assertEqual(after & 0x07, before & 0x07)
            self.assertEqual(after >> 3, 0x15)

            # Format cycles and polling toggles.
            await pilot.press('f')
            self.assertEqual(model.fmt, Format.DEC)
            await pilot.press('p')
            self.assertIn(status.key, model.watched_regs)
            self.assertIsNone(app._timer)  # interval 0: no timer

            app.interval = 0.05
            app._update_timer()
            self.assertIsNotNone(app._timer)
            count = app._read_count
            await pilot.pause(0.3)
            await app.workers.wait_for_complete()
            self.assertGreater(app._read_count, count)

            await pilot.press('p')
            self.assertNotIn(status.key, model.watched_regs)
            self.assertIsNone(app._timer)

    def test_poll_does_not_report_a_failing_register(self):
        asyncio.run(self._run_poll_failure())

    async def _run_poll_failure(self):
        # A block that cannot be opened, polled: the rows show the error,
        # no toast per tick. A read asked for by the user does report it.
        model = Model(UnpackedRegFile('T', [make_block('B', 0x10000)]))
        app = recording_tui(self.session, model, 0.05)
        async with app.run_test() as pilot:
            model.watch_all = True
            app._update_timer()
            self.assertIsNotNone(app._timer)
            self.assertTrue(await wait_until(pilot, lambda: app._read_count >= 3))
            self.assertEqual(app.errors, [])
            self.assertIsNotNone(app._timer)  # the session itself is fine

            model.watch_all = False
            app._update_timer()
            await app.workers.wait_for_complete()
            await pilot.press('r')
            self.assertTrue(await wait_until(pilot, lambda: len(app.errors) == 1))

    def test_write_waits_for_a_read_in_flight(self):
        asyncio.run(self._run_write_waits())

    async def _run_write_waits(self):
        # A write issued while a read holds the session goes through once
        # the read is done; it is not refused. Poll ticks meanwhile do not
        # pile up: one poll is in flight at a time.
        from rwmem.tui.widgets import RegisterTree

        app = recording_tui(self.session, self.model, 0.05)
        model = self.model
        ref = model.refs[('SENSOR_A', 'DATA_REG')]
        async with app.run_test() as pilot:
            tree = app.query_one(RegisterTree)
            tree.move_cursor(tree._reg_nodes[ref.key])
            await pilot.pause()

            # Stand in for a slow device: hold the session's lock.
            self.session._lock.acquire()
            try:
                model.watch_all = True
                app._update_timer()
                await pilot.pause(0.3)  # several ticks; one poll blocked on the lock
                self.assertEqual([w.name for w in app.workers], ['read'])

                await pilot.press('w')
                await pilot.pause()
                await pilot.press(*'0xabcd', 'enter')
                await pilot.pause()
                self.assertEqual(sorted(w.name for w in app.workers), ['read', 'write'])
                self.assertIsNone(model.state(ref).value)
            finally:
                self.session._lock.release()

            self.assertTrue(await wait_until(pilot, lambda: model.state(ref).value == 0xABCD))
            self.assertEqual(self.session.read(ref), 0xABCD)
            self.assertEqual(app.errors, [])

    def test_poll_stops_when_the_agent_dies(self):
        asyncio.run(self._run_poll_dead())

    async def _run_poll_dead(self):
        conn = local_agent()
        self.addCleanup(conn.close)
        session = Session('mmap', file=self.bin_path, conn=conn)
        self.addCleanup(session.close)
        app = recording_tui(session, self.model, 0.05)
        async with app.run_test() as pilot:
            self.model.watch_all = True
            app._update_timer()
            self.assertIsNotNone(app._timer)

            assert conn._proc is not None
            conn._proc.kill()
            # The first failing tick reports the loss and stops the polling.
            self.assertTrue(await wait_until(pilot, lambda: app._timer is None))
            self.assertFalse(session.alive)
            self.assertEqual(len(app.errors), 1, app.errors)
            self.assertIn('CONNECTION LOST', app.sub_title)

        self.assertTrue(conn.closed)  # the app closed the session on its way out


if __name__ == '__main__':
    unittest.main()
