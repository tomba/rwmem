"""Device-side agent for remote register access.

Reads newline-delimited JSON requests from stdin and writes one JSON reply
per request to stdout. Started on the target device by
``rwmem.remote.RemoteConnection``, either as ``python3 -m rwmem.agent`` when
pyrwmem is installed on the device, or through the in-memory bootstrap in
``rwmem._bootstrap`` when it is not.

Requests are objects with an ``op`` key. Ops that act on a target carry its
integer handle in ``t``. Enum arguments are passed as their integer values.

Replies are ``{"value": ...}`` on success or ``{"error": "<Type>: <msg>"}``
on failure. Replies go to a private duplicate of the original stdout; fd 1
is pointed at stderr at startup, so that a stray print() cannot corrupt the
protocol.
"""

from __future__ import annotations

import faulthandler
import json
import os
import sys
from collections.abc import Callable
from typing import Any, BinaryIO

from .enums import Endianness, MapMode
from .i2ctarget import I2CTarget
from .mmaptarget import MMapTarget
from .target import Target

__all__ = ['Agent', 'main']


class Agent:
    def __init__(self) -> None:
        self._targets: dict[int, Target] = {}
        self._next_handle = 1

    def _add(self, target: Target) -> int:
        handle = self._next_handle
        self._next_handle += 1
        self._targets[handle] = target
        return handle

    def _get(self, req: dict) -> Target:
        handle = req['t']
        try:
            return self._targets[handle]
        except KeyError:
            raise ValueError(f'Unknown target handle {handle}') from None

    # --- ops -------------------------------------------------------------

    def op_info(self, req: dict):
        return {
            'python': sys.version,
            'byteorder': sys.byteorder,
            # Where this module was loaded from: a file path, or 'mem:...'
            # when rwmem._bootstrap imported it from memory.
            'origin': __spec__.origin if __spec__ else None,
        }

    def op_open_mmap(self, req: dict):
        target = MMapTarget(
            req['file'],
            req['offset'],
            req['length'],
            Endianness(req['data_endianness']),
            req['data_size'],
            MapMode(req.get('mode', MapMode.ReadWrite.value)),
        )
        return self._add(target)

    def op_open_i2c(self, req: dict):
        target = I2CTarget(
            req['i2c_adapter_nr'],
            req['i2c_dev_addr'],
            req['offset'],
            req['length'],
            Endianness(req['addr_endianness']),
            req['addr_size'],
            Endianness(req['data_endianness']),
            req['data_size'],
            MapMode(req.get('mode', MapMode.ReadWrite.value)),
        )
        return self._add(target)

    def op_read(self, req: dict):
        target = self._get(req)
        return target.read(
            req['addr'],
            req.get('data_size'),
            Endianness(req.get('data_endianness', Endianness.Default.value)),
            req.get('addr_size'),
            Endianness(req.get('addr_endianness', Endianness.Default.value)),
        )

    def op_read_many(self, req: dict):
        """Perform several reads; each entry of ``reads`` takes the ``read`` arguments.

        Returns one ``{'value': ...}`` or ``{'error': ...}`` per entry, so
        that one failing read does not discard the others.
        """
        results = []
        for item in req['reads']:
            try:
                results.append({'value': self.op_read(item)})
            except Exception as e:  # noqa: BLE001 - reported per entry
                results.append({'error': f'{type(e).__name__}: {e}'})
        return results

    def op_write(self, req: dict):
        target = self._get(req)
        target.write(
            req['addr'],
            req['value'],
            req.get('data_size'),
            Endianness(req.get('data_endianness', Endianness.Default.value)),
            req.get('addr_size'),
            Endianness(req.get('addr_endianness', Endianness.Default.value)),
        )

    def op_close(self, req: dict):
        target = self._get(req)
        del self._targets[req['t']]
        target.close()

    def op_quit(self, req: dict):
        pass

    # --- loop ------------------------------------------------------------

    def _dispatch(self, req: dict):
        # An explicit table, rather than getattr(self, 'op_' + op), so that
        # only these methods are reachable from the wire.
        ops: dict[str, Callable[[dict], Any]] = {
            'info': self.op_info,
            'open_mmap': self.op_open_mmap,
            'open_i2c': self.op_open_i2c,
            'read': self.op_read,
            'read_many': self.op_read_many,
            'write': self.op_write,
            'close': self.op_close,
            'quit': self.op_quit,
        }
        op = req.get('op')
        fn = ops.get(op) if isinstance(op, str) else None
        if fn is None:
            raise ValueError(f'Unknown op {op!r}')
        return fn(req)

    def serve(self, inp: BinaryIO, out: BinaryIO) -> None:
        try:
            while True:
                line = inp.readline()
                if not line:
                    break
                if not line.strip():
                    continue

                quit_requested = False
                try:
                    req = json.loads(line)
                    if not isinstance(req, dict):
                        raise TypeError('Request must be a JSON object')
                    quit_requested = req.get('op') == 'quit'
                    resp = {'value': self._dispatch(req)}
                except Exception as e:  # noqa: BLE001 - report everything to the client
                    resp = {'error': f'{type(e).__name__}: {e}'}

                out.write(json.dumps(resp).encode() + b'\n')
                out.flush()

                if quit_requested:
                    break
        except BrokenPipeError:
            pass
        finally:
            for target in self._targets.values():
                target.close()
            self._targets.clear()


def main() -> None:
    # Replies go to a private duplicate of stdout, and fd 1 is pointed at
    # stderr, so that a stray print() cannot corrupt the protocol.
    sys.stdout.flush()
    out = os.fdopen(os.dup(sys.stdout.fileno()), 'wb')
    os.dup2(sys.stderr.fileno(), sys.stdout.fileno())

    # A faulting register access (SIGBUS on an unmapped or powered-down
    # address) kills this process. Report it on stderr with the traceback,
    # so that the other side can show it.
    if sys.version_info >= (3, 14):
        faulthandler.enable(c_stack=False)  # the C stack is noise here
    else:
        faulthandler.enable()
    Agent().serve(sys.stdin.buffer, out)


if __name__ == '__main__':
    main()
