from __future__ import annotations

import ctypes
import fcntl
import os
import sys
import weakref

from .enums import Endianness, MapMode

__all__ = [ 'I2CTarget', ]

I2C_FUNCS = 0x0705
I2C_RDWR = 0x0707
I2C_FUNC_I2C = 0x00000001
I2C_M_RD = 0x0001

class i2c_msg(ctypes.Structure):
    _fields_ = [
        ('addr', ctypes.c_uint16),
        ('flags', ctypes.c_uint16),
        ('len', ctypes.c_uint16),
        ('buf', ctypes.POINTER(ctypes.c_uint8)),
    ]

class i2c_rdwr_ioctl_data(ctypes.Structure):
    _fields_ = [
        ('msgs', ctypes.POINTER(i2c_msg)),
        ('nmsgs', ctypes.c_uint32),
    ]

class I2CTarget:
    def __init__(self, i2c_adapter_nr: int, i2c_dev_addr: int,
                 offset: int, length: int,
                 addr_endianness: Endianness, addr_size: int,
                 data_endianness: Endianness, data_size: int,
                 mode: MapMode = MapMode.ReadWrite) -> None:
        self.i2c_adapter = i2c_adapter_nr
        self.i2c_dev_addr = i2c_dev_addr

        self.offset = offset
        self.length = length

        self.addr_endianness = addr_endianness
        self.addr_size = addr_size
        self.data_endianness = data_endianness
        self.data_size = data_size

        self.mode = mode

        filename = f'/dev/i2c-{i2c_adapter_nr}'
        self.fd = os.open(filename, os.O_RDWR)

        weakref.finalize(self, os.close, self.fd)

        i2c_funcs = ctypes.c_uint64()
        fcntl.ioctl(self.fd, I2C_FUNCS, i2c_funcs, True)
        if (i2c_funcs.value & I2C_FUNC_I2C) == 0:
            raise RuntimeError('no i2c functionality')

    def _endianness_to_bo(self, endianness: Endianness):
        if endianness == Endianness.Default:
            return sys.byteorder
        elif endianness == Endianness.Little:
            return 'little'
        elif endianness == Endianness.Big:
            return 'big'

        raise NotImplementedError()

    def read(self, addr: int,
             data_size: int | None = None, data_endianness: Endianness = Endianness.Default,
             addr_size: int | None = None, addr_endianness: Endianness = Endianness.Default) -> int:
        if self.mode == MapMode.Write:
            raise RuntimeError()

        if addr_size is None:
            addr_size = self.addr_size
        elif addr_size <= 0:
            raise ValueError(f'Address size must be positive, got {addr_size}')

        if data_size is None:
            data_size = self.data_size
        elif data_size <= 0:
            raise ValueError(f'Data size must be positive, got {data_size}')

        if addr_endianness == Endianness.Default:
            addr_endianness = self.addr_endianness

        if data_endianness == Endianness.Default:
            data_endianness = self.data_endianness

        if addr < self.offset:
            raise RuntimeError()

        if addr + data_size > self.offset + self.length:
            raise RuntimeError(f'register {addr:#x} end {addr + data_size:#x} over block end {self.offset + self.length:#x}')

        addr_bo = self._endianness_to_bo(addr_endianness)
        data_bo = self._endianness_to_bo(data_endianness)

        #print(f'READ {self.mmap_offset:#x}+{addr:#x} (nbytes {nbytes}, bo {endianness})')

        addr_data = addr.to_bytes(addr_size, addr_bo)
        addr_buf = (ctypes.c_ubyte * len(addr_data)).from_buffer_copy(addr_data)

        data_buf = (ctypes.c_uint8 * data_size)()

        msgs = (i2c_msg * 2)()

        msgs[0].addr = self.i2c_dev_addr
        msgs[0].flags = 0
        msgs[0].len = addr_size
        msgs[0].buf = addr_buf

        msgs[1].addr = self.i2c_dev_addr
        msgs[1].flags = I2C_M_RD
        msgs[1].len = data_size
        msgs[1].buf = data_buf

        data = i2c_rdwr_ioctl_data()
        data.msgs = msgs
        data.nmsgs = 2

        r = fcntl.ioctl(self.fd, I2C_RDWR, data, True)

        assert r == 2

        ret = int.from_bytes(data_buf, data_bo)

        #print(f'READ {addr:#x} (nbytes {nbytes}, bo {endianness}) = {ret:#x} ({v})')

        return ret

    def write(self, addr: int, value: int,
              data_size: int | None = None, data_endianness: Endianness = Endianness.Default,
              addr_size: int | None = None, addr_endianness: Endianness = Endianness.Default):
        if self.mode == MapMode.Read:
            raise RuntimeError()

        if addr_size is None:
            addr_size = self.addr_size
        elif addr_size <= 0:
            raise ValueError(f'Address size must be positive, got {addr_size}')

        if data_size is None:
            data_size = self.data_size
        elif data_size <= 0:
            raise ValueError(f'Data size must be positive, got {data_size}')

        if addr_endianness == Endianness.Default:
            addr_endianness = self.addr_endianness

        if data_endianness == Endianness.Default:
            data_endianness = self.data_endianness

        if addr < self.offset:
            raise RuntimeError()

        if addr + data_size > self.offset + self.length:
            raise RuntimeError()

        addr_bo = self._endianness_to_bo(addr_endianness)
        data_bo = self._endianness_to_bo(data_endianness)

        # ctypes requires a writeable buffer...
        data = bytearray()
        data += addr.to_bytes(addr_size, addr_bo)
        data += value.to_bytes(data_size, data_bo)

        data_buf = (ctypes.c_ubyte * len(data)).from_buffer(data)

        msgs = (i2c_msg * 1)()

        msgs[0].addr = self.i2c_dev_addr
        msgs[0].flags = 0
        msgs[0].len = addr_size + data_size
        msgs[0].buf = data_buf

        ioctl_data = i2c_rdwr_ioctl_data()
        ioctl_data.msgs = msgs
        ioctl_data.nmsgs = 1

        fcntl.ioctl(self.fd, I2C_RDWR, ioctl_data, True)

        #print(f'WRITE {addr:#x} (nbytes {nbytes}, bo {endianness}) = {value:#x}')

        #self._map[addr:addr + nbytes] = value.to_bytes(nbytes, bo, signed=False)
