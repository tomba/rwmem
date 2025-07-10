#pragma once

#include <string>
#include "itarget.h"

class MMapTarget : public ITarget
{
public:
	MMapTarget(const std::string& filename);
	~MMapTarget();

	void map(uint64_t offset, uint64_t length,
		 Endianness default_addr_endianness, uint8_t default_addr_size,
		 Endianness default_data_endianness, uint8_t default_data_size,
		 MapMode mode) override;
	void unmap() override;
	void sync() override;

	uint64_t read(uint64_t addr, uint8_t nbytes, Endianness endianness) const override;
	void write(uint64_t addr, uint64_t value, uint8_t nbytes, Endianness endianness) override;

private:
	std::string m_filename;
	int m_fd;

	Endianness m_default_addr_endianness;
	uint8_t m_default_addr_size;
	Endianness m_default_data_endianness;
	uint8_t m_default_data_size;
	MapMode m_mode;

	// User requested offset (from the beginning of the file) and length
	uint64_t m_offset;
	uint64_t m_len;

	void* m_map_base;

	// mmapped offset (from the beginning of the file) and length
	uint64_t m_map_offset;
	uint64_t m_map_len;

	void validate_access(uint64_t addr, uint8_t nbytes) const;
	void* maddr(uint64_t addr) const;
};
