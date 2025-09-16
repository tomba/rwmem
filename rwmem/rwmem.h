#pragma once

#include <string>
#include <vector>
#include <cstdint>

#include <fmt/format.h>

#include "regfiledata.h"
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

enum class NumberPrintMode {
	Hex,
	Dec,
	Bin,
};

enum class TargetType {
	None,
	MMap,
	I2C,
};

struct RegMatch {
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

	// for i2c
	bool user_address_size = false;
	uint8_t address_size = 1; // bytes
	Endianness address_endianness = Endianness::Default;

	bool user_data_size = false;
	uint8_t data_size = 4; // bytes
	Endianness data_endianness = Endianness::Default;

	WriteMode write_mode = WriteMode::ReadWriteRead;
	PrintMode print_mode = PrintMode::RegFields;
	bool raw_output;

	std::string regfile;

	bool show_list;

	std::vector<std::string> args;
	std::vector<RwmemOptsArg> parsed_args;

	bool verbose;
	bool ignore_base;
	NumberPrintMode number_print_mode = NumberPrintMode::Hex;
};

struct RwmemFormatting {
	unsigned name_chars;
	unsigned address_chars;
	unsigned offset_chars;
	unsigned value_chars;
};

extern RwmemOpts rwmem_opts;

void parse_cmdline(int argc, char** argv);

#if HAS_INIH
extern INIReader rwmem_ini;

void load_opts_from_ini_pre();
void detect_platform();
#endif

#define rwmem_vprint(format, ...)                                  \
	do {                                                       \
		if (rwmem_opts.verbose)                            \
			fmt::print(stderr, format, ##__VA_ARGS__); \
	} while (0)

#define rwmem_printq(format, ...)                              \
	do {                                                   \
		if (rwmem_opts.print_mode != PrintMode::Quiet) \
			fmt::print(format, ##__VA_ARGS__);     \
	} while (0)
