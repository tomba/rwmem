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

const RegisterBlockData* RegisterFileData::block_at(uint32_t idx) const
{
	return &blocks()[idx];
}

const RegisterBlockData* RegisterFileData::find_block(const string& name) const
{
	for (unsigned i = 0; i < num_blocks(); ++i) {
		const RegisterBlockData* rbd = block_at(i);

		if (strcasecmp(rbd->name(this), name.c_str()) == 0)
			return rbd;
	}

	return nullptr;
}

const RegisterData* RegisterFileData::find_register(const string& name, const RegisterBlockData** rbd) const
{
	for (unsigned i = 0; i < num_blocks(); ++i) {
		*rbd = block_at(i);

		const RegisterData* rd = (*rbd)->find_register(this, name);
		if (rd) {
			return rd;
		}
	}

	return nullptr;
}

const RegisterData* RegisterFileData::find_register(uint64_t offset, const RegisterBlockData** rbd) const
{
	for (unsigned bidx = 0; bidx < num_blocks(); ++bidx) {
		*rbd = block_at(bidx);

		if (offset < (*rbd)->offset())
			continue;

		if (offset >= (*rbd)->offset() + (*rbd)->size())
			continue;

		for (unsigned ridx = 0; ridx < (*rbd)->num_regs(); ++ridx) {
			const RegisterData* rd = (*rbd)->register_at(this, ridx);

			if (rd->offset() == offset - (*rbd)->offset())
				return rd;
		}
	}

	return nullptr;
}

const RegisterData* RegisterBlockData::register_at(const RegisterFileData* rfd, uint32_t idx) const
{
	return &rfd->registers()[first_reg_index() + idx];
}

const RegisterData* RegisterBlockData::find_register(const RegisterFileData* rfd, const string& name) const
{
	for (unsigned i = 0; i < num_regs(); ++i) {
		const RegisterData* rd = &rfd->registers()[first_reg_index() + i];

		if (strcasecmp(rd->name(rfd), name.c_str()) == 0)
			return rd;
	}

	return nullptr;
}

const RegisterData* RegisterBlockData::find_register(const RegisterFileData* rfd, uint64_t offset) const
{
	for (unsigned i = 0; i < num_regs(); ++i) {
		const RegisterData* rd = &rfd->registers()[first_reg_index() + i];

		if (rd->offset() == offset)
			return rd;
	}

	return nullptr;
}

const FieldData* RegisterData::field_at(const RegisterFileData* rfd, uint32_t idx) const
{
	return &rfd->fields()[first_field_index() + idx];
}

const FieldData* RegisterData::find_field(const RegisterFileData* rfd, const string& name) const
{
	for (unsigned i = 0; i < num_fields(); ++i) {
		const FieldData* fd = &rfd->fields()[first_field_index() + i];

		if (strcasecmp(fd->name(rfd), name.c_str()) == 0)
			return fd;
	}

	return nullptr;
}

const FieldData* RegisterData::find_field(const RegisterFileData* rfd, uint8_t high, uint8_t low) const
{
	for (unsigned i = 0; i < num_fields(); ++i) {
		const FieldData* fd = &rfd->fields()[first_field_index() + i];

		if (fd->high() == high && fd->low() == low)
			return fd;
	}

	return nullptr;
}
