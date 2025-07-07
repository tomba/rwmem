#pragma once

#include "helpers.h"
#include "endianness.h"

enum class MapMode {
	Read,
	Write,
	ReadWrite,
};

class ITarget
{
public:
	virtual ~ITarget() {}

	// Make the area starting at offset accessible.
	// The offset is _not_ automatically added to the read/write addresses.
	virtual void map(uint64_t offset, uint64_t length,
			 Endianness default_addr_endianness = Endianness::Default, uint8_t default_addr_size = sizeof(void*),
			 Endianness default_data_endianness = Endianness::Default, uint8_t default_data_size = 4,
			 MapMode mode = MapMode::ReadWrite) = 0;
	virtual void unmap() = 0;
	virtual void sync() = 0;

	virtual uint64_t read(uint64_t addr, uint8_t nbytes = 0, Endianness endianness = Endianness::Default) const = 0;
	virtual void write(uint64_t addr, uint64_t value, uint8_t nbytes = 0, Endianness endianness = Endianness::Default) = 0;
};
