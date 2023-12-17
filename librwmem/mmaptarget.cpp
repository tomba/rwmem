#include "mmaptarget.h"

#include <stdexcept>
#include <sys/mman.h>
#include <sys/types.h>
#include <sys/stat.h>
#include <fcntl.h>
#include <unistd.h>
#include <cinttypes>

#include "helpers.h"

using namespace std;

static const uint64_t pagesize = sysconf(_SC_PAGESIZE);
static const uint64_t pagemask = pagesize - 1;

MMapTarget::MMapTarget(const string& filename)
	: m_filename(filename), m_fd(-1),
	 m_offset(0), m_map_base(MAP_FAILED), m_map_offset(0), m_map_len(0)
{

}

MMapTarget::~MMapTarget()
{
	unmap();
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

	ERR_ON_ERRNO(m_fd == -1, "Failed to open file '{}'", m_filename);

	const off_t mmap_offset = offset & ~pagemask;
	const size_t mmap_len = (offset + length - mmap_offset + pagesize - 1) & ~pagemask;

	//fmt::print("mmap offset={:#x} length={:#x} mmap_offset={:#x} mmap_len={:#x}\n",
	//       offset, length, mmap_offset, mmap_len);

	struct stat st;
	int r = fstat(m_fd, &st);
	ERR_ON_ERRNO(r, "Failed to get map file stat");

	if (S_ISREG(st.st_mode))
		ERR_ON((size_t)st.st_size < offset + length, "Trying to access file past its end");

	m_map_base = mmap(nullptr, mmap_len,
			  prot,
			  MAP_SHARED, m_fd, mmap_offset);

	ERR_ON_ERRNO(m_map_base == MAP_FAILED, "failed to mmap");

	m_offset = offset;
	m_len = length;
	m_map_offset = mmap_offset;
	m_map_len = mmap_len;
}

void MMapTarget::unmap()
{
	if (m_fd == -1)
		return;

	close(m_fd);
	m_fd = -1;

	if (m_map_base == MAP_FAILED)
		return;

	if (munmap(m_map_base, pagesize) == -1)
		ERR_ERRNO("failed to munmap");

	m_map_base = MAP_FAILED;
}

uint64_t MMapTarget::read(uint64_t addr, uint8_t nbytes, Endianness endianness) const
{
	if (!nbytes)
		nbytes = m_default_data_size;

	switch (nbytes) {
	case 1:
		return read8(addr);
	case 2:
		return read16(addr, endianness);
	case 4:
		return read32(addr, endianness);
	case 8:
		return read64(addr, endianness);
	default:
		FAIL("Illegal data regsize '{}'", nbytes);
	}
}

void MMapTarget::write(uint64_t addr, uint64_t value, uint8_t nbytes, Endianness endianness)
{
	if (!nbytes)
		nbytes = m_default_data_size;

	switch (nbytes) {
	case 1:
		write8(addr, value);
		break;
	case 2:
		write16(addr, value, endianness);
		break;
	case 4:
		write32(addr, value, endianness);
		break;
	case 8:
		write64(addr, value, endianness);
		break;
	default:
		FAIL("Illegal data regsize '{}'", nbytes);
	}
}

uint8_t MMapTarget::read8(uint64_t addr) const
{
	return *addr8(addr);
}

void MMapTarget::write8(uint64_t addr, uint8_t value)
{
	*addr8(addr) = value;
}

uint16_t MMapTarget::read16(uint64_t addr, Endianness endianness) const
{
	if (endianness == Endianness::Default)
		endianness = m_default_data_endianness;

	if (endianness == Endianness::Big)
		return be16toh(*addr16(addr));
	else
		return le16toh(*addr16(addr));
}

void MMapTarget::write16(uint64_t addr, uint16_t value, Endianness endianness)
{
	if (endianness == Endianness::Default)
		endianness = m_default_data_endianness;

	if (endianness == Endianness::Big)
		*addr16(addr) = htobe16(value);
	else
		*addr16(addr) = htole16(value);
}

uint32_t MMapTarget::read32(uint64_t addr, Endianness endianness) const
{
	if (endianness == Endianness::Default)
		endianness = m_default_data_endianness;

	if (endianness == Endianness::Big)
		return be32toh(*addr32(addr));
	else
		return le32toh(*addr32(addr));
}

void MMapTarget::write32(uint64_t addr, uint32_t value, Endianness endianness)
{
	if (endianness == Endianness::Default)
		endianness = m_default_data_endianness;

	if (endianness == Endianness::Big)
		*addr32(addr) = htobe32(value);
	else
		*addr32(addr) = htole32(value);
}

uint64_t MMapTarget::read64(uint64_t addr, Endianness endianness) const
{
	if (endianness == Endianness::Default)
		endianness = m_default_data_endianness;

	if (endianness == Endianness::Big)
		return be64toh(*addr64(addr));
	else
		return le64toh(*addr64(addr));
}

void MMapTarget::write64(uint64_t addr, uint64_t value, Endianness endianness)
{
	if (endianness == Endianness::Default)
		endianness = m_default_data_endianness;

	if (endianness == Endianness::Big)
		*addr64(addr) = htobe64(value);
	else
		*addr64(addr) = htole64(value);
}

void* MMapTarget::maddr(uint64_t addr) const
{
	if (addr < m_offset)
		throw runtime_error("address below map range");

	return (uint8_t*)m_map_base + (addr - m_map_offset);
}

volatile uint8_t* MMapTarget::addr8(uint64_t addr) const
{
	if (addr + 1 > m_offset + m_len)
		throw runtime_error("address above map range");

	return (volatile uint8_t*)maddr(addr);
}

volatile uint16_t* MMapTarget::addr16(uint64_t addr) const
{
	if (addr + 2 > m_offset + m_len)
		throw runtime_error("address above map range");

	return (volatile uint16_t*)maddr(addr);
}

volatile uint32_t* MMapTarget::addr32(uint64_t addr) const
{
	if (addr + 4 > m_offset + m_len)
		throw runtime_error("address above map range");

	return (volatile uint32_t*)maddr(addr);
}

volatile uint64_t* MMapTarget::addr64(uint64_t addr) const
{
	if (addr + 8 > m_offset + m_len)
		throw runtime_error("address above map range");

	return (volatile uint64_t*)maddr(addr);
}
