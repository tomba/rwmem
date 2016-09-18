#ifndef __RWMEM_H__
#define __RWMEM_H__

#include <memory>
#include <string>
#include <vector>
#include <inttypes.h>
#include <stdbool.h>

#include "regs.h"
#include "inireader.h"

enum class WriteMode {
	Write,
	ReadWrite,
	ReadWriteRead,
};

enum class PrintMode {
	Quiet,
	Reg,
	RegFields,
};

struct RwmemOp {
	uint64_t regblock_offset;
	uint64_t reg_offset;

	uint64_t range;

	bool custom_field;
	unsigned low, high;

	bool value_valid;
	uint64_t value;
};

struct RwmemOptsArg {
	std::string register_block;
	std::string address;
	std::string range;
	std::string field;
	std::string value;

	bool range_is_offset;
};

struct RwmemOpts {
	std::string filename = "/dev/mem";
	unsigned regsize = 4;
	WriteMode write_mode = WriteMode::ReadWriteRead;
	PrintMode print_mode = PrintMode::RegFields;
	bool raw_output;

	std::string regfile;

	bool show_list;
	std::string pattern;

	RwmemOptsArg arg;

	bool verbose;
	bool ignore_base;

	std::string platform;

	bool print_known_regs = true; // XXX get from cmdline
};

struct RwmemFormatting {
	unsigned name_chars;
	unsigned address_chars;
	unsigned offset_chars;
	unsigned value_chars;
};

extern RwmemOpts rwmem_opts;

void parse_cmdline(int argc, char **argv);

extern INIReader rwmem_ini;

void load_opts_from_ini();

#define vprint(format...) \
	do { \
		if (rwmem_opts.verbose) \
			fprintf(stderr, format); \
	} while(0)

#endif /* __RWMEM_H__ */
