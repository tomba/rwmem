from __future__ import annotations

import collections.abc

import rwmem.helpers
import rwmem.mmaptarget

__all__ = [ 'MappedRegister', 'MappedRegisterBlock', 'MappedRegisterFile' ]

class MappedRegister:
    def __init__(self, map, reg: rwmem.Register, block_offset):
        self._map = map
        self._reg = reg
        self._frozen = None
        self._block_offset = block_offset

    def freeze(self):
        if self._frozen is not None:
            raise RuntimeError('Register already frozen')

        value = self._map.read(self._block_offset + self._reg.offset, data_size=self._reg.effective_data_size)
        self._frozen = self._convert_endianness_if_needed(value, True)

    def unfreeze(self):
        if self._frozen is None:
            raise RuntimeError('Register not frozen')
        converted_val = self._convert_endianness_if_needed(self._frozen, False)
        self._map.write(self._block_offset + self._reg.offset, converted_val, data_size=self._reg.effective_data_size)
        self._frozen = None

    def get_fields(self):
        self.freeze()

        fields = { }
        for f in self._reg.values():
            fields[f.name] = self[f.name]

        self.unfreeze()

        return fields

    def _convert_endianness_if_needed(self, value: int, from_register: bool = True) -> int:
        """Convert endianness if register endianness differs from block endianness."""
        reg_endianness = self._reg.effective_data_endianness
        block_endianness = self._reg.parent_block.data_endianness

        if reg_endianness == block_endianness:
            return value

        # Need to convert between endiannesses
        data_size = self._reg.effective_data_size

        if from_register:
            # Converting from block endianness (MMapTarget) to register endianness
            if data_size == 1:
                return value  # No conversion needed for single bytes
            elif data_size == 2:
                return ((value & 0xFF) << 8) | ((value >> 8) & 0xFF)
            elif data_size == 4:
                return (((value & 0xFF) << 24) |
                       (((value >> 8) & 0xFF) << 16) |
                       (((value >> 16) & 0xFF) << 8) |
                       ((value >> 24) & 0xFF))
            elif data_size == 8:
                return (((value & 0xFF) << 56) |
                       (((value >> 8) & 0xFF) << 48) |
                       (((value >> 16) & 0xFF) << 40) |
                       (((value >> 24) & 0xFF) << 32) |
                       (((value >> 32) & 0xFF) << 24) |
                       (((value >> 40) & 0xFF) << 16) |
                       (((value >> 48) & 0xFF) << 8) |
                       ((value >> 56) & 0xFF))
        else:
            # Converting from register endianness to block endianness (MMapTarget)
            return self._convert_endianness_if_needed(value, True)  # Same conversion

        return value

    def get_value(self) -> int:
        if self._frozen is None:
            value = self._map.read(self._block_offset + self._reg.offset, data_size=self._reg.effective_data_size)
            return self._convert_endianness_if_needed(value, True)
        else:
            return self._frozen

    def set_value(self, val):
        if isinstance(val, dict):
            self.freeze()
            for k,v in val.items():
                self[k] = v
            self.unfreeze()
        else:
            if self._frozen is None:
                converted_val = self._convert_endianness_if_needed(val, False)
                self._map.write(self._block_offset + self._reg.offset, converted_val, data_size=self._reg.effective_data_size)
            else:
                self._frozen = val

    def get_field_value(self, idx: str | int | slice):
        reg_value = self.get_value()

        if isinstance(idx, str):
            f = self._reg[idx]
            if not f:
                raise IndexError('Field not found')

            return rwmem.helpers.get_field_value(reg_value, f.high, f.low)

        elif isinstance(idx, int):
            if idx < 0 or idx >= self._reg.effective_data_size * 8:
                raise IndexError('Index out of bounds')

            return rwmem.helpers.get_field_value(reg_value, idx, idx)
        elif isinstance(idx, slice):
            indices = idx.indices(self._reg.effective_data_size * 8 - 1)

            low = indices[0]
            high = indices[1]

            if low > high:
                low, high = high, low

            return rwmem.helpers.get_field_value(reg_value, high, low)
        else:
            raise IndexError('Field not found')

    def set_field_value(self, idx: str | int | slice, val: int):
        if isinstance(idx, str):
            f = self._reg[idx]
            if not f:
                raise IndexError('Field not found')

            v = self.get_value()
            v = rwmem.helpers.set_field_value(v, f.high, f.low, val)
        elif isinstance(idx, int):
            if idx < 0 or idx >= self._reg.effective_data_size * 8:
                raise IndexError('Index out of bounds')

            v = self.get_value()
            v = rwmem.helpers.set_field_value(v, idx, idx, val)
        elif isinstance(idx, slice):
            indices = idx.indices(self._reg.effective_data_size * 8 - 1)

            low = indices[0]
            high = indices[1]

            if low > high:
                low, high = high, low

            v = self.get_value()
            v = rwmem.helpers.set_field_value(v, high, low, val)
        else:
            raise IndexError('Field not found')

        self.set_value(v)

    @property
    def value(self):
        return self.get_value()

    def __int__(self):
        return self.get_value()

    def __str__(self):
        return '{:#x}'.format(self.get_value())

    def __getitem__(self, idx):
        return self.get_field_value(idx)

    def __setitem__(self, idx, val):
        self.set_field_value(idx, val)

    def __contains__(self, key):
        return key in self._reg


class MappedRegisterBlock(collections.abc.Mapping):
    def __init__(self, file, regblock: rwmem.RegisterBlock,
                 offset: int | None = None,
                 mode = rwmem.MapMode.ReadWrite):
        self._regblock = regblock

        self._offset = regblock.offset if offset is None else offset

        self._map = rwmem.mmaptarget.MMapTarget(file, self._offset, self._regblock.size,
                                     regblock.data_endianness, regblock.data_size,
                                     mode)

        self._registers: dict[str, MappedRegister | None] = dict.fromkeys(regblock.keys())

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_value, exc_tb):
        self._map.close()
        del self._regblock
        self._registers.clear()

    def __getitem__(self, key: str):
        if key not in self._registers:
            raise KeyError(f'MappedRegister "{key}" not found')

        mr = self._registers.get(key)
        if mr:
            return mr

        r = self._regblock.get(key)
        if r:
            mr = MappedRegister(self._map, r, self._offset)
            self._registers[r.name] = mr
            return mr

        raise RuntimeError()

    def __iter__(self):
        return iter(self._registers)

    def __len__(self):
        return len(self._registers)


class MappedRegisterFile(collections.abc.Mapping):
    def __init__(self, rf: rwmem.RegisterFile) -> None:
        self._rf = rf
        self._regblocks: dict[str, MappedRegisterBlock | None] = dict.fromkeys(rf.keys())

    def __getitem__(self, key: str):
        if key not in self._regblocks:
            raise KeyError(f'MappedRegisterBlock "{key}" not found')

        mrb = self._regblocks.get(key)
        if mrb:
            return mrb

        rbi = self._rf.get(key)
        if rbi:
            mrb = MappedRegisterBlock('/dev/mem', rbi)
            self._regblocks[rbi.name] = mrb
            return mrb

        raise RuntimeError()

    def __iter__(self):
        return iter(self._regblocks)

    def __len__(self):
        return len(self._regblocks)
