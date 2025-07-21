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

RwmemOpts rwmem_opts;

__attribute__((noreturn)) static void usage()
{
	fprintf(stderr,
		"usage: rwmem [options] <address>[:field][=value] ...\n"
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
		"	-h			show this help\n"
		"	-s <size>[endian]	bit size of the memory access\n"
		"	-S <size>[endian]	bit size of the address (i2c)\n"
		"	-w <mode>		write mode: w, rw or rwr (default)\n"
		"	-p <mode>		print mode: q, r or rf (default)\n"
		"	-R			raw output mode\n"
		"	--list			list-mode, do not read or write\n"
		"	--mmap <file>		mmap-mode, file to open (default: /dev/mem)\n"
		"	--i2c <bus>:<addr>	i2c-mode, device bus and address\n"
		"	--regs <file>		register description file\n"
		"	--ignore-base		ignore base from register desc file\n"
		"	-b,--binary		print values in binary\n"
		"	-d,--decimal		print values in decimal\n");

	exit(1);
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
			usage();
	}

	// extract field

	idx = str.find(':');

	if (idx != string::npos) {
		arg->field = str.substr(idx + 1);
		str.resize(idx);

		if (arg->field.empty())
			usage();
	}

	// extract len

	idx = str.find('+');

	if (idx != string::npos) {
		arg->range = str.substr(idx + 1);
		arg->range_is_offset = true;
		str.resize(idx);

		if (arg->range.empty())
			usage();
	} else {
		// extract end

		idx = str.find('-');

		if (idx != string::npos) {
			arg->range = str.substr(idx + 1);
			arg->range_is_offset = false;
			str.resize(idx);

			if (arg->range.empty())
				usage();
		}
	}

	arg->address = str;

	if (arg->address.empty())
		usage();
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
	OptionSet optionset = {
		Option("s=", [](string_view s) {
			Endianness endianness;
			uint32_t size;

			parse_size_endian(s, &size, &endianness);

			rwmem_opts.data_size = size / 8;
			rwmem_opts.data_endianness = endianness;
			rwmem_opts.user_data_size = true;
		}),
		Option("S=", [](string_view s) {
			Endianness endianness;
			uint32_t size;

			parse_size_endian(s, &size, &endianness);

			rwmem_opts.address_size = size / 8;
			rwmem_opts.address_endianness = endianness;
			rwmem_opts.user_address_size = true;
		}),
		Option("w=", [](string_view s) {
			if (s == "w")
				rwmem_opts.write_mode = WriteMode::Write;
			else if (s == "rw")
				rwmem_opts.write_mode = WriteMode::ReadWrite;
			else if (s == "rwr")
				rwmem_opts.write_mode = WriteMode::ReadWriteRead;
			else
				ERR("illegal write mode '{}'", s);
		}),
		Option("R|raw", []() {
			rwmem_opts.raw_output = true;
		}),
		Option("p=", [](string_view s) {
			if (s == "q")
				rwmem_opts.print_mode = PrintMode::Quiet;
			else if (s == "r")
				rwmem_opts.print_mode = PrintMode::Reg;
			else if (s == "rf")
				rwmem_opts.print_mode = PrintMode::RegFields;
			else
				ERR("illegal print mode '{}'", s);
		}),
		Option("|mmap=", [](string_view s) {
			rwmem_opts.mmap_target = s;
			rwmem_opts.target_type = TargetType::MMap;
		}),
		Option("|i2c=", [](string_view s) {
			rwmem_opts.i2c_target = s;
			rwmem_opts.target_type = TargetType::I2C;
		}),
		Option("|regs=", [](string_view s) {
			rwmem_opts.regfile = s;
		}),
		Option("|list", [](string_view s) {
			rwmem_opts.show_list = true;
		}),
		Option("|ignore-base", []() {
			rwmem_opts.ignore_base = true;
		}),
		Option("v|verbose", []() {
			rwmem_opts.verbose = true;
		}),
		Option("d|decimal", []() {
			rwmem_opts.number_print_mode = NumberPrintMode::Dec;
		}),
		Option("b|binary", []() {
			rwmem_opts.number_print_mode = NumberPrintMode::Bin;
		}),
		Option("h|help", []() {
			usage();
		}),
	};

	try {
		optionset.parse(argc, argv);
	} catch (std::exception const& e) {
		ERR("Failed to parse options: {}\n", e.what());
	}

	const vector<string>& params = optionset.params();

	rwmem_opts.args = params;
	rwmem_opts.parsed_args.clear();

	if (!rwmem_opts.show_list) {
		if (params.empty())
			usage();

		rwmem_opts.parsed_args.clear();
		rwmem_opts.parsed_args.reserve(params.size());

		for (const string& param : params) {
			RwmemOptsArg parsed_arg;
			parse_arg(param, &parsed_arg);
			rwmem_opts.parsed_args.push_back(parsed_arg);
		}
	}
}
