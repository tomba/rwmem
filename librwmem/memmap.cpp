#include "memmap.h"

#include <sys/mman.h>
#include <sys/types.h>
#include <sys/stat.h>
#include <fcntl.h>
#include <unistd.h>
#include <inttypes.h>

#include "helpers.h"

using namespace std;

static const unsigned pagesize = sysconf(_SC_PAGESIZE);
static const unsigned pagemask = pagesize - 1;

MemMap::MemMap(const string& filename, uint64_t offset, uint64_t length, bool read_only)
{
	m_fd = open(filename.c_str(), (read_only ? O_RDONLY : O_RDWR) | O_SYNC);

	ERR_ON_ERRNO(m_fd == -1, "Failed to open file '%s'", filename.c_str());

	const off_t mmap_offset = offset & ~pagemask;
	const size_t mmap_len = (offset + length + pagesize - 1) & ~pagemask;

	printf("mmap '%s' offset=%#" PRIx64 " length=%#" PRIx64 " mmap_offset=0x%jx mmap_len=0x%zx\n",
	       filename.c_str(), offset, length, mmap_offset, mmap_len);

	// how to do the check only for normal files?
	bool check_file_len = true;

	if (check_file_len) {
		const off_t file_len = lseek(m_fd, (size_t)0, SEEK_END);
		lseek(m_fd, 0, SEEK_SET);

		// note: use file_len only if lseek() succeeded
		ERR_ON(file_len != (off_t)-1 && file_len < mmap_offset + (off_t)mmap_len,
		       "Trying to access file past its end");
	}

	m_map_base = mmap(0, mmap_len,
			       PROT_READ | (read_only ? 0 : PROT_WRITE),
			       MAP_SHARED, m_fd, mmap_offset);

	ERR_ON_ERRNO(m_map_base == MAP_FAILED, "failed to mmap");

	m_vaddr = (uint8_t* )m_map_base + (offset & pagemask);
}

MemMap::~MemMap()
{
	if (munmap(m_map_base, pagesize) == -1)
		ERR_ERRNO("failed to munmap");

	close(m_fd);
}

static volatile uint32_t* addr32(void* base, uint64_t offset)
{
	return (volatile uint32_t*)((uint8_t*)base + offset);
}

uint32_t MemMap::read32(uint64_t addr) const
{
	return *addr32(m_vaddr, addr);
}

void MemMap::write32(uint64_t addr, uint32_t value)
{
	*addr32(m_vaddr, addr) = value;
}
