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

#include <unistd.h>
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <string.h>
#include <errno.h>
#include <fcntl.h>
#include <ctype.h>
#include <termios.h>
#include <sys/types.h>
#include <sys/mman.h>
#include <inttypes.h>
#include <stdbool.h>
#include <stdarg.h>

enum opmode {
	MODE_R,
	MODE_W,
	MODE_RW,
};

struct addr {
	uint64_t paddr;
	void *vaddr;
	int regsize;
};

struct field_desc {
	int shift;
	int width;
	uint64_t mask;
};

__attribute__ ((noreturn))
static void myerr(const char* format, ... )
{
	va_list args;

	va_start(args, format);
	vfprintf(stderr, format, args);
	va_end(args);

	fputs("\n", stderr);

	exit(1);
}

__attribute__ ((noreturn))
static void myerr2(const char* format, ... )
{
	va_list args;

	va_start(args, format);
	vfprintf(stderr, format, args);
	va_end(args);

	fprintf(stderr, ": %s\n", strerror(errno));

	exit(1);
}

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

static void print_reg(char m, const struct addr *addr, const struct field_desc *field, uint64_t v, uint64_t fv)
{
	printf("%c %#" PRIx64 " = %0#*" PRIx64, m, addr->paddr, addr->regsize / 4 + 2, v);
	if (field->width != addr->regsize)
		printf(" [%d:%d] = %#" PRIx64, field->shift + field->width - 1, field->shift, fv);
	printf("\n");
	fflush(stdout);
}

static uint64_t readmemprint(const struct addr *addr, const struct field_desc *field)
{
	uint64_t v, fv;

	v = readmem(addr->vaddr, addr->regsize);
	fv = (v & field->mask) >> field->shift;

	print_reg('R', addr, field, v, fv);

	return v;
}

static void writememprint(const struct addr *addr, const struct field_desc *field, uint64_t oldvalue, uint64_t value)
{
	uint64_t v;

	v = oldvalue;
	v &= ~field->mask;
	v |= value << field->shift;

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

int main(int argc, char **argv)
{
	const unsigned pagesize = sysconf(_SC_PAGESIZE);
	const unsigned pagemask = pagesize - 1;
	int fd;
	void *mmap_base, *vaddr;
	uint64_t paddr;
	enum opmode mode;
	int regsize;
	uint64_t userval;
	struct addr addr;
	struct field_desc field;
	int opt;
	const char *filename = "/dev/mem";
	bool writeonly = false;

	regsize = 32;

	while ((opt = getopt(argc, argv, "s:f:w")) != -1) {
		switch (opt) {
		case 's':
			regsize = atoi(optarg);

			if (regsize != 8 && regsize != 16 && regsize != 32 && regsize != 64)
				myerr("Invalid size '%s'", optarg);

			break;
		case 'f':
			filename = optarg;
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
		mode = MODE_R;
		break;
	case 2:
		if (writeonly)
			mode = MODE_W;
		else
			mode = MODE_RW;
		break;
	default:
		usage();
	}

	/* Parse address */

	paddr = parse_address(argv[optind], &field, regsize);

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

	fd = open(filename, (mode == MODE_R ? O_RDONLY : O_RDWR) | O_SYNC);

	if (fd == -1)
		myerr2("Failed to open file '%s'", filename);

	mmap_base = mmap(0, pagesize, mode == MODE_R ? PROT_READ : PROT_WRITE,
			MAP_SHARED, fd, (off_t)paddr & ~pagemask);

	if (mmap_base == MAP_FAILED)
		myerr2("failed to mmap");

	vaddr = (uint8_t* )mmap_base + (paddr & pagemask);

	addr.paddr = paddr;
	addr.vaddr = vaddr;
	addr.regsize = regsize;

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

