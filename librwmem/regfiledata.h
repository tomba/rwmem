#pragma once

#include <cstdint>
#include <endian.h>
#include <string>

struct __attribute__(( packed )) RegisterFileData;
struct __attribute__(( packed )) RegisterBlockData;
struct __attribute__(( packed )) RegisterData;
struct __attribute__(( packed )) FieldData;

struct __attribute__(( packed )) RegisterFileData
{
	uint32_t name_offset() const { return be32toh(m_name_offset); }
	uint32_t num_blocks() const { return be32toh(m_num_blocks); }
	uint32_t num_regs() const { return be32toh(m_num_regs); }
	uint32_t num_fields() const { return be32toh(m_num_fields); }

	const RegisterBlockData* blocks() const;
	const RegisterData* registers() const;
	const FieldData* fields() const;
	const char* strings() const;

	const char* name() const { return strings() + name_offset(); }
	const RegisterBlockData* at(uint32_t idx) const;
	const RegisterBlockData* find_block(const std::string& name) const;

	const RegisterData* find_register(const std::string& name, const RegisterBlockData** rbd) const;

private:
	uint32_t m_name_offset;
	uint32_t m_num_blocks;
	uint32_t m_num_regs;
	uint32_t m_num_fields;
};

struct __attribute__(( packed )) RegisterBlockData
{
	uint32_t name_offset() const { return be32toh(m_name_offset); }
	uint64_t offset() const { return be64toh(m_offset); }
	uint64_t size() const { return be64toh(m_size); }
	uint32_t num_regs() const { return be32toh(m_num_registers); }
	uint32_t regs_offset() const { return be32toh(m_regs_offset); }

	const char* name(const RegisterFileData* rfd) const { return rfd->strings() + name_offset(); }
	const RegisterData* at(const RegisterFileData* rfd, uint32_t idx) const;
	const RegisterData* find_register(const RegisterFileData* rfd, const std::string& name) const;

private:
	uint32_t m_name_offset;
	uint64_t m_offset;
	uint64_t m_size;
	uint32_t m_num_registers;
	uint32_t m_regs_offset;
};

struct __attribute__(( packed )) RegisterData
{
	uint32_t name_offset() const { return be32toh(m_name_offset); }
	uint64_t offset() const { return be64toh(m_offset); }
	uint32_t size() const { return be32toh(m_size); }

	uint32_t num_fields() const { return be32toh(m_num_fields); }
	uint32_t fields_offset() const { return be32toh(m_fields_offset); }

	const char* name(const RegisterFileData* rfd) const { return rfd->strings() + name_offset(); }
	const FieldData* at(const RegisterFileData* rfd, uint32_t idx) const;
	const FieldData* find_field(const RegisterFileData* rfd, const std::string& name) const;

private:
	uint32_t m_name_offset;
	uint64_t m_offset;
	uint32_t m_size;

	uint32_t m_num_fields;
	uint32_t m_fields_offset;
};

struct __attribute__(( packed )) FieldData
{
	uint32_t name_offset() const { return be32toh(m_name_offset); }
	uint8_t low() const { return m_low; }
	uint8_t high() const { return m_high; }

	const char* name(const RegisterFileData* rfd) const { return rfd->strings() + name_offset(); }

private:
	uint32_t m_name_offset;
	uint8_t m_high;
	uint8_t m_low;
};
