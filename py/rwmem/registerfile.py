from __future__ import annotations

import ctypes
import gc
import mmap
import os
import collections.abc
from typing import BinaryIO

from .enums import Endianness
from ._structs import (
    RegisterFileDataV3 as RegisterFileData,
    RegisterBlockDataV3 as RegisterBlockData,
    RegisterDataV3 as RegisterData,
    FieldDataV3 as FieldData,
    RegisterIndexV3,
    FieldIndexV3,
    RWMEM_MAGIC_V3 as RWMEM_MAGIC,
    RWMEM_VERSION_V3 as RWMEM_VERSION,
)

__all__ = [ 'RegisterFile', 'RegisterBlock', 'Register', 'Field' ]


# Structure definitions now imported from _structs.py


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

    @property
    def description(self) -> str | None:
        """Get field description, or None if not provided."""
        if self.fd.description_offset == 0:
            return None
        return self.rf._get_str(self.fd.description_offset)



class Register(collections.abc.Mapping):
    def __init__(self, rf: RegisterFile, rd: RegisterData, parent_block: RegisterBlock) -> None:
        self.rf = rf
        self.rd = rd
        self.parent_block = parent_block
        self.name = rf._get_str(rd.name_offset)

        field_names = []

        for idx in range(self.rd.num_fields):
            # Get field index from the FieldIndex array
            field_index_offset = self.rf.field_indices_offset + ctypes.sizeof(FieldIndexV3) * (self.rd.first_field_list_index + idx)
            field_index_data = FieldIndexV3.from_buffer(self.rf._map, field_index_offset)
            actual_field_index = field_index_data.field_index

            # Get the actual field using the resolved index
            offset = self.rf._get_field_offset(actual_field_index)
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

    @property
    def description(self) -> str | None:
        """Get register description, or None if not provided."""
        if self.rd.description_offset == 0:
            return None
        return self.rf._get_str(self.rd.description_offset)

    @property
    def reset_value(self) -> int:
        """Get register reset value."""
        return self.rd.reset_value


    @property
    def effective_addr_endianness(self) -> Endianness:
        """Get effective address endianness (register-specific or inherited from block)."""
        if self.rd.addr_endianness == 0:  # Inherit from block
            return self.parent_block.addr_endianness
        return Endianness(self.rd.addr_endianness)

    @property
    def effective_addr_size(self) -> int:
        """Get effective address size (register-specific or inherited from block)."""
        if self.rd.addr_size == 0:  # Inherit from block
            return self.parent_block.addr_size
        return self.rd.addr_size

    @property
    def effective_data_endianness(self) -> Endianness:
        """Get effective data endianness (register-specific or inherited from block)."""
        if self.rd.data_endianness == 0:  # Inherit from block
            return self.parent_block.data_endianness
        return Endianness(self.rd.data_endianness)

    @property
    def effective_data_size(self) -> int:
        """Get effective data size (register-specific or inherited from block)."""
        if self.rd.data_size == 0:  # Inherit from block
            return self.parent_block.data_size
        return self.rd.data_size

    def __getitem__(self, key: str):
        if key not in self._field_infos:
            raise KeyError(f'Field "{key}" not found')

        rbi = self._field_infos.get(key)
        if rbi:
            return rbi

        for idx in range(self.rd.num_fields):
            # Get field index from the FieldIndex array
            field_index_offset = self.rf.field_indices_offset + ctypes.sizeof(FieldIndexV3) * (self.rd.first_field_list_index + idx)
            field_index_data = FieldIndexV3.from_buffer(self.rf._map, field_index_offset)
            actual_field_index = field_index_data.field_index

            # Get the actual field using the resolved index
            offset = self.rf._get_field_offset(actual_field_index)
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

        for idx in range(self.rbd.num_regs):
            # Get register index from the RegisterIndex array
            reg_index_offset = self.rf.register_indices_offset + ctypes.sizeof(RegisterIndexV3) * (self.rbd.first_reg_list_index + idx)
            reg_index_data = RegisterIndexV3.from_buffer(self.rf._map, reg_index_offset)
            actual_reg_index = reg_index_data.register_index

            # Get the actual register using the resolved index
            offset = self.rf._get_register_offset(actual_reg_index)
            rd = RegisterData.from_buffer(self.rf._map, offset)
            name = self.rf._get_str(rd.name_offset)
            reg_names.append(name)

        self._reg_infos: dict[str, Register | None] = dict.fromkeys(reg_names)

    @property
    def num_registers(self) -> int:
        return self.rbd.num_regs

    @property
    def addr_endianness(self):
        return Endianness(self.rbd.default_addr_endianness)

    @property
    def addr_size(self) -> int:
        return self.rbd.default_addr_size

    @property
    def data_endianness(self):
        return Endianness(self.rbd.default_data_endianness)

    @property
    def data_size(self) -> int:
        return self.rbd.default_data_size

    @property
    def offset(self) -> int:
        return self.rbd.offset

    @property
    def size(self) -> int:
        return self.rbd.size

    @property
    def description(self) -> str | None:
        """Get block description, or None if not provided."""
        if self.rbd.description_offset == 0:
            return None
        return self.rf._get_str(self.rbd.description_offset)

    def __getitem__(self, key: str):
        if key not in self._reg_infos:
            raise KeyError(f'Register "{key}" not found')

        rbi = self._reg_infos.get(key)
        if rbi:
            return rbi

        for idx in range(self.rbd.num_regs):
            # Get register index from the RegisterIndex array
            reg_index_offset = self.rf.register_indices_offset + ctypes.sizeof(RegisterIndexV3) * (self.rbd.first_reg_list_index + idx)
            reg_index_data = RegisterIndexV3.from_buffer(self.rf._map, reg_index_offset)
            actual_reg_index = reg_index_data.register_index

            # Get the actual register using the resolved index
            offset = self.rf._get_register_offset(actual_reg_index)
            rd = RegisterData.from_buffer(self.rf._map, offset)
            name = self.rf._get_str(rd.name_offset)

            if key == name:
                r = Register(self.rf, rd, self)
                self._reg_infos[key] = r
                return r

        raise RuntimeError()

    def __iter__(self):
        return iter(self._reg_infos)

    def __len__(self):
        return len(self._reg_infos)


class RegisterFile(collections.abc.Mapping):

    RWMEM_MAGIC = RWMEM_MAGIC
    RWMEM_VERSION = RWMEM_VERSION

    def __init__(self, source: str | bytes | BinaryIO) -> None:
        if isinstance(source, str):
            filename = source

            self.fd = os.open(filename, os.O_RDONLY)

            try:
                # ctypes requires a writeable mmap, so we use ACCESS_COPY
                self._map = mmap.mmap(self.fd, 0, mmap.MAP_SHARED, access=mmap.ACCESS_COPY)
            finally:
                os.close(self.fd)

            self._mmap = self._map
        elif isinstance(source, bytes):
            # XXX ctypes requires a writeable buffer...
            self._map = bytearray(source)
            self._mmap = None
        elif isinstance(source, BinaryIO):
            self.fd = source.fileno()
            # ctypes requires a writeable mmap, so we use ACCESS_COPY
            self._map = mmap.mmap(self.fd, 0, mmap.MAP_SHARED, access=mmap.ACCESS_COPY)
            self._mmap = self._map
        else:
            raise TypeError(f'Unsupported source type: {type(source)}')

        self.rfd = RegisterFileData.from_buffer(self._map)

        if self.rfd.magic != RegisterFile.RWMEM_MAGIC:
            raise RuntimeError()

        if self.rfd.version != RegisterFile.RWMEM_VERSION:
            raise RuntimeError()

        self.blocks_offset = ctypes.sizeof(RegisterFileData)
        self.registers_offset = self.blocks_offset + ctypes.sizeof(RegisterBlockData) * self.rfd.num_blocks
        self.fields_offset = self.registers_offset + ctypes.sizeof(RegisterData) * self.rfd.num_regs
        self.register_indices_offset = self.fields_offset + ctypes.sizeof(FieldData) * self.rfd.num_fields
        self.field_indices_offset = self.register_indices_offset + ctypes.sizeof(RegisterIndexV3) * self.rfd.num_reg_indices
        self.strings_offset = self.field_indices_offset + ctypes.sizeof(FieldIndexV3) * self.rfd.num_field_indices

        self.name = self._get_str(self.rfd.name_offset)

        rb_names = []

        for idx in range(self.rfd.num_blocks):
            offset = self._get_regblock_offset(idx)
            rbd = RegisterBlockData.from_buffer(self._map, offset)
            name = self._get_str(rbd.name_offset)
            rb_names.append(name)

        self._regblock_infos: dict[str, RegisterBlock | None] = dict.fromkeys(rb_names)

    def close(self):
        if self._mmap:
            self._mmap.close()

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, exc_tb):
        del self.rfd
        self._regblock_infos.clear()
        # Force garbage collection to clean up circular references in ctypes structures
        gc.collect()
        if self._mmap:
            self._mmap.close()

    @property
    def num_blocks(self) -> int:
        return self.rfd.num_blocks

    @property
    def num_regs(self) -> int:
        return self.rfd.num_regs

    @property
    def num_fields(self) -> int:
        return self.rfd.num_fields

    @property
    def num_reg_indices(self) -> int:
        return self.rfd.num_reg_indices

    @property
    def num_field_indices(self) -> int:
        return self.rfd.num_field_indices

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
