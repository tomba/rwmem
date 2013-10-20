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

int main(int argc, char **argv)
{
	const unsigned pagesize = sysconf(_SC_PAGESIZE);
	const unsigned pagemask = pagesize - 1;
	uint64_t paddr;
	struct field_desc field;

	parse_cmdline(argc, argv);

	enum opmode mode = rwmem_opts.mode;

	/* Parse address */

	paddr = parse_address(rwmem_opts.address_str);
	parse_field(rwmem_opts.field_str, &field, rwmem_opts.regsize);

	/* Parse value */

	uint64_t userval = 0;

	if (mode == MODE_W || mode == MODE_RW) {
		const char *vstr = rwmem_opts.value_str;
		char *endptr;

		userval = strtoull(vstr, &endptr, 0);
		if (*vstr == 0 || *endptr != 0)
			myerr("Invalid value '%s'", vstr);

		userval &= field.mask >> field.shift;
	}


	int fd = open(rwmem_opts.filename,
			(mode == MODE_R ? O_RDONLY : O_RDWR) | O_SYNC);

	if (fd == -1)
		myerr2("Failed to open file '%s'", rwmem_opts.filename);

	void *mmap_base = mmap(0, pagesize,
			mode == MODE_R ? PROT_READ : PROT_WRITE,
			MAP_SHARED, fd, (off_t)paddr & ~pagemask);

	if (mmap_base == MAP_FAILED)
		myerr2("failed to mmap");

	void *vaddr = (uint8_t* )mmap_base + (paddr & pagemask);

	struct addr addr = { 0 };
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

