#include <memory>
#include <cstdint>
#include <cstdlib>
#include <cstring>
#include <fcntl.h>
#include <unistd.h>
#include <sys/mman.h>
#include <inttypes.h>

#include "regs.h"
#include "helpers.h"

using namespace std;

Register::Register(const AddressBlockData* abd, const RegisterData* rd, const FieldData* fd)
	: m_abd(abd), m_rd(rd), m_fd(fd)
{
	uint32_t max = 0;
	for (unsigned i = 0; i < num_fields(); ++i) {
		uint32_t len = strlen(m_fd[i].name());
		if (len > max)
			max = len;
	}
	m_max_field_name_len = max;
}

std::unique_ptr<Field> Register::field_by_index(unsigned idx)
{
	return std::make_unique<Field>(*this, &m_fd[idx]);
}

unique_ptr<Field> Register::find_field(const char* name)
{
	for (unsigned i = 0; i < m_rd->num_fields(); ++i) {
		if (strcmp(m_fd[i].name(), name) == 0)
			return make_unique<Field>(*this, &m_fd[i]);
	}

	return nullptr;
}

unique_ptr<Field> Register::find_field(uint8_t high, uint8_t low)
{
	for (unsigned i = 0; i < m_rd->num_fields(); ++i) {
		if (low == m_fd[i].low() && high == m_fd[i].high())
			return make_unique<Field>(*this, &m_fd[i]);
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

unique_ptr<Register> RegFile::find_reg(const char* name) const
{
	const AddressBlockData* abd = m_rfd->blocks();
	const RegisterData* rd = m_rfd->registers();
	const FieldData* fd = m_rfd->fields();

	for (unsigned bidx = 0; bidx < m_rfd->num_blocks(); ++bidx) {
		for (unsigned ridx = 0; ridx < abd->num_regs(); ++ridx) {
			if (strcmp(rd->name(), name) == 0)
				return make_unique<Register>(abd, rd, fd);

			fd += rd->num_fields();
			rd++;
		}
		abd++;
	}

	return nullptr;
}

unique_ptr<Register> RegFile::find_reg(uint64_t offset) const
{
	const AddressBlockData* abd = m_rfd->blocks();
	const RegisterData* rd = m_rfd->registers();
	const FieldData* fd = m_rfd->fields();

	for (unsigned bidx = 0; bidx < m_rfd->num_blocks(); ++bidx) {
		for (unsigned ridx = 0; ridx < abd->num_regs(); ++ridx) {
			if (rd->offset() == offset)
				return make_unique<Register>(abd, rd, fd);

			fd += rd->num_fields();
			rd++;
		}
		abd++;
	}

	return nullptr;
}

static void print_regfile(const RegFileData* rfd)
{
	printf("%s: total %u/%u/%u\n", rfd->name(), rfd->num_blocks(), rfd->num_regs(), rfd->num_fields());
}

static void print_address_block(const AddressBlockData* abd)
{
	printf("  %s: %#" PRIx64 " %#" PRIx64 ", regs %u\n", abd->name(), abd->offset(), abd->size(), abd->num_regs());
}

static void print_register(const RegisterData* rd)
{
	printf("    %s: %#" PRIx64 " %#x, fields %u\n", rd->name(), rd->offset(), rd->size(), rd->num_fields());
}

static void print_field(const FieldData* fd)
{
	printf("      %s: %u:%u\n", fd->name(), fd->high(), fd->low());
}

static void print_all(const RegFileData* rfd)
{
	const AddressBlockData* abd = rfd->blocks();
	const RegisterData* rd = rfd->registers();
	const FieldData* fd = rfd->fields();

	print_regfile(rfd);

	for (unsigned bidx = 0; bidx < rfd->num_blocks(); ++bidx, abd++) {
		print_address_block(abd);

		for (unsigned ridx = 0; ridx < abd->num_regs(); ++ridx, rd++) {
			print_register(rd);

			for (unsigned fidx = 0; fidx < rd->num_fields(); ++fidx, fd++) {
				print_field(fd);
			}
		}
	}
}


void RegFile::print(const char* pattern)
{
	if (!pattern) {
		print_all(m_rfd);
		return;
	}

	const AddressBlockData* abd = m_rfd->blocks();
	const RegisterData* rd = m_rfd->registers();
	const FieldData* fd = m_rfd->fields();

	bool regfile_printed = false;

	for (unsigned bidx = 0; bidx < m_rfd->num_blocks(); ++bidx, abd++) {
		bool block_printed = false;

		for (unsigned ridx = 0; ridx < abd->num_regs(); ++ridx, rd++) {
			if (strcasestr(rd->name(), pattern) == NULL)
				continue;

			if (!regfile_printed) {
				print_regfile(m_rfd);
				regfile_printed = true;
			}

			if (!block_printed) {
				print_address_block(abd);
				block_printed = true;
			}

			print_register(rd);

			for (unsigned fidx = 0; fidx < rd->num_fields(); ++fidx, fd++) {
				print_field(fd);
			}
		}
	}
}
