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

static void print_field(unsigned high, unsigned low,
	const struct reg_desc *reg, const struct field_desc *fd,
	uint64_t newval, uint64_t oldval,
	const struct rwmem_op *op)
{
	uint64_t mask = GENMASK(high, low);

	newval = (newval & mask) >> low;
	oldval = (oldval & mask) >> low;
	uint64_t userval = op->value & (mask >> low);

	if (fd)
		printf("\t%-*s ", reg->max_field_name_len, fd->name);
	else
		printf("\t");

	if (high == low)
		printf("   %-2d = ", low);
	else
		printf("%2d:%-2d = ", high, low);

	unsigned access_width = reg ? reg->width : rwmem_opts.regsize;

	if (!rwmem_opts.write_only)
		printf("%-#*" PRIx64 " ", access_width / 4 + 2, oldval);

	if (op->value_valid) {
		printf(":= %-#*" PRIx64 " ", access_width / 4 + 2, userval);
		if (!rwmem_opts.write_only)
			printf("-> %-#*" PRIx64 " ", access_width / 4 + 2, newval);
	}

	puts("");
}

static const struct field_desc *find_field_by_pos(const struct reg_desc *reg,
	unsigned high, unsigned low)
{
	for (unsigned i = 0; i < reg->num_fields; ++i) {
		const struct field_desc *field = &reg->fields[i];

		if (low == field->low && high == field->high)
			return field;
	}

	return NULL;
}

static const struct field_desc *find_field_by_name(const struct reg_desc *reg,
	const char *name)
{
	for (unsigned i = 0; i < reg->num_fields; ++i) {
		const struct field_desc *field = &reg->fields[i];

		if (strcmp(name, field->name) == 0)
			return field;
	}

	return NULL;
}

static void readwriteprint(const struct rwmem_op *op,
	uint64_t paddr, void *vaddr,
	uint64_t offset,
	unsigned width,
		const struct reg_desc *reg)
{
	if (reg)
		printf("%s ", reg->name);

	printf("%#" PRIx64 " ", paddr);
	if (offset != paddr)
		printf("(+%#" PRIx64 ") ", offset);

	uint64_t oldval = 0, newval = 0;

	if (!rwmem_opts.write_only) {
		oldval = readmem(vaddr, width);

		printf("= %0#*" PRIx64 " ", width / 4 + 2, oldval);

		newval = oldval;
	}

	if (op->value_valid) {
		uint64_t v;

		if (op->field_valid) {
			v = oldval;
			v &= ~GENMASK(op->high, op->low);
			v |= op->value << op->low;
		} else {
			v = op->value;
		}

		printf(":= %0#*" PRIx64 " ", width / 4 + 2, v);

		fflush(stdout);

		writemem(vaddr, width, v);

		newval = v;

		if (!rwmem_opts.write_only) {
			newval = readmem(vaddr, width);

			printf("-> %0#*" PRIx64 " ", width / 4 + 2, newval);
		}
	}

	printf("\n");

	if (!op->field_valid) {
		if (reg) {
			for (unsigned i = 0; i < reg->num_fields; ++i) {
				const struct field_desc *fd = &reg->fields[i];
				print_field(fd->high, fd->low, reg, fd,
					newval, oldval, op);
			}
		}
	} else {
		const struct field_desc *fd = NULL;

		if (reg)
			fd = find_field_by_pos(reg, op->high, op->low);

		print_field(op->high, op->low, reg, fd, newval, oldval,
			op);
	}
}

static void parse_op(const struct rwmem_opts_arg *arg, struct rwmem_op *op,
	const char *regfile)
{
	struct reg_desc *reg = NULL;

	/* Parse address */

	{
		char *endptr;
		op->address = strtoull(arg->address, &endptr, 0);
		if (*endptr != 0) {
			if (!regfile)
				myerr("Invalid address '%s'", arg->address);

			reg = find_reg_by_name(regfile, arg->address);
			op->address = reg->offset;
		}
	}

	/* Parse range */

	if (arg->range) {
		int r = parse_u64(arg->range, &op->range);
		ERR_ON(r, "Invalid range '%s'", arg->range);

		if (!arg->range_is_offset) {
			if (op->range <= op->address)
				myerr("range '%s' is <= 0", arg->range);
			op->range = op->range - op->address;
		}

		op->range_valid = true;
	} else {
		if (reg)
			op->range = reg->width / 8;
		else
			op->range = rwmem_opts.regsize / 8;
	}

	/* Parse field */

	if (arg->field) {
		unsigned fl, fh;
		char *endptr;

		bool ok = false;

		if (sscanf(arg->field, "%i:%i", &fh, &fl) == 2)
			ok = true;

		if (!ok) {
			fl = fh = strtoull(arg->field, &endptr, 0);
			if (*endptr == 0)
				ok = true;
		}

		if (!ok) {
			const struct field_desc *field;

			field = find_field_by_name(reg, arg->field);

			if (field) {
				fl = field->low;
				fh = field->high;
				ok = true;
			}
		}

		if (!ok)
			myerr("Field not found '%s'", arg->field);

		if (fl >= rwmem_opts.regsize ||
				fh >= rwmem_opts.regsize)
			myerr("Field bits higher than register size");

		op->low = fl;
		op->high = fh;
		op->field_valid = true;
	}

	/* Parse value */

	if (arg->value) {
		uint64_t value;
		int r = parse_u64(arg->value, &value);
		ERR_ON(r, "Invalid value '%s'", arg->value);

		uint64_t regmask = ~0ULL >> (64 - rwmem_opts.regsize);

		if (value & ~regmask)
			myerr("Value does not fit into the register size");

		if (op->field_valid &&
				(value & ~GENMASK(op->high - op->low, 0)))
			myerr("Value does not fit into the field");

		op->value = value;
		op->value_valid = true;
	}
}

static void do_op(int fd, uint64_t base, const struct rwmem_op *op,
	const char *regfile)
{
	const unsigned pagesize = sysconf(_SC_PAGESIZE);
	const unsigned pagemask = pagesize - 1;

	uint64_t paddr = base + op->address;
	off_t pa_offset = paddr & ~pagemask;
	size_t len = op->range + paddr - pa_offset;

	/*
	printf("range %#" PRIx64 " paddr %#" PRIx64 " pa_offset 0x%lx, len 0x%zx\n",
		op->range, paddr, pa_offset, len);
	*/

	void *mmap_base = mmap(0, len,
			op->value_valid ? PROT_WRITE : PROT_READ,
			MAP_SHARED, fd, pa_offset);

	if (mmap_base == MAP_FAILED)
		myerr2("failed to mmap");

	void *vaddr = (uint8_t* )mmap_base + (paddr & pagemask);

	uint64_t offset = op->address;
	uint64_t end_offset = offset + op->range;

	while (offset < end_offset) {
		struct reg_desc *reg = NULL;

		if (regfile)
			reg = find_reg_by_address(regfile, offset);

		unsigned access_width = reg ? reg->width : rwmem_opts.regsize;

		readwriteprint(op, paddr, vaddr, offset, access_width,
			reg);

		offset += access_width / 8;
	}

	if (munmap(mmap_base, pagesize) == -1)
		myerr2("failed to munmap");
}

int main(int argc, char **argv)
{
	uint64_t base;
	const char *regfile;

	parse_cmdline(argc, argv);

	/* Parse base */

	base = 0;
	regfile = NULL;

	if (rwmem_opts.base)
		parse_base(rwmem_opts.aliasfile, rwmem_opts.base, &base, &regfile);

	if (rwmem_opts.regfile)
		regfile = rwmem_opts.regfile;

	int num_ops = rwmem_opts.num_args;

	bool read_only = true;

	struct rwmem_op *ops = malloc(sizeof(struct rwmem_op) * num_ops);
	memset(ops, 0, sizeof(struct rwmem_op) * num_ops);
	for (int i = 0; i < num_ops; ++i) {
		const struct rwmem_opts_arg *arg = &rwmem_opts.args[i];
		struct rwmem_op *op = &ops[i];

		parse_op(arg, op, regfile);

		if (op->value_valid)
			read_only = false;
	}

	/* Open the file and mmap */

	int fd = open(rwmem_opts.filename,
			(read_only ? O_RDONLY : O_RDWR) | O_SYNC);

	if (fd == -1)
		myerr2("Failed to open file '%s'", rwmem_opts.filename);

	for (int i = 0; i < num_ops; ++i) {
		struct rwmem_op *op = &ops[i];

		do_op(fd, base, op, regfile);
	}

	close(fd);

	return 0;
}
