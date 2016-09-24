#include "mappedregs.h"
#include "helpers.h"

using namespace std;

MappedRegisterBlock::MappedRegisterBlock(const string& mapfile, const string& regfile, const string& blockname)
{
	m_rf = make_unique<RegisterFile>(regfile);

	m_rbd = m_rf->data()->find_block(blockname);

	m_map = make_unique<MemMap>(mapfile, m_rbd->offset(), m_rbd->size());
}

MappedRegisterBlock::MappedRegisterBlock(const string& mapfile, uint64_t offset, const string& regfile, const string& blockname)
{
	m_rf = make_unique<RegisterFile>(regfile);

	m_rbd = m_rf->data()->find_block(blockname);

	m_map = make_unique<MemMap>(mapfile, offset, m_rbd->size());
}

MappedRegisterBlock::MappedRegisterBlock(const string& mapfile, uint64_t offset, uint64_t length)
	: m_rf(nullptr), m_rbd(nullptr)
{
	m_map = make_unique<MemMap>(mapfile, offset, length);
}

uint32_t MappedRegisterBlock::read32(const string& regname) const
{
	if (!m_rf)
		throw runtime_error("no register file");

	const RegisterData* rd = m_rbd->find_register(m_rf->data(), regname);

	return m_map->read32(rd->offset());
}

uint32_t MappedRegisterBlock::read32(uint64_t offset) const
{
	return m_map->read32(offset);
}

MappedRegister MappedRegisterBlock::find_register(const string& regname)
{
	if (!m_rf)
		throw runtime_error("no register file");

	const RegisterData* rd = m_rbd->find_register(m_rf->data(), regname);

	return MappedRegister(this, rd);
}

MappedRegister MappedRegisterBlock::get_register(uint64_t offset)
{
	return MappedRegister(this, offset);
}


MappedRegister::MappedRegister(MappedRegisterBlock* mrb, const RegisterData* rd)
	: m_mrb(mrb), m_rd(rd), m_offset(rd->offset())
{

}

MappedRegister::MappedRegister(MappedRegisterBlock* mrb, uint64_t offset)
	: m_mrb(mrb), m_rd(nullptr), m_offset(offset)
{

}

uint32_t MappedRegister::read32() const
{
	return m_mrb->m_map->read32(m_offset);
}

RegisterValue MappedRegister::read32value() const
{
	return RegisterValue(m_mrb, m_rd, read32());
}

RegisterValue::RegisterValue(MappedRegisterBlock* mrb, const RegisterData* rd, uint64_t value)
	:m_mrb(mrb), m_rd(rd), m_value(value)
{

}

uint64_t RegisterValue::field_value(const string& fieldname) const
{
	if (!m_mrb->m_rf)
		throw runtime_error("no register file");

	const FieldData* fd = m_rd->find_field(m_mrb->m_rf->data(), fieldname);

	if (!fd)
		throw runtime_error("field not found");

	return field_value(fd->high(), fd->low());
}

uint64_t RegisterValue::field_value(uint8_t high, uint8_t low) const
{
	uint64_t mask = GENMASK(high, low);

	return (m_value & mask) >> low;
}
