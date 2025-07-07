#pragma once

#include <cerrno>
#include <cstdint>
#include <string>
#include <vector>
#include <string.h>
#include <fmt/format.h>

#define unlikely(x) __builtin_expect(!!(x), 0)

void err_vprint(fmt::string_view fmt, fmt::format_args args);

void errno_vprint(int eno, fmt::string_view fmt, fmt::format_args args);

template<typename... Args>
void ERR(fmt::format_string<Args...> format_str, Args&&... args)
{
	const auto& vargs = fmt::make_format_args(args...);
	err_vprint(format_str, vargs);
	exit(1);
}

template<typename... Args>
void ERR_ON(bool condition, fmt::format_string<Args...> format_str, Args&&... args)
{
	if (unlikely(condition)) {
		const auto& vargs = fmt::make_format_args(args...);
		err_vprint(format_str, vargs);
		exit(1);
	}
}

template<typename... Args>
void ERR_ERRNO(fmt::format_string<Args...> format_str, Args&&... args)
{
	int eno = errno;
	const auto& vargs = fmt::make_format_args(args...);
	errno_vprint(eno, format_str, vargs);
	exit(1);
}

template<typename... Args>
void ERR_ON_ERRNO(bool condition, fmt::format_string<Args...> format_str, Args&&... args)
{
	if (unlikely(condition)) {
		int eno = errno;
		const auto& vargs = fmt::make_format_args(args...);
		errno_vprint(eno, format_str, vargs);
		exit(1);
	}
}

#define FAIL(format_str, ...)                                                               \
	do {                                                                                \
		fmt::print(stderr, "{}:{}: {}\n", __FILE__, __LINE__, __PRETTY_FUNCTION__); \
		ERR(format_str, ##__VA_ARGS__);                                             \
		abort();                                                                    \
	} while (0)

#define FAIL_IF(condition, format_str, ...)              \
	do {                                             \
		if (unlikely(condition))                 \
			FAIL(format_str, ##__VA_ARGS__); \
	} while (0)

#define GENMASK(h, l) (((~0ULL) << (l)) & (~0ULL >> (64 - 1 - (h))))

void split(const std::string& s, char delim, std::vector<std::string>& elems);
std::vector<std::string> split(const std::string& s, char delim);

int parse_u64(const std::string& str, uint64_t* value);

int fls(uint64_t num);
#define DIV_ROUND_UP(n, d) (((n) + (d)-1) / (d))

bool file_exists(const std::string& name);

std::string get_home();
