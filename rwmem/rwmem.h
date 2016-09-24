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

struct RegMatch
{
	const RegisterBlockData* rbd;
	const RegisterData* rd;
	const FieldData* fd;
};

struct RwmemOp {
	const RegisterBlockData* rbd;
	std::vector<const RegisterData*> rds;

	uint64_t reg_offset;

	uint64_t range;

	bool custom_field;
	unsigned low, high;

	bool value_valid;
	uint64_t value;
};

struct RwmemOptsArg {
	std::string address;
	bool range_is_offset;
	std::string range;
	std::string field;
	std::string value;
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

	std::vector<RwmemOptsArg> args;

	bool verbose;
	bool ignore_base;
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
