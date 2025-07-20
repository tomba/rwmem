#pragma once

#include <cstdint>
#include <endian.h>
#include <string>

#include "endianness.h"

const uint32_t RWMEM_MAGIC = 0x00e11555;
const uint32_t RWMEM_VERSION = 3;

struct __attribute__((packed)) RegisterFileData;
struct __attribute__((packed)) RegisterBlockData;
struct __attribute__((packed)) RegisterData;
struct __attribute__((packed)) FieldData;
struct __attribute__((packed)) RegisterIndex;
struct __attribute__((packed)) FieldIndex;

/**
 * RegisterFileData - File header and root structure
 *
 * This is the first structure in the binary file and serves as the file header.
 * It contains magic number, version, and counts for all data structures in the file.
 * All arrays in the file are accessed through this structure using pointer arithmetic.
 *
 * Layout (32 bytes):
 * - magic (4 bytes): File format identifier (0x00e11555)
 * - version (4 bytes): Format version number
 * - name_offset (4 bytes): Offset to file name in string pool
 * - num_blocks (4 bytes): Count of RegisterBlockData structures
 * - num_regs (4 bytes): Total count of RegisterData structures
 * - num_fields (4 bytes): Total count of FieldData structures
 * - num_reg_indices (4 bytes): Total count of RegisterIndex entries
 * - num_field_indices (4 bytes): Total count of FieldIndex entries
 */
struct __attribute__((packed)) RegisterFileData {
	/// rwmem database magic number
	uint32_t magic() const { return le32toh(m_magic); }
	/// rwmem database version number
	uint32_t version() const { return le32toh(m_version); }
	/// Offset of the RegisterFile name
	uint32_t name_offset() const { return le32toh(m_name_offset); }
	/// Total number of RegisterBlocks in this file
	uint32_t num_blocks() const { return le32toh(m_num_blocks); }
	/// Total number of Registers in this file
	uint32_t num_regs() const { return le32toh(m_num_regs); }
	/// Total number of fields in this file
	uint32_t num_fields() const { return le32toh(m_num_fields); }
	/// Total number of register index entries
	uint32_t num_reg_indices() const { return le32toh(m_num_reg_indices); }
	/// Total number of field index entries
	uint32_t num_field_indices() const { return le32toh(m_num_field_indices); }

	/// Pointer to the first RegisterBlockData
	const RegisterBlockData* blocks() const;
	/// Pointer to the first RegisterData
	const RegisterData* registers() const;
	/// Pointer to the first FieldData
	const FieldData* fields() const;
	/// Pointer to the first RegisterIndex
	const uint32_t* register_indices() const;
	/// Pointer to the first FieldIndex
	const uint32_t* field_indices() const;
	/// Pointer to the first string
	const char* strings() const;

	/// Name of the RegisterFile
	const char* name() const { return strings() + name_offset(); }
	/// Pointer to the 'idx' RegisterBlockData
	const RegisterBlockData* block_at(uint32_t idx) const;
	/// Find RegisterBlockData with the given name
	const RegisterBlockData* find_block(const std::string& name) const;

	const RegisterData* find_register(const std::string& name, const RegisterBlockData** rbd) const;
	const RegisterData* find_register(uint64_t offset, const RegisterBlockData** rbd) const;

private:
	uint32_t m_magic;
	uint32_t m_version;
	uint32_t m_name_offset;
	uint32_t m_num_blocks;
	uint32_t m_num_regs;
	uint32_t m_num_fields;
	uint32_t m_num_reg_indices;
	uint32_t m_num_field_indices;
};

/**
 * RegisterBlockData - Describes a contiguous block of registers
 *
 * Represents a logical group of registers that share common properties like
 * address space, endianness, and data size. Used for both memory-mapped and
 * I2C register access patterns.
 *
 * Layout (36 bytes):
 * - name_offset (4 bytes): Offset to block name in string pool
 * - description_offset (4 bytes): Offset to block description in string pool
 * - offset (8 bytes): Base address of this register block
 * - size (8 bytes): Size of address space covered by this block
 * - num_registers (4 bytes): Count of registers in this block
 * - first_reg_list_index (4 bytes): Index of first register reference in RegisterIndex array
 * - default_addr_endianness (1 byte): Default endianness for address encoding (I2C)
 * - default_addr_size (1 byte): Default address size in bytes (I2C)
 * - default_data_endianness (1 byte): Default endianness for data encoding
 * - default_data_size (1 byte): Default data size in bytes
 */
struct __attribute__((packed)) RegisterBlockData {
	/// Offset of the RegisterBlock name
	uint32_t name_offset() const { return le32toh(m_name_offset); }
	/// Offset of the RegisterBlock description
	uint32_t description_offset() const { return le32toh(m_description_offset); }
	/// Address offset of the registers in this RegisterBlock
	uint64_t offset() const { return le64toh(m_offset); }
	/// Size of this RegisterBlock in bytes
	uint64_t size() const { return le64toh(m_size); }
	/// Number of Registers in this RegisterBlock
	uint32_t num_regs() const { return le32toh(m_num_regs); }
	/// Index of first register reference in RegisterIndex array
	uint32_t first_reg_list_index() const { return le32toh(m_first_reg_list_index); }
	/// Endianness of the address (for i2c) - block default
	Endianness addr_endianness() const { return (Endianness)m_default_addr_endianness; }
	/// Size of the address in bytes (for i2c) - block default
	uint8_t addr_size() const { return m_default_addr_size; }
	/// Endianness of the register data - block default
	Endianness data_endianness() const { return (Endianness)m_default_data_endianness; }
	/// Size of the register data in bytes - block default
	uint8_t data_size() const { return m_default_data_size; }

	const char* name(const RegisterFileData* rfd) const { return rfd->strings() + name_offset(); }
	const RegisterData* register_at(const RegisterFileData* rfd, uint32_t idx) const;
	const RegisterData* find_register(const RegisterFileData* rfd, const std::string& name) const;
	const RegisterData* find_register(const RegisterFileData* rfd, uint64_t offset) const;

private:
	uint32_t m_name_offset;
	uint32_t m_description_offset;
	uint64_t m_offset;
	uint64_t m_size;
	uint32_t m_num_regs;
	uint32_t m_first_reg_list_index;

	uint8_t m_default_addr_endianness;
	uint8_t m_default_addr_size;
	uint8_t m_default_data_endianness;
	uint8_t m_default_data_size;
};

/**
 * RegisterData - Describes a single register within a register block
 *
 * Represents an individual register with its address offset (relative to the
 * containing RegisterBlock) and associated bitfield definitions.
 *
 * Layout (34 bytes):
 * - name_offset (4 bytes): Offset to register name in string pool
 * - description_offset (4 bytes): Offset to register description in string pool
 * - offset (8 bytes): Address offset relative to containing RegisterBlock
 * - reset_value (8 bytes): Reset value of register
 * - num_fields (4 bytes): Count of bitfield definitions for this register
 * - first_field_list_index (4 bytes): Index of first field reference in FieldIndex array
 * - data_endianness (1 byte): Data encoding (0=inherit from block, others override)
 * - data_size (1 byte): Data size (0=inherit from block, others override)
 */
struct __attribute__((packed)) RegisterData {
	uint32_t name_offset() const { return le32toh(m_name_offset); }
	uint32_t description_offset() const { return le32toh(m_description_offset); }
	uint64_t offset() const { return le64toh(m_offset); }
	uint64_t reset_value() const { return le64toh(m_reset_value); }

	uint32_t num_fields() const { return le32toh(m_num_fields); }
	uint32_t first_field_index() const { return le32toh(m_first_field_list_index); }

	uint8_t data_endianness() const { return m_data_endianness; }
	uint8_t data_size() const { return m_data_size; }

	const char* name(const RegisterFileData* rfd) const { return rfd->strings() + name_offset(); }
	const FieldData* field_at(const RegisterFileData* rfd, uint32_t idx) const;
	const FieldData* find_field(const RegisterFileData* rfd, const std::string& name) const;
	const FieldData* find_field(const RegisterFileData* rfd, uint8_t high, uint8_t low) const;

	/// Get effective data endianness (resolve inheritance from block)
	Endianness effective_data_endianness(const RegisterBlockData* rbd) const;
	/// Get effective data size (resolve inheritance from block)
	uint8_t effective_data_size(const RegisterBlockData* rbd) const;

private:
	uint32_t m_name_offset;
	uint32_t m_description_offset;
	uint64_t m_offset;
	uint64_t m_reset_value;

	uint32_t m_num_fields;
	uint32_t m_first_field_list_index;

	uint8_t m_data_endianness;
	uint8_t m_data_size;
};

/**
 * FieldData - Describes a bitfield within a register
 *
 * Represents a named bitfield or bit range within a register, defined by
 * high and low bit positions (inclusive range).
 *
 * Layout (10 bytes):
 * - name_offset (4 bytes): Offset to field name in string pool
 * - description_offset (4 bytes): Offset to field description in string pool
 * - high (1 byte): High bit position (MSB of field)
 * - low (1 byte): Low bit position (LSB of field)
 */
struct __attribute__((packed)) FieldData {
	uint32_t name_offset() const { return le32toh(m_name_offset); }
	uint32_t description_offset() const { return le32toh(m_description_offset); }
	uint8_t low() const { return m_low; }
	uint8_t high() const { return m_high; }

	const char* name(const RegisterFileData* rfd) const { return rfd->strings() + name_offset(); }

private:
	uint32_t m_name_offset;
	uint32_t m_description_offset;
	uint8_t m_high;
	uint8_t m_low;
};

/**
 * RegisterIndex - Index entry pointing to a register
 *
 * Used for indirection in register lists to enable sharing of register
 * definitions between blocks.
 *
 * Layout (4 bytes):
 * - register_index (4 bytes): Index into RegisterData array
 */
struct __attribute__((packed)) RegisterIndex {
	uint32_t register_index() const { return le32toh(m_register_index); }

private:
	uint32_t m_register_index;
};

/**
 * FieldIndex - Index entry pointing to a field
 *
 * Used for indirection in field lists to enable sharing of field
 * definitions between registers.
 *
 * Layout (4 bytes):
 * - field_index (4 bytes): Index into FieldData array
 */
struct __attribute__((packed)) FieldIndex {
	uint32_t field_index() const { return le32toh(m_field_index); }

private:
	uint32_t m_field_index;
};
