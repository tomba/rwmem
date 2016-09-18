/**
 * Copyright 2013-2016 Tomi Valkeinen
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
#include "i2cmap.h"

#include <fnmatch.h>

using namespace std;

#define printq(format...) \
	do { \
	if (rwmem_opts.print_mode != PrintMode::Quiet) \
	printf(format); \
	} while(0)

struct RegMatch
{
	const RegisterBlockData* rbd;
	const RegisterData* rd;
	const FieldData* fd;
};

static vector<RegMatch> match_reg(const RegisterFileData* rfd, const string& pattern)
{
	string rb_pat;
	string r_pat;
	string f_pat;

	vector<string> strs = split(pattern, '.');

	rb_pat = strs[0];

	if (strs.size() > 1) {
		strs = split(strs[1], ':');

		r_pat = strs[0];

		if (strs.size() > 1) {
			f_pat = strs[1];
		}
	}

	vector<RegMatch> matches;

	for (unsigned bidx = 0; bidx < rfd->num_blocks(); ++bidx) {
		const RegisterBlockData* rbd = rfd->at(bidx);

		if (fnmatch(rb_pat.c_str(), rbd->name(rfd), FNM_CASEFOLD) != 0)
			continue;

		if (r_pat.empty()) {
			RegMatch m { };
			m.rbd = rbd;
			matches.push_back(m);
			continue;
		}

		for (unsigned ridx = 0; ridx < rbd->num_regs(); ++ridx) {
			const RegisterData* rd = rbd->at(rfd, ridx);

			if (fnmatch(r_pat.c_str(), rd->name(rfd), FNM_CASEFOLD) != 0)
				continue;

			if (f_pat.empty()) {
				RegMatch m { };
				m.rbd = rbd;
				m.rd = rd;
				matches.push_back(m);
				continue;
			}

			for (unsigned fidx = 0; fidx < rd->num_fields(); ++fidx) {
				const FieldData* fd = rd->at(rfd, fidx);

				if (fnmatch(f_pat.c_str(), fd->name(rfd), FNM_CASEFOLD) != 0)
					continue;

				RegMatch m { };
				m.rbd = rbd;
				m.rd = rd;
				m.fd = fd;
				matches.push_back(m);
			}
		}
	}

	return matches;
}

static void print_regfile_all(const RegisterFileData* rfd)
{
	printf("%s: total %u/%u/%u\n",
	       rfd->name(), rfd->num_blocks(), rfd->num_regs(), rfd->num_fields());

	for (unsigned bidx = 0; bidx < rfd->num_blocks(); ++bidx) {
		const RegisterBlockData* rbd = rfd->at(bidx);

		printf("  %s: %#" PRIx64 " %#" PRIx64 ", regs %u\n",
		       rbd->name(rfd), rbd->offset(), rbd->size(), rbd->num_regs());

		for (unsigned ridx = 0; ridx < rbd->num_regs(); ++ridx) {
			const RegisterData* rd = rbd->at(rfd, ridx);

			printf("    %s: %#" PRIx64 " %#x, fields %u\n",
			       rd->name(rfd), rd->offset(), rd->size(), rd->num_fields());

			for (unsigned fidx = 0; fidx < rd->num_fields(); ++fidx) {
				const FieldData* fd = rd->at(rfd, fidx);

				printf("      %s: %u:%u\n",
				       fd->name(rfd), fd->high(), fd->low());
			}
		}
	}
}

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
			   IMap* mm,
			   uint64_t op_addr,
			   uint64_t paddr,
			   unsigned width,
			   Register* reg,
			   const RwmemFormatting& formatting)
{
	if (reg)
		printq("%-*s ", formatting.name_chars, reg->name());

	printq("0x%0*" PRIx64 " ", formatting.address_chars, paddr);

	if (op_addr != paddr)
		printq("(+0x%0*" PRIx64 ") ", formatting.offset_chars, op_addr);

	uint64_t oldval, userval, newval;

	oldval = userval = newval = 0;

	if (rwmem_opts.write_mode != WriteMode::Write) {
		oldval = mm->read(op_addr, width);

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

		mm->write(op_addr, width, v);

		newval = v;
		userval = v;

		if (rwmem_opts.write_mode == WriteMode::ReadWriteRead) {
			newval = mm->read(op_addr, width);

			printq("-> 0x%0*" PRIx64 " ", formatting.value_chars, newval);
		}
	}

	printq("\n");

	if (rwmem_opts.print_mode != PrintMode::RegFields)
		return;

	if (reg) {
		if (op.custom_field) {
			unique_ptr<Field> field = reg->find_field(op.high, op.low);

			print_field(op.high, op.low, field.get(),
				    newval, userval, oldval, op, formatting);
		} else {
			for (unsigned i = 0; i < reg->num_fields(); ++i) {
				Field field = reg->at(i);

				if (field.high() >= op.low && field.low() <= op.high)
					print_field(field.high(), field.low(), &field,
						    newval, userval, oldval, op, formatting);
			}
		}
	} else {
		if (op.custom_field) {
			print_field(op.high, op.low, nullptr, newval, userval, oldval,
				    op, formatting);
		}
	}
}

static int readprint_raw(IMap* mm, uint64_t offset, unsigned size)
{
	uint64_t v = mm->read(offset, size);

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

		op.custom_field = true;
		op.low = fl;
		op.high = fh;
	} else {
		op.custom_field = false;
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
	vprint("do_op(%lx.%lx+%lx)\n", op.regblock_offset, op.reg_offset, op.range);

	bool read_only = !op.value_valid;

	// address to access
	const uint64_t op_base = (rwmem_opts.ignore_base ? 0 : op.regblock_offset) + op.reg_offset;

	// address in the register file
	const uint64_t regfile_base = op.regblock_offset + op.reg_offset;

	unique_ptr<IMap> mm;

	if (rwmem_opts.i2c_mode)
		mm = make_unique<I2CMap>(rwmem_opts.i2c_bus, rwmem_opts.i2c_addr);
	else
		mm = make_unique<MemMap>(filename, op_base, op.range, read_only);

	RwmemFormatting formatting;

	formatting.name_chars = 30;
	formatting.address_chars = op_base > 0xffffffff ? 16 : 8;
	formatting.offset_chars = DIV_ROUND_UP(fls(op.range), 4);
	formatting.value_chars = rwmem_opts.regsize * 2;

	uint64_t op_offset = 0;

	while (op_offset < op.range) {
		unique_ptr<Register> reg = nullptr;

		if (regfile) {
			reg = regfile->find_register(regfile_base + op_offset);

			if (rwmem_opts.print_known_regs && !reg) {
				op_offset += rwmem_opts.regsize;
				continue;
			}
		}

		unsigned access_size = reg ? reg->size() : rwmem_opts.regsize;

		if (rwmem_opts.raw_output)
			readprint_raw(mm.get(), op_base + op_offset, access_size);
		else
			readwriteprint(op, mm.get(), op_base + op_offset, regfile_base + op_offset, access_size, reg.get(), formatting);

		op_offset += access_size;
	}
}

static void print_reg_matches(const RegisterFileData* rfd, const vector<RegMatch>& matches)
{
	for (const RegMatch& m : matches) {
		if (m.rd && m.fd)
			printf("%s.%s:%s\n", m.rbd->name(rfd), m.rd->name(rfd), m.fd->name(rfd));
		else if (m.rd)
			printf("%s.%s\n", m.rbd->name(rfd), m.rd->name(rfd));
		else
			printf("%s\n", m.rbd->name(rfd));
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

		if (rwmem_opts.pattern.empty()) {
			print_regfile_all(regfile->data());
		} else {
			vector<RegMatch> m = match_reg(regfile->data(), rwmem_opts.pattern);

			print_reg_matches(regfile->data(), m);
		}

		return 0;
	}

	RwmemOp op = parse_op(rwmem_opts.arg, regfile.get());

	do_op(rwmem_opts.filename, op, regfile.get());

	return 0;
}
