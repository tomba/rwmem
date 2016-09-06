#pragma once

#include <memory>

#include "regs.h"
#include "memmap.h"

class MappedRegister;
class RegisterValue;

class MappedRegisterBlock
{
	friend class MappedRegister;
	friend class RegisterValue;
public:
	MappedRegisterBlock(const std::string& mapfile, const std::string& regfile, const std::string& blockname);
	MappedRegisterBlock(const std::string& mapfile, uint64_t offset, const std::string& regfile, const std::string& blockname);
	MappedRegisterBlock(const std::string& mapfile, uint64_t offset, uint64_t length);

	uint32_t read32(const std::string& regname) const;
	uint32_t read32(uint64_t offset) const;

	MappedRegister find_register(const std::string& regname);
	MappedRegister get_register(uint64_t offset);

private:
	std::unique_ptr<RegisterFile> m_rf;
	const RegisterBlockData* m_rbd;
	std::unique_ptr<MemMap> m_map;
};

class MappedRegister
{
public:
	MappedRegister(MappedRegisterBlock* mrb, const RegisterData* rd);
	MappedRegister(MappedRegisterBlock* mrb, uint64_t offset);

	uint32_t read32() const;
	RegisterValue read32value() const;

private:
	MappedRegisterBlock* m_mrb;
	const RegisterData* m_rd;
	uint64_t m_offset;
};

class RegisterValue
{
public:
	RegisterValue(MappedRegisterBlock* mrb, const RegisterData* rd, uint64_t value);

	uint64_t field_value(const std::string& fieldname) const;
	uint64_t field_value(uint8_t high, uint8_t low) const;

	operator uint64_t() const { return m_value; }

private:
	MappedRegisterBlock* m_mrb;
	const RegisterData* m_rd;
	uint64_t m_value;
};
