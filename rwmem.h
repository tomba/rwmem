#ifndef __RWMEM_H__
#define __RWMEM_H__

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

struct FieldDesc {
	unsigned low;
	unsigned high;
	unsigned width;
	uint64_t mask;

	std::string name;
};

struct RegDesc {
	uint64_t offset;
	unsigned width;

	std::string name;
	std::vector<FieldDesc> fields;
	unsigned max_field_name_len;
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

struct rwmem_opts_arg {
	const char *address;
	const char *range;
	const char *field;
	const char *value;

	bool range_is_offset;
};

struct rwmem_opts {
	const char *filename;
	unsigned regsize;
	WriteMode write_mode;
	PrintMode print_mode;
	bool raw_output;

	const char *base;
	const char *aliasfile;
	const char *regfile;

	int num_args;
	struct rwmem_opts_arg *args;
};

extern struct rwmem_opts rwmem_opts;

__attribute__ ((noreturn))
void myerr(const char* format, ... );

__attribute__ ((noreturn))
void myerr2(const char* format, ... );

uint64_t readmem(void *addr, unsigned regsize);
void writemem(void *addr, unsigned regsize, uint64_t value);

char *strip(char *str);

void parse_cmdline(int argc, char **argv);

/* parser */
RegDesc *find_reg_by_name(const char *regfile, const char *regname);
RegDesc *find_reg_by_address(const char *regfile, uint64_t addr);
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
