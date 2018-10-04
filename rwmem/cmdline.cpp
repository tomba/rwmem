#include <cstdio>
#include <cstdlib>
#include <cstdint>
#include <cstdarg>
#include <cstring>
#include <unistd.h>

#include "rwmem.h"
#include "helpers.h"
#include "opts.h"

using namespace std;

RwmemOpts rwmem_opts;

__attribute__ ((noreturn))
static void usage()
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
		"	-d,--decimal		print values in decimal\n"
		);

	exit(1);
}

void parse_arg(string str, RwmemOptsArg *arg)
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

static bool ends_with(const std::string& value, const std::string& ending)
{
	if (ending.size() > value.size())
		return false;
	return std::equal(ending.rbegin(), ending.rend(), value.rbegin());
}

static void parse_size_endian(string s, uint32_t* size, Endianness* e)
{
	if (ends_with(s, "be")) {
		*e = Endianness::Big;
		s = s.substr(0, s.length() - 2);
	} else if (ends_with(s, "le")) {
		*e = Endianness::Little;
		s = s.substr(0, s.length() - 2);
	} else if (ends_with(s, "bes")) {
		*e = Endianness::BigSwapped;
		s = s.substr(0, s.length() - 3);
	} else if (ends_with(s, "les")) {
		*e = Endianness::LittleSwapped;
		s = s.substr(0, s.length() - 3);
	} else {
		*e = Endianness::Default;
	}

	*size = stoi(s);
}

void parse_cmdline(int argc, char **argv)
{
	OptionSet optionset = {
		Option("s=", [](string s)
		{
			Endianness endianness;
			uint32_t size;

			parse_size_endian(s, &size, &endianness);

			ERR_ON(size != 8 && size != 16 && size != 32 && size != 64,
			"Invalid size '%s'", s.c_str());

			rwmem_opts.data_size = size / 8;
			rwmem_opts.data_endianness = endianness;
			rwmem_opts.user_data_size = true;
		}),
		Option("S=", [](string s)
		{
			Endianness endianness;
			uint32_t size;

			parse_size_endian(s, &size, &endianness);

			ERR_ON(size != 8 && size != 16 && size != 32 && size != 64,
			"Invalid address size '%s'", s.c_str());

			rwmem_opts.address_size = size / 8;
			rwmem_opts.address_endianness = endianness;
			rwmem_opts.user_address_size = true;
		}),
		Option("w=", [](string s)
		{
			if (s == "w")
			rwmem_opts.write_mode = WriteMode::Write;
			else if (s == "rw")
			rwmem_opts.write_mode = WriteMode::ReadWrite;
			else if (s == "rwr")
			rwmem_opts.write_mode = WriteMode::ReadWriteRead;
			else
			ERR("illegal write mode '%s'", s.c_str());
		}),
		Option("R|raw", []()
		{
			rwmem_opts.raw_output = true;
		}),
		Option("p=", [](string s)
		{
			if (s == "q")
			rwmem_opts.print_mode = PrintMode::Quiet;
			else if (s == "r")
			rwmem_opts.print_mode = PrintMode::Reg;
			else if (s == "rf")
			rwmem_opts.print_mode = PrintMode::RegFields;
			else
			ERR("illegal print mode '%s'", s.c_str());
		}),
		Option("|mmap=", [](string s)
		{
			rwmem_opts.mmap_target = s;
			rwmem_opts.target_type = TargetType::MMap;
		}),
		Option("|i2c=", [](string s)
		{
			rwmem_opts.i2c_target = s;
			rwmem_opts.target_type = TargetType::I2C;
		}),
		Option("|regs=", [](string s)
		{
			rwmem_opts.regfile = s;
		}),
		Option("|list", [](string s)
		{
			rwmem_opts.show_list = true;
		}),
		Option("|ignore-base", []()
		{
			rwmem_opts.ignore_base = true;
		}),
		Option("v|verbose", []()
		{
			rwmem_opts.verbose = true;
		}),
		Option("d|decimal", []()
		{
			rwmem_opts.print_decimal = true;
		}),
		Option("h|help", []()
		{
			usage();
		}),
	};

	try
	{
		optionset.parse(argc, argv);
	}
	catch(std::exception const& e)
	{
		ERR("Failed to parse options: %s\n", e.what());
	}

	const vector<string> params = optionset.params();

	if (!rwmem_opts.show_list && params.empty())
		usage();

	rwmem_opts.args = params;
}
