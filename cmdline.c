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
"usage: rwmem [options] <address>[:high[:low]] [value]\n"
"\n"
"	<address>	address to access\n"
"	[high]		bitfield's high bit number (inclusive, start from 0)\n"
"	[low]		bitfield's low bit number (inclusive, start from 0)\n"
"	[value]		value to be written\n"
"\n"
"	-s <size>	size of the memory access: 8/16/32/64 (default: 32)\n"
"	-f <file>	file to open (default: /dev/mem)\n"
"	-w		write only mode\n"
"	-b <address>	base address\n"
"	-a <file>	aliases file\n"
"	-r <file>	register set file\n"
"	-c		show comments\n"
"	-d		show default value\n"
);

	exit(1);
}

void parse_cmdline(int argc, char **argv)
{
	int opt;
	bool writeonly = false;

	memset(&rwmem_opts, 0, sizeof(rwmem_opts));

	rwmem_opts.filename = "/dev/mem";
	rwmem_opts.regsize = 32;

	while ((opt = getopt(argc, argv, "s:f:wb:a:r:cd")) != -1) {
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
			writeonly = true;
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
		default:
			usage();
		}
	}

	switch (argc - optind) {
	case 1:
		rwmem_opts.mode = MODE_R;
		break;
	case 2:
		if (writeonly)
			rwmem_opts.mode = MODE_W;
		else
			rwmem_opts.mode = MODE_RW;
		break;
	default:
		usage();
	}

	char *str = argv[optind];

	rwmem_opts.address = strsep(&str, ":");
	rwmem_opts.field = str;

	if (strlen(rwmem_opts.address) == 0)
		usage();

	if (rwmem_opts.field && strlen(rwmem_opts.field) == 0)
		usage();

	if (rwmem_opts.mode != MODE_R)
		rwmem_opts.value = argv[optind + 1];
}
