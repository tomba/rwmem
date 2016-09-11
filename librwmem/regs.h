#pragma once

#include "memmap.h"

class RegisterBlock;
class RegisterFile;
class Register;

#include "regfiledata.h"

class Field
{
public:
	Field(const RegisterFileData* rfd, const FieldData* fd)
		:m_rfd(rfd), m_fd(fd)
	{
	}

	const char* name() const { return m_fd->name(m_rfd); }
	uint8_t low() const { return m_fd->low(); }
	uint8_t high() const { return m_fd->high(); }

private:
	const RegisterFileData* m_rfd;
	const FieldData* m_fd;
};

class Register
{
public:
	Register(const RegisterFileData* rfd, const RegisterData* rd);

	const char* name() const { return m_rd->name(m_rfd); }
	uint64_t offset() const { return m_rd->offset(); }
	uint32_t size() const { return m_rd->size(); }
	uint32_t num_fields() const { return m_rd->num_fields(); }

	Field at(uint32_t idx) const;
	int find_field(const std::string& name) const;

	Field get_field(const std::string& name) const;
	Field get_field(uint8_t high, uint8_t low) const;

private:
	const RegisterFileData* m_rfd;
	const RegisterData* m_rd;
};

class RegisterBlock
{
public:
	RegisterBlock(const RegisterFileData* rfd, const RegisterBlockData* rbd)
		: m_rfd(rfd), m_rbd(rbd)
	{
	}

	const char* name() const { return m_rbd->name(m_rfd); }
	uint64_t offset() const { return m_rbd->offset(); }
	uint64_t size() const { return m_rbd->size(); }
	uint32_t num_regs() const { return m_rbd->num_regs(); }

	Register at(uint32_t idx) const;
	int find_register(const std::string& name) const;

	Register get_register(const std::string& name) const;

private:
	const RegisterFileData* m_rfd;
	const RegisterBlockData* m_rbd;
};

class RegisterFile
{
public:
	RegisterFile(const std::string& filename);
	~RegisterFile();

	const char* name() const { return m_rfd->name(); }
	uint32_t num_blocks() const { return m_rfd->num_blocks(); }
	uint32_t num_regs() const { return m_rfd->num_regs(); }
	uint32_t num_fields() const { return m_rfd->num_fields(); }

	RegisterBlock at(uint32_t idx) const;
	RegisterBlock get_register_block(const std::string& name) const;
	Register get_reg(const std::string& name) const;
	Register get_reg(uint64_t offset) const;

	void print(const std::string& pattern);

	const RegisterFileData* data() const { return m_rfd; }

private:
	const RegisterFileData* m_rfd;
	size_t m_size;
};
