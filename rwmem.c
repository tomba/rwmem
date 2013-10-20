/**
 * Copyright (C) 2013 Tomi Valkeinen
 *
 * This program is free software; you can redistribute it and/or
 * modify it under the terms of the GNU General Public License
 * as published by the Free Software Foundation; either version 2
 * of the License, or (at your option) any later version.
 *
 * This program is distributed in the hope that it will be useful,
 * but WITHOUT ANY WARRANTY; without even the implied warranty of
 * MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
 * GNU General Public License for more details.
 *
 * You should have received a copy of the GNU General Public License
 * along with this program; if not, write to the Free Software
 * Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston,
 * MA  02110-1301, USA.
 */

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

static uint64_t readmem(void *addr, int regsize)
{
	switch(regsize) {
	case 8:
		return *((uint8_t *)addr);
	case 16:
		return *((uint16_t *)addr);
	case 32:
		return *((uint32_t *)addr);
	case 64:
		return *((uint64_t *)addr);
	default:
		myerr("Illegal data regsize '%c'", regsize);
	}
}

static void writemem(void *addr, int regsize, uint64_t value)
{
	switch(regsize) {
	case 8:
		*((uint8_t *)addr) = value;
		break;
	case 16:
		*((uint16_t *)addr) = value;
		break;
	case 32:
		*((uint32_t *)addr) = value;
		break;
	case 64:
		*((uint64_t *)addr) = value;
		break;
	}
}

static void print_reg(char m, const struct addr *addr,
		const struct field_desc *field, uint64_t v, uint64_t fv)
{
	printf("%c %#" PRIx64 " = %0#*" PRIx64, m, addr->paddr, addr->regsize / 4 + 2, v);
	if (field && field->width != addr->regsize) {
		int fh = field->shift + field->width - 1;
		int fl = field->shift;
		printf(" [%d:%d] = %#" PRIx64, fh, fl, fv);
	}

	printf("\n");
	fflush(stdout);
}

static uint64_t readmemprint(const struct addr *addr,
		const struct field_desc *field)
{
	uint64_t v, fv;

	v = readmem(addr->vaddr, addr->regsize);
	if (field && field->width != addr->regsize)
		fv = (v & field->mask) >> field->shift;
	else
		fv = v;

	print_reg('R', addr, field, v, fv);

	return v;
}

static void writememprint(const struct addr *addr,
		const struct field_desc *field,
		uint64_t oldvalue, uint64_t value)
{
	uint64_t v;

	if (field) {
		v = oldvalue;
		v &= ~field->mask;
		v |= value << field->shift;
	} else {
		v = value;
	}

	print_reg('W', addr, field, v, value);

	writemem(addr->vaddr, addr->regsize, v);
}

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

static uint64_t parse_address(char *astr, struct field_desc *field, int regsize)
{
	char *s, *token, *endptr;
	uint64_t paddr;
	int fl, fh;

	s = astr;

	token = strsep(&s, ":");
	paddr = strtoull(token, &endptr, 0);
	if (*token == 0 || *endptr != 0)
		myerr("Invalid address '%s'", token);

	if (s) {
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

	return paddr;
}

struct rwmem_opts rwmem_opts;

int main(int argc, char **argv)
{
	const unsigned pagesize = sysconf(_SC_PAGESIZE);
	const unsigned pagemask = pagesize - 1;
	int fd;
	void *mmap_base, *vaddr;
	uint64_t paddr;
	enum opmode mode;
	uint64_t userval;
	struct addr addr;
	struct field_desc field;
	int opt;

	rwmem_opts.filename = "/dev/mem";
	rwmem_opts.regsize = 32;
	rwmem_opts.writeonly = false;

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
			rwmem_opts.writeonly = true;
			break;
		default:
			usage();
		}
	}

	switch (argc - optind) {
	case 1:
		mode = MODE_R;
		break;
	case 2:
		if (rwmem_opts.writeonly)
			mode = MODE_W;
		else
			mode = MODE_RW;
		break;
	default:
		usage();
	}

	/* Parse address */

	paddr = parse_address(argv[optind], &field, rwmem_opts.regsize);

	/* Parse value */

	if (mode == MODE_W || mode == MODE_RW) {
		const char *vstr = argv[optind + 1];
		char *endptr;

		userval = strtoull(vstr, &endptr, 0);
		if (*vstr == 0 || *endptr != 0)
			myerr("Invalid value '%s'", vstr);

		userval &= field.mask >> field.shift;
	} else {
		userval = 0;
	}

	fd = open(rwmem_opts.filename,
			(mode == MODE_R ? O_RDONLY : O_RDWR) | O_SYNC);

	if (fd == -1)
		myerr2("Failed to open file '%s'", rwmem_opts.filename);

	mmap_base = mmap(0, pagesize, mode == MODE_R ? PROT_READ : PROT_WRITE,
			MAP_SHARED, fd, (off_t)paddr & ~pagemask);

	if (mmap_base == MAP_FAILED)
		myerr2("failed to mmap");

	vaddr = (uint8_t* )mmap_base + (paddr & pagemask);

	addr.paddr = paddr;
	addr.vaddr = vaddr;
	addr.regsize = rwmem_opts.regsize;

	switch (mode) {
	case MODE_R:
		readmemprint(&addr, &field);
		break;

	case MODE_W:
		writememprint(&addr, &field, 0, userval);
		break;

	case MODE_RW:
		{
			uint64_t v;

			v = readmemprint(&addr, &field);

			writememprint(&addr, &field, v, userval);

			readmemprint(&addr, &field);
		}
		break;
	}

	if (munmap(mmap_base, pagesize) == -1)
		myerr2("failed to munmap");

	close(fd);

	return 0;
}

