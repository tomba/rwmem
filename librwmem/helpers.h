#pragma once

#include <vector>
#include <string.h>

#define unlikely(x) __builtin_expect(!!(x), 0)

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

#define FAIL(fmt, ...)		\
	do {			\
		fprintf(stderr, "%s:%d: %s:\n" fmt "\n", __FILE__, __LINE__, __PRETTY_FUNCTION__, ##__VA_ARGS__); \
		abort();	\
	} while(0)

#define FAIL_IF(x, fmt, ...)				\
	do {						\
		if (unlikely(x))			\
			FAIL(fmt, ##__VA_ARGS__);	\
	} while(0)

#define GENMASK(h, l) (((~0ULL) << (l)) & (~0ULL >> (64 - 1 - (h))))

void split(const std::string &s, char delim, std::vector<std::string> &elems);
std::vector<std::string> split(const std::string &s, char delim);

int parse_u64(const std::string& str, uint64_t *value);

int fls(uint64_t num);
#define DIV_ROUND_UP(n,d) (((n) + (d) - 1) / (d))

// Not thread safe
std::string sformat(const char *fmt, ...);

std::string to_binary_str(uint64_t value, uint8_t numbits);

enum class Endianness
{
	Default = 0,
	Big,
	Little,
};
