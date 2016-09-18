#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <stdarg.h>
#include <string.h>
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
		"usage: rwmem [options] [base] <address>[:field][=value]\n"
		"\n"
		"	base		base address or register block\n"
		"\n"
		"	address		address to access:\n"
		"			<address>	single address\n"
		"			<start-end>	range with end address\n"
		"			<start+len>	range with length\n"
		"\n"
		"	field		bitfield (inclusive, start from 0):\n"
		"			<bit>		single bit\n"
		"			<high>:<low>	bitfield from high to low\n"
		"\n"
		"	value		value to be written\n"
		"\n"
		"	-h		show this help\n"
		"	-s <size>	size of the memory access: 8/16/32/64 (default: 32)\n"
		"	-w <mode>	write mode: w, rw or rwr (default)\n"
		"	-p <mode>	print mode: q, r or rf (default)\n"
		"	-R		raw output mode\n"
		"	--file <file>	file to open (default: /dev/mem)\n"
		"	--regs <file>	register set file\n"
		);

	exit(1);
}

static void parse_arg(std::string str, RwmemOptsArg *arg)
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

	idx = str.find('.');

	if (idx != string::npos) {
		arg->address = str.substr(idx + 1);
		str.resize(idx);
		arg->register_block = str;

		if (arg->register_block.empty())
			usage();
	} else {
		arg->address = str;
	}

	if (arg->address.empty())
		usage();

	if (arg->address == "*") {
		if (arg->register_block.empty())
			usage();
		if (!arg->range.empty())
			usage();

		arg->range = "*";
		arg->range_is_offset = false;
	}
}

void parse_cmdline(int argc, char **argv)
{
	OptionSet optionset = {
		Option("s=", [](string s)
		{
			int rs = stoi(s);

			if (rs != 8 && rs != 16 && rs != 32 && rs != 64)
			ERR("Invalid size '%s'", s.c_str());

			rwmem_opts.regsize = rs / 8;
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
		Option("|file=", [](string s)
		{
			rwmem_opts.filename = s;
		}),
		Option("|regs=", [](string s)
		{
			rwmem_opts.regfile = s;
		}),
		Option("|list?", [](string s)
		{
			rwmem_opts.show_list = true;
			rwmem_opts.pattern = s;
		}),
		Option("|ignore-base", []()
		{
			rwmem_opts.ignore_base = true;
		}),
		Option("v|verbose", []()
		{
			rwmem_opts.verbose = true;
		}),
		Option("|i2c=", [](string s)
		{
			vector<string> strs = split(s, ':');
			ERR_ON(strs.size() != 2, "bad i2c parameter");

			int r;
			uint64_t v;

			r = parse_u64(strs[0], &v);
			ERR_ON(r, "failed to parse i2c bus");
			rwmem_opts.i2c_bus = v;

			r = parse_u64(strs[1], &v);
			ERR_ON(r, "failed to parse i2c address");
			rwmem_opts.i2c_addr = v;

			rwmem_opts.i2c_mode = true;
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

	switch (params.size()) {
	case 0:
		if (!rwmem_opts.show_list)
			usage();
		break;

	case 1:
		parse_arg(params[0], &rwmem_opts.arg);
		break;

	case 2:
		if (params[0].empty())
			usage();

		rwmem_opts.arg.register_block = params[0];

		parse_arg(params[1], &rwmem_opts.arg);
		break;

	default:
		usage();
	}
}
