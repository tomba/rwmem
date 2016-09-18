#pragma once

#include <string>
#include "imap.h"

class I2CMap : public IMap
{
public:
	I2CMap(unsigned adapter_nr, uint16_t i2c_addr);
	~I2CMap();

	uint64_t read(uint64_t addr, unsigned numbytes) const;
	void write(uint64_t addr, unsigned numbytes, uint64_t value);

private:
	int m_fd;
	uint16_t m_i2c_addr;
};
