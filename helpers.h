#pragma once

#include <vector>

uint64_t readmem(void *addr, unsigned regsize);
void writemem(void *addr, unsigned regsize, uint64_t value);

__attribute__ ((noreturn))
void myerr(const char* format, ... );

__attribute__ ((noreturn))
void myerr2(const char* format, ... );

#define ERR(format...) myerr(format)

#define ERR_ON(condition, format...) do {	\
	if (condition)				\
		ERR(format);			\
} while (0)

#define ERR_ERRNO(format...) myerr2(format)

#define ERR_ON_ERRNO(condition, format...) do {	\
	if (condition)				\
		ERR_ERRNO(format);		\
} while (0)

#define GENMASK(h, l) (((~0ULL) << (l)) & (~0ULL >> (64 - 1 - (h))))

void split(const std::string &s, char delim, std::vector<std::string> &elems);
std::vector<std::string> split(const std::string &s, char delim);
