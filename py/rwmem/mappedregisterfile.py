from __future__ import annotations

import collections.abc

import rwmem.helpers
import rwmem.mmaptarget

__all__ = [ 'MappedRegister', 'MappedRegisterBlock', 'MappedRegisterFile' ]

class MappedRegister:
    __initialized = False

    def __init__(self, map, reg: rwmem.Register, size, regblock):
        self._map = map
        self._size = size
        self._reg = reg
        self._frozen = None
        self.regblock = regblock
        self.__initialized = True

    def freeze(self):
        if not self._frozen is None:
            raise RuntimeError('Register already frozen')

        self._frozen = self._map.read(self.regblock.offset + self._reg.offset, data_size=self._size)

    def unfreeze(self):
        self._map.write(self.regblock.offset + self._reg.offset, self._frozen, data_size=self._size)
        self._frozen = None

    def get_fields(self):
        self.freeze()

        fields = { }
        for f in self._reg.values():
            fields[f.name] = self[f.name]

        self.unfreeze()

        return fields

    def get_value(self) -> int:
        if self._frozen is None:
            return self._map.read(self.regblock.offset + self._reg.offset, data_size=self._size)
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
                self._map.write(self.regblock.offset + self._reg.offset, val, data_size=self._size)
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
            if idx < 0 or idx >= self._size * 8:
                raise IndexError('Index out of bounds')

            return rwmem.helpers.get_field_value(reg_value, idx, idx)
        elif isinstance(idx, slice):
            indices = idx.indices(self._size * 8 - 1)

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
            if idx < 0 or idx >= self._size * 8:
                raise IndexError('Index out of bounds')

            v = self.get_value()
            v = rwmem.helpers.set_field_value(v, idx, idx, val)
        elif isinstance(idx, slice):
            indices = idx.indices(self._size * 8 - 1)

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

    def __getattr__(self, key):
        if key in self._reg:
            return self.get_field_value(key)
        else:
            raise AttributeError('No field {0} found!'.format(key))

    def __setattr__(self, key, value):
        if not self.__initialized or key in dir(self):
            super().__setattr__(key, value)
            return

        if key not in self._reg:
            raise AttributeError('No field {0} found!'.format(key))

        self.set_field_value(key, value)


class MappedRegisterBlock(collections.abc.Mapping):
    __initialized = False

    def __init__(self, file, regblock: rwmem.RegisterBlock,
                 offset: int | None = None,
                 mode = rwmem.MapMode.ReadWrite):
        self._regblock = regblock

        offset = regblock.offset if not offset else offset

        self._map = rwmem.mmaptarget.MMapTarget(file, offset, self._regblock.size,
                                     regblock.data_endianness, regblock.data_size,
                                     mode)

        self._registers: dict[str, MappedRegister | None] = dict.fromkeys(regblock.keys())

        self.__initialized = True

    def __getitem__(self, key: str):
        if key not in self._registers:
            raise KeyError(f'MappedRegister "{key}" not found')

        mr = self._registers.get(key)
        if mr:
            return mr

        r = self._regblock.get(key)
        if r:
            mr = MappedRegister(self._map, r, self._regblock.data_size, self._regblock)
            self._registers[r.name] = mr
            return mr

        raise RuntimeError()

    def __iter__(self):
        return iter(self._registers)

    def __len__(self):
        return len(self._registers)

    def __getattr__(self, key):
        if key in self:
            return self[key]
        else:
            raise AttributeError(f'No MappedRegister {key} found!')

    def __setitem__(self, key, val):
        reg = self.__getitem__(key)
        reg.set_value(val)

    def __setattr__(self, key, value):
        if not self.__initialized:
            super().__setattr__(key, value)
            return

        self.__setitem__(key, value)


class MappedRegisterFile(collections.abc.Mapping):
    __initialized = False

    def __init__(self, rf: rwmem.RegisterFile) -> None:
        self._rf = rf
        self._regblocks: dict[str, MappedRegisterBlock | None] = dict.fromkeys(rf.keys())
        self.__initialized = True

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

    def __getattr__(self, key):
        if key in self:
            return self[key]
        else:
            raise AttributeError(f'No MappedRegisterBlock {key} found!')

    def __setitem__(self, key, val):
        raise TypeError()

    def __setattr__(self, key, value):
        if self.__initialized:
            raise TypeError()

        super().__setattr__(key, value)
