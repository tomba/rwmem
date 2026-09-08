"""PC-side remote register access over ssh.

``RemoteConnection`` starts ``rwmem.agent`` on a device and speaks a
newline-delimited JSON protocol to it over the ssh session's stdin/stdout.
``RemoteTarget`` is a ``Target`` whose reads and writes are forwarded over
that connection, so it can be used anywhere an ``MMapTarget`` or
``I2CTarget`` is.

Two ways to start the agent:

* deploy mode (default): the few modules the agent needs are taken from the
  PC's copy of the package, zipped in memory and streamed to a small
  bootstrap that imports them from memory. The device needs only
  python3 (3.10 or newer).
* installed mode (``deploy=False``): ``python3 -m rwmem.agent`` on the device.
  pyrwmem must be importable there; use ``env={'PYTHONPATH': ...}`` if it is
  not installed system-wide. Skips the transfer and compiles nothing.

With ``host=None`` the agent runs as a local subprocess instead of over ssh,
which is what the tests use.

A connection can be used from several threads. Requests are serialised,
one in flight at a time, since the agent answers them in order; a request
waits for the reply to the one before it. Closing the connection from
another thread ends a request in flight.
"""

from __future__ import annotations

import importlib.resources
import io
import json
import os
import pathlib
import shlex
import subprocess
import threading
import zipfile
from collections import deque
from collections.abc import Callable, Mapping, Sequence
from typing import IO, Any

from .enums import Endianness, MapMode
from .mappedregisterfile import MappedRegisterFile
from .registerfile import RegisterFile
from .target import Target

__all__ = [
    'RemoteConnection',
    'RemoteError',
    'RemoteTarget',
]

# Stage one of deploy mode. Must contain no quote characters so that it
# survives the remote shell unchanged. It reads a length line and that many
# bytes from stdin and execs them; those bytes are rwmem/_bootstrap.py.
_STAGE1 = 'import sys;b=sys.stdin.buffer;exec(b.read(int(b.readline())))'

DEFAULT_SSH: Sequence[str] = ('ssh', '-o', 'BatchMode=yes')


class RemoteError(RuntimeError):
    """An error raised by the agent, or a broken connection to it."""


def _trunc(line: bytes, limit: int = 200) -> str:
    """A reply line as ``repr``, shortened for an error message."""
    text = line.decode(errors='replace').rstrip('\n')
    if len(text) > limit:
        text = text[:limit] + '...'
    return repr(text)


# What the agent needs from the package: rwmem.agent's imports inside it,
# and theirs. Keep in sync with agent.py's imports.
AGENT_MODULES = ('agent.py', 'enums.py', 'target.py', 'mmaptarget.py', 'i2ctarget.py')

# Replaces the package's __init__.py in the bundle. The real one imports
# the whole package, which the agent neither needs nor can always compile.
_STUB_INIT = "# Stub for rwmem.remote's deploy mode: only the agent's modules are shipped.\n"


def bundle_package() -> bytes:
    """Zip the modules the agent needs (source only) into memory.

    Only ``AGENT_MODULES`` is shipped, with a stub ``__init__`` in place of
    the real one, so that the device neither compiles nor runs the rest of
    the package.
    """
    import rwmem

    assert rwmem.__file__ is not None
    pkg_dir = pathlib.Path(rwmem.__file__).parent

    buf = io.BytesIO()
    with zipfile.ZipFile(buf, 'w', zipfile.ZIP_DEFLATED) as z:
        z.writestr('rwmem/__init__.py', _STUB_INIT)
        for rel in AGENT_MODULES:
            z.write(pkg_dir / rel, 'rwmem/' + rel)
    return buf.getvalue()


class RemoteConnection:
    def __init__(
        self,
        host: str | None,
        *,
        deploy: bool = True,
        ssh: Sequence[str] = DEFAULT_SSH,
        python: str = 'python3',
        env: Mapping[str, str] | None = None,
    ) -> None:
        self.host = host
        self.deploy = deploy
        self.ssh = list(ssh)
        self.python = python
        self.env = dict(env) if env else {}

        self._proc: subprocess.Popen | None = None
        # Tail of the agent's stderr, drained by a thread so that a chatty
        # agent cannot block on a full pipe. Shown when the agent dies.
        self._stderr_lines: deque[str] = deque(maxlen=50)
        self._stderr_lock = threading.Lock()
        self._stderr_thread: threading.Thread | None = None
        # Set once the agent has died, to the error describing it; every
        # later request fails with that same root cause.
        self._death: str | None = None
        # One request in flight at a time: the agent answers in order, so a
        # request from another thread waits for the reply to this one.
        self._lock = threading.Lock()

        # Handshake, so that a dead agent (ssh failure, missing python or
        # package) is reported here and not at the first access: a short
        # bundle can be written into the pipe before ssh exits.
        try:
            self._spawn()
            self.agent_info: dict = self._call('info')
        except RemoteError as e:
            self.close()
            raise RemoteError(f'Failed to connect: {e}') from None

    # --- process management ---------------------------------------------

    def _spawn(self) -> None:
        if self.deploy:
            py_args = ['-c', _STAGE1]
        else:
            py_args = ['-m', 'rwmem.agent']

        env = None
        if self.host is None:
            argv = [self.python, *py_args]
            env = {**os.environ, **self.env} if self.env else None
        else:
            # ssh joins its arguments into one string that the remote shell
            # parses, so build the remote command as a shell string.
            cmd = shlex.join([self.python, *py_args])
            if self.env:
                assigns = ' '.join(f'{k}={shlex.quote(v)}' for k, v in self.env.items())
                cmd = f'{assigns} {cmd}'
            argv = [*self.ssh, self.host, cmd]

        try:
            self._proc = subprocess.Popen(
                argv,
                stdin=subprocess.PIPE,
                stdout=subprocess.PIPE,
                stderr=subprocess.PIPE,
                env=env,
            )
        except OSError as e:
            raise RemoteError(f'Failed to start agent {shlex.join(argv)}: {e}') from e

        self._stderr_thread = threading.Thread(
            target=self._drain_stderr, args=(self._proc.stderr,), daemon=True
        )
        self._stderr_thread.start()

        if self.deploy:
            try:
                self._send_bundle()
            except (BrokenPipeError, OSError):
                raise self._agent_died('sending the package') from None

    def _send_bundle(self) -> None:
        stage2 = importlib.resources.files('rwmem').joinpath('_bootstrap.py').read_bytes()
        blob = bundle_package()

        w = self._stdin
        w.write(b'%d\n' % len(stage2))
        w.write(stage2)
        w.write(b'%d\n' % len(blob))
        w.write(blob)
        w.flush()

    def _drain_stderr(self, stream: IO[bytes]) -> None:
        for raw in stream:
            line = raw.decode(errors='replace').rstrip('\n')
            with self._stderr_lock:
                self._stderr_lines.append(line)

    @property
    def agent_stderr(self) -> list[str]:
        """The most recent lines the agent (or ssh) wrote to stderr."""
        with self._stderr_lock:
            return list(self._stderr_lines)

    def _agent_died(self, during: str) -> RemoteError:
        """Build the error for an agent that went away, with its stderr tail."""
        proc = self._proc
        rc: int | None = None
        if proc is not None:
            try:
                rc = proc.wait(timeout=5)
            except subprocess.TimeoutExpired:
                pass
        if self._stderr_thread is not None:
            self._stderr_thread.join(timeout=1)

        msg = f'Agent exited (returncode {rc}) while {during}'
        stderr = self.agent_stderr
        if stderr:
            msg += '. Agent stderr:\n' + '\n'.join(f'  {line}' for line in stderr)

        self._death = msg
        return RemoteError(msg)

    @property
    def _stdin(self) -> IO[bytes]:
        assert self._proc is not None and self._proc.stdin is not None
        return self._proc.stdin

    @property
    def closed(self) -> bool:
        return self._proc is None

    @property
    def dead(self) -> bool:
        """True once the agent has exited unexpectedly."""
        return self._death is not None

    def close(self) -> None:
        # Not under the lock: a thread stuck in a request holds it, and
        # ending the agent is what releases that thread.
        proc = self._proc
        if proc is None:
            return
        self._proc = None

        stdin, stdout, stderr = proc.stdin, proc.stdout, proc.stderr
        assert stdin is not None and stdout is not None and stderr is not None

        try:
            if proc.poll() is None:
                stdin.write(b'{"op": "quit"}\n')
                stdin.flush()
        except (BrokenPipeError, OSError):
            pass

        try:
            # Closing re-flushes whatever the failed write left buffered,
            # which breaks again if the agent is gone.
            stdin.close()
        except (BrokenPipeError, OSError):
            pass
        try:
            proc.wait(timeout=5)
        except subprocess.TimeoutExpired:
            proc.kill()
            proc.wait()
        stdout.close()
        if self._stderr_thread is not None:
            self._stderr_thread.join(timeout=1)
        stderr.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, exc_tb):
        self.close()

    # --- protocol -------------------------------------------------------

    def _call(self, op: str, **kw) -> Any:
        req = json.dumps({'op': op, **kw}).encode() + b'\n'

        with self._lock:
            if self._death is not None:
                raise RemoteError(self._death)
            # The process, not the properties: a close() from another thread
            # drops self._proc while this request is in flight.
            proc = self._proc
            if proc is None:
                raise RemoteError('Connection is closed')
            assert proc.stdin is not None and proc.stdout is not None

            try:
                proc.stdin.write(req)
                proc.stdin.flush()
                line = proc.stdout.readline()
            except (BrokenPipeError, OSError):
                raise self._agent_died(f'handling {op!r}') from None

            if not line:
                raise self._agent_died(f'handling {op!r}')

        try:
            resp = json.loads(line)
        except ValueError:
            resp = None
        if not isinstance(resp, dict):
            raise RemoteError(f'Expected a JSON reply from the agent, got {_trunc(line)}')
        if 'error' in resp:
            raise RemoteError(resp['error'])
        return resp.get('value')

    # --- public API -----------------------------------------------------

    def info(self) -> dict:
        return self._call('info')

    def open_mmap(
        self,
        file: str,
        offset: int,
        length: int,
        data_endianness: Endianness,
        data_size: int,
        mode: MapMode = MapMode.ReadWrite,
    ) -> RemoteTarget:
        handle = self._call(
            'open_mmap',
            file=file,
            offset=offset,
            length=length,
            data_endianness=data_endianness.value,
            data_size=data_size,
            mode=mode.value,
        )
        return RemoteTarget(self, handle)

    def open_i2c(
        self,
        i2c_adapter_nr: int,
        i2c_dev_addr: int,
        offset: int,
        length: int,
        addr_endianness: Endianness,
        addr_size: int,
        data_endianness: Endianness,
        data_size: int,
        mode: MapMode = MapMode.ReadWrite,
    ) -> RemoteTarget:
        handle = self._call(
            'open_i2c',
            i2c_adapter_nr=i2c_adapter_nr,
            i2c_dev_addr=i2c_dev_addr,
            offset=offset,
            length=length,
            addr_endianness=addr_endianness.value,
            addr_size=addr_size,
            data_endianness=data_endianness.value,
            data_size=data_size,
            mode=mode.value,
        )
        return RemoteTarget(self, handle)

    def read_many(
        self, reads: Sequence[tuple[RemoteTarget, int, int | None, Endianness]]
    ) -> list[int | RemoteError]:
        """Read registers from any targets of this connection in one round trip.

        Each entry is ``(target, addr, data_size, data_endianness)``. The
        result has one entry per read: the value, or a RemoteError for a
        read that failed, so that one bad address does not lose the others.
        """
        items = []
        for target, addr, data_size, data_endianness in reads:
            if target._conn is not self:
                raise ValueError('Target belongs to another connection')
            items.append(
                {
                    't': target._h(),
                    'addr': addr,
                    'data_size': data_size,
                    'data_endianness': data_endianness.value,
                }
            )
        if not items:
            return []

        replies = self._call('read_many', reads=items)
        return [RemoteError(r['error']) if 'error' in r else r['value'] for r in replies]

    def mmap_factory(
        self, file: str = '/dev/mem', mode: MapMode = MapMode.ReadWrite
    ) -> Callable[..., RemoteTarget]:
        """Return a target factory for ``MappedRegisterFile``.

        The factory takes a ``RegisterBlock`` and opens an mmap target on the
        remote device covering that block.
        """

        def factory(regblock) -> RemoteTarget:
            return self.open_mmap(
                file,
                regblock.offset,
                regblock.size,
                regblock.data_endianness,
                regblock.data_size,
                mode,
            )

        return factory

    def i2c_factory(
        self, i2c_adapter_nr: int, i2c_dev_addr: int, mode: MapMode = MapMode.ReadWrite
    ) -> Callable[..., RemoteTarget]:
        """Return a target factory for ``MappedRegisterFile``.

        The factory takes a ``RegisterBlock`` and opens an I2C target on the
        remote device covering that block, with the block's register address
        size and endianness.
        """

        def factory(regblock) -> RemoteTarget:
            return self.open_i2c(
                i2c_adapter_nr,
                i2c_dev_addr,
                regblock.offset,
                regblock.size,
                regblock.addr_endianness,
                regblock.addr_size,
                regblock.data_endianness,
                regblock.data_size,
                mode,
            )

        return factory

    def mapped_register_file(
        self,
        rf: RegisterFile,
        file: str = '/dev/mem',
        mode: MapMode = MapMode.ReadWrite,
    ) -> MappedRegisterFile:
        """A ``MappedRegisterFile`` whose blocks are mapped on the remote device.

        Each block is opened on the device, from ``file``, the first time it
        is accessed.
        """
        return MappedRegisterFile(rf, target_factory=self.mmap_factory(file, mode))


class RemoteTarget(Target):
    def __init__(self, conn: RemoteConnection, handle: int) -> None:
        self._conn = conn
        self._handle: int | None = handle

    def _h(self) -> int:
        if self._handle is None:
            raise RemoteError('Target is closed')
        return self._handle

    def read(
        self,
        addr: int,
        data_size: int | None = None,
        data_endianness: Endianness = Endianness.Default,
        addr_size: int | None = None,
        addr_endianness: Endianness = Endianness.Default,
    ) -> int:
        return self._conn._call(
            'read',
            t=self._h(),
            addr=addr,
            data_size=data_size,
            data_endianness=data_endianness.value,
            addr_size=addr_size,
            addr_endianness=addr_endianness.value,
        )

    def write(
        self,
        addr: int,
        value: int,
        data_size: int | None = None,
        data_endianness: Endianness = Endianness.Default,
        addr_size: int | None = None,
        addr_endianness: Endianness = Endianness.Default,
    ):
        self._conn._call(
            'write',
            t=self._h(),
            addr=addr,
            value=value,
            data_size=data_size,
            data_endianness=data_endianness.value,
            addr_size=addr_size,
            addr_endianness=addr_endianness.value,
        )

    def read_many(self, reads: Sequence[tuple[int, int | None, Endianness]]) -> list[int]:
        """Read several registers in one round trip.

        Every read is attempted, unlike ``Target.read_many``'s default;
        the first failed one is raised afterwards.
        """
        results = self._conn.read_many([(self, addr, size, end) for addr, size, end in reads])
        values: list[int] = []
        for i, r in enumerate(results):
            if isinstance(r, RemoteError):
                raise RemoteError(f'read {i} of {len(results)} at {reads[i][0]:#x} failed: {r}')
            values.append(r)
        return values

    def close(self):
        if self._handle is None:
            return
        handle, self._handle = self._handle, None
        # Nothing to release on a closed or dead agent.
        if self._conn.closed or self._conn.dead:
            return
        try:
            self._conn._call('close', t=handle)
        except RemoteError:
            # Closing is best effort: the agent may have died without that
            # being noticed yet, and this must not mask the real error.
            pass
