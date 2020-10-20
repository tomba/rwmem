#pragma once

#include "helpers.h"

class ITarget
{
public:
	virtual ~ITarget() {}

	virtual void map(uint64_t offset, uint64_t length, Endianness addr_endianness, uint8_t addr_size, Endianness data_endianness, uint8_t data_size) = 0;
	virtual void unmap() = 0;

	virtual uint64_t read(uint64_t addr) const = 0;
	virtual void write(uint64_t addr, uint64_t value) = 0;

	virtual uint64_t read(uint64_t addr, uint8_t numbytes) const = 0;
	virtual void write(uint64_t addr, uint8_t numbytes, uint64_t value) = 0;
};
