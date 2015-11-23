#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <stdarg.h>
#include <string.h>
#include <unistd.h>
#include <getopt.h>

#include "rwmem.h"
#include "helpers.h"

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
		"	-b <address>	base address\n"
		"	-R		raw output mode\n"
		"	--file <file>	file to open (default: /dev/mem)\n"
		"	--conf <file>	config file (default: ~/.rwmem/rwmemrc)\n"
		"	--regs <file>	register set file\n"
	       );

	exit(1);
}

static void parse_arg(char *str, RwmemOptsArg *arg)
{
	char *addr;

	arg->address = str;

	addr = strsep(&str, "=");
	arg->value = str;
	str = addr;

	addr = strsep(&str, ":");
	arg->field = str;

	str = addr;
	addr = strsep(&str, "+");
	if (str) {
		arg->range = str;
		arg->range_is_offset = true;
	} else {
		str = strstr(addr, "..");
		if (str) {
			*str = 0;
			arg->range = str + 2;
			arg->range_is_offset = false;
		}
	}

	if (strlen(arg->address) == 0)
		usage();

	if (arg->range && strlen(arg->range) == 0)
		usage();

	if (arg->field && strlen(arg->field) == 0)
		usage();

	if (arg->value && strlen(arg->value) == 0)
		usage();
}

static void parse_longopt(int idx)
{
	switch (idx) {
	case 0:	/* file */
		rwmem_opts.filename = optarg;
		break;
	case 1:	/* regs */
		rwmem_opts.regfile = optarg;
		break;
	case 2:	/* conf */
		rwmem_opts.aliasfile = optarg;
		break;
	default:
		usage();
	}
}

void parse_cmdline(int argc, char **argv)
{
	memset(&rwmem_opts, 0, sizeof(rwmem_opts));

	rwmem_opts.filename = "/dev/mem";
	rwmem_opts.regsize = 32;
	rwmem_opts.write_mode = WriteMode::ReadWriteRead;
	rwmem_opts.print_mode = PrintMode::RegFields;

	int c;

	while (1) {
		int option_index = 0;
		static const struct option lopts[] = {
			{"file", required_argument, 0, 0 },
			{"regs", required_argument, 0, 0 },
			{"conf", required_argument, 0, 0 },
			{0, 0, 0, 0 }
		};

		c = getopt_long(argc, argv, "s:w:b:hRp:",
				lopts, &option_index);
		if (c == -1)
			break;

		switch (c) {
		case 0:
			parse_longopt(option_index);
			break;

		case 's': {
			int rs = atoi(optarg);

			if (rs != 8 && rs != 16 && rs != 32 && rs != 64)
				myerr("Invalid size '%s'", optarg);

			rwmem_opts.regsize = rs;
			break;
		}
		case 'w':
			if (strcmp(optarg, "w") == 0)
				rwmem_opts.write_mode = WriteMode::Write;
			else if (strcmp(optarg, "rw") == 0)
				rwmem_opts.write_mode = WriteMode::ReadWrite;
			else if (strcmp(optarg, "rwr") == 0)
				rwmem_opts.write_mode = WriteMode::ReadWriteRead;
			else
				ERR("illegal write mode '%s'", optarg);
			break;
		case 'b':
			rwmem_opts.base = optarg;
			break;
		case 'R':
			rwmem_opts.raw_output = true;
			break;
		case 'p':
			if (strcmp(optarg, "q") == 0)
				rwmem_opts.print_mode = PrintMode::Quiet;
			else if (strcmp(optarg, "r") == 0)
				rwmem_opts.print_mode = PrintMode::Reg;
			else if (strcmp(optarg, "rf") == 0)
				rwmem_opts.print_mode = PrintMode::RegFields;
			else
				ERR("illegal print mode '%s'", optarg);
			break;
		case 'h':
		default:
			usage();
		}
	}

	int num_args = argc - optind;

	if (num_args == 0)
		usage();

	rwmem_opts.args.resize(num_args);

	for (int i = 0; i < num_args; ++i)
		parse_arg(argv[optind + i], &rwmem_opts.args[i]);
}
