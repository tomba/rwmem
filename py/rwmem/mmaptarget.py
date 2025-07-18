from __future__ import annotations

import mmap
import os
import sys
import weakref
from typing import BinaryIO

from .enums import Endianness, MapMode

__all__ = [ 'MMapTarget', ]

class MMapTarget:
    def __init__(self, file: str | BinaryIO,
                 offset: int, length: int,
                 data_endianness: Endianness, data_size: int,
                 mode: MapMode = MapMode.ReadWrite) -> None:

        if length <= 0:
            raise ValueError(f'Length must be positive, got {length}')
        if data_size <= 0:
            raise ValueError(f'Data size must be positive, got {data_size}')

        self.offset = offset
        self.length = length

        self.data_endianness = data_endianness
        self.data_size = data_size

        self.mode = mode

        if mode == MapMode.Read:
            oflag = os.O_RDONLY
            prot = mmap.PROT_READ
        elif mode == MapMode.Write:
            oflag = os.O_WRONLY
            prot = mmap.PROT_WRITE
        else:
            oflag = os.O_RDWR
            prot = mmap.PROT_READ | mmap.PROT_WRITE

        if isinstance(file, str):
            # XXX It is not clear if os.O_SYNC affects mmap. Do we need msync()?
            fd = os.open(file, oflag | os.O_SYNC)
        else:
            # mmap will (apparently?) close its fd, so duplicate it first
            fd = os.dup(file.fileno())

        try:
            pagesize = mmap.ALLOCATIONGRANULARITY
            pagemask = pagesize - 1

            mmap_offset = offset & ~pagemask
            mmap_len = length + (offset - mmap_offset)

            self.mmap_offset = mmap_offset
            self.mmap_len = mmap_len

            #print(f'\nMAP off: {offset:#x} len: {length:#x} ->  mmap_offset: {mmap_offset:#x} mmap_len: {mmap_len:#x}')

            self._map = mmap.mmap(fd, mmap_len, mmap.MAP_SHARED, prot, offset=mmap_offset)
        finally:
            os.close(fd)

        weakref.finalize(self, MMapTarget.cleanup, self._map)

    @staticmethod
    def cleanup(m):
        # It is ok to call close() multiple times
        m.close()

    def close(self):
        self._map.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, exc_tb):
        self._map.close()

    def _endianness_to_bo(self, endianness: Endianness):
        if endianness == Endianness.Default:
            endianness = self.data_endianness

        if endianness == Endianness.Default:
            return sys.byteorder
        elif endianness == Endianness.Little:
            return 'little'
        elif endianness == Endianness.Big:
            return 'big'

        raise NotImplementedError()

    def _check_access(self, addr: int,
                      data_size,  addr_size, addr_endianness):
        if addr_size is not None and addr_size != 0:
            raise RuntimeError('Address size must be 0')

        if addr_endianness != Endianness.Default:
            raise RuntimeError('Address endianness must be Default')

        if addr < self.offset:
            raise RuntimeError(f'Access outside mmap area: {addr} < {self.offset}')

        if addr + data_size > self.offset + self.length:
            raise RuntimeError(f'Access outside mmap area: {addr + data_size} > {self.offset + self.length}')

    def read(self, addr: int,
             data_size: int | None = None, data_endianness: Endianness = Endianness.Default,
             addr_size: int | None = None, addr_endianness: Endianness = Endianness.Default) -> int:
        if self.mode == MapMode.Write:
            raise RuntimeError()

        if data_size is None:
            data_size = self.data_size
        elif data_size <= 0:
            raise ValueError(f'Data size must be positive, got {data_size}')

        self._check_access(addr, data_size, addr_size, addr_endianness)

        bo = self._endianness_to_bo(data_endianness)

        addr -= self.mmap_offset

        #print(f'READ {self.mmap_offset:#x}+{addr:#x} (nbytes {nbytes}, bo {endianness})')

        v = self._map[addr:addr + data_size]

        ret = int.from_bytes(v, bo, signed=False)

        #print(f'READ {addr:#x} (data_size={data_size}, bo={data_endianness}) = {ret:#x} ({v})')

        return ret

    def write(self, addr: int, value: int,
              data_size: int | None = None, data_endianness: Endianness = Endianness.Default,
              addr_size: int | None = None, addr_endianness: Endianness = Endianness.Default):
        if self.mode == MapMode.Read:
            raise RuntimeError()

        if data_size is None:
            data_size = self.data_size
        elif data_size <= 0:
            raise ValueError(f'Data size must be positive, got {data_size}')

        self._check_access(addr, data_size, addr_size, addr_endianness)

        bo = self._endianness_to_bo(data_endianness)

        #print(f'WRITE {addr:#x} (data_size={data_size}, bo={data_endianness}) = {value:#x}')

        addr -= self.mmap_offset

        self._map[addr:addr + data_size] = value.to_bytes(data_size, bo, signed=False)
