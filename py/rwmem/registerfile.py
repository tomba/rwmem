from __future__ import annotations

import ctypes
import mmap
import os
import collections.abc
from typing import BinaryIO

from .enums import Endianness

__all__ = [ 'RegisterFile', 'RegisterBlock', 'Register', 'Field' ]


class RegisterFileData(ctypes.BigEndianStructure):
    _pack_ = 1
    _fields_ = [('magic', ctypes.c_uint32),
                ('version', ctypes.c_uint32),
                ('name_offset', ctypes.c_uint32),
                ('num_blocks', ctypes.c_uint32),
                ('num_registers', ctypes.c_uint32),
                ('num_fields', ctypes.c_uint32),
               ]


class RegisterBlockData(ctypes.BigEndianStructure):
    _pack_ = 1
    _fields_ = [
                ('name_offset', ctypes.c_uint32),
                ('offset', ctypes.c_uint64),
                ('size', ctypes.c_uint64),
                ('num_registers', ctypes.c_uint32),
                ('regs_offset', ctypes.c_uint32),
                ('addr_endianness', ctypes.c_uint8),
                ('addr_size', ctypes.c_uint8),
                ('data_endianness', ctypes.c_uint8),
                ('data_size', ctypes.c_uint8),
               ]


class RegisterData(ctypes.BigEndianStructure):
    _pack_ = 1
    _fields_ = [
                ('name_offset', ctypes.c_uint32),
                ('offset', ctypes.c_uint64),
                ('num_fields', ctypes.c_uint32),
                ('fields_offset', ctypes.c_uint32),
               ]


class FieldData(ctypes.BigEndianStructure):
    _pack_ = 1
    _fields_ = [
                ('name_offset', ctypes.c_uint32),
                ('high', ctypes.c_uint8),
                ('low', ctypes.c_uint8),
               ]


class Field:
    def __init__(self, rf: RegisterFile, fd: FieldData) -> None:
        self.rf = rf
        self.fd = fd
        self.name = rf._get_str(fd.name_offset)

    @property
    def high(self) -> int:
        return self.fd.high

    @property
    def low(self) -> int:
        return self.fd.low


class Register(collections.abc.Mapping):
    def __init__(self, rf: RegisterFile, rd: RegisterData) -> None:
        self.rf = rf
        self.rd = rd
        self.name = rf._get_str(rd.name_offset)

        field_names = []

        for idx in range(self.rd.num_fields):
            offset = self.rf._get_field_offset(self.rd.fields_offset + idx)
            fd = FieldData.from_buffer(self.rf._map, offset)
            name = self.rf._get_str(fd.name_offset)
            field_names.append(name)

        self._field_infos: dict[str, Field | None] = dict.fromkeys(field_names)

    @property
    def num_fields(self) -> int:
        return self.rd.num_fields

    @property
    def offset(self) -> int:
        return self.rd.offset

    def __getitem__(self, key: str):
        if key not in self._field_infos:
            raise KeyError(f'Field "{key}" not found')

        rbi = self._field_infos.get(key)
        if rbi:
            return rbi

        for idx in range(self.rd.num_fields):
            offset = self.rf._get_field_offset(self.rd.fields_offset + idx)
            fd = FieldData.from_buffer(self.rf._map, offset)
            name = self.rf._get_str(fd.name_offset)

            if key == name:
                f = Field(self.rf, fd)
                self._field_infos[key] = f
                return f

        raise RuntimeError()

    def __iter__(self):
        return iter(self._field_infos)

    def __len__(self):
        return len(self._field_infos)


class RegisterBlock(collections.abc.Mapping):
    def __init__(self, rf: RegisterFile, rbd: RegisterBlockData) -> None:
        self.rf = rf
        self.rbd = rbd
        self.name = rf._get_str(rbd.name_offset)

        reg_names = []

        for idx in range(self.rbd.num_registers):
            offset = self.rf._get_register_offset(self.rbd.regs_offset + idx)
            rd = RegisterData.from_buffer(self.rf._map, offset)
            name = self.rf._get_str(rd.name_offset)
            reg_names.append(name)

        self._reg_infos: dict[str, Register | None] = dict.fromkeys(reg_names)

    @property
    def num_registers(self) -> int:
        return self.rbd.num_registers

    @property
    def addr_endianness(self):
        return Endianness(self.rbd.addr_endianness)

    @property
    def addr_size(self) -> int:
        return self.rbd.addr_size

    @property
    def data_endianness(self):
        return Endianness(self.rbd.data_endianness)

    @property
    def data_size(self) -> int:
        return self.rbd.data_size

    @property
    def offset(self) -> int:
        return self.rbd.offset

    @property
    def size(self) -> int:
        return self.rbd.size

    def __getitem__(self, key: str):
        if key not in self._reg_infos:
            raise KeyError(f'Register "{key}" not found')

        rbi = self._reg_infos.get(key)
        if rbi:
            return rbi

        for idx in range(self.rbd.num_registers):
            offset = self.rf._get_register_offset(self.rbd.regs_offset + idx)
            rd = RegisterData.from_buffer(self.rf._map, offset)
            name = self.rf._get_str(rd.name_offset)

            if key == name:
                r = Register(self.rf, rd)
                self._reg_infos[key] = r
                return r

        raise RuntimeError()

    def __iter__(self):
        return iter(self._reg_infos)

    def __len__(self):
        return len(self._reg_infos)


class RegisterFile(collections.abc.Mapping):

    RWMEM_MAGIC = 0x00e11554
    RWMEM_VERSION = 2

    def __init__(self, source: str | bytes | BinaryIO) -> None:
        if isinstance(source, str):
            filename = source

            self.fd = os.open(filename, os.O_RDONLY)

            try:
                # ctypes requires a writeable mmap, so we use ACCESS_COPY
                self._map = mmap.mmap(self.fd, 0, mmap.MAP_SHARED, access=mmap.ACCESS_COPY)
            finally:
                os.close(self.fd)
        elif isinstance(source, bytes):
            # XXX ctypes requires a writeable buffer...
            self._map = bytearray(source)
        else:
            self.fd = source.fileno()
            # ctypes requires a writeable mmap, so we use ACCESS_COPY
            self._map = mmap.mmap(self.fd, 0, mmap.MAP_SHARED, access=mmap.ACCESS_COPY)

        self.rfd = RegisterFileData.from_buffer(self._map)

        if self.rfd.magic != RegisterFile.RWMEM_MAGIC:
            raise RuntimeError()

        if self.rfd.version != RegisterFile.RWMEM_VERSION:
            raise RuntimeError()

        self.blocks_offset = ctypes.sizeof(RegisterFileData)
        self.registers_offset = self.blocks_offset + ctypes.sizeof(RegisterBlockData) * self.rfd.num_blocks
        self.fields_offset = self.registers_offset + ctypes.sizeof(RegisterData) * self.rfd.num_registers
        self.strings_offset = self.fields_offset + ctypes.sizeof(FieldData) * self.rfd.num_fields

        self.name = self._get_str(self.rfd.name_offset)

        rb_names = []

        for idx in range(self.rfd.num_blocks):
            offset = self._get_regblock_offset(idx)
            rbd = RegisterBlockData.from_buffer(self._map, offset)
            name = self._get_str(rbd.name_offset)
            rb_names.append(name)

        self._regblock_infos: dict[str, RegisterBlock | None] = dict.fromkeys(rb_names)

    def close(self):
        if self.fd:
            self._map.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, exc_tb):
        if self.fd:
            self._map.close()

    @property
    def num_blocks(self) -> int:
        return self.rfd.num_blocks

    @property
    def num_regs(self) -> int:
        return self.rfd.num_registers

    @property
    def num_fields(self) -> int:
        return self.rfd.num_fields

    def _get_regblock_offset(self, idx: int):
        return self.blocks_offset + ctypes.sizeof(RegisterBlockData) * idx

    def _get_register_offset(self, idx: int):
        return self.registers_offset + ctypes.sizeof(RegisterData) * idx

    def _get_field_offset(self, idx: int):
        return self.fields_offset + ctypes.sizeof(FieldData) * idx

    def _get_str(self, offset: int):
        c = ctypes.c_char.from_buffer(self._map, self.strings_offset + offset)
        c_addr = ctypes.addressof(c)
        cp = ctypes.c_char_p(c_addr)
        v = cp.value
        if not v:
            raise RuntimeError()
        return v.decode('ascii') # pylint: disable=no-member

    def __getitem__(self, key: str):
        if key not in self._regblock_infos:
            raise KeyError(f'RegisterBlock "{key}" not found')

        rbi = self._regblock_infos.get(key)
        if rbi:
            return rbi

        for idx in range(self.rfd.num_blocks):
            offset = self._get_regblock_offset(idx)

            rbd = RegisterBlockData.from_buffer(self._map, offset)
            name = self._get_str(rbd.name_offset)

            if key == name:
                rb = RegisterBlock(self, rbd)
                self._regblock_infos[key] = rb
                return rb

        raise RuntimeError()

    def __iter__(self):
        return iter(self._regblock_infos)

    def __len__(self):
        return len(self._regblock_infos)
