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
#include "helpers.h"
#include "regs.h"

using namespace std;

#define printq(format...) \
	do { \
		if (rwmem_opts.print_mode != PrintMode::Quiet) \
		printf(format); \
	} while(0)

static void print_field(unsigned high, unsigned low,
			Register* reg, Field* fd,
			uint64_t newval, uint64_t userval, uint64_t oldval,
			const RwmemOp *op)
{
	uint64_t mask = GENMASK(high, low);

	newval = (newval & mask) >> low;
	oldval = (oldval & mask) >> low;
	userval = (userval & mask) >> low;

	if (fd)
		printq("\t%-*s ", reg->max_field_name_len(), fd->name());
	else
		printq("\t");

	if (high == low)
		printq("   %-2d = ", low);
	else
		printq("%2d:%-2d = ", high, low);

	unsigned access_width = reg ? reg->size() : rwmem_opts.regsize;

	if (rwmem_opts.write_mode != WriteMode::Write)
		printq("%-#*" PRIx64 " ", access_width / 4 + 2, oldval);

	if (op->value_valid) {
		printq(":= %-#*" PRIx64 " ", access_width / 4 + 2, userval);
		if (rwmem_opts.write_mode == WriteMode::ReadWriteRead)
			printq("-> %-#*" PRIx64 " ", access_width / 4 + 2, newval);
	}

	printq("\n");
}

static void readwriteprint(const RwmemOp *op,
			   uint64_t paddr, void *vaddr,
			   uint64_t offset,
			   unsigned width,
			   Register* reg)
{
	if (reg)
		printq("%s ", reg->name());

	printq("%#" PRIx64 " ", paddr);
	if (offset != paddr)
		printq("(+%#" PRIx64 ") ", offset);

	uint64_t oldval, userval, newval;

	oldval = userval = newval = 0;

	if (rwmem_opts.write_mode != WriteMode::Write) {
		oldval = readmem(vaddr, width);

		printq("= %0#*" PRIx64 " ", width / 4 + 2, oldval);

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

		printq(":= %0#*" PRIx64 " ", width / 4 + 2, v);

		fflush(stdout);

		writemem(vaddr, width, v);

		newval = v;
		userval = v;

		if (rwmem_opts.write_mode == WriteMode::ReadWriteRead) {
			newval = readmem(vaddr, width);

			printq("-> %0#*" PRIx64 " ", width / 4 + 2, newval);
		}
	}

	printq("\n");

	if (rwmem_opts.print_mode != PrintMode::RegFields)
		return;

	if (!op->field_valid) {
		if (reg) {
			for (unsigned i = 0; i < reg->num_fields(); ++i) {
				unique_ptr<Field> field = reg->field_by_index(i);
				print_field(field->high(), field->low(), reg, field.get(),
					    newval, userval, oldval, op);
			}
		}
	} else {
		unique_ptr<Field> field = nullptr;

		if (reg)
			field = reg->find_field(op->high, op->low);

		print_field(op->high, op->low, reg, field.get(), newval, userval, oldval,
			    op);
	}
}

static int readprint_raw(void *vaddr, unsigned width)
{
	uint64_t v = readmem(vaddr, width);

	width /= 8;

	return write(STDOUT_FILENO, &v, width);
}

static void parse_op(const RwmemOptsArg *arg, RwmemOp *op,
		     const RegFile* regfile)
{
	unique_ptr<Register> reg = nullptr;

	/* Parse address */

	if (parse_u64(arg->address, &op->address) != 0) {
		if (!regfile)
			ERR("Invalid address '%s'", arg->address);

		reg = regfile->find_reg(arg->address);

		ERR_ON(!reg, "Register not found '%s'", arg->address);
		op->address = reg->offset();
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
			op->range = reg->size() / 8;
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

		if (!ok && reg) {
			unique_ptr<Field> field = reg->find_field(arg->field);

			if (field) {
				fl = field->low();
				fh = field->high();
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

static void do_op(int fd, uint64_t base, const RwmemOp *op,
		  const RegFile* regfile)
{
	const unsigned pagesize = sysconf(_SC_PAGESIZE);
	const unsigned pagemask = pagesize - 1;

	uint64_t paddr = base + op->address;
	off_t mmap_offset = paddr & ~pagemask;
	size_t mmap_len = op->range + (paddr & pagemask);

	/*
	printf("range %#" PRIx64 " paddr %#" PRIx64 " pa_offset 0x%lx, len 0x%zx\n",
		op->range, paddr, mmap_offset, mmap_len);
	*/

	void *mmap_base = mmap(0, mmap_len,
			       op->value_valid ? PROT_WRITE : PROT_READ,
			       MAP_SHARED, fd, mmap_offset);

	if (mmap_base == MAP_FAILED)
		myerr2("failed to mmap");

	void *vaddr = (uint8_t* )mmap_base + (paddr & pagemask);

	uint64_t reg_offset = op->address;
	uint64_t end_reg_offset = reg_offset + op->range;

	while (reg_offset < end_reg_offset) {
		unique_ptr<Register> reg = nullptr;

		if (regfile)
			reg = regfile->find_reg(reg_offset);

		unsigned access_width = reg ? reg->size() : rwmem_opts.regsize;

		if (rwmem_opts.raw_output)
			readprint_raw(vaddr, access_width);
		else
			readwriteprint(op, paddr, vaddr, reg_offset, access_width, reg.get());

		paddr += access_width / 8;
		vaddr = (uint8_t*)vaddr + access_width / 8;
		reg_offset += access_width / 8;
	}

	if (munmap(mmap_base, pagesize) == -1)
		myerr2("failed to munmap");
}

int main(int argc, char **argv)
{
	uint64_t base;
	const char *regfilename;

	parse_cmdline(argc, argv);

	/* Parse base */

	base = 0;
	regfilename = NULL;

	if (rwmem_opts.regfile)
		regfilename = rwmem_opts.regfile;

	unique_ptr<RegFile> regfile = nullptr;

	if (regfilename)
		regfile = make_unique<RegFile>(regfilename);

	if (rwmem_opts.show_list) {
		ERR_ON(!regfile, "No regfile given");
		regfile->print(rwmem_opts.show_list_pattern);
		return 0;
	}

	unsigned num_ops = rwmem_opts.args.size();

	bool read_only = true;

	vector<RwmemOp> ops;
	ops.resize(num_ops);

	for (unsigned i = 0; i < num_ops; ++i) {
		const RwmemOptsArg *arg = &rwmem_opts.args[i];
		RwmemOp *op = &ops[i];

		parse_op(arg, op, regfile.get());

		if (op->value_valid)
			read_only = false;
	}

	/* Open the file and mmap */

	int fd = open(rwmem_opts.filename,
		      (read_only ? O_RDONLY : O_RDWR) | O_SYNC);

	if (fd == -1)
		myerr2("Failed to open file '%s'", rwmem_opts.filename);

	for (unsigned i = 0; i < num_ops; ++i) {
		RwmemOp *op = &ops[i];

		do_op(fd, base, op, regfile.get());
	}

	close(fd);

	return 0;
}
