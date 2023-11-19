#pragma once

#include <string>
#include "itarget.h"
#include "helpers.h"

class I2CTarget : public ITarget
{
public:
	I2CTarget(uint16_t adapter_nr, uint16_t i2c_addr);
	~I2CTarget();

	// length is ignored
	void map(uint64_t offset, uint64_t length, Endianness addr_endianness, uint8_t addr_size, Endianness data_endianness, uint8_t data_size) override;
	void unmap() override;

	uint64_t read(uint64_t addr) const override { return read(addr, m_data_bytes); }
	void write(uint64_t addr, uint64_t value) override { write(addr, m_data_bytes, value); };

	uint64_t read(uint64_t addr, uint8_t numbytes) const override;
	void write(uint64_t addr, uint8_t numbytes, uint64_t value) override;

private:
	uint16_t m_adapter_nr;
	uint16_t m_i2c_addr;
	int m_fd;

	uint64_t m_offset;

	uint8_t m_address_bytes;
	Endianness m_address_endianness;
	uint8_t m_data_bytes;
	Endianness m_data_endianness;
};
