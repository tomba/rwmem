#pragma once

#include <memory>

#include "regs.h"
#include "memmap.h"

class MappedRegisterBlock
{
public:
	MappedRegisterBlock(const RegisterBlock rb, const std::string& filename, bool read_only);
	MappedRegisterBlock(const RegisterBlock rb, const std::string& filename, uint64_t offset, uint64_t length, bool read_only);

	uint32_t read32(const std::string& regname);

private:
	const RegisterBlock m_rb;
	MemMap m_map;

};

class MappedRegister
{
public:
	MappedRegister(std::shared_ptr<MappedRegisterBlock> mrb, const Register reg);

private:
	const Register m_reg;
};
