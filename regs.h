#pragma once

class AddressBlock;
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

struct __attribute__(( packed )) AddressBlockData
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

	const AddressBlockData* blocks() const { return (AddressBlockData*)((uint8_t*)this + sizeof(RegFileData)); }
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
	Register(const RegFileData* rfd, const AddressBlockData* abd, const RegisterData* rd);

	const char* name() const { return m_rfd->strings() + m_rd->name_offset(); }
	uint64_t offset() const { return m_rd->offset(); }
	uint32_t size() const { return m_rd->size(); }
	uint32_t num_fields() const { return m_rd->num_fields(); }

	const Field field(uint32_t idx) const;

	std::unique_ptr<Field> find_field(const std::string& name);
	std::unique_ptr<Field> find_field(uint8_t high, uint8_t low);

private:
	const RegFileData* m_rfd;
	const AddressBlockData* m_abd;
	const RegisterData* m_rd;
};

class AddressBlock
{
public:
	AddressBlock(const RegFileData* rfd, const AddressBlockData* abd)
		: m_rfd(rfd), m_abd(abd)
	{
	}

	const char* name() const { return m_rfd->strings() + m_abd->name_offset(); }
	uint64_t offset() const { return m_abd->offset(); }
	uint64_t size() const { return m_abd->size(); }
	uint32_t num_regs() const { return m_abd->num_regs(); }

	Register reg(uint32_t idx) const;

	std::unique_ptr<Register> find_reg(const std::string& name) const;

private:
	const RegFileData* m_rfd;
	const AddressBlockData* m_abd;
};

class RegFile
{
public:
	RegFile(const char* filename);
	~RegFile();

	const char* name() const { return m_rfd->strings() + m_rfd->name_offset(); }
	uint32_t num_blocks() const { return m_rfd->num_blocks(); }
	uint32_t num_regs() const { return m_rfd->num_regs(); }
	uint32_t num_fields() const { return m_rfd->num_fields(); }

	AddressBlock address_block(uint32_t idx) const;

	std::unique_ptr<AddressBlock> find_address_block(const std::string& name) const;

	std::unique_ptr<Register> find_reg(const std::string& name) const;
	std::unique_ptr<Register> find_reg(uint64_t offset) const;

	void print(const std::string& pattern);

private:
	const RegFileData* m_rfd;
	size_t m_size;
};
