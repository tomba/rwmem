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

string sformat(const char *fmt, ...)
{
	static char s_format_buf[1024];

	va_list args;
	va_start(args, fmt);

	vsnprintf(s_format_buf, sizeof(s_format_buf), fmt, args);

	va_end(args);

	return string(s_format_buf);
}

string to_binary_str(uint64_t value, uint8_t numbits)
{
	string s = "0b";

	for (unsigned i = 0; i < numbits; ++i) {
		uint8_t b = (value >> (numbits - i)) & 1;

		s += b ? '1' : '0';
	}

	return s;
}
