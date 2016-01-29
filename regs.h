#pragma once

class RegisterBlock;
class RegFile;
class Register;

struct  __attribute__(( packed )) FieldData
{
	uint32_t name_offset() const { return be32toh(m_name_offset); }
	uint8_t low() const { return m_low; }
	uint8_t high() const { return m_high; }

private:
	uint32_t m_name_offset;
	uint8_t m_low;
	uint8_t m_high;
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

struct __attribute__(( packed )) RegFileData
{
	uint32_t name_offset() const { return be32toh(m_name_offset); }
	uint32_t num_blocks() const { return be32toh(m_num_blocks); }
	uint32_t num_regs() const { return be32toh(m_num_regs); }
	uint32_t num_fields() const { return be32toh(m_num_fields); }

	const RegisterBlockData* blocks() const { return (RegisterBlockData*)((uint8_t*)this + sizeof(RegFileData)); }
	const RegisterData* registers() const { return (RegisterData*)(&blocks()[num_blocks()]); }
	const FieldData* fields() const { return (FieldData*)(&registers()[num_regs()]); }
	const char* strings() const { return (const char*)(&fields()[num_fields()]); }

private:
	uint32_t m_name_offset;
	uint32_t m_num_blocks;
	uint32_t m_num_regs;
	uint32_t m_num_fields;
};

class Field
{
public:
	Field(const RegFileData* rfd, const FieldData* fd)
		:m_rfd(rfd), m_fd(fd)
	{
	}

	const char* name() const { return m_rfd->strings() + m_fd->name_offset(); }
	uint8_t low() const { return m_fd->low(); }
	uint8_t high() const { return m_fd->high(); }

private:
	const RegFileData* m_rfd;
	const FieldData* m_fd;
};

class Register
{
public:
	Register(const RegFileData* rfd, const RegisterBlockData* rbd, const RegisterData* rd);

	const char* name() const { return m_rfd->strings() + m_rd->name_offset(); }
	uint64_t offset() const { return m_rd->offset(); }
	uint32_t size() const { return m_rd->size(); }
	uint32_t num_fields() const { return m_rd->num_fields(); }

	const RegisterBlock register_block() const;
	const Field field(uint32_t idx) const;

	std::unique_ptr<Field> find_field(const std::string& name);
	std::unique_ptr<Field> find_field(uint8_t high, uint8_t low);

	uint32_t get_max_field_name_len();

private:
	const RegFileData* m_rfd;
	const RegisterBlockData* m_rbd;
	const RegisterData* m_rd;
	uint32_t m_max_field_name_len = 0;
};

class RegisterBlock
{
public:
	RegisterBlock(const RegFileData* rfd, const RegisterBlockData* rbd)
		: m_rfd(rfd), m_rbd(rbd)
	{
	}

	const char* name() const { return m_rfd->strings() + m_rbd->name_offset(); }
	uint64_t offset() const { return m_rbd->offset(); }
	uint64_t size() const { return m_rbd->size(); }
	uint32_t num_regs() const { return m_rbd->num_regs(); }

	Register reg(uint32_t idx) const;

	std::unique_ptr<Register> find_reg(const std::string& name) const;

private:
	const RegFileData* m_rfd;
	const RegisterBlockData* m_rbd;
};

class RegFile
{
public:
	RegFile(std::string filename);
	~RegFile();

	const char* name() const { return m_rfd->strings() + m_rfd->name_offset(); }
	uint32_t num_blocks() const { return m_rfd->num_blocks(); }
	uint32_t num_regs() const { return m_rfd->num_regs(); }
	uint32_t num_fields() const { return m_rfd->num_fields(); }

	RegisterBlock register_block(uint32_t idx) const;

	std::unique_ptr<RegisterBlock> find_register_block(const std::string& name) const;

	std::unique_ptr<Register> find_reg(const std::string& name) const;
	std::unique_ptr<Register> find_reg(uint64_t offset) const;

	void print(const std::string& pattern);

private:
	const RegFileData* m_rfd;
	size_t m_size;
};
