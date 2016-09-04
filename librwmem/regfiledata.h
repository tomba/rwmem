#pragma once

#include <cstdint>

struct  __attribute__(( packed )) FieldData
{
	uint32_t name_offset() const { return be32toh(m_name_offset); }
	uint8_t low() const { return m_low; }
	uint8_t high() const { return m_high; }

private:
	uint32_t m_name_offset;
	uint8_t m_high;
	uint8_t m_low;
};

struct __attribute__(( packed )) RegisterData
{
	uint32_t name_offset() const { return be32toh(m_name_offset); }
	uint64_t offset() const { return be64toh(m_offset); }
	uint32_t size() const { return be32toh(m_size); }

	uint32_t num_fields() const { return be32toh(m_num_fields); }
	uint32_t fields_offset() const { return be32toh(m_fields_offset); }

private:
	uint32_t m_name_offset;
	uint64_t m_offset;
	uint32_t m_size;

	uint32_t m_num_fields;
	uint32_t m_fields_offset;
};

struct __attribute__(( packed )) RegisterBlockData
{
	uint32_t name_offset() const { return be32toh(m_name_offset); }
	uint64_t offset() const { return be64toh(m_offset); }
	uint64_t size() const { return be64toh(m_size); }
	uint32_t num_regs() const { return be32toh(m_num_registers); }
	uint32_t regs_offset() const { return be32toh(m_regs_offset); }

private:
	uint32_t m_name_offset;
	uint64_t m_offset;
	uint64_t m_size;
	uint32_t m_num_registers;
	uint32_t m_regs_offset;
};

struct __attribute__(( packed )) RegisterFileData
{
	uint32_t name_offset() const { return be32toh(m_name_offset); }
	uint32_t num_blocks() const { return be32toh(m_num_blocks); }
	uint32_t num_regs() const { return be32toh(m_num_regs); }
	uint32_t num_fields() const { return be32toh(m_num_fields); }

	const RegisterBlockData* blocks() const { return (RegisterBlockData*)((uint8_t*)this + sizeof(RegisterFileData)); }
	const RegisterData* registers() const { return (RegisterData*)(&blocks()[num_blocks()]); }
	const FieldData* fields() const { return (FieldData*)(&registers()[num_regs()]); }
	const char* strings() const { return (const char*)(&fields()[num_fields()]); }

private:
	uint32_t m_name_offset;
	uint32_t m_num_blocks;
	uint32_t m_num_regs;
	uint32_t m_num_fields;
};
