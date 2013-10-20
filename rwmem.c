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
#include <inttypes.h>
#include <stdbool.h>
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

static void print_field(const struct reg_desc *reg, const struct field_desc *fd,
		uint64_t value)
{
	uint64_t fv = (value & fd->mask) >> fd->shift;

	printf("\t%-*s ", reg->max_field_name_len, fd->name);

	if (fd->width == 1)
		printf("   %-2d = ", fd->shift);
	else
		printf("%2d:%-2d = ",
				fd->shift + fd->width - 1, fd->shift);

	printf("%-#*" PRIx64, reg->width / 4 + 2, fv);

	if (rwmem_opts.show_defval)
		printf(" (%0#" PRIx64 ")", fd->defval);

	if (rwmem_opts.show_comments && fd->comment)
		printf(" # %s", fd->comment);

	puts("");
}

static uint64_t readmemprint2(const struct addr *addr,
		const struct reg_desc *reg,
		const struct field_desc *field)
{
	uint64_t v, fv;

	v = readmem(addr->vaddr, addr->regsize);
	if (field) {
		fv = (v & field->mask) >> field->shift;
		print_reg('R', addr, field, v, fv);
		return v;
	}

	fv = v;

	printf("%s (%#" PRIx64 ") = %0#*" PRIx64,
			reg->name, addr->paddr, addr->regsize / 4 + 2, v);

	if (rwmem_opts.show_comments && reg->comment)
		printf(" # %s", reg->comment);

	puts("");

	for (int i = 0; i < reg->num_fields; ++i) {
		const struct field_desc *fd = &reg->fields[i];

		print_field(reg, fd, v);
	}

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
	uint64_t base;
	enum opmode mode;
	const char *regfile;

	parse_cmdline(argc, argv);

	mode = rwmem_opts.mode;

	/* Parse base */

	base = 0;
	regfile = NULL;

	if (rwmem_opts.base)
		parse_base("rwmem.cfg", rwmem_opts.base, &base, &regfile);

	if (rwmem_opts.regfile)
		regfile = rwmem_opts.regfile;

	/* Parse address */

	struct reg_desc *reg = parse_address(rwmem_opts.address, regfile);

	/* Parse field */

	struct field_desc *field = parse_field(rwmem_opts.field, reg);

	if (field) {
		if (field->shift >= rwmem_opts.regsize ||
			(field->width + field->shift) > rwmem_opts.regsize)
		myerr("Field bits higher than size");
	}

	/* Parse value */

	uint64_t userval = parse_value(rwmem_opts.value, field);


	int fd = open(rwmem_opts.filename,
			(mode == MODE_R ? O_RDONLY : O_RDWR) | O_SYNC);

	if (fd == -1)
		myerr2("Failed to open file '%s'", rwmem_opts.filename);

	uint64_t paddr = base + reg->address;

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
		readmemprint2(&addr, reg, field);
		break;

	case MODE_W:
		writememprint(&addr, field, 0, userval);
		break;

	case MODE_RW:
		{
			uint64_t v;

			v = readmemprint(&addr, field);

			writememprint(&addr, field, v, userval);

			readmemprint(&addr, field);
		}
		break;
	}

	if (munmap(mmap_base, pagesize) == -1)
		myerr2("failed to munmap");

	close(fd);

	return 0;
}

