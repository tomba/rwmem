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
 * Foundation, Inc., 51 Franklin Street, Fifth Floor, Boston, MA  02110-1301, USA.
 */

#define _BSD_SOURCE

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

struct field {
	int shift;
	int width;
	uint64_t mask;
};

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
		fprintf(stderr, "Illegal data regsize '%c'.\n", regsize);
		exit(1);
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

static void print_reg(char m, const struct addr *addr, const struct field *field, uint64_t v, uint64_t fv)
{
	printf("%c %#" PRIx64 " = %0#*" PRIx64, m, addr->paddr, addr->regsize / 4 + 2, v);
	if (field->width != addr->regsize)
		printf(" [%d:%d] = %#" PRIx64, field->shift + field->width - 1, field->shift, fv);
	printf("\n");
	fflush(stdout);
}

static uint64_t readmemprint(const struct addr *addr, const struct field *field)
{
	uint64_t v, fv;

	v = readmem(addr->vaddr, addr->regsize);
	fv = (v & field->mask) >> field->shift;

	print_reg('R', addr, field, v, fv);

	return v;
}

static void writememprint(const struct addr *addr, const struct field *field, uint64_t oldvalue, uint64_t value)
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
	fprintf(stderr, "usage: rwmem <mode> <regsize> <address>[:h[:l]] [value]\n"
			"	mode		r/w/rw\n"
			"	regsize		8/16/32/64\n"
			"	address		memory address\n"
			"	h		field's high bit number\n"
			"	l		field's low bit number\n"
			"	value		value to be written\n");
	exit(1);
}

static enum opmode parse_mode(const char *str)
{
	if (strcmp(str, "r") == 0)
		return MODE_R;
	else if (strcmp(str, "w") == 0)
		return MODE_W;
	else if (strcmp(str, "rw") == 0)
		return MODE_RW;
	else
		usage();
}

static int parse_regsize(const char *str)
{
	int r;

	r = strtoul(str, NULL, 10);

	if (r != 8 && r != 16 && r != 32 && r != 64)
		usage();

	return r;
}

int main(int argc, char **argv)
{
	const unsigned pagesize = sysconf(_SC_PAGESIZE);
	const unsigned pagemask = pagesize - 1;
	int fd;
	void *base, *vaddr;
	uint64_t paddr;
	enum opmode mode;
	int regsize;
	uint64_t userval;
	int fl, fh;
	char *s, *token;
	struct addr addr;
	struct field field;

	if(argc < 4 || argc > 5)
		usage();

	mode = parse_mode(argv[1]);

	if ((mode == MODE_W || mode == MODE_RW) && argc == 4) {
		fprintf(stderr, "No value given\n");
		exit(1);
	}

	regsize = parse_regsize(argv[2]);

	s = argv[3];

	token = strsep(&s, ":");
	paddr = strtoull(token, NULL, 0);

	if (s) {
		token = strsep(&s, ":");
		fl = strtoull(token, NULL, 0);

		if (s) {
			token = strsep(&s, ":");
			fh = strtoull(token, NULL, 0);
		} else {
			fh = fl;
		}
	} else {
		fl = 0;
		fh = regsize - 1;
	}

	if (fh >= regsize || fl >= regsize) {
		fprintf(stderr, "Field bits too high\n");
		exit(1);
	}

	if (fh < fl) {
		int tmp = fh;
		fh = fl;
		fl = tmp;
	}

	field.shift = fl;
	field.width = fh - fl + 1;
	field.mask = ((1ULL << field.width) - 1) << field.shift;

	if (argc == 5) {
		userval = strtoull(argv[4], 0, 0);
		userval &= field.mask >> field.shift;
	} else {
		userval = 0;
	}

	fd = open("/dev/mem", O_RDWR | O_SYNC);

	if (fd == -1) {
		perror("failed to open /dev/mem");
		return 1;
	}

	base = mmap(0, pagesize, PROT_READ | PROT_WRITE, MAP_SHARED, fd, (off_t)paddr & ~pagemask);

	if (base == MAP_FAILED) {
		perror("failed to mmap");
		return 1;
	}

	vaddr = (uint8_t* )base + (paddr & pagemask);

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

	if (munmap(base, pagesize) == -1) {
		perror("failed to munmap");
		return 1;
	}

	close(fd);

	return 0;
}

