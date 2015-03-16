#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <stdarg.h>
#include <string.h>
#include <unistd.h>

#include "rwmem.h"

struct rwmem_opts rwmem_opts;

__attribute__ ((noreturn))
static void usage()
{
	fprintf(stderr,
"usage: rwmem [options] <address>[:field][=value]\n"
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
"	-s <size>	size of the memory access: 8/16/32/64 (default: 32)\n"
"	-f <file>	file to open (default: /dev/mem)\n"
"	-w		write only mode\n"
"	-b <address>	base address\n"
"	-a <file>	aliases file\n"
"	-r <file>	register set file\n"
"	-c		show comments\n"
"	-d		show default value\n"
"	-h		show this help\n"
);

	exit(1);
}

static void parse_arg(char *str, struct rwmem_opts_arg *arg)
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

void parse_cmdline(int argc, char **argv)
{
	int opt;

	memset(&rwmem_opts, 0, sizeof(rwmem_opts));

	rwmem_opts.filename = "/dev/mem";
	rwmem_opts.regsize = 32;

	while ((opt = getopt(argc, argv, "s:f:wb:a:r:cdh")) != -1) {
		switch (opt) {
		case 's': {
			int rs = atoi(optarg);

			if (rs != 8 && rs != 16 && rs != 32 && rs != 64)
				myerr("Invalid size '%s'", optarg);

			rwmem_opts.regsize = rs;
			break;
		}
		case 'f':
			rwmem_opts.filename = optarg;
			break;
		case 'w':
			rwmem_opts.write_only = true;
			break;
		case 'b':
			rwmem_opts.base = optarg;
			break;
		case 'a':
			rwmem_opts.aliasfile = optarg;
			break;
		case 'r':
			rwmem_opts.regfile = optarg;
			break;
		case 'c':
			rwmem_opts.show_comments = true;
			break;
		case 'd':
			rwmem_opts.show_defval = true;
			break;
		case 'h':
		default:
			usage();
		}
	}

	if (argc - optind == 0)
		usage();

	rwmem_opts.num_args = argc - optind;
	rwmem_opts.args = malloc(sizeof(struct rwmem_opts_arg) * rwmem_opts.num_args);

	for (int i = 0; i < rwmem_opts.num_args; ++i)
		parse_arg(argv[optind + i], &rwmem_opts.args[i]);
}
