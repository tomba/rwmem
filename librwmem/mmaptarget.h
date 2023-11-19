#pragma once

#include <string>
#include "itarget.h"

class MMapTarget : public ITarget
{
public:
	MMapTarget(const std::string& filename);
	~MMapTarget();

	// addr_endianness, addr_size are ignored
	void map(uint64_t offset, uint64_t length, Endianness addr_endianness, uint8_t addr_size, Endianness data_endianness, uint8_t data_size) override;
	void unmap() override;

	uint64_t read(uint64_t addr) const override { return read(addr, m_data_size); }
	void write(uint64_t addr, uint64_t value) override { write(addr, m_data_size, value); };

	uint64_t read(uint64_t addr, uint8_t numbytes) const override;
	void write(uint64_t addr, uint8_t numbytes, uint64_t value) override;

private:
	std::string m_filename;
	int m_fd;

	uint64_t m_offset;

	void* m_map_base;

	uint64_t m_map_offset;
	uint64_t m_map_len;

	Endianness m_data_endianness;
	uint8_t m_data_size;

	uint8_t read8(uint64_t addr) const;
	void write8(uint64_t addr, uint8_t value);

	uint16_t read16(uint64_t addr) const;
	void write16(uint64_t addr, uint16_t value);

	uint32_t read32(uint64_t addr) const;
	void write32(uint64_t addr, uint32_t value);

	uint64_t read64(uint64_t addr) const;
	void write64(uint64_t addr, uint64_t value);

	void* maddr(uint64_t addr) const;

	volatile uint8_t* addr8(uint64_t addr) const;
	volatile uint16_t* addr16(uint64_t addr) const;
	volatile uint32_t* addr32(uint64_t addr) const;
	volatile uint64_t* addr64(uint64_t addr) const;
};
