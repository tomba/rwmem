#pragma once

#include <string>
#include "itarget.h"
#include "helpers.h"

class I2CTarget : public ITarget
{
public:
	I2CTarget(unsigned adapter_nr, uint16_t i2c_addr, uint16_t addr_len, Endianness addr_endianness,
	       Endianness data_endianness);
	~I2CTarget();

	uint64_t read(uint64_t addr, unsigned numbytes) const;
	void write(uint64_t addr, unsigned numbytes, uint64_t value);

	uint32_t read32(uint64_t addr) const;
	void write32(uint64_t addr, uint32_t value);

	void map(uint64_t offset, uint64_t length) { m_offset = offset; }
	void unmap() { }

private:
	int m_fd;
	uint16_t m_i2c_addr;

	uint64_t m_offset;

	uint8_t m_address_bytes;
	Endianness m_address_endianness;
	Endianness m_data_endianness;
};
