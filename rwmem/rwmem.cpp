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

#include <stdio.h>
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
			Field* field,
			uint64_t newval, uint64_t userval, uint64_t oldval,
			const RwmemOp& op,
			const RwmemFormatting& formatting)
{
	uint64_t mask = GENMASK(high, low);

	newval = (newval & mask) >> low;
	oldval = (oldval & mask) >> low;
	userval = (userval & mask) >> low;

	printq("  ");

	if (field)
		printq("%-*s ", formatting.name_chars, field->name());

	if (high == low)
		printq("   %-2d = ", low);
	else
		printq("%2d:%-2d = ", high, low);

	if (rwmem_opts.write_mode != WriteMode::Write)
		printq("0x%-*" PRIx64 " ", formatting.value_chars, oldval);

	if (op.value_valid) {
		printq(":= 0x%-*" PRIx64 " ", formatting.value_chars, userval);
		if (rwmem_opts.write_mode == WriteMode::ReadWriteRead)
			printq("-> 0x%-*" PRIx64 " ", formatting.value_chars, newval);
	}

	printq("\n");
}

static void readwriteprint(const RwmemOp& op,
			   uint64_t paddr, void *vaddr,
			   uint64_t offset,
			   unsigned width,
			   Register* reg,
			   const RwmemFormatting& formatting)
{
	if (reg)
		printq("%-*s ", formatting.name_chars, reg->name());

	printq("0x%0*" PRIx64 " ", formatting.address_chars, paddr);

	if (offset != paddr)
		printq("(+0x%0*" PRIx64 ") ", formatting.offset_chars, offset);

	uint64_t oldval, userval, newval;

	oldval = userval = newval = 0;

	if (rwmem_opts.write_mode != WriteMode::Write) {
		oldval = readmem(vaddr, width);

		printq("= 0x%0*" PRIx64 " ", formatting.value_chars, oldval);

		newval = oldval;
	}

	if (op.value_valid) {
		uint64_t v;

		v = oldval;
		v &= ~GENMASK(op.high, op.low);
		v |= op.value << op.low;

		printq(":= 0x%0*" PRIx64 " ", formatting.value_chars, v);

		fflush(stdout);

		writemem(vaddr, width, v);

		newval = v;
		userval = v;

		if (rwmem_opts.write_mode == WriteMode::ReadWriteRead) {
			newval = readmem(vaddr, width);

			printq("-> 0x%0*" PRIx64 " ", formatting.value_chars, newval);
		}
	}

	printq("\n");

	if (rwmem_opts.print_mode != PrintMode::RegFields)
		return;

	if (reg) {
		for (unsigned i = 0; i < reg->num_fields(); ++i) {
			Field field = reg->at(i);

			if (field.high() >= op.low && field.low() <= op.high)
				print_field(field.high(), field.low(), &field,
					    newval, userval, oldval, op, formatting);
		}
	} else {
		print_field(op.high, op.low, nullptr, newval, userval, oldval,
			    op, formatting);
	}
}

static int readprint_raw(void *vaddr, unsigned size)
{
	uint64_t v = readmem(vaddr, size);

	return write(STDOUT_FILENO, &v, size);
}

static RwmemOp parse_op(const RwmemOptsArg& arg, const RegisterFile* regfile)
{
	RwmemOp op { };

	const RegisterFileData* rfd = nullptr;
	if (regfile)
		rfd = regfile->data();

	/* Parse register block */

	const RegisterBlockData* rbd = nullptr;

	if (arg.register_block.size()) {
		ERR_ON(!rfd, "Invalid register block '%s'", arg.register_block.c_str());

		rbd = rfd->find_block(arg.register_block);
		ERR_ON(!rbd, "Invalid register block '%s'", arg.register_block.c_str());

		op.regblock_offset = rbd->offset();
	}

	/* Parse address */

	const RegisterData* rd = nullptr;

	if (parse_u64(arg.address, &op.reg_offset) != 0) {
		ERR_ON(!rfd, "Invalid address '%s'", arg.address.c_str());

		if (rbd && arg.address == "*") {
			op.reg_offset = 0;
		} else {
			if (rbd)
				rd = rbd->find_register(rfd, arg.address);
			else
				rd = rfd->find_register(arg.address, &rbd);

			ERR_ON(!rd, "Register not found '%s'", arg.address.c_str());

			op.reg_offset = rd->offset();
			op.regblock_offset = rbd->offset();
		}
	}

	/* Parse range */

	if (arg.range.size()) {
		if (rbd && arg.range == "*") {
			op.range = rbd->size();
		} else {
			int r = parse_u64(arg.range, &op.range);
			ERR_ON(r, "Invalid range '%s'", arg.range.c_str());

			if (!arg.range_is_offset) {
				ERR_ON(op.range <= op.reg_offset, "range '%s' is <= 0", arg.range.c_str());

				op.range = op.range - op.reg_offset;
			}
		}
	} else {
		if (rd)
			op.range = rd->size();
		else
			op.range = rwmem_opts.regsize;
	}

	/* Parse field */

	if (arg.field.size()) {
		unsigned fl, fh;
		char *endptr;

		bool ok = false;

		if (sscanf(arg.field.c_str(), "%i:%i", &fh, &fl) == 2)
			ok = true;

		if (!ok) {
			fl = fh = strtoull(arg.field.c_str(), &endptr, 0);
			if (*endptr == 0)
				ok = true;
		}

		if (!ok && rd) {
			const FieldData* fd = rd->find_field(rfd, arg.field);
			if (fd) {
				fl = fd->low();
				fh = fd->high();
				ok = true;
			}
		}

		ERR_ON(!ok, "Field not found '%s'", arg.field.c_str());

		ERR_ON(fl >= rwmem_opts.regsize * 8 || fh >= rwmem_opts.regsize * 8,
		       "Field bits higher than register size");

		op.low = fl;
		op.high = fh;
	} else {
		op.low = 0;
		op.high = rwmem_opts.regsize * 8 - 1;
	}

	/* Parse value */

	if (arg.value.size()) {
		uint64_t value;
		int r = parse_u64(arg.value, &value);
		ERR_ON(r, "Invalid value '%s'", arg.value.c_str());

		uint64_t regmask = ~0ULL >> (64 - rwmem_opts.regsize * 8);

		ERR_ON(value & ~regmask, "Value does not fit into the register size");

		ERR_ON(value & ~GENMASK(op.high - op.low, 0),
		       "Value does not fit into the field");

		op.value = value;
		op.value_valid = true;
	}

	return op;
}

static void do_op(const string& filename, const RwmemOp& op, const RegisterFile* regfile)
{
	bool read_only = !op.value_valid;

	const uint64_t file_base = (rwmem_opts.ignore_base ? 0 : op.regblock_offset) + op.reg_offset;

	MemMap mm(filename, file_base, op.range, read_only);

	const uint64_t regfile_base = op.regblock_offset + op.reg_offset;
	const uint64_t reg_base = op.reg_offset;

	RwmemFormatting formatting;

	formatting.name_chars = 30;
	formatting.address_chars = file_base > 0xffffffff ? 16 : 8;
	formatting.offset_chars = DIV_ROUND_UP(fls(op.range), 4);
	formatting.value_chars = rwmem_opts.regsize * 2;

	uint64_t offset = 0;

	while (offset < op.range) {
		unique_ptr<Register> reg = nullptr;

		if (regfile) {
			reg = regfile->find_register(regfile_base + offset);

			if (rwmem_opts.print_known_regs && !reg) {
				offset += rwmem_opts.regsize;
				continue;
			}
		}

		unsigned access_size = reg ? reg->size() : rwmem_opts.regsize;

		void* va = (uint8_t*)mm.vaddr() + offset;

		if (rwmem_opts.raw_output)
			readprint_raw(va, access_size);
		else
			readwriteprint(op, file_base + offset, va, reg_base + offset, access_size, reg.get(), formatting);

		offset += access_size;
	}
}

int main(int argc, char **argv)
{
	try {
		rwmem_ini.load(string(getenv("HOME")) + "/.rwmem/rwmem.ini");
		load_opts_from_ini();
	} catch(...) {
	}

	parse_cmdline(argc, argv);

	unique_ptr<RegisterFile> regfile = nullptr;

	if (!rwmem_opts.regfile.empty()) {
		vprint("Reading regfile '%s'\n", rwmem_opts.regfile.c_str());
		regfile = make_unique<RegisterFile>(rwmem_opts.regfile.c_str());
	}

	if (rwmem_opts.show_list) {
		ERR_ON(!regfile, "No regfile given");
		regfile->print(rwmem_opts.show_list_pattern);
		return 0;
	}

	RwmemOp op = parse_op(rwmem_opts.arg, regfile.get());

	do_op(rwmem_opts.filename, op, regfile.get());

	return 0;
}
