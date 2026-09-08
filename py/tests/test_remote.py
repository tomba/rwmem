#!/usr/bin/env python3

import io
import os
import shlex
import shutil
import signal
import sys
import tempfile
import threading
import unittest
import zipfile
from unittest import mock

import rwmem as rw
from rwmem.remote import RemoteConnection, RemoteError, bundle_package

TEST_DIR = os.path.dirname(os.path.abspath(__file__))
BIN_PATH = TEST_DIR + '/test.bin'
REGDB_PATH = TEST_DIR + '/test.regdb'
# The directory containing the rwmem package, so that the agent subprocess
# can import it in installed mode regardless of how the tests were started.
PY_DIR = os.path.dirname(TEST_DIR)


class Base:
    # Nested so that discovery does not run the shared tests on the base
    # itself; only the two concrete subclasses below are collected.

    class RemoteTests(unittest.TestCase):
        """Tests run against a local agent subprocess, in both agent start modes."""

        deploy = False

        def setUp(self):
            self.tmpdir = tempfile.mkdtemp()
            self.bin_path = os.path.join(self.tmpdir, 'test.bin')
            shutil.copy(BIN_PATH, self.bin_path)

            with open(BIN_PATH, 'rb') as f:
                self.data = f.read()

            self.conn = RemoteConnection(
                None,
                deploy=self.deploy,
                python=sys.executable,
                env={'PYTHONPATH': PY_DIR},
            )

        def tearDown(self):
            self.conn.close()
            shutil.rmtree(self.tmpdir)

        def _be(self, off, size):
            return int.from_bytes(self.data[off : off + size], 'big')

        def _le(self, off, size):
            return int.from_bytes(self.data[off : off + size], 'little')

        def test_info(self):
            info = self.conn.info()
            self.assertEqual(info, self.conn.agent_info)
            self.assertEqual(info['byteorder'], sys.byteorder)
            origin = info['origin']
            if self.deploy:
                self.assertTrue(origin.startswith('mem:'), origin)
            else:
                self.assertTrue(origin.endswith(os.path.join('rwmem', 'agent.py')), origin)

        def test_read(self):
            with self.conn.open_mmap(self.bin_path, 0, 64, rw.Endianness.Big, 4) as t:
                self.assertIsInstance(t, rw.Target)
                for off in (0, 4, 8, 60):
                    self.assertEqual(t.read(off), self._be(off, 4))

                self.assertEqual(t.read(2, data_size=2), self._be(2, 2))
                self.assertEqual(t.read(5, data_size=1), self.data[5])
                self.assertEqual(
                    t.read(0, data_size=8, data_endianness=rw.Endianness.Little), self._le(0, 8)
                )

        def test_read_with_offset(self):
            with self.conn.open_mmap(self.bin_path, 0x100, 0x40, rw.Endianness.Little, 2) as t:
                self.assertEqual(t.read(0x100), self._le(0x100, 2))
                self.assertEqual(t.read(0x13E), self._le(0x13E, 2))
                self.assertEqual(t.read(0x110, data_size=4), self._le(0x110, 4))

        def test_write(self):
            with self.conn.open_mmap(self.bin_path, 0, 64, rw.Endianness.Little, 4) as t:
                t.write(8, 0x12345678)
                self.assertEqual(t.read(8), 0x12345678)

                t.write(16, 0xAB, data_size=1)
                self.assertEqual(t.read(16, data_size=1), 0xAB)

                t.write(24, 0x1122, data_size=2, data_endianness=rw.Endianness.Big)
                self.assertEqual(t.read(24, data_size=2, data_endianness=rw.Endianness.Big), 0x1122)

            # The writes must have reached the file, not just the agent's view.
            with open(self.bin_path, 'rb') as f:
                d = f.read()
            self.assertEqual(d[8:12], (0x12345678).to_bytes(4, 'little'))
            self.assertEqual(d[16], 0xAB)
            self.assertEqual(d[24:26], b'\x11\x22')

        def test_out_of_range(self):
            with self.conn.open_mmap(self.bin_path, 0, 64, rw.Endianness.Big, 4) as t:
                with self.assertRaises(RuntimeError):
                    t.read(64)
                with self.assertRaises(RuntimeError):
                    t.read(62)
                with self.assertRaises(RuntimeError):
                    t.write(100, 0)

                # An error must not poison the connection.
                self.assertEqual(t.read(0), self._be(0, 4))

        def test_read_only_mode(self):
            with self.conn.open_mmap(
                self.bin_path, 0, 64, rw.Endianness.Big, 4, rw.MapMode.Read
            ) as t:
                self.assertEqual(t.read(0), self._be(0, 4))
                with self.assertRaises(RuntimeError):
                    t.write(0, 1)

        def test_read_many(self):
            D = rw.Endianness.Default
            with self.conn.open_mmap(self.bin_path, 0, 64, rw.Endianness.Big, 4) as t:
                reads = [(0, None, D), (4, 2, D), (8, 8, rw.Endianness.Little), (60, 1, D)]
                expected = [t.read(addr, size, end) for addr, size, end in reads]
                self.assertEqual(t.read_many(reads), expected)
                self.assertEqual(t.read_many([]), [])

                with self.assertRaises(RemoteError) as cm:
                    t.read_many([(0, None, D), (64, None, D)])
                self.assertIn('read 1 of 2 at 0x40', str(cm.exception))

                # A failed batch must not poison the connection.
                self.assertEqual(t.read(0), expected[0])

        def test_connection_read_many(self):
            D = rw.Endianness.Default
            t1 = self.conn.open_mmap(self.bin_path, 0, 64, rw.Endianness.Big, 4)
            t2 = self.conn.open_mmap(self.bin_path, 64, 64, rw.Endianness.Little, 2)

            res = self.conn.read_many(
                [
                    (t1, 0, None, D),
                    (t2, 64, None, D),
                    (t1, 100, None, D),
                    (t2, 66, 4, rw.Endianness.Big),
                ]
            )
            self.assertEqual(res[0], self._be(0, 4))
            self.assertEqual(res[1], self._le(64, 2))
            self.assertIsInstance(res[2], RemoteError)
            self.assertEqual(res[3], self._be(66, 4))
            self.assertEqual(self.conn.read_many([]), [])

            with RemoteConnection(
                None, deploy=self.deploy, python=sys.executable, env={'PYTHONPATH': PY_DIR}
            ) as other:
                t3 = other.open_mmap(self.bin_path, 0, 64, rw.Endianness.Big, 4)
                with self.assertRaises(ValueError):
                    self.conn.read_many([(t3, 0, None, D)])

            t1.close()
            t2.close()

        def test_multiple_targets(self):
            t1 = self.conn.open_mmap(self.bin_path, 0, 64, rw.Endianness.Big, 4)
            t2 = self.conn.open_mmap(self.bin_path, 64, 64, rw.Endianness.Little, 2)

            self.assertEqual(t1.read(0), self._be(0, 4))
            self.assertEqual(t2.read(64), self._le(64, 2))

            t1.close()
            with self.assertRaises(RemoteError):
                t1.read(0)
            # Closing twice is fine.
            t1.close()

            self.assertEqual(t2.read(66), self._le(66, 2))
            t2.close()

        def test_threads_share_the_connection(self):
            # Requests from several threads are serialised on the one pipe;
            # without that, a thread reads another thread's reply.
            D = rw.Endianness.Default
            errors: list[Exception] = []

            def reader(t, off):
                try:
                    for _ in range(50):
                        self.assertEqual(t.read(off), self._be(off, 4))
                        self.assertEqual(
                            t.read_many([(off, 2, D), (off + 2, 2, D)]),
                            [self._be(off, 2), self._be(off + 2, 2)],
                        )
                except Exception as e:  # noqa: BLE001 - reported by the test
                    errors.append(e)

            with self.conn.open_mmap(self.bin_path, 0, 256, rw.Endianness.Big, 4) as t:
                threads = [threading.Thread(target=reader, args=(t, 4 * i)) for i in range(8)]
                for thread in threads:
                    thread.start()
                for thread in threads:
                    thread.join()
            self.assertEqual(errors, [])

        def test_agent_death(self):
            t = self.conn.open_mmap(self.bin_path, 0, 64, rw.Endianness.Big, 4)
            assert self.conn._proc is not None
            self.conn._proc.kill()

            with self.assertRaises(RemoteError) as cm:
                t.read(0)
            first = str(cm.exception)
            self.assertIn("while handling 'read'", first)
            self.assertTrue(self.conn.dead)

            # Later calls fail immediately with the same root cause, and
            # releasing things does not raise.
            with self.assertRaises(RemoteError) as cm:
                t.read(4)
            self.assertEqual(str(cm.exception), first)
            t.close()
            self.conn.close()

        def test_close_after_agent_death(self):
            t = self.conn.open_mmap(self.bin_path, 0, 64, rw.Endianness.Big, 4)
            assert self.conn._proc is not None
            # wait(), unlike test_agent_death, so that the writes that the
            # failed request left buffered are re-flushed by close().
            self.conn._proc.kill()
            self.conn._proc.wait()

            with self.assertRaises(RemoteError):
                t.read(0)

            # Releasing things after a death must not raise.
            t.close()
            self.conn.close()

        def test_death_does_not_mask_body_error(self):
            # The death is not noticed before the with-block ends, so closing
            # the target fails; that must not replace the body's exception.
            with self.assertRaises(ZeroDivisionError):
                with self.conn.open_mmap(self.bin_path, 0, 64, rw.Endianness.Big, 4):
                    assert self.conn._proc is not None
                    self.conn._proc.kill()
                    self.conn._proc.wait()
                    raise ZeroDivisionError('body error')

        def test_agent_fault_reports_stderr(self):
            t = self.conn.open_mmap(self.bin_path, 0, 64, rw.Endianness.Big, 4)
            assert self.conn._proc is not None
            # What a faulting register access does to the agent, without the hardware.
            os.kill(self.conn._proc.pid, signal.SIGSEGV)

            with self.assertRaises(RemoteError) as cm:
                t.read(0)
            msg = str(cm.exception)
            self.assertIn('Fatal Python error: Segmentation fault', msg)

        def test_open_failure(self):
            with self.assertRaises(RemoteError):
                self.conn.open_mmap(
                    os.path.join(self.tmpdir, 'missing'), 0, 64, rw.Endianness.Big, 4
                )
            with self.assertRaises(RemoteError):
                self.conn.open_mmap(self.bin_path, 0, 0, rw.Endianness.Big, 4)

            # Still usable afterwards.
            self.assertIn('origin', self.conn.info())

        def test_close(self):
            t = self.conn.open_mmap(self.bin_path, 0, 64, rw.Endianness.Big, 4)
            proc = self.conn._proc
            assert proc is not None

            self.conn.close()

            self.assertEqual(proc.returncode, 0)
            self.assertTrue(self.conn.closed)
            with self.assertRaises(RemoteError):
                self.conn.info()

            # Targets of a closed connection close silently.
            t.close()

            # Closing twice is fine.
            self.conn.close()

        def test_context_manager(self):
            with RemoteConnection(
                None, deploy=self.deploy, python=sys.executable, env={'PYTHONPATH': PY_DIR}
            ) as conn:
                with conn.open_mmap(self.bin_path, 0, 64, rw.Endianness.Big, 4) as t:
                    self.assertEqual(t.read(0), self._be(0, 4))
            self.assertTrue(conn.closed)

        # RegisterFile.__exit__ closes the regdb mmap, which fails while RegisterBlock
        # or MappedRegister objects are still alive. Do the work in helpers so that
        # their locals are gone before the with-block ends.

        def test_mapped_register_block(self):
            with rw.RegisterFile(REGDB_PATH) as rf:
                self._check_mapped_register_block(rf)

        def _check_mapped_register_block(self, rf):
            block = rf['SENSOR_A']

            with rw.MappedRegisterBlock(self.bin_path, block) as local:
                expected = dict(local.read())

            target = self.conn.open_mmap(
                self.bin_path, block.offset, block.size, block.data_endianness, block.data_size
            )
            with rw.MappedRegisterBlock(target, block) as remote:
                self.assertEqual(dict(remote.read()), expected)

                new_mode = (remote['STATUS_REG:MODE'] + 1) & 0x1F
                remote['STATUS_REG:MODE'] = new_mode
                self.assertEqual(remote['STATUS_REG:MODE'], new_mode)
                self.assertEqual(remote['STATUS_REG:7:3'], new_mode)

            # Leaving the block closes the target it was given.
            with self.assertRaises(RemoteError):
                target.read(block.offset)

            # The write went through to the file.
            with rw.MappedRegisterBlock(self.bin_path, block) as local:
                self.assertEqual(local['STATUS_REG:MODE'], new_mode)

        def test_mapped_register_file(self):
            with rw.RegisterFile(REGDB_PATH) as rf:
                self._check_mapped_register_file(rf)

        def _check_mapped_register_file(self, rf):
            local = rw.MappedRegisterFile(
                rf,
                target_factory=lambda rb: rw.MMapTarget(
                    self.bin_path, rb.offset, rb.size, rb.data_endianness, rb.data_size
                ),
            )
            remote = self.conn.mapped_register_file(rf, self.bin_path)
            self.assertIsInstance(remote, rw.MappedRegisterFile)

            self.assertEqual(list(remote), list(rf.keys()))

            for bname in rf.keys():
                for rname in rf[bname].keys():
                    path = f'{bname}.{rname}'
                    self.assertEqual(int(remote[path]), int(local[path]), path)

        def test_i2c_factory(self):
            with rw.RegisterFile(REGDB_PATH) as rf:
                self._check_i2c_factory(rf)

        def _check_i2c_factory(self, rf):
            block = rf['SENSOR_A']

            # The block is opened as an I2C target on the device, addressed
            # as the database says.
            with mock.patch.object(self.conn, 'open_i2c') as open_i2c:
                target = self.conn.i2c_factory(1, 0x45)(block)
            self.assertIs(target, open_i2c.return_value)
            open_i2c.assert_called_once_with(
                1,
                0x45,
                block.offset,
                block.size,
                block.addr_endianness,
                block.addr_size,
                block.data_endianness,
                block.data_size,
                rw.MapMode.ReadWrite,
            )

            # There is no such bus, so the agent's open fails: the request
            # reached it intact, and the connection is still usable.
            with self.assertRaises(RemoteError) as cm:
                self.conn.i2c_factory(999, 0x45, rw.MapMode.Read)(block)
            self.assertIn('/dev/i2c-999', str(cm.exception))
            self.assertIn('origin', self.conn.info())

        def test_mapped_register_block_endianness(self):
            with rw.RegisterFile(REGDB_PATH) as rf:
                self._check_mapped_register_block_endianness(rf)

        def _check_mapped_register_block_endianness(self, rf):
            # MEMORY_CTRL is big-endian, the target below is not: the
            # registers must read and write as they do through a file.
            block = rf['MEMORY_CTRL']

            with rw.MappedRegisterBlock(self.bin_path, block, mode=rw.MapMode.Read) as local:
                expected = dict(local.read())

            target = self.conn.open_mmap(
                self.bin_path, block.offset, block.size, rw.Endianness.Default, block.data_size
            )
            with rw.MappedRegisterBlock(target, block) as remote:
                self.assertEqual(dict(remote.read()), expected)
                remote['DATA_HI_REG'] = 0x12345678

            with rw.MappedRegisterBlock(self.bin_path, block, mode=rw.MapMode.Read) as local:
                self.assertEqual(int(local['DATA_HI_REG']), 0x12345678)

        def test_mapped_register_block_rejects_mode(self):
            with rw.RegisterFile(REGDB_PATH) as rf:
                self._check_mapped_register_block_rejects_mode(rf)

        def _check_mapped_register_block_rejects_mode(self, rf):
            block = rf['SENSOR_A']

            with self.conn.open_mmap(
                self.bin_path, block.offset, block.size, block.data_endianness, block.data_size
            ) as target:
                # The target was opened with a mode of its own.
                with self.assertRaises(ValueError):
                    rw.MappedRegisterBlock(target, block, mode=rw.MapMode.Read)

        def test_mapped_register_file_closes_before_the_register_file(self):
            # The RegisterFile and the mapped file nested as a user would
            # write them, with nothing hidden in a helper: closing the
            # mapped file drops the views into the regdb mmap, so the
            # RegisterFile can close it.
            with rw.RegisterFile(REGDB_PATH) as rf:
                with self.conn.mapped_register_file(rf, self.bin_path) as mrf:
                    self.assertEqual(int(mrf['SENSOR_A']['STATUS_REG']), self.data[0])


class RemoteFailureTests(unittest.TestCase):
    def setUp(self):
        self.tmpdir = tempfile.mkdtemp()

    def tearDown(self):
        shutil.rmtree(self.tmpdir)

    def test_agent_import_failure_reports_stderr(self):
        # A PYTHONPATH with a broken rwmem package shadows the real one, so
        # the agent dies at import time whatever is installed on this machine.
        bad = os.path.join(self.tmpdir, 'rwmem')
        os.makedirs(bad)
        with open(os.path.join(bad, '__init__.py'), 'w') as f:
            f.write("raise ImportError('broken on purpose')\n")

        # PYTHONSAFEPATH keeps 'python -m rwmem.agent' from putting the
        # current directory ahead of PYTHONPATH, which would find the real
        # package when the tests are run from py/. Python 3.11+; older
        # versions ignore it and need a cwd without an rwmem package.
        env = {'PYTHONPATH': self.tmpdir, 'PYTHONSAFEPATH': '1'}
        with self.assertRaises(RemoteError) as cm:
            RemoteConnection(None, deploy=False, python=sys.executable, env=env)

        msg = str(cm.exception)
        self.assertIn('Failed to connect', msg)
        self.assertIn('returncode 1', msg)
        self.assertIn('broken on purpose', msg)

    def test_missing_python(self):
        with self.assertRaises(RemoteError) as cm:
            RemoteConnection(None, python=os.path.join(self.tmpdir, 'no-such-python'))
        self.assertIn('Failed to start agent', str(cm.exception))

    def test_banner_on_stdout(self):
        # A device whose shell prints something on non-interactive logins,
        # e.g. an echo in ~/.bashrc, puts a non-JSON line before the replies.
        pidfile = os.path.join(self.tmpdir, 'pid')
        wrapper = os.path.join(self.tmpdir, 'python-with-banner')
        with open(wrapper, 'w') as f:
            f.write(
                '#!/bin/sh\n'
                f'echo $$ > {shlex.quote(pidfile)}\n'
                'echo rwmem-test-banner\n'
                f'exec {shlex.quote(sys.executable)} "$@"\n'
            )
        os.chmod(wrapper, 0o755)

        with self.assertRaises(RemoteError) as cm:
            RemoteConnection(None, deploy=False, python=wrapper, env={'PYTHONPATH': PY_DIR})

        msg = str(cm.exception)
        self.assertIn('Failed to connect', msg)
        self.assertIn('rwmem-test-banner', msg)

        # The failed connection must not leave the agent process behind.
        with open(pidfile) as f:
            pid = int(f.read())
        with self.assertRaises(ProcessLookupError):
            os.kill(pid, 0)

    def test_default_is_deploy(self):
        with RemoteConnection(None, python=sys.executable, env={'PYTHONPATH': PY_DIR}) as conn:
            self.assertTrue(conn.deploy)
            self.assertTrue(conn.info()['origin'].startswith('mem:'))

    def test_stray_output_goes_to_stderr(self):
        # A print() in the agent, or in a module it imports, must not end up
        # in the reply stream: the agent moves fd 1 to stderr at startup.
        script = os.path.join(self.tmpdir, 'agent-with-print.py')
        with open(script, 'w') as f:
            f.write(
                'import os\n'
                'import rwmem.agent as agent\n'
                'orig = agent.Agent.op_info\n'
                'def op_info(self, req):\n'
                '    print("stray print")\n'
                '    os.write(1, b"stray write\\n")\n'
                '    return orig(self, req)\n'
                'agent.Agent.op_info = op_info\n'
                'agent.main()\n'
            )
        wrapper = os.path.join(self.tmpdir, 'python-with-print')
        with open(wrapper, 'w') as f:
            f.write(f'#!/bin/sh\nexec "{sys.executable}" "{script}"\n')
        os.chmod(wrapper, 0o755)

        conn = RemoteConnection(None, deploy=False, python=wrapper, env={'PYTHONPATH': PY_DIR})
        with conn:
            self.assertEqual(conn.info()['byteorder'], sys.byteorder)
        self.assertIn('stray write', conn.agent_stderr)
        self.assertIn('stray print', conn.agent_stderr)


class BundleTests(unittest.TestCase):
    def test_bundle_holds_only_the_agents_modules(self):
        with zipfile.ZipFile(io.BytesIO(bundle_package())) as z:
            names = sorted(z.namelist())
            init = z.read('rwmem/__init__.py').decode()

        # What the agent imports, and nothing else: no remote.py, none of
        # the register file machinery.
        self.assertEqual(
            names,
            [
                'rwmem/__init__.py',
                'rwmem/agent.py',
                'rwmem/enums.py',
                'rwmem/i2ctarget.py',
                'rwmem/mmaptarget.py',
                'rwmem/target.py',
            ],
        )
        # The shipped __init__ is a stub; the real one imports everything.
        self.assertNotIn('import', init)


class RemoteInstalledTests(Base.RemoteTests):
    deploy = False


class RemoteDeployTests(Base.RemoteTests):
    deploy = True


if __name__ == '__main__':
    unittest.main()
