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

#include <cstdio>
#include <unistd.h>

#include "rwmem.h"
#include "helpers.h"
#include "regs.h"
#include "i2ctarget.h"

#include <fnmatch.h>
#include <limits>

using namespace std;

static vector<const RegisterData*> match_registers(const RegisterFileData* rfd, const RegisterBlockData* rbd, const string& pattern)
{
	vector<const RegisterData*> matches;

	for (unsigned ridx = 0; ridx < rbd->num_regs(); ++ridx) {
		const RegisterData* rd = rbd->at(rfd, ridx);

		if (fnmatch(pattern.c_str(), rd->name(rfd), FNM_CASEFOLD) != 0)
			continue;

		matches.push_back(rd);
	}

	return matches;
}

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

		RegMatch m{};
		m.rbd = rbd;

		if (r_pat.empty()) {
			matches.push_back(m);
			continue;
		}

		for (unsigned ridx = 0; ridx < rbd->num_regs(); ++ridx) {
			const RegisterData* rd = rbd->at(rfd, ridx);

			if (fnmatch(r_pat.c_str(), rd->name(rfd), FNM_CASEFOLD) != 0)
				continue;

			m.rd = rd;

			if (f_pat.empty()) {
				matches.push_back(m);
				continue;
			}

			for (unsigned fidx = 0; fidx < rd->num_fields(); ++fidx) {
				const FieldData* fd = rd->at(rfd, fidx);

				if (fnmatch(f_pat.c_str(), fd->name(rfd), FNM_CASEFOLD) != 0)
					continue;

				m.fd = fd;
				matches.push_back(m);
			}
		}
	}

	return matches;
}

static void print_regfile_all(const RegisterFileData* rfd)
{
	fmt::print("{}: total {}/{}/{}\n",
		   rfd->name(), rfd->num_blocks(), rfd->num_regs(), rfd->num_fields());

	for (unsigned bidx = 0; bidx < rfd->num_blocks(); ++bidx) {
		const RegisterBlockData* rbd = rfd->at(bidx);

		fmt::print("  {}: {:#x} {:#x}, regs {}, endianness: {}/{}\n",
			   rbd->name(rfd), rbd->offset(), rbd->size(), rbd->num_regs(),
			   (unsigned)rbd->addr_endianness(), (unsigned)rbd->data_endianness());

		for (unsigned ridx = 0; ridx < rbd->num_regs(); ++ridx) {
			const RegisterData* rd = rbd->at(rfd, ridx);

			fmt::print("    {}: {:#x}, fields {}\n",
				   rd->name(rfd), rd->offset(), rd->num_fields());

			if (rwmem_opts.print_mode != PrintMode::RegFields)
				continue;

			for (unsigned fidx = 0; fidx < rd->num_fields(); ++fidx) {
				const FieldData* fd = rd->at(rfd, fidx);

				fmt::print("      {}: {}:{}\n",
					   fd->name(rfd), fd->high(), fd->low());
			}
		}
	}
}

static void print_field(unsigned high, unsigned low,
			const RegisterFileData* rfd,
			const FieldData* fd,
			uint64_t newval, uint64_t userval, uint64_t oldval,
			const RwmemOp& op,
			const RwmemFormatting& formatting)
{
	uint64_t mask = GENMASK(high, low);

	newval = (newval & mask) >> low;
	oldval = (oldval & mask) >> low;
	userval = (userval & mask) >> low;

	rwmem_printq("  ");

	if (fd)
		rwmem_printq("{:<{}} ", fd->name(rfd), formatting.name_chars);

	if (high == low)
		rwmem_printq("   {:<2} = ", low);
	else
		rwmem_printq("{:2}:{:<2} = ", high, low);

	if (rwmem_opts.write_mode != WriteMode::Write) {
		switch (rwmem_opts.number_print_mode) {
		case NumberPrintMode::Dec:
			rwmem_printq("{:<{}} ", oldval, formatting.value_chars);
			break;
		default:
		case NumberPrintMode::Hex:
			rwmem_printq("{:#0{}x} ", oldval, formatting.value_chars);
			break;
		case NumberPrintMode::Bin:
			rwmem_printq("{:#0{}b} ", oldval, formatting.value_chars);
			break;
		}
	}

	if (op.value_valid) {
		switch (rwmem_opts.number_print_mode) {
		case NumberPrintMode::Dec:
			rwmem_printq(":= {:<{}} ", userval, formatting.value_chars);
			break;
		default:
		case NumberPrintMode::Hex:
			rwmem_printq(":= {:#0{}x} ", userval, formatting.value_chars);
			break;
		case NumberPrintMode::Bin:
			rwmem_printq(":= {:#0{}b} ", userval, formatting.value_chars);
			break;
		}

		if (rwmem_opts.write_mode == WriteMode::ReadWriteRead) {
			switch (rwmem_opts.number_print_mode) {
			case NumberPrintMode::Dec:
				rwmem_printq("-> {:<{}} ", newval, formatting.value_chars);
				break;
			default:
			case NumberPrintMode::Hex:
				rwmem_printq("-> {:#0{}x} ", newval, formatting.value_chars);
				break;
			case NumberPrintMode::Bin:
				rwmem_printq("-> {:#0{}b} ", newval, formatting.value_chars);
				break;
			}
		}
	}

	rwmem_printq("\n");
}

static void readwriteprint(const RwmemOp& op,
			   ITarget* mm,
			   uint64_t op_addr,
			   uint64_t paddr,
			   unsigned width,
			   const RegisterFileData* rfd,
			   const RegisterBlockData* rbd,
			   const RegisterData* rd,
			   const RwmemFormatting& formatting)
{
	if (rd) {
		string name = fmt::format("{}.{}", rbd->name(rfd), rd->name(rfd));
		rwmem_printq("{:<{}} ", name.c_str(), formatting.name_chars);
	}

	rwmem_printq("{:#0{}x} ", paddr, formatting.address_chars);
	rwmem_vprint("Accessing {:#0{}x}", paddr, formatting.address_chars);

	if (op_addr != paddr) {
		rwmem_printq("(+{:#0{}x}) ", op_addr, formatting.offset_chars);
		rwmem_vprint(" (+{:#{}x})", op_addr, formatting.offset_chars);
	}

	rwmem_vprint("\n");

	uint64_t oldval, userval, newval;

	oldval = userval = newval = 0;

	if (rwmem_opts.write_mode != WriteMode::Write) {
		oldval = mm->read(op_addr, width);

		switch (rwmem_opts.number_print_mode) {
		case NumberPrintMode::Dec:
			rwmem_printq("= {:{}}", oldval, formatting.value_chars);
			break;
		default:
		case NumberPrintMode::Hex:
			rwmem_printq("= {:#0{}x}", oldval, formatting.value_chars);
			break;
		case NumberPrintMode::Bin:
			rwmem_printq("= {:#0{}b}", oldval, formatting.value_chars);
			break;
		}

		newval = oldval;
	}

	if (op.value_valid) {
		uint64_t v;

		v = oldval;
		v &= ~GENMASK(op.high, op.low);
		v |= op.value << op.low;

		switch (rwmem_opts.number_print_mode) {
		case NumberPrintMode::Dec:
			rwmem_printq(" := {:{}}", v, formatting.value_chars);
			break;
		default:
		case NumberPrintMode::Hex:
			rwmem_printq(" := {:#0{}x}", v, formatting.value_chars);
			break;
		case NumberPrintMode::Bin:
			rwmem_printq(" := {:#0{}b}", v, formatting.value_chars);
			break;
		}

		fflush(stdout);

		mm->write(op_addr, width, v);

		newval = v;
		userval = v;

		if (rwmem_opts.write_mode == WriteMode::ReadWriteRead) {
			newval = mm->read(op_addr, width);

			switch (rwmem_opts.number_print_mode) {
			case NumberPrintMode::Dec:
				rwmem_printq(" -> {:{}}", newval, formatting.value_chars);
				break;
			default:
			case NumberPrintMode::Hex:
				rwmem_printq(" -> {:#0{}x}", newval, formatting.value_chars);
				break;
			case NumberPrintMode::Bin:
				rwmem_printq(" -> {:#0{}b}", newval, formatting.value_chars);
				break;
			}
		}
	}

	rwmem_printq("\n");

	if (rwmem_opts.print_mode != PrintMode::RegFields)
		return;

	if (rd) {
		if (op.custom_field) {
			const FieldData* fd = rd->find_field(rfd, op.high, op.low);

			print_field(op.high, op.low, rfd, fd,
				    newval, userval, oldval, op, formatting);
		} else {
			for (unsigned i = 0; i < rd->num_fields(); ++i) {
				const FieldData* fd = rd->at(rfd, i);

				if (fd->high() >= op.low && fd->low() <= op.high)
					print_field(fd->high(), fd->low(), rfd, fd,
						    newval, userval, oldval, op, formatting);
			}
		}
	} else {
		if (op.custom_field) {
			print_field(op.high, op.low, nullptr, nullptr, newval, userval, oldval,
				    op, formatting);
		}
	}
}

static int readprint_raw(ITarget* mm, uint64_t offset, unsigned size)
{
	uint64_t v = mm->read(offset, size);

	return write(STDOUT_FILENO, &v, size);
}

static RwmemOp parse_op(const string& arg_str, const RegisterFile* regfile)
{
	RwmemOptsArg arg;

	parse_arg(arg_str, &arg);

	RwmemOp op{};

	const RegisterFileData* rfd = nullptr;
	if (regfile)
		rfd = regfile->data();

	/* Parse address */

	// first register from the match
	const RegisterData* rd = nullptr;

	if (parse_u64(arg.address, &op.reg_offset) != 0) {
		ERR_ON(!rfd, "Invalid address '{}'", arg.address);

		vector<string> strs = split(arg.address, '.');

		ERR_ON(strs.size() > 2, "Invalid address '{}'", arg.address);

		// First try with str[0] meaning the reg block, if that fails
		// search all regblocks for the str[0] register.
		if (const RegisterBlockData* rbd = rfd->find_block(strs[0])) {
			op.rbd = rbd;

			if (strs.size() > 1) {
				op.rds = match_registers(rfd, rbd, strs[1]);
				ERR_ON(op.rds.empty(), "Failed to find register");
				rd = op.rds[0];
			} else {
				rd = rbd->at(rfd, 0);
				ERR_ON(!rd, "Failed to figure out first register");
			}
		} else if (strs.size() == 1) {
			for (uint32_t bidx = 0; bidx < rfd->num_blocks(); ++bidx) {
				const RegisterBlockData* rbd = rfd->at(bidx);
				const auto rds = match_registers(rfd, rbd, strs[0]);
				if (!rds.empty()) {
					op.rbd = rbd;
					op.rds = rds;
					break;
				}
			}

			ERR_ON(op.rds.empty(), "Failed to find reg by search");

			rd = op.rds[0];
			ERR_ON(!rd, "Failed to figure out first register");
		} else {
			ERR("Failed to find register block or register");
		}
	}

	/* Parse range */

	if (arg.range.size()) {
		int r = parse_u64(arg.range, &op.range);
		ERR_ON(r, "Invalid range '{}'", arg.range);

		if (!arg.range_is_offset) {
			ERR_ON(op.range <= op.reg_offset, "range '{}' is <= 0", arg.range);

			op.range = op.range - op.reg_offset;
		}
	} else {
		if (op.rbd)
			op.range = op.rbd->data_size();
		else
			op.range = rwmem_opts.data_size;
	}

	/* Parse field */

	if (arg.field.size()) {
		unsigned fl, fh;
		char* endptr;

		bool ok = false;

		if (sscanf(arg.field.c_str(), "%u:%u", &fh, &fl) == 2)
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

		ERR_ON(!ok, "Field not found '{}'", arg.field);

		ERR_ON(fl >= rwmem_opts.data_size * 8 || fh >= rwmem_opts.data_size * 8,
		       "Field bits higher than register size");

		op.custom_field = true;
		op.low = fl;
		op.high = fh;
	} else {
		op.custom_field = false;
		op.low = 0;
		op.high = rwmem_opts.data_size * 8 - 1;
	}

	/* Parse value */

	if (arg.value.size()) {
		uint64_t value;
		int r = parse_u64(arg.value, &value);
		ERR_ON(r, "Invalid value '{}'", arg.value);

		uint64_t regmask = ~0ULL >> (64 - rwmem_opts.data_size * 8);

		ERR_ON(value & ~regmask, "Value does not fit into the register size");

		ERR_ON(value & ~GENMASK(op.high - op.low, 0),
		       "Value does not fit into the field");

		op.value = value;
		op.value_valid = true;
	}

	return op;
}

static uint32_t print_chars_needed(uint32_t numbytes, NumberPrintMode mode)
{
	switch (mode) {
	default:
	case NumberPrintMode::Hex:
		return numbytes * 2 + 2; // for hex: 2 chars per byte and "0x"
	case NumberPrintMode::Dec:
		switch (numbytes) {
		case 1:
			return std::numeric_limits<uint8_t>::digits10 + 1;
		case 2:
			return std::numeric_limits<uint16_t>::digits10 + 1;
		case 4:
			return std::numeric_limits<uint32_t>::digits10 + 1;
		case 8:
			return std::numeric_limits<uint64_t>::digits10 + 1;
		default:
			FAIL("Bad num bytes");
		}
	case NumberPrintMode::Bin:
		return numbytes * 8 + 2; // for bin: 8 chars per byte and "0b"
	}
}

static void do_op_numeric(const RwmemOp& op, ITarget* mm)
{
	const uint64_t op_base = op.reg_offset;
	const uint64_t range = op.range;

	const uint8_t data_size = rwmem_opts.data_size;
	const uint8_t addr_size = rwmem_opts.address_size;

	rwmem_vprint("mmap offset={:x} length={:x}\n", op_base, range);

	mm->map(op_base, range, rwmem_opts.address_endianness, rwmem_opts.address_size,
		rwmem_opts.data_endianness, data_size,
	        op.value_valid ? MapMode::ReadWrite : MapMode::Read);

	RwmemFormatting formatting;
	formatting.name_chars = 30;
	formatting.address_chars = print_chars_needed(addr_size, NumberPrintMode::Hex);
	formatting.offset_chars = DIV_ROUND_UP(fls(range), 4);
	formatting.value_chars = print_chars_needed(data_size, rwmem_opts.number_print_mode);

	uint64_t op_offset = 0;

	while (op_offset < range) {
		if (rwmem_opts.raw_output)
			readprint_raw(mm, op_offset, data_size);
		else
			readwriteprint(op, mm, op_offset, op_base + op_offset, data_size, nullptr, nullptr, nullptr, formatting);

		op_offset += data_size;
	}
}

static void do_op_symbolic(const RwmemOp& op, const RegisterFile* regfile, ITarget* mm)
{
	const RegisterBlockData* rbd = op.rbd;

	const uint64_t rb_base = rbd->offset();
	const uint64_t rb_access_base = rwmem_opts.ignore_base ? 0 : rbd->offset();
	const uint64_t range = rbd->size();

	Endianness addr_endianness, data_endianness;
	uint8_t addr_size, data_size;

	if (rwmem_opts.user_address_size) {
		addr_endianness = rwmem_opts.address_endianness;
		addr_size = rwmem_opts.address_size;
	} else {
		addr_endianness = rbd->addr_endianness();
		addr_size = rbd->addr_size();
	}

	if (rwmem_opts.user_data_size) {
		data_endianness = rwmem_opts.data_endianness;
		data_size = rwmem_opts.data_size;
	} else {
		data_endianness = rbd->data_endianness();
		data_size = rbd->data_size();
	}

	rwmem_vprint("mmap offset={:x} length={:x}\n", rb_access_base, rbd->size());

	mm->map(rb_access_base, rbd->size(), addr_endianness, addr_size, data_endianness, data_size,
	        op.value_valid ? MapMode::ReadWrite : MapMode::Read);

	RwmemFormatting formatting;
	formatting.name_chars = 30;
	formatting.address_chars = print_chars_needed(addr_size, NumberPrintMode::Hex);
	formatting.offset_chars = DIV_ROUND_UP(fls(range), 4);
	formatting.value_chars = print_chars_needed(data_size, rwmem_opts.number_print_mode);

	const RegisterFileData* rfd = regfile->data();

	// Accessing addresses not defined in regfile may cause problems. So skip those.
	const bool skip_undefined_regs = true;

	if (op.rds.empty()) {
		uint64_t op_offset = 0;

		while (op_offset < range) {
			const RegisterData* rd = rbd->find_register(rfd, op_offset);

			if (!rd && skip_undefined_regs) {
				if (rwmem_opts.raw_output) {
					uint64_t v = 0;
					ssize_t l = write(STDOUT_FILENO, &v, data_size);
					ERR_ON_ERRNO(l == -1, "write failed");
				}

				op_offset += data_size;
				continue;
			}

			if (rwmem_opts.raw_output)
				readprint_raw(mm, rb_access_base + op_offset, data_size);
			else
				readwriteprint(op, mm, op_offset, rb_base + op_offset, data_size, rfd, rbd, rd, formatting);

			op_offset += data_size;
		}
	} else {
		for (const RegisterData* rd : op.rds) {
			uint64_t op_offset = rd->offset();

			if (rwmem_opts.raw_output)
				readprint_raw(mm, op_offset, data_size);
			else
				readwriteprint(op, mm, op_offset, rb_base + op_offset, data_size, rfd, rbd, rd, formatting);
		}
	}
}

static void do_op(const RwmemOp& op, const RegisterFile* regfile, ITarget* mm)
{
	if (op.rbd)
		do_op_symbolic(op, regfile, mm);
	else
		do_op_numeric(op, mm);
}

static void print_reg_matches(const RegisterFileData* rfd, const vector<RegMatch>& matches)
{
	for (const RegMatch& m : matches) {
		if (m.rd && m.fd)
			fmt::print("{}.{}:{}\n", m.rbd->name(rfd), m.rd->name(rfd), m.fd->name(rfd));
		else if (m.rd)
			fmt::print("{}.{}\n", m.rbd->name(rfd), m.rd->name(rfd));
		else
			fmt::print("{}\n", m.rbd->name(rfd));
	}
}

int main(int argc, char** argv)
{
	try {
		rwmem_ini.load(get_home() + "/.rwmem/rwmem.ini");
	} catch (...) {
	}

	load_opts_from_ini_pre();

	parse_cmdline(argc, argv);

	if (rwmem_opts.target_type == TargetType::None) {
		rwmem_opts.target_type = TargetType::MMap;
		rwmem_opts.mmap_target = "/dev/mem";

		detect_platform();
	}

	unique_ptr<RegisterFile> regfile = nullptr;

	if (!rwmem_opts.regfile.empty()) {
		string path = get_home() + "/.rwmem/" + rwmem_opts.regfile;

		if (!file_exists(path))
			path = rwmem_opts.regfile;

		rwmem_vprint("Reading regfile '{}'\n", path.c_str());
		regfile = make_unique<RegisterFile>(path.c_str());
	}

	if (rwmem_opts.show_list) {
		ERR_ON(!regfile, "No regfile given");

		if (rwmem_opts.args.empty()) {
			print_regfile_all(regfile->data());
		} else {
			for (const string& arg : rwmem_opts.args) {
				vector<RegMatch> m = match_reg(regfile->data(), arg);
				print_reg_matches(regfile->data(), m);
			}
		}

		return 0;
	}

	vector<RwmemOp> ops;

	for (const string& arg : rwmem_opts.args) {
		RwmemOp op = parse_op(arg, regfile.get());
		ops.push_back(op);
	}

	if (rwmem_opts.address_endianness == Endianness::Default)
		rwmem_opts.address_endianness = Endianness::Little;

	if (rwmem_opts.data_endianness == Endianness::Default)
		rwmem_opts.data_endianness = Endianness::Little;

	unique_ptr<ITarget> mm;

	switch (rwmem_opts.target_type) {
	case TargetType::MMap: {
		string file = rwmem_opts.mmap_target;
		if (file.empty())
			file = "/dev/mem";

		mm = make_unique<MMapTarget>(file);
		break;
	}

	case TargetType::I2C: {
		vector<string> strs = split(rwmem_opts.i2c_target, ':');
		ERR_ON(strs.size() != 2, "bad i2c parameter");

		int r;
		uint64_t bus, addr;

		r = parse_u64(strs[0], &bus);
		ERR_ON(r, "failed to parse i2c bus");

		r = parse_u64(strs[1], &addr);
		ERR_ON(r, "failed to parse i2c address");

		mm = make_unique<I2CTarget>(bus, addr);
		break;
	}

	default:
		FAIL("bad target type");
	}

	for (const RwmemOp& op : ops)
		do_op(op, regfile.get(), mm.get());

	return 0;
}
