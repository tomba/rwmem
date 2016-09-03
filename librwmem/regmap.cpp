#include "regmap.h"

#include <sys/mman.h>
#include <sys/types.h>
#include <sys/stat.h>
#include <fcntl.h>
#include <unistd.h>
#include <inttypes.h>

#include "helpers.h"

using namespace std;

RegMap::RegMap(const string& filename, uint64_t offset, uint64_t length, bool read_only)
{
	m_fd = open(filename.c_str(), (read_only ? O_RDONLY : O_RDWR) | O_SYNC);

	ERR_ON_ERRNO(m_fd == -1, "Failed to open file '%s'", filename.c_str());

	const unsigned pagesize = sysconf(_SC_PAGESIZE);
	const unsigned pagemask = pagesize - 1;

	const off_t mmap_offset = offset & ~pagemask;
	const size_t mmap_len = length + (offset & pagemask);

	printf("mmap: offset=%#" PRIx64 " length=%#" PRIx64 " mmap_offset=0x%jx mmap_len=0x%zx\n",
	       offset, length, mmap_offset, mmap_len);

	// how to do the check only for normal files?
	bool check_file_len = true;

	if (check_file_len) {
		const off_t file_len = lseek(m_fd, (size_t)0, SEEK_END);
		lseek(m_fd, 0, SEEK_SET);

		// note: use file_len only if lseek() succeeded
		ERR_ON(file_len != (off_t)-1 && file_len < mmap_offset + (off_t)mmap_len,
		       "Trying to access file past its end");
	}

	void *mmap_base = mmap(0, mmap_len,
			       PROT_READ | (read_only ? 0 : PROT_WRITE),
			       MAP_SHARED, m_fd, mmap_offset);

	ERR_ON_ERRNO(mmap_base == MAP_FAILED, "failed to mmap");

	m_vaddr = (uint8_t* )mmap_base + (offset & pagemask);

}

RegMap::~RegMap()
{
	close(m_fd);
}
