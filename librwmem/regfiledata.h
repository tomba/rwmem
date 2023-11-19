#pragma once

#include <cstdint>
#include <endian.h>
#include <string>

#include "helpers.h"

const uint32_t RWMEM_MAGIC = 0x00e11554;
const uint32_t RWMEM_VERSION = 2;

struct __attribute__((packed)) RegisterFileData;
struct __attribute__((packed)) RegisterBlockData;
struct __attribute__((packed)) RegisterData;
struct __attribute__((packed)) FieldData;

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
