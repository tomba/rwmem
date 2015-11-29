#include <memory>
#include <cstdint>
#include <cstdlib>
#include <cstring>
#include <fcntl.h>
#include <unistd.h>
#include <sys/mman.h>
#include <inttypes.h>
#include <exception>

#include "regs.h"
#include "helpers.h"

using namespace std;

Register::Register(const RegFileData* rfd, const AddressBlockData* abd, const RegisterData* rd)
	: m_rfd(rfd), m_abd(abd), m_rd(rd)
{
}

const Field Register::field(uint32_t idx) const
{
	if (idx >= m_rd->num_fields())
		throw runtime_error("field idx too high");

	const FieldData* fd = &m_rfd->fields()[m_rd->fields_offset() + idx];
	return Field(m_rfd, fd);
}

unique_ptr<Field> Register::find_field(const string& name)
{
	for (unsigned i = 0; i < num_fields(); ++i) {
		Field f = field(i);
		if (strcmp(f.name(), name.c_str()) == 0)
			return make_unique<Field>(f);
	}

	return nullptr;
}

unique_ptr<Field> Register::find_field(uint8_t high, uint8_t low)
{
	for (unsigned i = 0; i < num_fields(); ++i) {
		Field f = field(i);
		if (low == f.low() && high == f.high())
			return make_unique<Field>(f);
	}

	return nullptr;
}


Register AddressBlock::reg(uint32_t idx) const
{
	if (idx >= m_abd->num_regs())
		throw runtime_error("register idx too high");

	const RegisterData* rd = &m_rfd->registers()[m_abd->regs_offset() + idx];
	return Register(m_rfd, m_abd, rd);
}

unique_ptr<Register> AddressBlock::find_reg(const string& name) const
{
	for (unsigned ridx = 0; ridx < num_regs(); ++ridx) {
		Register reg = this->reg(ridx);

		if (strcmp(reg.name(), name.c_str()) == 0)
			return make_unique<Register>(reg);
	}

	return nullptr;
}


RegFile::RegFile(const char* filename)
{
	int fd = open(filename, O_RDONLY);
	ERR_ON_ERRNO(fd < 0, "Open regfile '%s' failed", filename);

	off_t len = lseek(fd, (size_t)0, SEEK_END);
	lseek(fd, 0, SEEK_SET);

	void* data = mmap(NULL, len, PROT_READ, MAP_PRIVATE, fd, 0);
	ERR_ON_ERRNO(data == MAP_FAILED, "mmap regfile failed");

	m_rfd = (RegFileData*)data;
	m_size = len;
}

RegFile::~RegFile()
{
	munmap((void*)m_rfd, m_size);
}

AddressBlock RegFile::address_block(uint32_t idx) const
{
	if (idx >= m_rfd->num_blocks())
		throw runtime_error("address block idx too high");

	const AddressBlockData* abd = &m_rfd->blocks()[idx];
	return AddressBlock(m_rfd, abd);
}

unique_ptr<AddressBlock> RegFile::find_address_block(const string& name) const
{
	for (unsigned bidx = 0; bidx < num_blocks(); ++bidx) {
		const AddressBlock ab = address_block(bidx);

		if (strcmp(ab.name(), name.c_str()) == 0)
			return make_unique<AddressBlock>(ab);
	}

	return nullptr;
}

unique_ptr<Register> RegFile::find_reg(const string& name) const
{
	for (unsigned bidx = 0; bidx < num_blocks(); ++bidx) {
		const AddressBlock ab = address_block(bidx);

		for (unsigned ridx = 0; ridx < ab.num_regs(); ++ridx) {
			Register reg = ab.reg(ridx);

			if (strcmp(reg.name(), name.c_str()) == 0)
				return make_unique<Register>(reg);
		}
	}

	return nullptr;
}

unique_ptr<Register> RegFile::find_reg(uint64_t offset) const
{
	for (unsigned bidx = 0; bidx < num_blocks(); ++bidx) {
		const AddressBlock ab = address_block(bidx);

		if (offset < ab.offset())
			continue;

		if (offset >= ab.offset() + ab.size())
			continue;

		for (unsigned ridx = 0; ridx < ab.num_regs(); ++ridx) {
			Register reg = ab.reg(ridx);

			if (reg.offset() == offset - ab.offset())
				return make_unique<Register>(reg);
		}
	}

	return nullptr;
}

static void print_regfile(const RegFile& rf)
{
	printf("%s: total %u/%u/%u\n", rf.name(), rf.num_blocks(), rf.num_regs(), rf.num_fields());
}

static void print_address_block(const AddressBlock& ab)
{
	printf("  %s: %#" PRIx64 " %#" PRIx64 ", regs %u\n", ab.name(), ab.offset(), ab.size(), ab.num_regs());
}

static void print_register(const Register& reg)
{
	printf("    %s: %#" PRIx64 " %#x, fields %u\n", reg.name(), reg.offset(), reg.size(), reg.num_fields());
}

static void print_field(const Field& field)
{
	printf("      %s: %u:%u\n", field.name(), field.high(), field.low());
}

static void print_all(const RegFile& rf)
{
	print_regfile(rf);

	for (unsigned bidx = 0; bidx < rf.num_blocks(); ++bidx) {
		AddressBlock ab = rf.address_block(bidx);
		print_address_block(ab);

		for (unsigned ridx = 0; ridx < ab.num_regs(); ++ridx) {
			Register reg = ab.reg(ridx);
			print_register(reg);

			for (unsigned fidx = 0; fidx < reg.num_fields(); ++fidx) {
				Field field = reg.field(fidx);
				print_field(field);
			}
		}
	}
}

static void print_pattern(const RegFile& rf, const string& pattern)
{
	bool regfile_printed = false;

	for (unsigned bidx = 0; bidx < rf.num_blocks(); ++bidx) {
		AddressBlock ab = rf.address_block(bidx);

		bool block_printed = false;

		for (unsigned ridx = 0; ridx < ab.num_regs(); ++ridx) {
			Register reg = ab.reg(ridx);

			if (strcasestr(reg.name(), pattern.c_str()) == NULL)
				continue;

			if (!regfile_printed) {
				print_regfile(rf);
				regfile_printed = true;
			}

			if (!block_printed) {
				print_address_block(ab);
				block_printed = true;
			}

			print_register(reg);

			for (unsigned fidx = 0; fidx < reg.num_fields(); ++fidx) {
				Field field = reg.field(fidx);

				print_field(field);
			}
		}
	}
}

void RegFile::print(const string& pattern)
{
	if (pattern.empty())
		print_all(*this);
	else
		print_pattern(*this, pattern);
}
