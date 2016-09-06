#pragma once

#include <string>

class MemMap
{
public:
	MemMap(const std::string& filename, uint64_t offset, uint64_t length, bool read_only);
	~MemMap();

	uint64_t read(uint64_t addr, unsigned numbits) const;
	void writemem(uint64_t addr, unsigned numbits, uint64_t value);

	uint32_t read32(uint64_t addr) const;
	void write32(uint64_t addr, uint32_t value);

private:
	int m_fd;
	void* m_map_base;
	void* m_vaddr;
};
