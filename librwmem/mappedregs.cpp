#include "mappedregs.h"

using namespace std;

void test()
{
	auto rf = RegisterFile("/home/tomba/work-lappy/rwmem-db/k2g.bin");
	auto rb = *rf.find_register_block("DSS").get();

	auto mrb2 = new MappedRegisterBlock(rb, "/dev/mem", true);

	auto mrb = new MappedRegisterBlock(rb, "LICENSE", 0x80, 0x1000, true);
	uint32_t val = mrb->read32("DSS_REVISION");

	printf("tuli %x\n", val);
}

MappedRegisterBlock::MappedRegisterBlock(const RegisterBlock rb, const string& filename, bool read_only)
	: m_rb(rb), m_map(filename, rb.offset(), rb.size(), read_only)
{

}

MappedRegisterBlock::MappedRegisterBlock(const RegisterBlock rb, const string& filename, uint64_t offset, uint64_t length, bool read_only)
	: m_rb(rb), m_map(filename, offset, length, read_only)
{

}

uint32_t MappedRegisterBlock::read32(const string& regname)
{
	auto r = m_rb.find_reg(regname);
	return m_map.read32(r->offset());
}
