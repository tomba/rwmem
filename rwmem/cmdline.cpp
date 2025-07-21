#include <algorithm>
#include <cstdio>
#include <cstdlib>
#include <cstdint>
#include <cstdarg>
#include <cstring>
#include <unistd.h>
#include <charconv>
#include <CLI/CLI.hpp>

#include "rwmem.h"
#include "helpers.h"

using namespace std;

RwmemOpts rwmem_opts;

static void parse_arg(string str, RwmemOptsArg* arg, const CLI::App& app)
{
	size_t idx;

	// extract value

	idx = str.find('=');

	if (idx != string::npos) {
		arg->value = str.substr(idx + 1);
		str.resize(idx);

		if (arg->value.empty())
			throw CLI::ValidationError("Empty value not allowed");
	}

	// extract field

	idx = str.find(':');

	if (idx != string::npos) {
		arg->field = str.substr(idx + 1);
		str.resize(idx);

		if (arg->field.empty())
			throw CLI::ValidationError("Empty field not allowed");
	}

	// extract len

	idx = str.find('+');

	if (idx != string::npos) {
		arg->range = str.substr(idx + 1);
		arg->range_is_offset = true;
		str.resize(idx);

		if (arg->range.empty())
			throw CLI::ValidationError("Empty range not allowed");
	} else {
		// extract end

		idx = str.find('-');

		if (idx != string::npos) {
			arg->range = str.substr(idx + 1);
			arg->range_is_offset = false;
			str.resize(idx);

			if (arg->range.empty())
				throw CLI::ValidationError("Empty range not allowed");
		}
	}

	arg->address = str;

	if (arg->address.empty())
		throw CLI::ValidationError("Empty address not allowed");
}

static void parse_size_endian(string_view s, uint32_t* size, Endianness* e)
{
	auto start = s.begin();
	auto end = s.end();
	uint32_t num;

	auto [ptr, ec]{ std::from_chars(start, end, num) };

	if (ec != std::errc()) {
		throw CLI::ValidationError("Failed to parse size '" + std::string(s) + "'");
	}

	if (num == 0 || num > 64 || (num % 8) != 0) {
		throw CLI::ValidationError("Invalid size '" + std::to_string(num) + "' (must be 8-64 bits, multiple of 8)");
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
		throw CLI::ValidationError("Bad endianness '" + std::string(ending) + "'");

	*size = num;
}

void parse_cmdline(const std::vector<std::string>& args)
{
	CLI::App app{ "rwmem - read/write memory tool\n\n"
		      "USAGE:\n"
		      "  rwmem <address>...                          # Shortcut for 'mmap /dev/mem'\n"
		      "  rwmem mmap <file> [options] <address>...    # Access memory-mapped file\n"
		      "  rwmem i2c <bus:addr> [options] <address>... # Access I2C device\n"
		      "  rwmem list [options] [pattern]...           # List register database\n"
		      "\n"
		      "For detailed options: rwmem <subcommand> --help\n"
		      "\n"
		      "EXAMPLES:\n"
		      "  rwmem 0x1000                    # Read from /dev/mem\n"
		      "  rwmem mmap /dev/mem 0x1000      # Equivalent explicit form\n"
		      "  rwmem i2c 1:0x50 0x10           # Read I2C device\n"
		      "  rwmem list DISPC.*              # List DISPC registers" };

	// Custom variables for CLI11 parsing
	std::string data_size_str, addr_size_str, write_mode_str, print_mode_str, format_str;
	std::string i2c_param;
	std::string mmap_file;
	std::vector<std::string> op_strs;

	// Create subcommands
	auto* mmap_cmd = app.add_subcommand("mmap", "Memory-mapped access mode");
	auto* i2c_cmd = app.add_subcommand("i2c", "I2C device access mode");
	auto* list_cmd = app.add_subcommand("list", "List registers from register database");

	// Mmap subcommand setup
	mmap_cmd->add_option("file", mmap_file, "File to open")->required();
	mmap_cmd->add_option("-d,--data", data_size_str, "Data size and endianness (<size>[endian])");
	mmap_cmd->add_option("-w,--write", write_mode_str, "Write mode: w, rw or rwr (default)");
	mmap_cmd->add_option("-p,--print", print_mode_str, "Print mode: q, r or rf (default)");
	mmap_cmd->add_option("-f,--format", format_str, "Number format: x (hex, default), b (bin), d (dec)");
	mmap_cmd->add_option("-r,--regs", rwmem_opts.regfile, "Register description file");
	mmap_cmd->add_flag("-R,--raw", rwmem_opts.raw_output, "Raw output mode");
	mmap_cmd->add_flag("--ignore-base", rwmem_opts.ignore_base, "Ignore base from register desc file");
	mmap_cmd->add_flag("-v,--verbose", rwmem_opts.verbose, "Verbose output");
	mmap_cmd->add_option("operations", op_strs,
			     "<address>[:field][=value]\n"
			     "\n"
			     "address to access:\n"
			     "<address>	single address\n"
			     "<address-end>	range with end address\n"
			     "<address+len>	range with length\n"
			     "\n"
			     "bitfield (inclusive, start from 0):\n"
			     "<bit>		single bit\n"
			     "<high>:<low>	bitfield from high to low\n"
			     "\n"
			     "value to be written\n");

	// I2C subcommand setup
	i2c_cmd->add_option("bus_addr", i2c_param, "I2C bus and device address (<bus>:<addr>)")->required();
	i2c_cmd->add_option("-a,--addr", addr_size_str, "Address size and endianness (<size>[endian])");
	i2c_cmd->add_option("-d,--data", data_size_str, "Data size and endianness (<size>[endian])");
	i2c_cmd->add_option("-w,--write", write_mode_str, "Write mode: w, rw or rwr (default)");
	i2c_cmd->add_option("-p,--print", print_mode_str, "Print mode: q, r or rf (default)");
	i2c_cmd->add_option("-f,--format", format_str, "Number format: x (hex, default), b (bin), d (dec)");
	i2c_cmd->add_option("-r,--regs", rwmem_opts.regfile, "Register description file");
	i2c_cmd->add_flag("-R,--raw", rwmem_opts.raw_output, "Raw output mode");
	i2c_cmd->add_flag("--ignore-base", rwmem_opts.ignore_base, "Ignore base from register desc file");
	i2c_cmd->add_flag("-v,--verbose", rwmem_opts.verbose, "Verbose output");
	i2c_cmd->add_option("operations", op_strs,
			    "<address>[:field][=value]\n"
			    "\n"
			    "address to access:\n"
			    "<address>	single address\n"
			    "<address-end>	range with end address\n"
			    "<address+len>	range with length\n"
			    "\n"
			    "bitfield (inclusive, start from 0):\n"
			    "<bit>		single bit\n"
			    "<high>:<low>	bitfield from high to low\n"
			    "\n"
			    "value to be written\n");

	// List subcommand setup
	list_cmd->add_option("-r,--regs", rwmem_opts.regfile, "Register description file");
	list_cmd->add_option("-p,--print", print_mode_str, "Print mode: r or rf (default)");
	list_cmd->add_flag("-v,--verbose", rwmem_opts.verbose, "Verbose output");
	list_cmd->add_option("patterns", rwmem_opts.list_patterns, "Register patterns to match (optional)");

	// Require exactly one subcommand
	app.require_subcommand(1);

	// CLI11 wants the arguments in reverse order, without command name
	std::vector<std::string> cli11_args;
	std::reverse_copy(args.begin() + 1, args.end(), std::back_inserter(cli11_args));

	// If no arguments provided, show help
	if (cli11_args.empty()) {
		std::cout << app.help() << std::endl;
		exit(0);
	}

	try {
		// CLI11 mutates the args vector, so keep a copy of the original
		std::vector<std::string> original_args = cli11_args;

		try {
			// First attempt: parse original arguments
			app.parse(cli11_args);
		} catch (const CLI::RequiredError& e) {
			bool any_parsed = mmap_cmd->parsed() || i2c_cmd->parsed() || list_cmd->parsed();

			if (any_parsed)
				throw;

			// Failed due to missing subcommand - try default mode
			// Use original_args since args was modified by the first parse attempt
			// Add /dev/mem and mmap in reverse order
			original_args.push_back("/dev/mem");
			original_args.push_back("mmap");

			// Re-parse with default mode
			app.parse(original_args);
		}

		// Determine which mode we're in
		if (mmap_cmd->parsed()) {
			rwmem_opts.target_type = TargetType::MMap;
			rwmem_opts.mmap_target = mmap_file;
		} else if (i2c_cmd->parsed()) {
			rwmem_opts.target_type = TargetType::I2C;
			rwmem_opts.i2c_target = i2c_param;

			// Validate I2C parameter format
			vector<string> strs = split(i2c_param, ':');
			if (strs.size() != 2 || strs[0].empty() || strs[1].empty()) {
				throw CLI::ValidationError("Invalid I2C parameter '" + i2c_param + "'. Expected format: <bus>:<addr>");
			}

			// Validate that both parts are numeric
			uint64_t bus, addr;
			if (parse_u64(strs[0], &bus) != 0) {
				throw CLI::ValidationError("Invalid I2C bus '" + strs[0] + "'. Must be a number");
			}
			if (parse_u64(strs[1], &addr) != 0) {
				throw CLI::ValidationError("Invalid I2C address '" + strs[1] + "'. Must be a number");
			}
		} else if (list_cmd->parsed()) {
			rwmem_opts.show_list = true;
		} else {
			throw CLI::RequiredError("No subcommand parsed");
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
				throw CLI::ValidationError("illegal write mode '" + write_mode_str + "'");
		}

		if (!print_mode_str.empty()) {
			if (print_mode_str == "q")
				rwmem_opts.print_mode = PrintMode::Quiet;
			else if (print_mode_str == "r")
				rwmem_opts.print_mode = PrintMode::Reg;
			else if (print_mode_str == "rf")
				rwmem_opts.print_mode = PrintMode::RegFields;
			else
				throw CLI::ValidationError("illegal print mode '" + print_mode_str + "'");
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
				throw CLI::ValidationError("Invalid format '" + format_str + "'. Valid formats: x (hex), d (dec), b (bin)");

			// Validate format scope
			if (rwmem_opts.print_mode == PrintMode::Quiet && !format_str.empty()) {
				rwmem_vprint("Warning: --format option ignored in quiet mode\n");
			}
			if (rwmem_opts.raw_output && !format_str.empty()) {
				rwmem_vprint("Warning: --format option ignored in raw output mode\n");
			}
		}

		if (!rwmem_opts.show_list) {
			if (op_strs.empty())
				throw CLI::RequiredError("No operations specified");

			rwmem_opts.parsed_args.clear();
			rwmem_opts.parsed_args.reserve(op_strs.size());

			for (const string& param : op_strs) {
				RwmemOptsArg parsed_arg;
				parse_arg(param, &parsed_arg, app);
				rwmem_opts.parsed_args.push_back(parsed_arg);
			}
		}

	} catch (const CLI::CallForHelp& e) {
		std::cout << app.help() << std::endl;
		exit(0);
	} catch (const CLI::ParseError& e) {
		exit(app.exit(e));
	}
}
