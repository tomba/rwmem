"""
Register database v3 binary format structure definitions.

This module defines the ctypes structures used for packing and unpacking
v3 register database binary files. v3 uses little-endian format for
optimal performance on x86/ARM platforms.
"""

import ctypes


class RegisterFileDataV3(ctypes.LittleEndianStructure):
    """v3 register file header (32 bytes)."""
    _pack_ = 1
    _fields_ = [
        ('magic', ctypes.c_uint32),           # Format identifier (0x00e11555)
        ('version', ctypes.c_uint32),         # Format version (3)
        ('name_offset', ctypes.c_uint32),     # Offset to file name in string pool
        ('num_blocks', ctypes.c_uint32),      # Total number of register blocks
        ('num_regs', ctypes.c_uint32),        # Total number of registers
        ('num_fields', ctypes.c_uint32),      # Total number of fields
        ('num_reg_indices', ctypes.c_uint32), # Total number of register index entries
        ('num_field_indices', ctypes.c_uint32), # Total number of field index entries
    ]


class RegisterBlockDataV3(ctypes.LittleEndianStructure):
    """v3 register block definition (36 bytes)."""
    _pack_ = 1
    _fields_ = [
        ('name_offset', ctypes.c_uint32),           # Offset to block name
        ('description_offset', ctypes.c_uint32),    # Offset to block description (0 = no description)
        ('offset', ctypes.c_uint64),                # Base address of register block
        ('size', ctypes.c_uint64),                  # Address space size covered by block
        ('num_regs', ctypes.c_uint32),              # Number of registers in this block
        ('first_reg_list_index', ctypes.c_uint32),  # Index of first register reference in RegisterIndex array
        ('default_addr_endianness', ctypes.c_uint8), # Default address encoding endianness
        ('default_addr_size', ctypes.c_uint8),      # Default address size in bytes (1, 2, 4, 8)
        ('default_data_endianness', ctypes.c_uint8), # Default data encoding endianness
        ('default_data_size', ctypes.c_uint8),      # Default data size in bytes (1, 2, 4, 8)
    ]


class RegisterDataV3(ctypes.LittleEndianStructure):
    """v3 register definition (36 bytes)."""
    _pack_ = 1
    _fields_ = [
        ('name_offset', ctypes.c_uint32),           # Offset to register name
        ('description_offset', ctypes.c_uint32),    # Offset to register description (0 = no description)
        ('offset', ctypes.c_uint64),                # Address offset relative to containing block
        ('reset_value', ctypes.c_uint64),           # Reset value of register
        ('num_fields', ctypes.c_uint32),            # Number of fields for this register
        ('first_field_list_index', ctypes.c_uint32), # Index of first field reference in FieldIndex array
        ('addr_endianness', ctypes.c_uint8),        # Address encoding (0=inherit from block, 1=little, 2=big, 3=little-swapped, 4=big-swapped)
        ('addr_size', ctypes.c_uint8),              # Address size (0=inherit from block, 1,2,4,8=bytes)
        ('data_endianness', ctypes.c_uint8),        # Data encoding (0=inherit from block, 1=little, 2=big, 3=little-swapped, 4=big-swapped)
        ('data_size', ctypes.c_uint8),              # Data size (0=inherit from block, 1,2,4,8=bytes)
    ]


class FieldDataV3(ctypes.LittleEndianStructure):
    """v3 field definition (10 bytes)."""
    _pack_ = 1
    _fields_ = [
        ('name_offset', ctypes.c_uint32),        # Offset to field name
        ('description_offset', ctypes.c_uint32), # Offset to field description (0 = no description)
        ('high', ctypes.c_uint8),                # High bit position (MSB, inclusive)
        ('low', ctypes.c_uint8),                 # Low bit position (LSB, inclusive)
    ]


class RegisterIndexV3(ctypes.LittleEndianStructure):
    """v3 register index entry (4 bytes)."""
    _pack_ = 1
    _fields_ = [
        ('register_index', ctypes.c_uint32),     # Index into RegisterData array
    ]


class FieldIndexV3(ctypes.LittleEndianStructure):
    """v3 field index entry (4 bytes)."""
    _pack_ = 1
    _fields_ = [
        ('field_index', ctypes.c_uint32),        # Index into FieldData array
    ]


# Constants for v3 format
RWMEM_MAGIC_V3 = 0x00e11555
RWMEM_VERSION_V3 = 3
