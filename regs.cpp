#include <memory>
#include <cstdint>
#include <cstdlib>
#include <cstring>
#include <fcntl.h>
#include <unistd.h>
#include <sys/mman.h>

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

	m_blocks = (AddressBlockData*)((uint8_t*)m_rfd + sizeof(RegFileData));
	m_regs = (RegisterData*)(&m_blocks[m_rfd->num_blocks()]);
	m_fields = (FieldData*)(&m_regs[m_rfd->num_regs()]);
}

RegFile::~RegFile()
{
	munmap((void*)m_rfd, m_size);
}

unique_ptr<Register> RegFile::find_reg(const char* name) const
{
	const AddressBlockData* abd = m_blocks;
	const RegisterData* rd = m_regs;
	const FieldData* fd = m_fields;

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
	const AddressBlockData* abd = m_blocks;
	const RegisterData* rd = m_regs;
	const FieldData* fd = m_fields;

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
