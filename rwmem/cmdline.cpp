#include <cstdio>
#include <cstdlib>
#include <cstdint>
#include <cstdarg>
#include <cstring>
#include <unistd.h>
#include <charconv>

#include "rwmem.h"
#include "helpers.h"
#include "opts.h"

using namespace std;
using namespace rwmem;

RwmemOpts rwmem_opts;

// Option IDs
enum OptId {
	OPT_HELP = 1,
	OPT_DATA,
	OPT_ADDR,
	OPT_WRITE,
	OPT_PRINT,
	OPT_FORMAT,
	OPT_REGS,
	OPT_RAW,
	OPT_IGNORE_BASE,
	OPT_VERBOSE,
};

// Mmap options
static const std::vector<OptDef> mmap_opts = {
	{ OPT_HELP, 'h', "help", ArgReq::NONE },
	{ OPT_DATA, 'd', "data", ArgReq::REQUIRED },
	{ OPT_WRITE, 'w', "write", ArgReq::REQUIRED },
	{ OPT_PRINT, 'p', "print", ArgReq::REQUIRED },
	{ OPT_FORMAT, 'f', "format", ArgReq::REQUIRED },
	{ OPT_REGS, 'r', "regs", ArgReq::REQUIRED },
	{ OPT_RAW, 'R', "raw", ArgReq::NONE },
	{ OPT_IGNORE_BASE, '\0', "ignore-base", ArgReq::NONE },
	{ OPT_VERBOSE, 'v', "verbose", ArgReq::NONE },
};

// I2C options (includes address option)
static const std::vector<OptDef> i2c_opts = {
	{ OPT_HELP, 'h', "help", ArgReq::NONE },
	{ OPT_ADDR, 'a', "addr", ArgReq::REQUIRED },
	{ OPT_DATA, 'd', "data", ArgReq::REQUIRED },
	{ OPT_WRITE, 'w', "write", ArgReq::REQUIRED },
	{ OPT_PRINT, 'p', "print", ArgReq::REQUIRED },
	{ OPT_FORMAT, 'f', "format", ArgReq::REQUIRED },
	{ OPT_REGS, 'r', "regs", ArgReq::REQUIRED },
	{ OPT_RAW, 'R', "raw", ArgReq::NONE },
	{ OPT_IGNORE_BASE, '\0', "ignore-base", ArgReq::NONE },
	{ OPT_VERBOSE, 'v', "verbose", ArgReq::NONE },
};

// List options (minimal set)
static const std::vector<OptDef> list_opts = {
	{ OPT_HELP, 'h', "help", ArgReq::NONE },
	{ OPT_REGS, 'r', "regs", ArgReq::REQUIRED },
	{ OPT_PRINT, 'p', "print", ArgReq::REQUIRED },
	{ OPT_VERBOSE, 'v', "verbose", ArgReq::NONE },
};

static void print_help()
{
	fputs("usage: rwmem [options] <address>[:field][=value] ...\n"
	      "       rwmem mmap <file> [options] <address>[:field][=value] ...\n"
	      "       rwmem i2c <bus>:<addr> [options] <address>[:field][=value] ...\n"
	      "       rwmem list [options] [pattern] ...\n"
	      "\n"
	      "	address			address to access:\n"
	      "				<address>	single address\n"
	      "				<start-end>	range with end address\n"
	      "				<start+len>	range with length\n"
	      "\n"
	      "	field			bitfield (inclusive, start from 0):\n"
	      "				<bit>		single bit\n"
	      "				<high>:<low>	bitfield from high to low\n"
	      "\n"
	      "	value			value to be written\n"
	      "\n"
	      "	size			8-64 bits, multiple of 8\n"
	      "	endian			be, le, bes, les\n"
	      "\n"
	      "	-h, --help		show this help\n"
	      "	-d, --data <size>[endian]	data access size (mmap, i2c)\n"
	      "	-a, --addr <size>[endian]	address size (i2c only)\n"
	      "	-w, --write <mode>	write mode: w, rw or rwr (default) (mmap, i2c)\n"
	      "	-p, --print <mode>	print mode: q, r or rf (default)\n"
	      "	-f, --format <fmt>	number format: x (hex), b (bin) or d (dec)\n"
	      "	-r, --regs <file>	register description file\n"
	      "	-R, --raw		raw output mode (mmap, i2c)\n"
	      "	--ignore-base		ignore base from register file (mmap, i2c)\n"
	      "	-v, --verbose		verbose output\n",
	      stdout);
}

static void parse_arg(string str, RwmemOptsArg* arg)
{
	size_t idx;

	// extract value

	idx = str.find('=');

	if (idx != string::npos) {
		arg->value = str.substr(idx + 1);
		str.resize(idx);

		if (arg->value.empty())
			throw runtime_error("Empty value not allowed");
	}

	// extract field

	idx = str.find(':');

	if (idx != string::npos) {
		arg->field = str.substr(idx + 1);
		str.resize(idx);

		if (arg->field.empty())
			throw runtime_error("Empty field not allowed");
	}

	// extract len

	idx = str.find('+');

	if (idx != string::npos) {
		arg->range = str.substr(idx + 1);
		arg->range_is_offset = true;
		str.resize(idx);

		if (arg->range.empty())
			throw runtime_error("Empty range not allowed");
	} else {
		// extract end

		idx = str.find('-');

		if (idx != string::npos) {
			arg->range = str.substr(idx + 1);
			arg->range_is_offset = false;
			str.resize(idx);

			if (arg->range.empty())
				throw runtime_error("Empty range not allowed");
		}
	}

	arg->address = str;

	if (arg->address.empty())
		throw runtime_error("Empty address not allowed");
}

static void parse_size_endian(string_view s, uint32_t* size, Endianness* e)
{
	auto start = s.begin();
	auto end = s.end();
	uint32_t num;

	auto [ptr, ec]{ std::from_chars(start, end, num) };

	if (ec != std::errc()) {
		throw runtime_error("Failed to parse size '" + std::string(s) + "'");
	}

	if (num == 0 || num > 64 || (num % 8) != 0) {
		throw runtime_error("Invalid size '" + std::to_string(num) + "' (must be 8-64 bits, multiple of 8)");
	}

	string_view ending(ptr, end);

	if (ending == "")
		*e = Endianness::Default;
	else if (ending == "be")
		*e = Endianness::Big;
	else if (ending == "le")
		*e = Endianness::Little;
	else if (ending == "bes")
		*e = Endianness::BigSwapped;
	else if (ending == "les")
		*e = Endianness::LittleSwapped;
	else
		throw runtime_error("Bad endianness '" + std::string(ending) + "'");

	*size = num;
}

// Pass 1: Normalize arguments for default mode
static void normalize_args_for_default_mode(std::vector<std::string>& args)
{
	// Find first positional (skip program name and options)
	size_t first_pos_idx = 0;
	for (size_t i = 1; i < args.size(); i++) {
		if (args[i][0] != '-') {
			first_pos_idx = i;
			break;
		}
	}

	// Check if explicit subcommand
	if (first_pos_idx > 0) {
		const string& cmd = args[first_pos_idx];
		if (cmd == "mmap" || cmd == "i2c" || cmd == "list") {
			return; // Already explicit, nothing to do
		}
	}

	// Need to insert default mode
	// Insert "mmap" and "/dev/mem" at first positional position
	// Or after program name if no positionals yet
	size_t insert_pos = (first_pos_idx > 0) ? first_pos_idx : args.size();
	args.insert(args.begin() + insert_pos, "/dev/mem");
	args.insert(args.begin() + insert_pos, "mmap");
}

void parse_cmdline(const std::vector<std::string>& args)
{
	// Show help if no arguments
	if (args.size() == 1) {
		print_help();
		exit(0);
	}

	try {
		// Check for --help before any processing
		for (size_t i = 1; i < args.size(); i++) {
			if (args[i] == "--help" || args[i] == "-h") {
				print_help();
				exit(0);
			}
		}

		// Pass 1: Normalize arguments for default mode
		std::vector<std::string> mutable_args(args);
		normalize_args_for_default_mode(mutable_args);

		// Pass 2: Full parsing
		ArgParser parser(mutable_args);

		// Parse subcommand (always present after normalization)
		// Use minimal option set for initial parsing (just to skip options before subcommand)
		auto cmd_arg = parser.get_next(mmap_opts);
		if (!cmd_arg || cmd_arg->type != ArgType::POSITIONAL) {
			throw runtime_error("Expected subcommand");
		}

		string subcommand = string(cmd_arg->positional);

		// Variables for option parsing
		string data_size_str, addr_size_str, write_mode_str, print_mode_str, format_str;
		vector<string> op_strs;
		bool help_requested = false;

		// Parse subcommand argument and set mode
		std::span<const OptDef> opts;

		if (subcommand == "mmap") {
			auto file_arg = parser.get_next(mmap_opts);
			if (!file_arg || file_arg->type != ArgType::POSITIONAL) {
				throw runtime_error("mmap requires file argument");
			}
			rwmem_opts.target_type = TargetType::MMap;
			rwmem_opts.mmap_target = string(file_arg->positional);
			opts = mmap_opts;
		} else if (subcommand == "i2c") {
			auto param_arg = parser.get_next(i2c_opts);
			if (!param_arg || param_arg->type != ArgType::POSITIONAL) {
				throw runtime_error("i2c requires bus:addr argument");
			}
			rwmem_opts.target_type = TargetType::I2C;
			rwmem_opts.i2c_target = string(param_arg->positional);

			// Validate I2C parameter format
			vector<string> strs = split(rwmem_opts.i2c_target, ':');
			if (strs.size() != 2 || strs[0].empty() || strs[1].empty()) {
				throw runtime_error("Invalid I2C parameter '" + rwmem_opts.i2c_target + "'. Expected format: <bus>:<addr>");
			}

			// Validate that both parts are numeric
			uint64_t bus, addr;
			if (parse_u64(strs[0], &bus) != 0) {
				throw runtime_error("Invalid I2C bus '" + strs[0] + "'. Must be a number");
			}
			if (parse_u64(strs[1], &addr) != 0) {
				throw runtime_error("Invalid I2C address '" + strs[1] + "'. Must be a number");
			}
			opts = i2c_opts;
		} else if (subcommand == "list") {
			rwmem_opts.show_list = true;
			opts = list_opts;
		} else {
			throw runtime_error("Unknown subcommand: " + subcommand);
		}

		// Parse remaining arguments
		while (parser.has_more()) {
			auto arg = parser.get_next(opts);
			if (!arg)
				break;

			if (arg->type == ArgType::OPTION) {
				switch (arg->option_id) {
				case OPT_HELP:
					help_requested = true;
					break;
				case OPT_DATA:
					data_size_str = string(arg->option_value);
					break;
				case OPT_ADDR:
					addr_size_str = string(arg->option_value);
					break;
				case OPT_WRITE:
					write_mode_str = string(arg->option_value);
					break;
				case OPT_PRINT:
					print_mode_str = string(arg->option_value);
					break;
				case OPT_FORMAT:
					format_str = string(arg->option_value);
					break;
				case OPT_REGS:
					rwmem_opts.regfile = string(arg->option_value);
					break;
				case OPT_RAW:
					rwmem_opts.raw_output = true;
					break;
				case OPT_IGNORE_BASE:
					rwmem_opts.ignore_base = true;
					break;
				case OPT_VERBOSE:
					rwmem_opts.verbose = true;
					break;
				}
			} else if (arg->type == ArgType::POSITIONAL) {
				if (rwmem_opts.show_list) {
					rwmem_opts.list_patterns.push_back(string(arg->positional));
				} else {
					op_strs.push_back(string(arg->positional));
				}
			}
		}

		// Handle help request
		if (help_requested) {
			print_help();
			exit(0);
		}

		// Post-processing for custom parsing
		if (!data_size_str.empty()) {
			Endianness endianness;
			uint32_t size;
			parse_size_endian(data_size_str, &size, &endianness);
			rwmem_opts.data_size = size / 8;
			rwmem_opts.data_endianness = endianness;
			rwmem_opts.user_data_size = true;
		}

		if (!addr_size_str.empty()) {
			Endianness endianness;
			uint32_t size;
			parse_size_endian(addr_size_str, &size, &endianness);
			rwmem_opts.address_size = size / 8;
			rwmem_opts.address_endianness = endianness;
			rwmem_opts.user_address_size = true;
		}

		if (!write_mode_str.empty()) {
			if (write_mode_str == "w")
				rwmem_opts.write_mode = WriteMode::Write;
			else if (write_mode_str == "rw")
				rwmem_opts.write_mode = WriteMode::ReadWrite;
			else if (write_mode_str == "rwr")
				rwmem_opts.write_mode = WriteMode::ReadWriteRead;
			else
				throw runtime_error("illegal write mode '" + write_mode_str + "'");
		}

		if (!print_mode_str.empty()) {
			if (print_mode_str == "q")
				rwmem_opts.print_mode = PrintMode::Quiet;
			else if (print_mode_str == "r")
				rwmem_opts.print_mode = PrintMode::Reg;
			else if (print_mode_str == "rf")
				rwmem_opts.print_mode = PrintMode::RegFields;
			else
				throw runtime_error("illegal print mode '" + print_mode_str + "'");
		}

		// Handle format option
		if (!format_str.empty()) {
			if (format_str == "x")
				rwmem_opts.number_print_mode = NumberPrintMode::Hex;
			else if (format_str == "d")
				rwmem_opts.number_print_mode = NumberPrintMode::Dec;
			else if (format_str == "b")
				rwmem_opts.number_print_mode = NumberPrintMode::Bin;
			else
				throw runtime_error("Invalid format '" + format_str + "'. Valid formats: x (hex), d (dec), b (bin)");

			// Validate format scope
			if (rwmem_opts.print_mode == PrintMode::Quiet && !format_str.empty()) {
				rwmem_vprint("Warning: --format option ignored in quiet mode\n");
			}
			if (rwmem_opts.raw_output && !format_str.empty()) {
				rwmem_vprint("Warning: --format option ignored in raw output mode\n");
			}
		}

		// Parse operation arguments
		if (!rwmem_opts.show_list) {
			if (op_strs.empty())
				throw runtime_error("No operations specified");

			rwmem_opts.parsed_args.clear();
			rwmem_opts.parsed_args.reserve(op_strs.size());

			for (const string& param : op_strs) {
				RwmemOptsArg parsed_arg;
				parse_arg(param, &parsed_arg);
				rwmem_opts.parsed_args.push_back(parsed_arg);
			}
		}

	} catch (const runtime_error& e) {
		ERR("Error: {}\n", e.what());
	}
}
