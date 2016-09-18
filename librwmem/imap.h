#pragma once

class IMap
{
public:
	virtual uint64_t read(uint64_t addr, unsigned numbytes) const = 0;
	virtual void write(uint64_t addr, unsigned numbytes, uint64_t value) = 0;
};
