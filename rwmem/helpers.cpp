#include <string>
#include <sstream>
#include <vector>

#include <cctype>
#include <cerrno>
#include <cstdio>
#include <cstdlib>

#include <cstdarg>
#include <cstring>
#include <sys/stat.h>

#include "helpers.h"

using namespace std;

void err_vprint(fmt::string_view fmt, fmt::format_args args)
{
	fmt::vprint(stderr, fmt, args);
	fputc('\n', stderr);
}

void errno_vprint(int eno, fmt::string_view fmt, fmt::format_args args)
{
	fmt::vprint(stderr, fmt, args);
	fmt::print(": {}\n", strerror(eno));
}

void split(const string& s, char delim, vector<string>& elems)
{
	stringstream ss(s);
	string item;

	while (getline(ss, item, delim))
		elems.push_back(item);
}

vector<string> split(const string& s, char delim)
{
	vector<string> elems;
	split(s, delim, elems);
	return elems;
}

int parse_u64(const std::string& str, uint64_t* value)
{
	uint64_t v;
	char* endptr;

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

bool file_exists(const string& name)
{
	struct stat buffer;
	return (stat(name.c_str(), &buffer) == 0);
}

std::string get_home()
{
	char *p = getenv("HOME");
	if (!p)
		throw runtime_error("Failed to get home directory");

	return string(p);
}
