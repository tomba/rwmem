#include <string>
#include <sstream>
#include <vector>

#include <ctype.h>
#include <errno.h>
#include <inttypes.h>
#include <stdio.h>
#include <stdlib.h>
#include <stdbool.h>
#include <stdarg.h>
#include <string.h>

#include "helpers.h"

using namespace std;

uint64_t readmem(void *addr, unsigned regsize)
{
	switch (regsize) {
	case 1:
		return *((uint8_t *)addr);
	case 2:
		return *((uint16_t *)addr);
	case 4:
		return *((uint32_t *)addr);
	case 8:
		return *((uint64_t *)addr);
	default:
		ERR("Illegal data regsize '%d'", regsize);
	}
}

void writemem(void *addr, unsigned regsize, uint64_t value)
{
	switch (regsize) {
	case 1:
		*((uint8_t *)addr) = value;
		break;
	case 2:
		*((uint16_t *)addr) = value;
		break;
	case 4:
		*((uint32_t *)addr) = value;
		break;
	case 8:
		*((uint64_t *)addr) = value;
		break;
	default:
		ERR("Illegal data regsize '%d'", regsize);
	}
}

void split(const string &s, char delim, vector<string> &elems)
{
	stringstream ss(s);
	string item;

	while (getline(ss, item, delim))
		elems.push_back(item);
}

vector<string> split(const string &s, char delim)
{
	vector<string> elems;
	split(s, delim, elems);
	return elems;
}

int parse_u64(const std::string& str, uint64_t *value)
{
	uint64_t v;
	char *endptr;

	v = strtoull(str.c_str(), &endptr, 0);
	if (*endptr != 0)
		return -EINVAL;

	*value = v;
	return 0;
}

int fls(uint64_t num)
{
	int i = 0;
	while (num >>= 1)
		++i;
	return i;
}
