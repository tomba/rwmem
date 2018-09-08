#include "regfiledata.h"
#include <cstring>

using namespace std;

const RegisterBlockData* RegisterFileData::blocks() const
{
	return (RegisterBlockData*)((uint8_t*)this + sizeof(RegisterFileData));
}

const RegisterData* RegisterFileData::registers() const
{
	return (RegisterData*)(&blocks()[num_blocks()]);
}

const FieldData* RegisterFileData::fields() const
{
	return (FieldData*)(&registers()[num_regs()]);
}

const char* RegisterFileData::strings() const
{
	return (const char*)(&fields()[num_fields()]);
}

const RegisterBlockData* RegisterFileData::at(uint32_t idx) const
{
	return &blocks()[idx];
}

const RegisterBlockData* RegisterFileData::find_block(const string& name) const
{
	for (unsigned i = 0; i < num_blocks(); ++i) {
		const RegisterBlockData* rbd = at(i);

		if (strcasecmp(rbd->name(this), name.c_str()) == 0)
			return rbd;
	}

	return nullptr;
}

const RegisterData* RegisterFileData::find_register(const string& name, const RegisterBlockData** rbd) const
{
	for (unsigned i = 0; i < num_blocks(); ++i) {
		*rbd = at(i);

		const RegisterData* rd = (*rbd)->find_register(this, name);

		if (strcasecmp(rd->name(this), name.c_str()) == 0)
			return rd;
	}

	return nullptr;
}

const RegisterData* RegisterFileData::find_register(uint64_t offset, const RegisterBlockData** rbd) const
{
	for (unsigned bidx = 0; bidx < num_blocks(); ++bidx) {
		*rbd = at(bidx);

		if (offset < (*rbd)->offset())
			continue;

		if (offset >= (*rbd)->offset() + (*rbd)->size())
			continue;

		for (unsigned ridx = 0; ridx < (*rbd)->num_regs(); ++ridx) {
			const RegisterData* rd = (*rbd)->at(this, ridx);

			if (rd->offset() == offset - (*rbd)->offset())
				return rd;
		}
	}

	return nullptr;
}

const RegisterData* RegisterBlockData::at(const RegisterFileData* rfd, uint32_t idx) const
{
	return &rfd->registers()[regs_offset() + idx];
}

const RegisterData* RegisterBlockData::find_register(const RegisterFileData* rfd, const string& name) const
{
	for (unsigned i = 0; i < num_regs(); ++i) {
		const RegisterData* rd = &rfd->registers()[regs_offset() + i];

		if (strcasecmp(rd->name(rfd), name.c_str()) == 0)
			return rd;
	}

	return nullptr;
}

const RegisterData* RegisterBlockData::find_register(const RegisterFileData* rfd, uint64_t offset) const
{
	for (unsigned i = 0; i < num_regs(); ++i) {
		const RegisterData* rd = &rfd->registers()[regs_offset() + i];

		if (rd->offset() == offset)
			return rd;
	}

	return nullptr;
}

const FieldData* RegisterData::at(const RegisterFileData* rfd, uint32_t idx) const
{
	return &rfd->fields()[fields_offset() + idx];
}

const FieldData* RegisterData::find_field(const RegisterFileData* rfd, const string& name) const
{
	for (unsigned i = 0; i < num_fields(); ++i) {
		const FieldData* fd = &rfd->fields()[fields_offset() + i];

		if (strcasecmp(fd->name(rfd), name.c_str()) == 0)
			return fd;
	}

	return nullptr;
}

const FieldData* RegisterData::find_field(const RegisterFileData* rfd, uint8_t high, uint8_t low) const
{
	for (unsigned i = 0; i < num_fields(); ++i) {
		const FieldData* fd = &rfd->fields()[fields_offset() + i];

		if (fd->high() == high && fd->low() == low)
			return fd;
	}

	return nullptr;
}
