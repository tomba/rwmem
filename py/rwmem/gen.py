from __future__ import annotations

import io

from ._packer import RegFilePacker


class UnpackedField:
    def __init__(self, name, high, low) -> None:
        self.name = name
        self.high = high
        self.low = low


class UnpackedRegister:
    def __init__(self, name, offset, fields=None) -> None:
        self.name = name
        self.offset = offset
        if fields:
            self.fields = [f if isinstance(f, UnpackedField) else UnpackedField(*f) for f in fields]
        else:
            self.fields = []


class UnpackedRegBlock:
    def __init__(self, name, offset, size, regs, addr_endianness, addr_size, data_endianness, data_size) -> None:
        self.name = name
        self.offset = offset
        self.size = size
        self.regs = [r if isinstance(r, UnpackedRegister) else UnpackedRegister(*r) for r in regs]
        self.addr_endianness = addr_endianness
        self.addr_size = addr_size
        self.data_endianness = data_endianness
        self.data_size = data_size


class UnpackedRegFile:
    def __init__(self, name: str, blocks) -> None:
        self.name = name
        self.blocks = [b if isinstance(b, UnpackedRegBlock) else UnpackedRegBlock(*b) for b in blocks]

    def pack_to(self, out: io.IOBase):
        packer = RegFilePacker(self)
        packer.pack_to(out)
