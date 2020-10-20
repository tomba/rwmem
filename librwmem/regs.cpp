#include <memory>
#include <stdexcept>
#include <cstdint>
#include <cstdlib>
#include <cstring>
#include <fcntl.h>
#include <unistd.h>
#include <sys/mman.h>
#include <cinttypes>
#include <exception>

#include "regs.h"
#include "helpers.h"

using namespace std;

Register::Register(const RegisterFileData* rfd, const RegisterBlockData* rbd, const RegisterData* rd)
	: m_rfd(rfd), m_rbd(rbd), m_rd(rd)
{
}

Field Register::at(uint32_t idx) const
{
	if (idx >= m_rd->num_fields())
		throw out_of_range("field idx too high");

	const FieldData* fd = m_rd->at(m_rfd, idx);
	return Field(m_rfd, fd);
}

unique_ptr<Field> Register::find_field(const string& name) const
{
	const FieldData* fd = m_rd->find_field(m_rfd, name);

	if (!fd)
		return nullptr;

	return make_unique<Field>(m_rfd, fd);
}

unique_ptr<Field> Register::find_field(uint8_t high, uint8_t low) const
{
	for (unsigned i = 0; i < num_fields(); ++i) {
		const FieldData* fd = m_rd->at(m_rfd, i);

		if (low == fd->low() && high == fd->high())
			return make_unique<Field>(m_rfd, fd);
	}

	return nullptr;
}

RegisterBlock Register::register_block() const
{
	return RegisterBlock(m_rfd, m_rbd);
}

Register RegisterBlock::at(uint32_t idx) const
{
	if (idx >= m_rbd->num_regs())
		throw out_of_range("register idx too high");

	const RegisterData* rd = m_rbd->at(m_rfd, idx);
	return Register(m_rfd, m_rbd, rd);
}

unique_ptr<Register> RegisterBlock::get_register(const string& name) const
{
	const RegisterData* rd = m_rbd->find_register(m_rfd, name);

	if (!rd)
		return nullptr;

	return make_unique<Register>(m_rfd, m_rbd, rd);
}

RegisterFile::RegisterFile(const std::string& filename)
{
	int fd = open(filename.c_str(), O_RDONLY);
	ERR_ON_ERRNO(fd < 0, "Open regfile '%s' failed", filename.c_str());

	off_t len = lseek(fd, (size_t)0, SEEK_END);
	lseek(fd, 0, SEEK_SET);

	void* data = mmap(nullptr, len, PROT_READ, MAP_PRIVATE, fd, 0);
	ERR_ON_ERRNO(data == MAP_FAILED, "mmap regfile failed");

	m_rfd = (RegisterFileData*)data;
	m_size = len;

	if (m_rfd->magic() != RWMEM_MAGIC)
		throw runtime_error("Bad registerfile magic number");

	if (m_rfd->version() != RWMEM_VERSION)
		throw runtime_error("Bad registerfile version");
}

RegisterFile::~RegisterFile()
{
	munmap((void*)m_rfd, m_size);
}

RegisterBlock RegisterFile::at(uint32_t idx) const
{
	if (idx >= m_rfd->num_blocks())
		throw out_of_range("register block idx too high");

	const RegisterBlockData* rbd = m_rfd->at(idx);
	return RegisterBlock(m_rfd, rbd);
}

unique_ptr<RegisterBlock> RegisterFile::find_register_block(const string& name) const
{
	const RegisterBlockData* rb = m_rfd->find_block(name);

	if (rb)
		return make_unique<RegisterBlock>(m_rfd, rb);

	return nullptr;
}

unique_ptr<Register> RegisterFile::find_register(const string& name) const
{
	const RegisterData* rd;
	const RegisterBlockData* rbd;

	rd = m_rfd->find_register(name, &rbd);

	if (!rd)
		return nullptr;

	return make_unique<Register>(m_rfd, rbd, rd);
}

unique_ptr<Register> RegisterFile::find_register(uint64_t offset) const
{
	const RegisterData* rd;
	const RegisterBlockData* rbd;

	rd = m_rfd->find_register(offset, &rbd);

	if (!rd)
		return nullptr;

	return make_unique<Register>(m_rfd, rbd, rd);
}
