#include "mmaptarget.h"

#include <stdexcept>
#include <cstdio>
#include <cstring>
#include <sys/mman.h>
#include <sys/types.h>
#include <sys/stat.h>
#include <fcntl.h>
#include <unistd.h>
#include <format>

using namespace std;

static const uint64_t pagesize = sysconf(_SC_PAGESIZE);
static const uint64_t pagemask = pagesize - 1;

template<typename T>
static T ioread(void* addr)
{
	return *static_cast<volatile T*>(addr);
}

template<typename T>
static void iowrite(void* addr, T value)
{
	*static_cast<volatile T*>(addr) = value;
}

static uint64_t read_bytes(void* base_addr, uint8_t nbytes, Endianness endianness)
{
	volatile uint8_t* addr = static_cast<volatile uint8_t*>(base_addr);
	uint64_t result = 0;

	if (endianness == Endianness::Little) {
		for (int i = 0; i < nbytes; i++) {
			result |= ((uint64_t)addr[i]) << (i * 8);
		}
	} else {
		for (int i = 0; i < nbytes; i++) {
			result = (result << 8) | addr[i];
		}
	}

	return result;
}

static void write_bytes(void* base_addr, uint64_t value, uint8_t nbytes, Endianness endianness)
{
	volatile uint8_t* addr = static_cast<volatile uint8_t*>(base_addr);

	if (endianness == Endianness::Little) {
		for (int i = 0; i < nbytes; i++) {
			addr[i] = (value >> (i * 8)) & 0xff;
		}
	} else {
		for (int i = 0; i < nbytes; i++) {
			addr[i] = (value >> ((nbytes - 1 - i) * 8)) & 0xff;
		}
	}
}

MMapTarget::MMapTarget(const string& filename)
	: m_filename(filename), m_fd(-1),
	  m_default_addr_endianness(Endianness::Default), m_default_addr_size(0),
	  m_default_data_endianness(Endianness::Default), m_default_data_size(0),
	  m_mode(MapMode::ReadWrite), m_offset(0), m_len(0),
	  m_map_base(MAP_FAILED), m_map_offset(0), m_map_len(0)
{
}

MMapTarget::~MMapTarget()
{
	MMapTarget::unmap();
}

void MMapTarget::map(uint64_t offset, uint64_t length,
		     Endianness default_addr_endianness, uint8_t default_addr_size,
		     Endianness default_data_endianness, uint8_t default_data_size,
		     MapMode mode)
{
	unmap();

	m_default_addr_endianness = default_addr_endianness;
	m_default_addr_size = default_addr_size;
	m_default_data_endianness = default_data_endianness;
	m_default_data_size = default_data_size;
	m_mode = mode;

	int oflag;
	int prot;

	switch (mode) {
	case MapMode::Read:
		oflag = O_RDONLY;
		prot = PROT_READ;
		break;
	case MapMode::Write:
		oflag = O_WRONLY;
		prot = PROT_WRITE;
		break;
	default:
	case MapMode::ReadWrite:
		oflag = O_RDWR;
		prot = PROT_READ | PROT_WRITE;
		break;
	}

	m_fd = open(m_filename.c_str(), oflag | O_SYNC);

	if (m_fd == -1)
		throw runtime_error(std::format("Failed to open file '{}': {}", m_filename, strerror(errno)));

	const off_t mmap_offset = offset & ~pagemask;
	const size_t mmap_len = (offset + length - mmap_offset + pagesize - 1) & ~pagemask;

	//fmt::print("mmap offset={:#x} length={:#x} mmap_offset={:#x} mmap_len={:#x}\n",
	//       offset, length, mmap_offset, mmap_len);

	struct stat st;
	int r = fstat(m_fd, &st);
	if (r != 0)
		throw runtime_error(std::format("Failed to get map file stat: {}", strerror(errno)));

	if (S_ISREG(st.st_mode) && (size_t)st.st_size < offset + length)
		throw runtime_error("Trying to access file past its end");

	m_map_base = mmap(nullptr, mmap_len,
			  prot,
			  MAP_SHARED, m_fd, mmap_offset);

	if (m_map_base == MAP_FAILED)
		throw runtime_error(std::format("failed to mmap: {}", strerror(errno)));

	m_offset = offset;
	m_len = length;
	m_map_offset = mmap_offset;
	m_map_len = mmap_len;
}

void MMapTarget::unmap()
{
	if (m_map_base != MAP_FAILED) {
		if (munmap(m_map_base, m_map_len) == -1)
			fputs(std::format("Warning: failed to munmap: {}\n", strerror(errno)).c_str(), stderr);

		m_map_base = MAP_FAILED;
	}

	if (m_fd != -1) {
		close(m_fd);
		m_fd = -1;
	}
}

void MMapTarget::sync()
{
	if (m_map_base == MAP_FAILED)
		return;

	int ret = msync(m_map_base, m_map_len, MS_SYNC);
	if (ret != 0)
		throw runtime_error(std::format("failed to msync(): {}", strerror(errno)));
}

uint64_t MMapTarget::read(uint64_t addr, uint8_t nbytes, Endianness endianness) const
{
	if (!nbytes)
		nbytes = m_default_data_size;

	if (endianness == Endianness::Default)
		endianness = m_default_data_endianness;

	validate_access(addr, nbytes);

	void* base_addr = maddr(addr);

	switch (nbytes) {
	case 1:
		return ioread<uint8_t>(base_addr);
	case 2:
		return to_host(ioread<uint16_t>(base_addr), endianness);
	case 4:
		return to_host(ioread<uint32_t>(base_addr), endianness);
	case 8:
		return to_host(ioread<uint64_t>(base_addr), endianness);
	case 3:
	case 5:
	case 6:
	case 7:
		return read_bytes(base_addr, nbytes, endianness);
	default:
		throw runtime_error(std::format("Illegal data regsize '{}'", nbytes));
	}
}

void MMapTarget::write(uint64_t addr, uint64_t value, uint8_t nbytes, Endianness endianness)
{
	if (m_mode != MapMode::Write && m_mode != MapMode::ReadWrite)
		throw runtime_error("Trying to write to a read-only mapping");

	if (!nbytes)
		nbytes = m_default_data_size;

	if (endianness == Endianness::Default)
		endianness = m_default_data_endianness;

	validate_access(addr, nbytes);

	void* base_addr = maddr(addr);

	switch (nbytes) {
	case 1:
		iowrite<uint8_t>(base_addr, (uint8_t)value);
		break;
	case 2:
		iowrite<uint16_t>(base_addr, from_host((uint16_t)value, endianness));
		break;
	case 4:
		iowrite<uint32_t>(base_addr, from_host((uint32_t)value, endianness));
		break;
	case 8:
		iowrite<uint64_t>(base_addr, from_host(value, endianness));
		break;
	case 3:
	case 5:
	case 6:
	case 7:
		write_bytes(base_addr, value, nbytes, endianness);
		break;
	default:
		throw runtime_error(std::format("Illegal data regsize '{}'", nbytes));
	}
}

void MMapTarget::validate_access(uint64_t addr, uint8_t nbytes) const
{
	if (addr < m_offset)
		throw runtime_error(std::format("address {:#x} below map range {:#x}-{:#x}",
						addr, m_offset, m_offset + m_len));

	if (addr + nbytes > m_offset + m_len)
		throw runtime_error("address above map range");
}

void* MMapTarget::maddr(uint64_t addr) const
{
	return (uint8_t*)m_map_base + (addr - m_map_offset);
}
