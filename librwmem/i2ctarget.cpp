#include "i2ctarget.h"
#include "helpers.h"

#include <fmt/format.h>
#include <stdexcept>
#include <sys/types.h>
#include <sys/stat.h>
#include <fcntl.h>
#include <unistd.h>
#include <linux/i2c.h>
#include <linux/i2c-dev.h>
#include <sys/ioctl.h>

using namespace std;

I2CTarget::I2CTarget(uint16_t adapter_nr, uint16_t i2c_addr)
	: m_adapter_nr(adapter_nr), m_i2c_addr(i2c_addr), m_fd(-1), m_offset(0)
{

}

I2CTarget::~I2CTarget()
{
	unmap();
}

void I2CTarget::map(uint64_t offset, uint64_t length,
		 Endianness default_addr_endianness, uint8_t default_addr_size,
		 Endianness default_data_endianness, uint8_t default_data_size,
		 MapMode mode)
{
	unmap();

	string name = fmt::format("/dev/i2c-{}", m_adapter_nr);

	m_fd = open(name.c_str(), O_RDWR);
	ERR_ON_ERRNO(m_fd < 0, "Failed to open i2c device");

	unsigned long i2c_funcs;
	int r = ioctl(m_fd, I2C_FUNCS, &i2c_funcs);
	ERR_ON_ERRNO(r < 0, "failed to get i2c functions");

	ERR_ON(!(i2c_funcs & I2C_FUNC_I2C), "no i2c functionality");

	m_offset = offset;
	m_address_endianness = default_addr_endianness;
	m_address_bytes = default_addr_size;
	m_data_endianness = default_data_endianness;
	m_data_bytes = default_data_size;
}

void I2CTarget::unmap()
{
	if (m_fd == -1)
		return;

	close(m_fd);

	m_fd = -1;
}

static uint32_t swap32(uint32_t v)
{
	return (v << 16) | (v >> 16);
}

static uint64_t swap64(uint64_t v)
{
	return (v << 32) | (v >> 32);
}

static uint64_t device_to_host(uint8_t buf[], unsigned numbytes, Endianness endianness)
{
	switch (numbytes) {
	case 1:
		return buf[0];
	case 2: {
		uint16_t v = *((uint16_t*)buf);

		switch (endianness) {
		case Endianness::Big:
			return be16toh(v);
		case Endianness::Little:
			return le16toh(v);
		default:
			throw invalid_argument("Bad endianness");
		}
	}
	case 4: {
		uint32_t v = *((uint32_t*)buf);

		switch (endianness) {
		case Endianness::Big:
			return be32toh(v);
		case Endianness::Little:
			return le32toh(v);
		case Endianness::BigSwapped:
			return swap32(be32toh(v));
		case Endianness::LittleSwapped:
			return swap32(le32toh(v));
		default:
			throw invalid_argument("Bad endianness");
		}
	}
	case 8: {
		uint64_t v = *((uint64_t*)buf);

		switch (endianness) {
		case Endianness::Big:
			return be64toh(v);
		case Endianness::Little:
			return le64toh(v);
		case Endianness::BigSwapped:
			return swap64(be64toh(v));
		case Endianness::LittleSwapped:
			return swap64(le64toh(v));
		default:
			throw invalid_argument("Bad endianness");
		}
	}
	default:
		abort();
	}
}

static void host_to_device(uint64_t value, unsigned numbytes, uint8_t buf[], Endianness endianness)
{
	switch (numbytes) {
	case 1:
		buf[0] = value & 0xff;
		break;
	case 2: {
		uint16_t v = (uint16_t)value;
		uint16_t* p = (uint16_t*)buf;

		switch (endianness) {
		case Endianness::Big:
			*p = htobe16(v);
			break;
		case Endianness::Little:
			*p = htole16(v);
			break;
		default:
			throw invalid_argument("Bad endianness");
		}

		break;
	}
	case 4: {
		uint32_t v = (uint32_t)value;
		uint32_t* p = (uint32_t*)buf;

		switch (endianness) {
		case Endianness::Big:
			*p = htobe32(v);
			break;
		case Endianness::Little:
			*p = htole32(v);
			break;
		case Endianness::BigSwapped:
			*p = swap32(htobe32(v));
			break;
		case Endianness::LittleSwapped:
			*p = swap32(htole32(v));
			break;
		default:
			throw invalid_argument("Bad endianness");
		}

		break;
	}
	case 8: {
		uint64_t v = (uint64_t)value;
		uint64_t* p = (uint64_t*)buf;

		switch (endianness) {
		case Endianness::Big:
			*p = htobe64(v);
			break;
		case Endianness::Little:
			*p = htole64(v);
			break;
		case Endianness::BigSwapped:
			*p = swap64(htobe64(v));
			break;
		case Endianness::LittleSwapped:
			*p = swap64(htole64(v));
			break;
		default:
			throw invalid_argument("Bad endianness");
		}

		break;
	}
	default:
		abort();
	}
}

uint64_t I2CTarget::read(uint64_t addr, uint8_t nbytes, Endianness endianness) const
{
	if (!nbytes)
		nbytes = m_data_bytes;

	if (endianness == Endianness::Default)
		endianness = m_data_endianness;

	addr += m_offset;

	uint8_t addr_buf[8]{};
	uint8_t data_buf[8]{};

	host_to_device(addr, m_address_bytes, addr_buf, m_address_endianness);

	struct i2c_msg msgs[2]{};

	msgs[0].addr = m_i2c_addr;
	msgs[0].flags = 0;
	msgs[0].len = m_address_bytes;
	msgs[0].buf = addr_buf;

	msgs[1].addr = m_i2c_addr;
	msgs[1].flags = I2C_M_RD;
	msgs[1].len = nbytes;
	msgs[1].buf = data_buf;

	struct i2c_rdwr_ioctl_data data;
	data.msgs = msgs;
	data.nmsgs = 2;

	int r = ioctl(m_fd, I2C_RDWR, &data);
	ERR_ON_ERRNO(r < 0, "i2c transfer failed");

	return device_to_host(data_buf, nbytes, endianness);
}

void I2CTarget::write(uint64_t addr, uint64_t value, uint8_t nbytes, Endianness endianness)
{
	if (!nbytes)
		nbytes = m_data_bytes;

	if (endianness == Endianness::Default)
		endianness = m_data_endianness;

	addr += m_offset;

	uint8_t data_buf[12]{};

	host_to_device(addr, m_address_bytes, data_buf, m_address_endianness);

	host_to_device(value, nbytes, data_buf + m_address_bytes, endianness);

	struct i2c_msg msgs[1]{};

	msgs[0].addr = m_i2c_addr;
	msgs[0].flags = 0;
	msgs[0].len = m_address_bytes + nbytes;
	msgs[0].buf = data_buf;

	struct i2c_rdwr_ioctl_data data;
	data.msgs = msgs;
	data.nmsgs = 1;

	int r = ioctl(m_fd, I2C_RDWR, &data);
	ERR_ON_ERRNO(r < 0, "i2c transfer failed");
}
