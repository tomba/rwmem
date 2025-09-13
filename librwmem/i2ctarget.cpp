#include "i2ctarget.h"

#include <fmt/format.h>
#include <stdexcept>
#include <cstring>
#include <sys/types.h>
#include <sys/stat.h>
#include <fcntl.h>
#include <unistd.h>
#include <linux/i2c.h>
#include <linux/i2c-dev.h>
#include <sys/ioctl.h>

using namespace std;

I2CTarget::I2CTarget(uint16_t adapter_nr, uint16_t i2c_addr)
	: m_adapter_nr(adapter_nr), m_i2c_addr(i2c_addr), m_fd(-1),
	  m_address_bytes(0), m_address_endianness(Endianness::Default),
	  m_data_bytes(0), m_data_endianness(Endianness::Default)
{
}

I2CTarget::~I2CTarget()
{
	I2CTarget::unmap();
}

void I2CTarget::map(uint64_t offset, uint64_t length,
		    Endianness default_addr_endianness, uint8_t default_addr_size,
		    Endianness default_data_endianness, uint8_t default_data_size,
		    MapMode mode)
{
	unmap();

	string name = fmt::format("/dev/i2c-{}", m_adapter_nr);

	m_fd = open(name.c_str(), O_RDWR);
	if (m_fd < 0)
		throw runtime_error(fmt::format("Failed to open i2c device: {}", strerror(errno)));

	unsigned long i2c_funcs;
	int r = ioctl(m_fd, I2C_FUNCS, &i2c_funcs);
	if (r < 0)
		throw runtime_error(fmt::format("failed to get i2c functions: {}", strerror(errno)));

	if (!(i2c_funcs & I2C_FUNC_I2C))
		throw runtime_error("no i2c functionality");

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

static uint64_t device_to_host(uint8_t buf[], unsigned numbytes, Endianness endianness)
{
	if (numbytes == 0 || numbytes > 8)
		throw invalid_argument(fmt::format("Invalid number of bytes: {}", numbytes));

	if (numbytes == 1)
		return buf[0];

	// For standard sizes, use typed access for potential efficiency
	if (numbytes == 2 || numbytes == 4 || numbytes == 8) {
		switch (numbytes) {
		case 2: {
			uint16_t v = *((uint16_t*)buf);
			return to_host(v, endianness);
		}
		case 4: {
			uint32_t v = *((uint32_t*)buf);
			return to_host(v, endianness);
		}
		case 8: {
			uint64_t v = *((uint64_t*)buf);
			return to_host(v, endianness);
		}
		}
	}

	// For arbitrary sizes, use byte-oriented access
	uint64_t result = 0;
	if (endianness == Endianness::Little) {
		for (unsigned i = 0; i < numbytes; i++) {
			result |= ((uint64_t)buf[i]) << (i * 8);
		}
	} else {
		for (unsigned i = 0; i < numbytes; i++) {
			result = (result << 8) | buf[i];
		}
	}
	return result;
}

static void host_to_device(uint64_t value, unsigned numbytes, uint8_t buf[], Endianness endianness)
{
	if (numbytes == 0 || numbytes > 8)
		throw invalid_argument(fmt::format("Invalid number of bytes: {}", numbytes));

	if (numbytes == 1) {
		buf[0] = value & 0xff;
		return;
	}

	// For standard sizes, use typed access for potential efficiency
	if (numbytes == 2 || numbytes == 4 || numbytes == 8) {
		switch (numbytes) {
		case 2: {
			uint16_t v = (uint16_t)value;
			uint16_t* p = (uint16_t*)buf;
			*p = from_host(v, endianness);
			break;
		}
		case 4: {
			uint32_t v = (uint32_t)value;
			uint32_t* p = (uint32_t*)buf;
			*p = from_host(v, endianness);
			break;
		}
		case 8: {
			uint64_t v = (uint64_t)value;
			uint64_t* p = (uint64_t*)buf;
			*p = from_host(v, endianness);
			break;
		}
		}
		return;
	}

	// For arbitrary sizes, use byte-oriented access
	if (endianness == Endianness::Little) {
		for (unsigned i = 0; i < numbytes; i++) {
			buf[i] = (value >> (i * 8)) & 0xff;
		}
	} else {
		for (unsigned i = 0; i < numbytes; i++) {
			buf[i] = (value >> ((numbytes - 1 - i) * 8)) & 0xff;
		}
	}
}

uint64_t I2CTarget::read(uint64_t addr, uint8_t nbytes, Endianness endianness) const
{
	if (!nbytes)
		nbytes = m_data_bytes;

	if (endianness == Endianness::Default)
		endianness = m_data_endianness;

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
	if (r < 0)
		throw runtime_error(fmt::format("i2c transfer failed: {}", strerror(errno)));

	return device_to_host(data_buf, nbytes, endianness);
}

void I2CTarget::write(uint64_t addr, uint64_t value, uint8_t nbytes, Endianness endianness)
{
	if (!nbytes)
		nbytes = m_data_bytes;

	if (endianness == Endianness::Default)
		endianness = m_data_endianness;

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
	if (r < 0)
		throw runtime_error(fmt::format("i2c transfer failed: {}", strerror(errno)));
}
