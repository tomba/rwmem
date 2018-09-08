#include "mmaptarget.h"

#include <sys/mman.h>
#include <sys/types.h>
#include <sys/stat.h>
#include <fcntl.h>
#include <unistd.h>
#include <cinttypes>

#include "helpers.h"

using namespace std;

static const unsigned pagesize = sysconf(_SC_PAGESIZE);
static const unsigned pagemask = pagesize - 1;

MMapTarget::MMapTarget(const string& filename, Endianness data_endianness)
	: m_map_base(MAP_FAILED), m_data_endianness(data_endianness)
{
	m_fd = open(filename.c_str(), O_RDWR | O_SYNC);

	ERR_ON_ERRNO(m_fd == -1, "Failed to open file '%s'", filename.c_str());
}

MMapTarget::MMapTarget(const string &filename, Endianness data_endianness, uint64_t offset, uint64_t length)
	:MMapTarget(filename, data_endianness)
{
	map(offset, length);
}

MMapTarget::~MMapTarget()
{
	unmap();
	close(m_fd);
}

void MMapTarget::map(uint64_t offset, uint64_t length)
{
	unmap();

	const off_t mmap_offset = offset & ~pagemask;
	const size_t mmap_len = (offset + length + pagesize - 1) & ~pagemask;

	//printf("mmap '%s' offset=%#" PRIx64 " length=%#" PRIx64 " mmap_offset=0x%jx mmap_len=0x%zx\n",
	//       filename.c_str(), offset, length, mmap_offset, mmap_len);

	struct stat st;
	int r = fstat(m_fd, &st);
	ERR_ON_ERRNO(r, "Failed to get map file stat");

	if (S_ISREG(st.st_mode))
		ERR_ON(st.st_size < mmap_offset + (off_t)mmap_len, "Trying to access file past its end");

	m_map_base = mmap(0, mmap_len,
			  PROT_READ | PROT_WRITE,
			  MAP_SHARED, m_fd, mmap_offset);

	ERR_ON_ERRNO(m_map_base == MAP_FAILED, "failed to mmap");

	m_map_offset = mmap_offset;
	m_map_len = mmap_len;
}

void MMapTarget::unmap()
{
	if (m_map_base == MAP_FAILED)
		return;

	if (munmap(m_map_base, pagesize) == -1)
		ERR_ERRNO("failed to munmap");

	m_map_base = MAP_FAILED;
}

uint64_t MMapTarget::read(uint64_t addr, unsigned numbytes) const
{
	switch (numbytes) {
	case 1:
		return read8(addr);
	case 2:
		return read16(addr);
	case 4:
		return read32(addr);
	case 8:
		return read64(addr);
	default:
		FAIL("Illegal data regsize '%d'", numbytes);
	}
}

void MMapTarget::write(uint64_t addr, unsigned numbytes, uint64_t value)
{
	switch (numbytes) {
	case 1:
		write8(addr, value);
		break;
	case 2:
		write16(addr, value);
		break;
	case 4:
		write32(addr, value);
		break;
	case 8:
		write64(addr, value);
		break;
	default:
		FAIL("Illegal data regsize '%d'", numbytes);
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

uint16_t MMapTarget::read16(uint64_t addr) const
{
	if (m_data_endianness == Endianness::Big)
		return be16toh(*addr16(addr));
	else
		return le16toh(*addr16(addr));
}

void MMapTarget::write16(uint64_t addr, uint16_t value)
{
	if (m_data_endianness == Endianness::Big)
		*addr16(addr) = htobe16(value);
	else
		*addr16(addr) = htole16(value);
}

uint32_t MMapTarget::read32(uint64_t addr) const
{
	if (m_data_endianness == Endianness::Big)
		return be32toh(*addr32(addr));
	else
		return le32toh(*addr32(addr));
}

void MMapTarget::write32(uint64_t addr, uint32_t value)
{
	if (m_data_endianness == Endianness::Big)
		*addr32(addr) = htobe32(value);
	else
		*addr32(addr) = htole32(value);
}

uint64_t MMapTarget::read64(uint64_t addr) const
{
	if (m_data_endianness == Endianness::Big)
		return be64toh(*addr64(addr));
	else
		return le16toh(*addr64(addr));
}

void MMapTarget::write64(uint64_t addr, uint64_t value)
{
	if (m_data_endianness == Endianness::Big)
		*addr64(addr) = htobe64(value);
	else
		*addr64(addr) = htole64(value);
}

void* MMapTarget::maddr(uint64_t addr) const
{
	FAIL_IF(addr < m_map_offset, "address below map range");
	FAIL_IF(addr >= m_map_offset + m_map_len, "address above map range");

	return (uint8_t*)m_map_base + (addr - m_map_offset);
}

volatile uint8_t* MMapTarget::addr8(uint64_t addr) const
{
	return (volatile uint8_t*)maddr(addr);
}

volatile uint16_t* MMapTarget::addr16(uint64_t addr) const
{
	return (volatile uint16_t*)maddr(addr);
}

volatile uint32_t* MMapTarget::addr32(uint64_t addr) const
{
	return (volatile uint32_t*)maddr(addr);
}

volatile uint64_t* MMapTarget::addr64(uint64_t addr) const
{
	return (volatile uint64_t*)maddr(addr);
}
