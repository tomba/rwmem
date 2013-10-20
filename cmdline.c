#include <ctype.h>
#include <fcntl.h>
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <stdarg.h>
#include <string.h>
#include <sys/mman.h>
#include <sys/types.h>
#include <termios.h>
#include <unistd.h>

#include "rwmem.h"

struct rwmem_opts rwmem_opts;

__attribute__ ((noreturn))
static void usage()
{
	fprintf(stderr,
"usage: rwmem [-s <size>] [-f file] [-w] <address>[:h[:l]] [value]\n"
"	-s		size of the memory access: 8/16/32/64 (default: 32)\n"
"	-f		file to open (default: /dev/mem)\n"
"	-w		write only mode\n"
"	<address>	address to access\n"
"	h		bitfield's high bit number (inclusive, start from 0)\n"
"	l		bitfield's low bit number (inclusive, start from 0)\n"
"	<value>		value to be written\n");

	exit(1);
}

uint64_t parse_address(const char *astr)
{
	char *endptr;

	uint64_t paddr = strtoull(astr, &endptr, 0);
	if (*endptr != 0)
		myerr("Invalid address '%s'", astr);

	return paddr;
}

void parse_field(const char *fstr, struct field_desc *field, int regsize)
{
	int fl, fh;

	if (fstr) {
		char *s, *token, *endptr;
		char str[256];

		strcpy(str, fstr);

		s = str;

		token = strsep(&s, ":");
		fl = strtoull(token, &endptr, 0);
		if (*token == 0 || *endptr != 0)
			myerr("Invalid bit '%s'", token);

		if (s) {
			token = strsep(&s, ":");
			fh = strtoull(token, &endptr, 0);
			if (*token == 0 || *endptr != 0)
				myerr("Invalid bit '%s'", token);
		} else {
			fh = fl;
		}
	} else {
		fl = 0;
		fh = regsize - 1;
	}

	if (fh >= regsize || fl >= regsize)
		myerr("Field bits higher than size");

	if (fh < fl) {
		int tmp = fh;
		fh = fl;
		fl = tmp;
	}

	field->shift = fl;
	field->width = fh - fl + 1;
	field->mask = ((1ULL << field->width) - 1) << field->shift;
}

uint64_t parse_value(const char *vstr, const struct field_desc *field)
{
	if (!vstr)
		return 0;

	char *endptr;

	uint64_t val = strtoull(vstr, &endptr, 0);
	if (*endptr != 0)
		myerr("Invalid value '%s'", vstr);

	val &= field->mask >> field->shift;

	return val;
}

void parse_cmdline(int argc, char **argv)
{
	int opt;
	bool writeonly = false;

	memset(&rwmem_opts, 0, sizeof(rwmem_opts));

	rwmem_opts.filename = "/dev/mem";
	rwmem_opts.regsize = 32;

	while ((opt = getopt(argc, argv, "s:f:w")) != -1) {
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


