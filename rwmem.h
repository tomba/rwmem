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

void parse_cmdline(int argc, char **argv);

/* parser */
void parse_base(const char *file, const char *arg, uint64_t *base,
		const char **regfile);
int parse_u64(const char *str, uint64_t *value);

#endif /* __RWMEM_H__ */
