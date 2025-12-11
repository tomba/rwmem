#pragma once

#include <cerrno>
#include <cstdint>
#include <cstdio>
#include <string>
#include <vector>
#include <format>

#define unlikely(x) __builtin_expect(!!(x), 0)

void err_vprint(std::string_view fmt, std::format_args args);

void errno_vprint(int eno, std::string_view fmt, std::format_args args);

template<typename... Args>
void print(std::format_string<Args...> format_str, Args&&... args)
{
	std::fputs(std::format(format_str, std::forward<Args>(args)...).c_str(), stdout);
}

template<typename... Args>
void eprint(std::format_string<Args...> format_str, Args&&... args)
{
	std::fputs(std::format(format_str, std::forward<Args>(args)...).c_str(), stderr);
}

template<typename... Args>
void ERR(std::format_string<Args...> format_str, Args&&... args)
{
	const auto& vargs = std::make_format_args(args...);
	err_vprint(format_str.get(), vargs);
	exit(1);
}

template<typename... Args>
void ERR_ON(bool condition, std::format_string<Args...> format_str, Args&&... args)
{
	if (unlikely(condition)) {
		const auto& vargs = std::make_format_args(args...);
		err_vprint(format_str.get(), vargs);
		exit(1);
	}
}

template<typename... Args>
void ERR_ON_ERRNO(bool condition, std::format_string<Args...> format_str, Args&&... args)
{
	if (unlikely(condition)) {
		int eno = errno;
		const auto& vargs = std::make_format_args(args...);
		errno_vprint(eno, format_str.get(), vargs);
		exit(1);
	}
}

#define GENMASK(h, l) (((~0ULL) << (l)) & (~0ULL >> (64 - 1 - (h))))

void split(const std::string& s, char delim, std::vector<std::string>& elems);
std::vector<std::string> split(const std::string& s, char delim);

int parse_u64(const std::string& str, uint64_t* value);

int fls(uint64_t num);
#define DIV_ROUND_UP(n, d) (((n) + (d) - 1) / (d))

bool file_exists(const std::string& name);

std::string get_home();
