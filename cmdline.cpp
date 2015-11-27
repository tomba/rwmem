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
		"usage: rwmem [options] <address>[:field][=value] [<address>[:field][=value]...]\n"
		"\n"
		"	address		address to access:\n"
		"			<address>	single address\n"
		"			<start..end>	range with end address\n"
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

static void parse_arg(const std::string arg_str, RwmemOptsArg *arg)
{
	char *str = strdup(arg_str.c_str());
	char *orig_str = str;
	char *tmp;
	const char *address = nullptr;
	const char *field = nullptr;
	const char *value = nullptr;
	const char *range = nullptr;
	bool range_is_offset;

	address = str;

	tmp = strsep(&str, "=");
	value = str;
	str = tmp;

	tmp = strsep(&str, ":");
	field = str;

	str = tmp;
	tmp = strsep(&str, "+");
	if (str) {
		range = str;
		range_is_offset = true;
	} else {
		str = strstr(tmp, "..");
		if (str) {
			*str = 0;
			range = str + 2;
			range_is_offset = false;
		}
	}

	if (strlen(address) == 0)
		usage();

	if (range && strlen(range) == 0)
		usage();

	if (field && strlen(field) == 0)
		usage();

	if (value && strlen(value) == 0)
		usage();

	arg->address = address;

	if (field) {
		arg->field = field;
		arg->field_set = true;
	}

	if (range) {
		arg->range = range;
		arg->range_set = true;
		arg->range_is_offset = range_is_offset;
	}

	if (value) {
		arg->value = value;
		arg->value_set = true;
	}

	free(orig_str);
}

void parse_cmdline(int argc, char **argv)
{
	memset(&rwmem_opts, 0, sizeof(rwmem_opts));

	rwmem_opts.filename = "/dev/mem";
	rwmem_opts.regsize = 32;
	rwmem_opts.write_mode = WriteMode::ReadWriteRead;
	rwmem_opts.print_mode = PrintMode::RegFields;

	OptionSet optionset = {
		Option("s=",
		[&](string s)
		{
			int rs = stoi(s);

			if (rs != 8 && rs != 16 && rs != 32 && rs != 64)
				ERR("Invalid size '%s'", s.c_str());

			rwmem_opts.regsize = rs;
		}),
		Option("w=", [&](string s)
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
		Option("R", [&]()
		{
			rwmem_opts.raw_output = true;
		}),
		Option("p=", [&](string s)
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
		Option("|file=", [&](string s)
		{
			rwmem_opts.filename = s;
		}),
		Option("|regs=", [&](string s)
		{
			rwmem_opts.regfile = s;
		}),
		Option("|list?", [&](string s)
		{
			rwmem_opts.show_list = true;
			rwmem_opts.show_list_pattern = s;
		}),
		Option("h|help", [&]()
		{
			usage();
		}),
	};

	optionset.parse(argc, argv);

	const vector<string> params = optionset.params();

	if (params.size() == 0 && !rwmem_opts.show_list)
		usage();

	rwmem_opts.args.resize(params.size());

	for (unsigned i = 0; i < params.size(); ++i)
		parse_arg(params[i], &rwmem_opts.args[i]);
}
