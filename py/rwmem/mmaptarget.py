from __future__ import annotations

import mmap
import os
import sys
import weakref

from .enums import Endianness, MapMode

__all__ = [ 'MMapTarget', ]

class MMapTarget:
    def __init__(self, filename: str,
                 offset: int, length: int,
                 data_endianness: Endianness, data_size: int,
                 mode: MapMode = MapMode.ReadWrite) -> None:
        self.filename = filename
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

        # XXX It is not clear if os.O_SYNC affects mmap. Do we need msync()?
        fd = os.open(self.filename, oflag | os.O_SYNC)

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
        m.close()

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

    def read(self, addr: int,
             data_size: int = 0, data_endianness: Endianness = Endianness.Default,
             addr_size: int = 0, addr_endianness: Endianness = Endianness.Default) -> int:
        if self.mode == MapMode.Write:
            raise RuntimeError()

        if addr_size != 0:
            raise RuntimeError()

        if addr_endianness != Endianness.Default:
            raise RuntimeError()

        if data_size == 0:
            data_size = self.data_size

        if addr < self.offset:
            raise RuntimeError()

        if addr + data_size > self.offset + self.length:
            raise RuntimeError()

        bo = self._endianness_to_bo(data_endianness)

        addr -= self.mmap_offset

        #print(f'READ {self.mmap_offset:#x}+{addr:#x} (nbytes {nbytes}, bo {endianness})')

        v = self._map[addr:addr + data_size]

        ret = int.from_bytes(v, bo, signed=False)

        #print(f'READ {addr:#x} (data_size={data_size}, bo={data_endianness}) = {ret:#x} ({v})')

        return ret

    def write(self, addr: int, value: int,
              data_size: int = 0, data_endianness: Endianness = Endianness.Default,
              addr_size: int = 0, addr_endianness: Endianness = Endianness.Default):
        if self.mode == MapMode.Read:
            raise RuntimeError()

        if addr_size != 0:
            raise RuntimeError()

        if addr_endianness != Endianness.Default:
            raise RuntimeError()

        if data_size == 0:
            data_size = self.data_size

        if addr < self.offset:
            raise RuntimeError()

        if addr + data_size > self.offset + self.length:
            raise RuntimeError()

        bo = self._endianness_to_bo(data_endianness)

        #print(f'WRITE {addr:#x} (data_size={data_size}, bo={data_endianness}) = {value:#x}')

        addr -= self.mmap_offset

        self._map[addr:addr + data_size] = value.to_bytes(data_size, bo, signed=False)
