#include "regfiledata.h"
#include <cstring>

using namespace std;

const RegisterBlockData* RegisterFileData::blocks() const
{
	return reinterpret_cast<const RegisterBlockData*>(reinterpret_cast<const uint8_t*>(this) + sizeof(RegisterFileData));
}

const RegisterData* RegisterFileData::registers() const
{
	return (RegisterData*)(&blocks()[num_blocks()]);
}

const FieldData* RegisterFileData::fields() const
{
	return (FieldData*)(&registers()[num_regs()]);
}

const uint32_t* RegisterFileData::register_indices() const
{
	return (const uint32_t*)(&fields()[num_fields()]);
}

const uint32_t* RegisterFileData::field_indices() const
{
	return &register_indices()[num_reg_indices()];
}

const char* RegisterFileData::strings() const
{
	return (const char*)(&field_indices()[num_field_indices()]);
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
	if (idx >= num_regs())
		return nullptr;
	uint32_t reg_idx = rfd->register_indices()[first_reg_list_index() + idx];
	return &rfd->registers()[reg_idx];
}

const RegisterData* RegisterBlockData::find_register(const RegisterFileData* rfd, const string& name) const
{
	for (unsigned i = 0; i < num_regs(); ++i) {
		uint32_t reg_idx = rfd->register_indices()[first_reg_list_index() + i];
		const RegisterData* rd = &rfd->registers()[reg_idx];

		if (strcasecmp(rd->name(rfd), name.c_str()) == 0)
			return rd;
	}

	return nullptr;
}

const RegisterData* RegisterBlockData::find_register(const RegisterFileData* rfd, uint64_t offset) const
{
	for (unsigned i = 0; i < num_regs(); ++i) {
		uint32_t reg_idx = rfd->register_indices()[first_reg_list_index() + i];
		const RegisterData* rd = &rfd->registers()[reg_idx];

		if (rd->offset() == offset)
			return rd;
	}

	return nullptr;
}

const FieldData* RegisterData::field_at(const RegisterFileData* rfd, uint32_t idx) const
{
	if (idx >= num_fields())
		return nullptr;
	uint32_t field_idx = rfd->field_indices()[first_field_index() + idx];
	return &rfd->fields()[field_idx];
}

const FieldData* RegisterData::find_field(const RegisterFileData* rfd, const string& name) const
{
	for (unsigned i = 0; i < num_fields(); ++i) {
		uint32_t field_idx = rfd->field_indices()[first_field_index() + i];
		const FieldData* fd = &rfd->fields()[field_idx];

		if (strcasecmp(fd->name(rfd), name.c_str()) == 0)
			return fd;
	}

	return nullptr;
}

const FieldData* RegisterData::find_field(const RegisterFileData* rfd, uint8_t high, uint8_t low) const
{
	for (unsigned i = 0; i < num_fields(); ++i) {
		uint32_t field_idx = rfd->field_indices()[first_field_index() + i];
		const FieldData* fd = &rfd->fields()[field_idx];

		if (fd->high() == high && fd->low() == low)
			return fd;
	}

	return nullptr;
}

Endianness RegisterData::effective_data_endianness(const RegisterBlockData* rbd) const
{
	return data_endianness() == 0 ? rbd->data_endianness() : (Endianness)data_endianness();
}

uint8_t RegisterData::effective_data_size(const RegisterBlockData* rbd) const
{
	return data_size() == 0 ? rbd->data_size() : data_size();
}
