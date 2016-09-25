#pragma once

#include "helpers.h"

class IMap
{
public:
	virtual ~IMap() { }

	virtual uint64_t read(uint64_t addr, unsigned numbytes) const = 0;
	virtual void write(uint64_t addr, unsigned numbytes, uint64_t value) = 0;

	virtual void map(uint64_t offset, uint64_t length) = 0;
	virtual void unmap() = 0;
};
