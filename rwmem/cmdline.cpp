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

		if (arg->value.empty()) {
			std::cout << app.help() << std::endl;
			exit(0);
		}
	}

	// extract field

	idx = str.find(':');

	if (idx != string::npos) {
		arg->field = str.substr(idx + 1);
		str.resize(idx);

		if (arg->field.empty()) {
			std::cout << app.help() << std::endl;
			exit(0);
		}
	}

	// extract len

	idx = str.find('+');

	if (idx != string::npos) {
		arg->range = str.substr(idx + 1);
		arg->range_is_offset = true;
		str.resize(idx);

		if (arg->range.empty()) {
			std::cout << app.help() << std::endl;
			exit(0);
		}
	} else {
		// extract end

		idx = str.find('-');

		if (idx != string::npos) {
			arg->range = str.substr(idx + 1);
			arg->range_is_offset = false;
			str.resize(idx);

			if (arg->range.empty()) {
				std::cout << app.help() << std::endl;
				exit(0);
			}
		}
	}

	arg->address = str;

	if (arg->address.empty()) {
		std::cout << app.help() << std::endl;
		exit(0);
	}
}

static void parse_size_endian(string_view s, uint32_t* size, Endianness* e)
{
	auto start = s.begin();
	auto end = s.end();
	uint32_t num;

	auto [ptr, ec]{ std::from_chars(start, end, num) };

	if (ec != std::errc()) {
		ERR("Failed to parse size '{}'\n", s);
		return;
	}

	ERR_ON(num == 0 || num > 64 || (num % 8) != 0,
	       "Invalid size '{}' (must be 8-64 bits, multiple of 8)", num);

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
		ERR("Bad endianness '{}'", ending);

	*size = num;
}

void parse_cmdline(int argc, char** argv)
{
	CLI::App app{"rwmem - read/write memory tool"};

	// Custom variables for CLI11 parsing
	std::string data_size_str, addr_size_str, write_mode_str, print_mode_str, format_str;
	std::string i2c_param;
	std::string mmap_file = "/dev/mem";

	// Create subcommands
	auto* mmap_cmd = app.add_subcommand("mmap", "Memory-mapped access mode");
	auto* i2c_cmd = app.add_subcommand("i2c", "I2C device access mode");
	auto* list_cmd = app.add_subcommand("list", "List registers from register database");

	// Mmap subcommand setup
	mmap_cmd->add_option("file", mmap_file, "File to open")->default_val("/dev/mem");
	mmap_cmd->add_option("-d,--data", data_size_str, "Data size and endianness (<size>[endian])");
	mmap_cmd->add_option("-w,--write", write_mode_str, "Write mode: w, rw or rwr (default)");
	mmap_cmd->add_option("-p,--print", print_mode_str, "Print mode: q, r or rf (default)");
	mmap_cmd->add_option("-f,--format", format_str, "Number format: x (hex, default), b (bin), d (dec)");
	mmap_cmd->add_option("-r,--regs", rwmem_opts.regfile, "Register description file");
	mmap_cmd->add_flag("-R,--raw", rwmem_opts.raw_output, "Raw output mode");
	mmap_cmd->add_flag("--ignore-base", rwmem_opts.ignore_base, "Ignore base from register desc file");
	mmap_cmd->add_flag("-v,--verbose", rwmem_opts.verbose, "Verbose output");
	mmap_cmd->add_option("operations", rwmem_opts.args,
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
		       "value to be written\n"
		       );

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
	i2c_cmd->add_option("operations", rwmem_opts.args,
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
		       "value to be written\n"
		       );

	// List subcommand setup
	list_cmd->add_option("-r,--regs", rwmem_opts.regfile, "Register description file");
	list_cmd->add_option("-p,--print", print_mode_str, "Print mode: r or rf (default)");
	list_cmd->add_flag("-v,--verbose", rwmem_opts.verbose, "Verbose output");
	list_cmd->add_option("patterns", rwmem_opts.args, "Register patterns to match (optional)");

	// Global options for default mode (simplified mmap /dev/mem usage)
	app.add_option("-d,--data", data_size_str, "Data size and endianness (<size>[endian])");
	app.add_option("-w,--write", write_mode_str, "Write mode: w, rw or rwr (default)");
	app.add_option("-p,--print", print_mode_str, "Print mode: q, r or rf (default)");
	app.add_option("-f,--format", format_str, "Number format: x (hex, default), b (bin), d (dec)");
	app.add_option("-r,--regs", rwmem_opts.regfile, "Register description file");
	app.add_flag("-R,--raw", rwmem_opts.raw_output, "Raw output mode");
	app.add_flag("--ignore-base", rwmem_opts.ignore_base, "Ignore base from register desc file");
	app.add_flag("-v,--verbose", rwmem_opts.verbose, "Verbose output");
	app.add_option("operations", rwmem_opts.args,
		       "<address>[:field][=value] (defaults to mmap /dev/mem)\n"
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
		       "value to be written\n"
		       );
	
	// Ensure subcommands are processed before main arguments
	app.require_subcommand(0, 1);

	try {
		app.parse(argc, argv);

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
				ERR("Invalid I2C parameter '{}'. Expected format: <bus>:<addr>", i2c_param);
			}
			
			// Validate that both parts are numeric
			uint64_t bus, addr;
			if (parse_u64(strs[0], &bus) != 0) {
				ERR("Invalid I2C bus '{}'. Must be a number", strs[0]);
			}
			if (parse_u64(strs[1], &addr) != 0) {
				ERR("Invalid I2C address '{}'. Must be a number", strs[1]);
			}
		} else if (list_cmd->parsed()) {
			rwmem_opts.show_list = true;
		} else {
			// Default mode: simplified mmap /dev/mem
			rwmem_opts.target_type = TargetType::MMap;
			rwmem_opts.mmap_target = "/dev/mem";
		}

		// Context-specific validation
		if (!addr_size_str.empty() && rwmem_opts.target_type != TargetType::I2C) {
			ERR("--addr option only applies to i2c mode");
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
				ERR("illegal write mode '{}'", write_mode_str);
		}

		if (!print_mode_str.empty()) {
			if (print_mode_str == "q")
				rwmem_opts.print_mode = PrintMode::Quiet;
			else if (print_mode_str == "r")
				rwmem_opts.print_mode = PrintMode::Reg;
			else if (print_mode_str == "rf")
				rwmem_opts.print_mode = PrintMode::RegFields;
			else
				ERR("illegal print mode '{}'", print_mode_str);
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
				ERR("Invalid format '{}'. Valid formats: x (hex), d (dec), b (bin)", format_str);
			
			// Validate format scope
			if (rwmem_opts.print_mode == PrintMode::Quiet && !format_str.empty()) {
				rwmem_vprint("Warning: --format option ignored in quiet mode\n");
			}
			if (rwmem_opts.raw_output && !format_str.empty()) {
				rwmem_vprint("Warning: --format option ignored in raw output mode\n");
			}
		}

		if (!rwmem_opts.show_list) {
			if (rwmem_opts.args.empty()) {
				std::cout << app.help() << std::endl;
				exit(0);
			}

			rwmem_opts.parsed_args.clear();
			rwmem_opts.parsed_args.reserve(rwmem_opts.args.size());

			for (const string& param : rwmem_opts.args) {
				RwmemOptsArg parsed_arg;
				parse_arg(param, &parsed_arg, app);
				rwmem_opts.parsed_args.push_back(parsed_arg);
			}
		}

	} catch (const CLI::CallForHelp &e) {
		std::cout << app.help() << std::endl;
		exit(0);
	} catch (const CLI::ParseError &e) {
		ERR("Failed to parse options: {}\n", e.what());
	}
}
