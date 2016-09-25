#include "i2cmap.h"
#include "helpers.h"

#include <sys/types.h>
#include <sys/stat.h>
#include <fcntl.h>
#include <unistd.h>
#include <linux/i2c.h>
#include <linux/i2c-dev.h>
#include <sys/ioctl.h>

using namespace std;

I2CMap::I2CMap(unsigned adapter_nr, uint16_t i2c_addr,
	       uint16_t addr_len, Endianness addr_endianness, Endianness data_endianness)
	: m_i2c_addr(i2c_addr),
	  m_address_bytes(addr_len), m_address_endianness(addr_endianness),
	  m_data_endianness(data_endianness)
{
	string name("/dev/i2c-");
	name += to_string(adapter_nr);

	m_fd = open(name.c_str(), O_RDWR);
	ERR_ON_ERRNO(m_fd < 0, "Failed to open i2c device");

	unsigned long i2c_funcs;
	int r = ioctl(m_fd, I2C_FUNCS, &i2c_funcs);
	ERR_ON_ERRNO(r < 0, "failed to get i2c functions");

	ERR_ON(!(i2c_funcs & I2C_FUNC_I2C), "no i2c functionality");
}

I2CMap::~I2CMap()
{
	close(m_fd);
}

static uint64_t device_to_host(uint8_t buf[], unsigned numbytes, Endianness endianness)
{
	switch (numbytes) {
	case 1:
		return buf[0];
	case 2:
		if (endianness == Endianness::Big)
			return be16toh(*((uint16_t*)buf));
		else
			return le16toh(*((uint16_t*)buf));
	case 4:
		if (endianness == Endianness::Big)
			return be32toh(*((uint32_t*)buf));
		else
			return le32toh(*((uint32_t*)buf));
	case 8:
		if (endianness == Endianness::Big)
			return be64toh(*((uint64_t*)buf));
		else
			return le64toh(*((uint64_t*)buf));
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
	case 2:
		if (endianness == Endianness::Big)
			*((uint16_t*)buf) = htobe16((uint16_t)value);
		else
			*((uint16_t*)buf) = htole16((uint16_t)value);
		break;
	case 4:
		if (endianness == Endianness::Big)
			*((uint32_t*)buf) = htobe32((uint32_t)value);
		else
			*((uint32_t*)buf) = htole32((uint32_t)value);
		break;
	case 8:
		if (endianness == Endianness::Big)
			*((uint64_t*)buf) = htobe64((uint64_t)value);
		else
			*((uint64_t*)buf) = htole64((uint64_t)value);
		break;
	default:
		abort();
	}
}

uint64_t I2CMap::read(uint64_t addr, unsigned numbytes) const
{
	uint8_t addr_buf[8] { };
	uint8_t data_buf[8] { };

	host_to_device(addr, m_address_bytes, addr_buf, m_address_endianness);

	struct i2c_msg msgs[2] { };

	msgs[0].addr = m_i2c_addr;
	msgs[0].flags = 0;
	msgs[0].len = m_address_bytes;
	msgs[0].buf = addr_buf;

	msgs[1].addr = m_i2c_addr;
	msgs[1].flags = I2C_M_RD;
	msgs[1].len = numbytes;
	msgs[1].buf = data_buf;

	struct i2c_rdwr_ioctl_data data;
	data.msgs = msgs;
	data.nmsgs = 2;

	int r = ioctl(m_fd, I2C_RDWR, &data);
	ERR_ON_ERRNO(r < 0, "i2c transfer failed");

	return device_to_host(data_buf, numbytes, m_data_endianness);
}

void I2CMap::write(uint64_t addr, unsigned numbytes, uint64_t value)
{
	uint8_t addr_buf[8] { };
	uint8_t data_buf[8] { };

	host_to_device(addr, m_address_bytes, addr_buf, m_address_endianness);

	host_to_device(value, numbytes, data_buf, m_data_endianness);

	struct i2c_msg msgs[2] { };

	msgs[0].addr = m_i2c_addr;
	msgs[0].flags = 0;
	msgs[0].len = m_address_bytes;
	msgs[0].buf = addr_buf;

	msgs[1].addr = m_i2c_addr;
	msgs[1].flags = 0;
	msgs[1].len = numbytes;
	msgs[1].buf = data_buf;

	struct i2c_rdwr_ioctl_data data;
	data.msgs = msgs;
	data.nmsgs = 2;

	int r = ioctl(m_fd, I2C_RDWR, &data);
	ERR_ON_ERRNO(r < 0, "i2c transfer failed");
}
