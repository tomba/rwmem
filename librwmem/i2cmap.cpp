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

I2CMap::I2CMap(unsigned adapter_nr, uint16_t i2c_addr)
	: m_i2c_addr(i2c_addr)
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

uint64_t I2CMap::read(uint64_t addr, unsigned numbytes) const
{
	uint8_t buf[8] { };
	uint8_t reg_addr = (uint8_t)addr;

	struct i2c_msg msgs[2] { };

	msgs[0].addr = m_i2c_addr;
	msgs[0].flags = 0;
	msgs[0].len = 1;
	msgs[0].buf = &reg_addr;

	msgs[1].addr = m_i2c_addr;
	msgs[1].flags = I2C_M_RD;
	msgs[1].len = numbytes;
	msgs[1].buf = buf;

	struct i2c_rdwr_ioctl_data data;
	data.msgs = msgs;
	data.nmsgs = 2;

	int r = ioctl(m_fd, I2C_RDWR, &data);
	ERR_ON_ERRNO(r < 0, "i2c transfer failed");

	switch (numbytes) {
	case 1:
		return buf[0];
	case 2:
		return be16toh(*((uint16_t*)buf));
	case 4:
		return be32toh(*((uint32_t*)buf));
	case 8:
		return be64toh(*((uint64_t*)buf));
	default:
		abort();
	}
}

void I2CMap::write(uint64_t addr, unsigned numbytes, uint64_t value)
{
	uint8_t reg_addr = (uint8_t)addr;
	uint8_t buf[8];

	switch (numbytes) {
	case 1:
		buf[0] = value & 0xff;
		break;
	case 4: {
		uint32_t v32 = htobe32((uint32_t)value);
		buf[0] = (v32 >> 0) & 0xff;
		buf[1] = (v32 >> 8) & 0xff;
		buf[2] = (v32 >> 16) & 0xff;
		buf[3] = (v32 >> 24) & 0xff;
		break;
	}
	default:
		abort();
	}

	struct i2c_msg msgs[2] { };

	msgs[0].addr = m_i2c_addr;
	msgs[0].flags = 0;
	msgs[0].len = 1;
	msgs[0].buf = &reg_addr;

	msgs[1].addr = m_i2c_addr;
	msgs[1].flags = 0;
	msgs[1].len = numbytes;
	msgs[1].buf = buf;

	struct i2c_rdwr_ioctl_data data;
	data.msgs = msgs;
	data.nmsgs = 2;

	int r = ioctl(m_fd, I2C_RDWR, &data);
	ERR_ON_ERRNO(r < 0, "i2c transfer failed");
}
