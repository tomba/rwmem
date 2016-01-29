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

Register::Register(const RegFileData* rfd, const RegisterBlockData* rbd, const RegisterData* rd)
	: m_rfd(rfd), m_rbd(rbd), m_rd(rd)
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

uint32_t Register::get_max_field_name_len()
{
	if (m_max_field_name_len)
		return m_max_field_name_len;

	uint32_t max = 0;

	for (unsigned i = 0; i < num_fields(); ++i) {
		Field f = field(i);
		uint32_t len = strlen(f.name());
		if (len > max)
			max = len;
	}

	m_max_field_name_len = max;

	return max;
}


Register RegisterBlock::reg(uint32_t idx) const
{
	if (idx >= m_rbd->num_regs())
		throw runtime_error("register idx too high");

	const RegisterData* rd = &m_rfd->registers()[m_rbd->regs_offset() + idx];
	return Register(m_rfd, m_rbd, rd);
}

unique_ptr<Register> RegisterBlock::find_reg(const string& name) const
{
	for (unsigned ridx = 0; ridx < num_regs(); ++ridx) {
		Register reg = this->reg(ridx);

		if (strcmp(reg.name(), name.c_str()) == 0)
			return make_unique<Register>(reg);
	}

	return nullptr;
}


RegFile::RegFile(string filename)
{
	int fd = open(filename.c_str(), O_RDONLY);
	ERR_ON_ERRNO(fd < 0, "Open regfile '%s' failed", filename.c_str());

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

RegisterBlock RegFile::register_block(uint32_t idx) const
{
	if (idx >= m_rfd->num_blocks())
		throw runtime_error("register block idx too high");

	const RegisterBlockData* rbd = &m_rfd->blocks()[idx];
	return RegisterBlock(m_rfd, rbd);
}

unique_ptr<RegisterBlock> RegFile::find_register_block(const string& name) const
{
	for (unsigned bidx = 0; bidx < num_blocks(); ++bidx) {
		const RegisterBlock rb = register_block(bidx);

		if (strcmp(rb.name(), name.c_str()) == 0)
			return make_unique<RegisterBlock>(rb);
	}

	return nullptr;
}

unique_ptr<Register> RegFile::find_reg(const string& name) const
{
	for (unsigned bidx = 0; bidx < num_blocks(); ++bidx) {
		const RegisterBlock rb = register_block(bidx);

		for (unsigned ridx = 0; ridx < rb.num_regs(); ++ridx) {
			Register reg = rb.reg(ridx);

			if (strcmp(reg.name(), name.c_str()) == 0)
				return make_unique<Register>(reg);
		}
	}

	return nullptr;
}

unique_ptr<Register> RegFile::find_reg(uint64_t offset) const
{
	for (unsigned bidx = 0; bidx < num_blocks(); ++bidx) {
		const RegisterBlock rb = register_block(bidx);

		if (offset < rb.offset())
			continue;

		if (offset >= rb.offset() + rb.size())
			continue;

		for (unsigned ridx = 0; ridx < rb.num_regs(); ++ridx) {
			Register reg = rb.reg(ridx);

			if (reg.offset() == offset - rb.offset())
				return make_unique<Register>(reg);
		}
	}

	return nullptr;
}

static void print_regfile(const RegFile& rf)
{
	printf("%s: total %u/%u/%u\n", rf.name(), rf.num_blocks(), rf.num_regs(), rf.num_fields());
}

static void print_register_block(const RegisterBlock& rb)
{
	printf("  %s: %#" PRIx64 " %#" PRIx64 ", regs %u\n", rb.name(), rb.offset(), rb.size(), rb.num_regs());
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
		RegisterBlock rb = rf.register_block(bidx);
		print_register_block(rb);

		for (unsigned ridx = 0; ridx < rb.num_regs(); ++ridx) {
			Register reg = rb.reg(ridx);
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
		RegisterBlock rb = rf.register_block(bidx);

		bool block_printed = false;

		for (unsigned ridx = 0; ridx < rb.num_regs(); ++ridx) {
			Register reg = rb.reg(ridx);

			if (strcasestr(reg.name(), pattern.c_str()) == NULL)
				continue;

			if (!regfile_printed) {
				print_regfile(rf);
				regfile_printed = true;
			}

			if (!block_printed) {
				print_register_block(rb);
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
