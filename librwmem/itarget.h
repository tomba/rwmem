#pragma once

#include "helpers.h"

class ITarget
{
public:
	virtual ~ITarget() { }

	virtual uint64_t read(uint64_t addr, unsigned numbytes) const = 0;
	virtual void write(uint64_t addr, unsigned numbytes, uint64_t value) = 0;

	virtual uint32_t read32(uint64_t addr) const = 0;
	virtual void write32(uint64_t addr, uint32_t value) = 0;

	virtual void map(uint64_t offset, uint64_t length) = 0;
	virtual void unmap() = 0;
};
