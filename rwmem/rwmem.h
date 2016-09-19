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

enum class TargetType {
	None,
	MMap,
	I2C,
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
	TargetType target_type;

	std::string mmap_target;
	std::string i2c_target;

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

void load_opts_from_ini_pre();
void detect_platform();

#define vprint(format...) \
	do { \
		if (rwmem_opts.verbose) \
			fprintf(stderr, format); \
	} while(0)

#endif /* __RWMEM_H__ */
