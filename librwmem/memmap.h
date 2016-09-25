#pragma once

#include <string>
#include "imap.h"

class MemMap : public IMap
{
public:
	MemMap(const std::string& filename, Endianness data_endianness);
	MemMap(const std::string& filename, Endianness data_endianness, uint64_t offset, uint64_t length);
	~MemMap();

	void map(uint64_t offset, uint64_t length);
	void unmap();

	uint64_t read(uint64_t addr, unsigned numbytes) const;
	void write(uint64_t addr, unsigned numbytes, uint64_t value);

	uint8_t read8(uint64_t addr) const;
	void write8(uint64_t addr, uint8_t value);

	uint16_t read16(uint64_t addr) const;
	void write16(uint64_t addr, uint16_t value);

	uint32_t read32(uint64_t addr) const;
	void write32(uint64_t addr, uint32_t value);

	uint64_t read64(uint64_t addr) const;
	void write64(uint64_t addr, uint64_t value);

private:
	int m_fd;
	void* m_map_base;

	uint64_t m_map_offset;
	uint64_t m_map_len;

	Endianness m_data_endianness;

	void* maddr(uint64_t addr) const;

	volatile uint8_t* addr8(uint64_t addr) const;
	volatile uint16_t* addr16(uint64_t addr) const;
	volatile uint32_t* addr32(uint64_t addr) const;
	volatile uint64_t* addr64(uint64_t addr) const;
};
