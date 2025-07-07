#pragma once

#include <cstdint>
#include <endian.h>
#include <string>

#include "endianness.h"

/*
 * Binary Register File Format
 * ===========================
 *
 * This file defines the binary format for rwmem register description files.
 * The format is designed to be memory-mappable and efficient for lookups.
 *
 * File Structure:
 * ---------------
 * The binary file is laid out as a single contiguous block of memory with
 * the following structure:
 *
 * +------------------+
 * | RegisterFileData | <- File header with counts and metadata
 * +------------------+
 * | RegisterBlockData| <- Array of register blocks
 * | RegisterBlockData|
 * | ...              |
 * +------------------+
 * | RegisterData     | <- Array of all registers from all blocks
 * | RegisterData     |
 * | ...              |
 * +------------------+
 * | FieldData        | <- Array of all fields from all registers
 * | FieldData        |
 * | ...              |
 * +------------------+
 * | String Pool      | <- Null-terminated strings referenced by offsets
 * | "block1\0"       |
 * | "register1\0"    |
 * | "field1\0"       |
 * | ...              |
 * +------------------+
 *
 * Key Design Principles:
 * - All multi-byte integers are stored in big-endian format
 * - Structures are packed to ensure consistent layout across platforms
 * - String references use offsets into the string pool for space efficiency
 * - Arrays are contiguous and indexed by offset/count pairs
 * - The entire file can be memory-mapped for direct access
 *
 * Hierarchy:
 * - RegisterFile contains multiple RegisterBlocks
 * - RegisterBlock contains multiple Registers
 * - Register contains multiple Fields (bitfield definitions)
 *
 * Access Pattern:
 * 1. Memory-map the file
 * 2. Cast the start to RegisterFileData*
 * 3. Use pointer arithmetic to access arrays and strings
 * 4. All offsets are relative to the start of the file
 */

const uint32_t RWMEM_MAGIC = 0x00e11554;
const uint32_t RWMEM_VERSION = 2;

struct __attribute__((packed)) RegisterFileData;
struct __attribute__((packed)) RegisterBlockData;
struct __attribute__((packed)) RegisterData;
struct __attribute__((packed)) FieldData;

/**
 * RegisterFileData - File header and root structure
 *
 * This is the first structure in the binary file and serves as the file header.
 * It contains magic number, version, and counts for all data structures in the file.
 * All arrays in the file are accessed through this structure using pointer arithmetic.
 *
 * Layout (24 bytes):
 * - magic (4 bytes): File format identifier (0x00e11554)
 * - version (4 bytes): Format version number
 * - name_offset (4 bytes): Offset to file name in string pool
 * - num_blocks (4 bytes): Count of RegisterBlockData structures
 * - num_regs (4 bytes): Total count of RegisterData structures
 * - num_fields (4 bytes): Total count of FieldData structures
 */
struct __attribute__((packed)) RegisterFileData {
	/// rwmem database magic number
	uint32_t magic() const { return be32toh(m_magic); }
	/// rwmem database version number
	uint32_t version() const { return be32toh(m_version); }
	/// Offset of the RegisterFile name
	uint32_t name_offset() const { return be32toh(m_name_offset); }
	/// Total number of RegisterBlocks in this file
	uint32_t num_blocks() const { return be32toh(m_num_blocks); }
	/// Total number of Registers in this file
	uint32_t num_regs() const { return be32toh(m_num_regs); }
	/// Total number of fields in this file
	uint32_t num_fields() const { return be32toh(m_num_fields); }

	/// Pointer to the first RegisterBlockData
	const RegisterBlockData* blocks() const;
	/// Pointer to the first RegisterData
	const RegisterData* registers() const;
	/// Pointer to the first FieldData
	const FieldData* fields() const;
	/// Pointer to the first string
	const char* strings() const;

	/// Name of the RegisterFile
	const char* name() const { return strings() + name_offset(); }
	/// Pointer to the 'idx' RegisterBlockData
	const RegisterBlockData* at(uint32_t idx) const;
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
 * - offset (8 bytes): Base address of this register block
 * - size (8 bytes): Size of address space covered by this block
 * - num_registers (4 bytes): Count of registers in this block
 * - regs_offset (4 bytes): Index of first register in global register array
 * - addr_endianness (1 byte): Endianness for address encoding (I2C)
 * - addr_size (1 byte): Address size in bytes (I2C)
 * - data_endianness (1 byte): Endianness for data encoding
 * - data_size (1 byte): Data size in bytes
 */
struct __attribute__((packed)) RegisterBlockData {
	/// Offset of the RegisterBlock name
	uint32_t name_offset() const { return be32toh(m_name_offset); }
	/// Address offset of the registers in this RegisterBlock
	uint64_t offset() const { return be64toh(m_offset); }
	/// Size of this RegisterBlock in bytes
	uint64_t size() const { return be64toh(m_size); }
	/// Number of Registers in this RegisterBlock
	uint32_t num_regs() const { return be32toh(m_num_registers); }
	/// Offset of the first register in this RegisterBlock
	uint32_t regs_offset() const { return be32toh(m_regs_offset); }
	/// Endianness of the address (for i2c)
	Endianness addr_endianness() const { return (Endianness)m_addr_endianness; }
	/// Size of the address in bytes (for i2c)
	uint8_t addr_size() const { return m_addr_size; }
	/// Endianness of the register data
	Endianness data_endianness() const { return (Endianness)m_data_endianness; }
	/// Size of the register data in bytes
	uint8_t data_size() const { return m_data_size; }

	const char* name(const RegisterFileData* rfd) const { return rfd->strings() + name_offset(); }
	const RegisterData* at(const RegisterFileData* rfd, uint32_t idx) const;
	const RegisterData* find_register(const RegisterFileData* rfd, const std::string& name) const;
	const RegisterData* find_register(const RegisterFileData* rfd, uint64_t offset) const;

private:
	uint32_t m_name_offset;
	uint64_t m_offset;
	uint64_t m_size;
	uint32_t m_num_registers;
	uint32_t m_regs_offset;

	uint8_t m_addr_endianness;
	uint8_t m_addr_size;
	uint8_t m_data_endianness;
	uint8_t m_data_size;
};

/**
 * RegisterData - Describes a single register within a register block
 *
 * Represents an individual register with its address offset (relative to the
 * containing RegisterBlock) and associated bitfield definitions.
 *
 * Layout (20 bytes):
 * - name_offset (4 bytes): Offset to register name in string pool
 * - offset (8 bytes): Address offset relative to containing RegisterBlock
 * - num_fields (4 bytes): Count of bitfield definitions for this register
 * - fields_offset (4 bytes): Index of first field in global fields array
 */
struct __attribute__((packed)) RegisterData {
	uint32_t name_offset() const { return be32toh(m_name_offset); }
	uint64_t offset() const { return be64toh(m_offset); }

	uint32_t num_fields() const { return be32toh(m_num_fields); }
	uint32_t fields_offset() const { return be32toh(m_fields_offset); }

	const char* name(const RegisterFileData* rfd) const { return rfd->strings() + name_offset(); }
	const FieldData* at(const RegisterFileData* rfd, uint32_t idx) const;
	const FieldData* find_field(const RegisterFileData* rfd, const std::string& name) const;
	const FieldData* find_field(const RegisterFileData* rfd, uint8_t high, uint8_t low) const;

private:
	uint32_t m_name_offset;
	uint64_t m_offset;

	uint32_t m_num_fields;
	uint32_t m_fields_offset;
};

/**
 * FieldData - Describes a bitfield within a register
 *
 * Represents a named bitfield or bit range within a register, defined by
 * high and low bit positions (inclusive range).
 *
 * Layout (6 bytes):
 * - name_offset (4 bytes): Offset to field name in string pool
 * - high (1 byte): High bit position (MSB of field)
 * - low (1 byte): Low bit position (LSB of field)
 */
struct __attribute__((packed)) FieldData {
	uint32_t name_offset() const { return be32toh(m_name_offset); }
	uint8_t low() const { return m_low; }
	uint8_t high() const { return m_high; }

	const char* name(const RegisterFileData* rfd) const { return rfd->strings() + name_offset(); }

private:
	uint32_t m_name_offset;
	uint8_t m_high;
	uint8_t m_low;
};
