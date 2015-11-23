#ifndef __RWMEM_H__
#define __RWMEM_H__

#include <memory>
#include <string>
#include <vector>
#include <inttypes.h>
#include <stdbool.h>

enum class WriteMode {
	Write,
	ReadWrite,
	ReadWriteRead,
};

enum class PrintMode{
	Quiet,
	Reg,
	RegFields,
};

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
	uint32_t num_regs() const { return be32toh(m_num_registers); }

private:
	char m_name[32];
	uint64_t m_size;
	uint32_t m_num_registers;
};

struct __attribute__(( packed )) RegFileData
{
	const char* name() const { return m_name; }
	uint32_t num_blocks() const { return be32toh(m_num_blocks); }
	uint32_t num_regs() const { return be32toh(m_num_regs); }

private:
	char m_name[32];
	uint32_t m_num_blocks;
	uint32_t m_num_regs;
	uint32_t m_num_fields;
};

class AddressBlock;
class RegFile;
class Register;

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
	Register(const AddressBlockData* abd, const RegisterData* rd, const FieldData* fd)
		: m_abd(abd), m_rd(rd), m_fd(fd)
	{
		uint32_t max = 0;
		for (unsigned i = 0; i < num_fields(); ++i) {
			uint32_t len = strlen(m_fd[i].name());
			if (len > max)
				max = len;
		}
		m_max_field_name_len = max;
	}

	const char* name() const { return m_rd->name(); }
	uint64_t offset() const { return m_rd->offset(); }
	uint32_t size() const { return m_rd->size(); }

	uint32_t num_fields() const { return m_rd->num_fields(); }

	uint32_t max_field_name_len() const { return m_max_field_name_len; }

	std::unique_ptr<Field> field_by_index(unsigned idx)
	{
		return std::make_unique<Field>(*this, &m_fd[idx]);
	}

	std::unique_ptr<Field> find_field(const char* name);
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

	std::unique_ptr<Register> find_reg(const char* name) const;
	std::unique_ptr<Register> find_reg(uint64_t offset) const;

private:
	const RegFile& m_regfile;
	const AddressBlockData* m_abd;
};

class RegFile
{
public:
	RegFile(const char* filename);
	~RegFile();

	std::unique_ptr<Register> find_reg(const char* name) const;
	std::unique_ptr<Register> find_reg(uint64_t offset) const;

private:
	const RegFileData* m_rfd;
	size_t m_size;

	struct AddressBlockData* m_blocks;
	struct RegisterData* m_regs;
	struct FieldData* m_fields;
};

struct RwmemOp {
	uint64_t address;

	bool range_valid;
	uint64_t range;

	bool field_valid;
	unsigned low, high;

	bool value_valid;
	uint64_t value;
};

struct RwmemOptsArg {
	const char *address;
	const char *range;
	const char *field;
	const char *value;

	bool range_is_offset;
};

struct RwmemOpts {
	const char *filename;
	unsigned regsize;
	WriteMode write_mode;
	PrintMode print_mode;
	bool raw_output;

	const char *base;
	const char *aliasfile;
	const char *regfile;

	std::vector<RwmemOptsArg> args;
};

extern RwmemOpts rwmem_opts;

__attribute__ ((noreturn))
void myerr(const char* format, ... );

__attribute__ ((noreturn))
void myerr2(const char* format, ... );

uint64_t readmem(void *addr, unsigned regsize);
void writemem(void *addr, unsigned regsize, uint64_t value);

void parse_cmdline(int argc, char **argv);

/* parser */
void parse_base(const char *file, const char *arg, uint64_t *base,
		const char **regfile);
int parse_u64(const char *str, uint64_t *value);

#define ERR(format...) myerr(format)

#define ERR_ON(condition, format...) do {	\
	if (condition)				\
		ERR(format);			\
} while (0)

#define ERR_ERRNO(format...) myerr2(format)

#define ERR_ON_ERRNO(condition, format...) do {	\
	if (condition)				\
		ERR_ERRNO(format);		\
} while (0)

#define GENMASK(h, l) (((~0ULL) << (l)) & (~0ULL >> (64 - 1 - (h))))

void split(const std::string &s, char delim, std::vector<std::string> &elems);
std::vector<std::string> split(const std::string &s, char delim);

#endif /* __RWMEM_H__ */
