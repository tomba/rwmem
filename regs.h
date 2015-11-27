#pragma once

class AddressBlock;
class RegFile;
class Register;

struct  __attribute__(( packed )) FieldData
{
	const char* name() const { return m_name; }
	uint8_t low() const { return m_low; }
	uint8_t high() const { return m_high; }

private:
	char m_name[32];
	uint8_t m_low;
	uint8_t m_high;
};

struct __attribute__(( packed )) RegisterData
{
	const char* name() const { return m_name; }
	uint64_t offset() const { return be64toh(m_offset); }
	uint32_t size() const { return be32toh(m_size); }

	uint32_t num_fields() const { return be32toh(m_num_fields); }

private:
	char m_name[32];
	uint64_t m_offset;
	uint32_t m_size;

	uint32_t m_num_fields;
};

struct __attribute__(( packed )) AddressBlockData
{
	const char* name() const { return m_name; }
	uint64_t offset() const { return be64toh(m_offset); }
	uint64_t size() const { return be64toh(m_size); }
	uint32_t num_regs() const { return be32toh(m_num_registers); }

private:
	char m_name[32];
	uint64_t m_offset;
	uint64_t m_size;
	uint32_t m_num_registers;
};

struct __attribute__(( packed )) RegFileData
{
	const char* name() const { return m_name; }
	uint32_t num_blocks() const { return be32toh(m_num_blocks); }
	uint32_t num_regs() const { return be32toh(m_num_regs); }
	uint32_t num_fields() const { return be32toh(m_num_fields); }

	const AddressBlockData* blocks() const { return (AddressBlockData*)((uint8_t*)this + sizeof(RegFileData)); }
	const RegisterData* registers() const { return (RegisterData*)(&blocks()[num_blocks()]); }
	const FieldData* fields() const { return (FieldData*)(&registers()[num_regs()]); }

private:
	char m_name[32];
	uint32_t m_num_blocks;
	uint32_t m_num_regs;
	uint32_t m_num_fields;
};

class Field
{
public:
	Field(Register& reg, const FieldData* fd)
		:m_reg(reg), m_fd(fd)
	{
	}

	const char* name() const { return m_fd->name(); }
	uint8_t low() const { return m_fd->low(); }
	uint8_t high() const { return m_fd->high(); }

private:
	const Register& m_reg;
	const FieldData* m_fd;
};

class Register
{
public:
	Register(const AddressBlockData* abd, const RegisterData* rd, const FieldData* fd);

	const char* name() const { return m_rd->name(); }
	uint64_t offset() const { return m_rd->offset(); }
	uint32_t size() const { return m_rd->size(); }

	uint32_t num_fields() const { return m_rd->num_fields(); }

	uint32_t max_field_name_len() const { return m_max_field_name_len; }

	std::unique_ptr<Field> field_by_index(unsigned idx);

	std::unique_ptr<Field> find_field(const std::string& name);
	std::unique_ptr<Field> find_field(uint8_t high, uint8_t low);

private:
	const AddressBlockData* m_abd;
	const RegisterData* m_rd;
	const FieldData* m_fd;

	uint32_t m_max_field_name_len;
};

class AddressBlock
{
public:
	AddressBlock(const RegFile& regfile, const AddressBlockData* abd)
		: m_regfile(regfile), m_abd(abd)
	{

	}

private:
	const RegFile& m_regfile;
	const AddressBlockData* m_abd;
};

class RegFile
{
public:
	RegFile(const char* filename);
	~RegFile();

	std::unique_ptr<Register> find_reg(const std::string& name) const;
	std::unique_ptr<Register> find_reg(uint64_t offset) const;

	void print(const char* pattern);

private:
	const RegFileData* m_rfd;
	size_t m_size;
};
