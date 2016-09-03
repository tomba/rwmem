#include <string>

class RegMap
{
public:
	RegMap(const std::string& filename, uint64_t offset, uint64_t length, bool read_only);
	~RegMap();

private:
	int m_fd;
	void* m_vaddr;
};
