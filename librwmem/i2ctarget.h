#pragma once

#include "itarget.h"

class I2CTarget : public ITarget
{
public:
	I2CTarget(uint16_t adapter_nr, uint16_t i2c_addr);
	~I2CTarget();

	// length is ignored
	void map(uint64_t offset, uint64_t length,
		 Endianness default_addr_endianness, uint8_t default_addr_size,
		 Endianness default_data_endianness, uint8_t default_data_size,
		 MapMode mode) override;
	void unmap() override;
	void sync() override {}

	uint64_t read(uint64_t addr, uint8_t nbytes, Endianness endianness) const override;
	void write(uint64_t addr, uint64_t value, uint8_t nbytes, Endianness endianness) override;

private:
	uint16_t m_adapter_nr;
	uint16_t m_i2c_addr;
	int m_fd;

	uint8_t m_address_bytes;
	Endianness m_address_endianness;
	uint8_t m_data_bytes;
	Endianness m_data_endianness;
};
