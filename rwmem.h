#ifndef __RWMEM_H__
#define __RWMEM_H__

#include <memory>
#include <string>
#include <vector>
#include <inttypes.h>
#include <stdbool.h>

#include "regs.h"

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
	uint64_t ab_offset;
	uint64_t reg_offset;

	bool range_valid;
	uint64_t range;

	bool field_valid;
	unsigned low, high;

	bool value_valid;
	uint64_t value;
};

struct RwmemOptsArg {
	std::string base;
	std::string address;
	std::string range;
	std::string field;
	std::string value;

	bool range_is_offset;
};

struct RwmemOpts {
	std::string filename;
	unsigned regsize;
	WriteMode write_mode;
	PrintMode print_mode;
	bool raw_output;

	std::string regfile;

	bool show_list;
	std::string show_list_pattern;

	std::vector<RwmemOptsArg> args;

	bool verbose;
	bool ignore_base;
};

extern RwmemOpts rwmem_opts;

void parse_cmdline(int argc, char **argv);

#endif /* __RWMEM_H__ */
