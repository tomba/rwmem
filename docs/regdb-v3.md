# Register Database Binary Format v3

## Overview

The rwmem register database format v3 enables flexible register definitions and efficient data sharing. The format maintains memory-mappable binary efficiency while allowing flexible and compact register file descriptions.

## File Structure

The v3 binary file uses a sequential layout optimized for memory mapping:

```
+------------------+ <- File start
| RegisterFileData | <- Header (32 bytes)
+------------------+
| RegisterBlockData| <- Block array (40 bytes each)
| RegisterBlockData|
| ...              |
+------------------+
| RegisterData     | <- Register array (34 bytes each)
| RegisterData     |
| ...              |
+------------------+
| FieldData        | <- Field array (10 bytes each)
| FieldData        |
| ...              |
+------------------+
| RegisterIndex    | <- Register index arrays (4 bytes each)
| RegisterIndex    |
| ...              |
+------------------+
| FieldIndex       | <- Field index arrays (4 bytes each)
| FieldIndex       |
| ...              |
+------------------+
| String Pool      | <- Null-terminated strings
| "block1\0"       |
| "register1\0"    |
| "field1\0"       |
| ...              |
+------------------+ <- File end
```

**Key Properties:**
- All multi-byte integers stored in **little-endian format**
- Structures are packed for consistent cross-platform layout
- All data accessible via pointer arithmetic from file start
- Magic number: `0x00e11555`, Version: `3`

## Data Structures

### RegisterFileData (32 bytes)
File header containing metadata and counts:
- `magic` (4 bytes): Format identifier `0x00e11555`
- `version` (4 bytes): Format version `3`
- `name_offset` (4 bytes): Offset to file name in string pool
- `num_blocks` (4 bytes): Total number of register blocks
- `num_regs` (4 bytes): Total number of registers across all blocks
- `num_fields` (4 bytes): Total number of fields across all registers
- `num_reg_indices` (4 bytes): Total number of register index entries
- `num_field_indices` (4 bytes): Total number of field index entries

### RegisterBlockData (36 bytes)
Represents a logical group of registers with shared base properties:
- `name_offset` (4 bytes): Offset to block name
- `description_offset` (4 bytes): Offset to block description (0 = no description)
- `offset` (8 bytes): Base address of register block
- `size` (8 bytes): Address space size covered by block
- `num_regs` (4 bytes): Number of registers in this block
- `first_reg_list_index` (4 bytes): Index of first register reference in RegisterIndex array
- `default_addr_endianness` (1 byte): Default address encoding endianness (for I2C)
- `default_addr_size` (1 byte): Default address size in bytes (1, 2, 4, 8)
- `default_data_endianness` (1 byte): Default data encoding endianness
- `default_data_size` (1 byte): Default data size in bytes (1-8)

Block address settings are inherited by all registers in the block. Data endianness and size can be overridden per-register.

### RegisterData (34 bytes)
Describes an individual register with its own data size/endianness and reset value:
- `name_offset` (4 bytes): Offset to register name
- `description_offset` (4 bytes): Offset to register description (0 = no description)
- `offset` (8 bytes): Address offset relative to containing block
- `reset_value` (8 bytes): Reset value of register (interpret based on data_size)
- `num_fields` (4 bytes): Number of fields for this register
- `first_field_list_index` (4 bytes): Index of first field reference in FieldIndex array
- `data_endianness` (1 byte): Data encoding (0=inherit from block, 1=little, 2=big, 3=little-swapped, 4=big-swapped)
- `data_size` (1 byte): Data size (0=inherit from block, 1-8=bytes)

### FieldData (10 bytes)
Defines a bitfield within a register:
- `name_offset` (4 bytes): Offset to field name
- `description_offset` (4 bytes): Offset to field description (0 = no description)
- `high` (1 byte): High bit position (MSB, inclusive)
- `low` (1 byte): Low bit position (LSB, inclusive)

### RegisterIndex (4 bytes)
Index entry pointing to a register in the RegisterData array:
- `register_index` (4 bytes): Index into RegisterData array

### FieldIndex (4 bytes)
Index entry pointing to a field in the FieldData array:
- `field_index` (4 bytes): Index into FieldData array

## String Pool Management

- Strings are null-terminated ASCII
- References use byte offsets from string pool start
- Duplicate strings are shared (single copy in pool)
- Empty string always at offset 0
- Description fields use offset 0 when no description is provided
