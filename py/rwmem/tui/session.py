"""Register access for rwmem-tui.

A Session opens one Target per register block, locally or through a
RemoteConnection, and performs all reads and writes. Access is serialised
with a lock: the UI calls in from several worker threads at once, and a
write's read-modify-write and readback must not have another access
between them. A call that finds the lock taken waits for its turn.
"""

from __future__ import annotations

import threading
from collections.abc import Sequence
from dataclasses import dataclass

from rwmem.enums import Endianness, MapMode
from rwmem.gen import UnpackedRegBlock, UnpackedRegister
from rwmem.i2ctarget import I2CTarget
from rwmem.mmaptarget import MMapTarget
from rwmem.remote import RemoteConnection, RemoteTarget
from rwmem.target import Target


@dataclass(frozen=True)
class RegRef:
    """A register within a block: the unit of reads and writes.

    ``base`` is the address the block is accessed at. It is the block's
    offset from the register database unless overridden.
    """

    block: UnpackedRegBlock
    reg: UnpackedRegister
    base: int

    @property
    def key(self) -> tuple[str, str]:
        return (self.block.name, self.reg.name)

    @property
    def addr(self) -> int:
        return self.base + self.reg.offset

    @property
    def data_size(self) -> int:
        return self.reg.get_effective_data_size(self.block.data_size)

    @property
    def data_endianness(self) -> Endianness:
        return self.reg.get_effective_data_endianness(self.block.data_endianness)

    @property
    def bits(self) -> int:
        return self.data_size * 8


class Session:
    def __init__(
        self,
        mode: str,
        *,
        file: str = '/dev/mem',
        i2c_bus: int = 0,
        i2c_addr: int = 0,
        conn: RemoteConnection | None = None,
    ) -> None:
        if mode not in ('mmap', 'i2c'):
            raise ValueError(f'Unknown mode {mode!r}')
        self.mode = mode
        self.file = file
        self.i2c_bus = i2c_bus
        self.i2c_addr = i2c_addr
        self.conn = conn

        self._targets: dict[str, Target] = {}
        self._lock = threading.Lock()
        self._closed = False

    @property
    def alive(self) -> bool:
        """False once a remote agent has died; the reason comes with each failed access."""
        return self.conn is None or not self.conn.dead

    @property
    def description(self) -> str:
        if self.mode == 'mmap':
            s = f'mmap {self.file}'
        else:
            s = f'i2c {self.i2c_bus}:{self.i2c_addr:#x}'
        if self.conn is not None:
            s += f' on {self.conn.host}'
        return s

    # --- targets --------------------------------------------------------

    def _open(self, block: UnpackedRegBlock, base: int) -> Target:
        if self.mode == 'mmap':
            if self.conn is not None:
                return self.conn.open_mmap(
                    self.file, base, block.size, block.data_endianness, block.data_size
                )
            return MMapTarget(self.file, base, block.size, block.data_endianness, block.data_size)

        if self.conn is not None:
            return self.conn.open_i2c(
                self.i2c_bus,
                self.i2c_addr,
                base,
                block.size,
                block.addr_endianness,
                block.addr_size,
                block.data_endianness,
                block.data_size,
            )
        return I2CTarget(
            self.i2c_bus,
            self.i2c_addr,
            base,
            block.size,
            block.addr_endianness,
            block.addr_size,
            block.data_endianness,
            block.data_size,
            MapMode.ReadWrite,
        )

    def _target(self, ref: RegRef) -> Target:
        """The target of the register's block, opened on first use. Raises if that fails."""
        if self._closed:
            raise RuntimeError('session closed')
        target = self._targets.get(ref.block.name)
        if target is None:
            target = self._open(ref.block, ref.base)
            self._targets[ref.block.name] = target
        return target

    # --- access ---------------------------------------------------------

    def read_many(self, refs: Sequence[RegRef]) -> list[int | Exception]:
        """Read registers; one value or exception per entry, in order.

        On a remote session this is one round trip for all entries whose
        block could be opened. A block that cannot be opened is tried once
        per call, not once per register; the next call tries again.
        """
        results: list[int | Exception] = [RuntimeError('not read')] * len(refs)
        failed: dict[str, Exception] = {}

        def open_once(ref: RegRef) -> Target:
            """The block's target, or the error the block already failed with."""
            error = failed.get(ref.block.name)
            if error is not None:
                raise error
            try:
                return self._target(ref)
            except Exception as e:
                failed[ref.block.name] = e
                raise

        with self._lock:
            if self.conn is not None:
                items: list[tuple[RemoteTarget, int, int | None, Endianness]] = []
                indices: list[int] = []
                for i, ref in enumerate(refs):
                    try:
                        target = open_once(ref)
                    except Exception as e:  # noqa: BLE001 - reported per entry
                        # A dead agent is not a per-register failure: it
                        # fails the batch, as it does for an opened block.
                        if self.conn.dead:
                            raise
                        results[i] = e
                        continue
                    assert isinstance(target, RemoteTarget)
                    items.append((target, ref.addr, ref.data_size, ref.data_endianness))
                    indices.append(i)

                for i, r in zip(indices, self.conn.read_many(items), strict=True):
                    results[i] = r
            else:
                for i, ref in enumerate(refs):
                    try:
                        target = open_once(ref)
                        results[i] = target.read(ref.addr, ref.data_size, ref.data_endianness)
                    except Exception as e:  # noqa: BLE001 - reported per entry
                        results[i] = e

        return results

    def read(self, ref: RegRef) -> int:
        with self._lock:
            return self._target(ref).read(ref.addr, ref.data_size, ref.data_endianness)

    def write(self, ref: RegRef, value: int, mask: int | None = None) -> int:
        """Write a register and return the value read back.

        With a mask, only the bits set in it are written: the register is
        read, those bits replaced, and the result written. The whole
        sequence, readback included, runs under the lock, so no other access
        gets between its steps.
        """
        with self._lock:
            target = self._target(ref)
            if mask is not None:
                current = target.read(ref.addr, ref.data_size, ref.data_endianness)
                value = (current & ~mask) | (value & mask)
            target.write(ref.addr, value, ref.data_size, ref.data_endianness)
            return target.read(ref.addr, ref.data_size, ref.data_endianness)

    def close(self) -> None:
        """Release everything. Best effort: closing never raises, and closing twice is fine."""
        # An access still queued behind the lock fails instead of reopening
        # a target.
        self._closed = True
        if self.conn is not None:
            # Closing the connection ends the agent, and with it all of its
            # targets and a request a worker may be stuck in. The lock is
            # not taken: that worker holds it.
            self._targets.clear()
            self.conn.close()
            return

        with self._lock:
            for target in self._targets.values():
                target.close()
            self._targets.clear()
