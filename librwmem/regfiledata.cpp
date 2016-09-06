#include "regfiledata.h"
#include <string.h>

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

const RegisterBlockData* RegisterFileData::find_block(const std::string& name) const
{
	for (unsigned i = 0; i < num_blocks(); ++i) {
		const RegisterBlockData* rbd = at(i);

		if (strcmp(rbd->name(this), name.c_str()) == 0)
			return rbd;
	}

	return nullptr;
}

const RegisterData* RegisterBlockData::at(const RegisterFileData* rfd, uint32_t idx) const
{
	return &rfd->registers()[regs_offset() + idx];
}

const RegisterData* RegisterBlockData::find_register(const RegisterFileData* rfd, const std::string& name) const
{
	for (unsigned i = 0; i < num_regs(); ++i) {
		const RegisterData* rd = &rfd->registers()[regs_offset() + i];

		if (strcmp(rd->name(rfd), name.c_str()) == 0)
			return rd;
	}

	return nullptr;
}

const FieldData* RegisterData::at(const RegisterFileData* rfd, uint32_t idx) const
{
	return &rfd->fields()[fields_offset() + idx];
}

const FieldData* RegisterData::find_field(const RegisterFileData* rfd, const std::__cxx11::string& name) const
{
	for (unsigned i = 0; i < num_fields(); ++i) {
		const FieldData* fd = &rfd->fields()[fields_offset() + i];

		if (strcmp(fd->name(rfd), name.c_str()) == 0)
			return fd;
	}

	return nullptr;
}
