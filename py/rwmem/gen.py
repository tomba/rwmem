from __future__ import annotations

import io
import struct


class UnpackedField:
    def __init__(self, name, high, low) -> None:
        self.name = name
        self.high = high
        self.low = low

        self.name_offset = -1


class UnpackedRegister:
    def __init__(self, name, offset, fields=None) -> None:
        self.name = name
        self.offset = offset
        if fields:
            self.fields = [f if isinstance(f, UnpackedField) else UnpackedField(*f) for f in fields]
        else:
            self.fields = []

        self.name_offset = -1
        self.first_field_index = -1


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

        self.name_offset = -1
        self.first_reg_index = -1


class UnpackedRegFile:
    def __init__(self, name: str, blocks) -> None:
        self.name = name
        self.blocks = [b if isinstance(b, UnpackedRegBlock) else UnpackedRegBlock(*b) for b in blocks]

    @staticmethod
    def pack_regfile(name_offset, num_blocks, num_regs, num_fields):
        RWMEM_MAGIC = 0x00e11554
        RWMEM_VERSION = 2
        fmt_regfile = '>IIIIII'
        return struct.pack(fmt_regfile, RWMEM_MAGIC, RWMEM_VERSION, name_offset, num_blocks, num_regs, num_fields)

    @staticmethod
    def pack_block(name_offset, block_offset, block_size, num_regs, first_reg_index,
                   addr_e, addr_s, data_e, data_s):
        fmt_block = '>IQQIIBBBB'
        return struct.pack(fmt_block, name_offset, block_offset, block_size, num_regs, first_reg_index,
                           addr_e.value, addr_s, data_e.value, data_s)

    @staticmethod
    def pack_register(name_offset, reg_offset, num_fields, first_field_index):
        fmt_reg = '>IQII'
        return struct.pack(fmt_reg, name_offset, reg_offset, num_fields, first_field_index)

    @staticmethod
    def pack_field(name_offset, high, low):
        fmt_field = '>IBB'
        return struct.pack(fmt_field, name_offset, high, low)

    def pack_to(self, out: io.IOBase):
        blocks = sorted(self.blocks, key=lambda b: b.offset)

        num_blocks = len(blocks)
        num_regs = 0
        num_fields = 0

        # Python 3.7 elevates this implementation detail to a language specification,
        # so it is now mandatory that dict preserves order in all Python implementations
        # compatible with that version or newer

        strs = { '': 0 }
        str_idx = 1

        def get_str_idx(str):
            nonlocal str_idx
            nonlocal strs

            if str not in strs:
                strs[str] = str_idx
                str_idx += len(str) + 1

            return strs[str]

        self.name_offset = get_str_idx(self.name)

        for block in blocks:
            block.regs = sorted(block.regs, key=lambda x: x.offset)
            block.first_reg_index = num_regs
            num_regs += len(block.regs)

            block.name_offset = get_str_idx(block.name)

            if block.size == 0:
                reg = max(block.regs, key=lambda x: x.offset)
                block.size = reg.offset + block.data_size if block.data_size else 4

            for reg in block.regs:
                reg.fields = sorted(reg.fields, key=lambda x: x.high, reverse=True)
                reg.first_field_index = num_fields
                num_fields += len(reg.fields)
                reg.name_offset = get_str_idx(reg.name)

                for field in reg.fields:
                    field.name_offset = get_str_idx(field.name)

        # Write out the data

        out.write(UnpackedRegFile.pack_regfile(self.name_offset, num_blocks, num_regs, num_fields))

        # First all the blocks

        for block in blocks:
            addr_e = block.addr_endianness
            addr_s = block.addr_size
            data_e = block.data_endianness
            data_s = block.data_size

            out.write(UnpackedRegFile.pack_block(block.name_offset, block.offset, block.size,
                                 len(block.regs), block.first_reg_index,
                                 addr_e, addr_s, data_e, data_s))

        # Then all the registers

        for block in blocks:
            for reg in block.regs:
                out.write(UnpackedRegFile.pack_register(reg.name_offset, reg.offset,
                                        len(reg.fields), reg.first_field_index))

        # And then all the fields

        for block in blocks:
            for reg in block.regs:
                for field in reg.fields:
                    try:
                        out.write(UnpackedRegFile.pack_field(field.name_offset, field.high, field.low))
                    except:
                        print(field.name_offset, field.high, field.low)
                        raise

        # At the end, write out all the strings

        first_pos = out.tell()

        for str, idx in strs.items():
            assert idx == out.tell() - first_pos

            out.write(bytes(str, 'ascii'))
            out.write(b'\0')
