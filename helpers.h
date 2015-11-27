#pragma once

#include <vector>

uint64_t readmem(void *addr, unsigned regsize);
void writemem(void *addr, unsigned regsize, uint64_t value);

#define ERR(fmt, ...)						\
	do {							\
		fprintf(stderr, fmt "\n", ##__VA_ARGS__);	\
		exit(1);					\
	} while(0)

#define ERR_ON(condition, fmt, ...)			\
	do {						\
		if (condition)				\
			ERR(fmt, ##__VA_ARGS__);	\
	} while (0)

#define ERR_ERRNO(fmt, ...)							\
	do {									\
		fprintf(stderr, fmt ": %s\n", ##__VA_ARGS__, strerror(errno));	\
		exit(1);							\
	} while(0)

#define ERR_ON_ERRNO(condition, fmt, ...)		\
	do {						\
		if (condition)				\
			ERR_ERRNO(fmt, ##__VA_ARGS__);	\
	} while (0)

#define GENMASK(h, l) (((~0ULL) << (l)) & (~0ULL >> (64 - 1 - (h))))

void split(const std::string &s, char delim, std::vector<std::string> &elems);
std::vector<std::string> split(const std::string &s, char delim);

int parse_u64(const std::string& str, uint64_t *value);
