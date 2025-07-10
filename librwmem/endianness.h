#pragma once

#include <bit>

// Note: values stored in the register file
enum class Endianness {
	Default = 0,
	Big = 1,
	Little = 2,
	BigSwapped = 3, // Big endian, 16/32 bit words swapped
	LittleSwapped = 4, // Little endian, 16/32 bit words swapped
};


template<typename T>
static T byteswap(T value)
{
	if constexpr (sizeof(T) == 1)
		return value;
	else if constexpr (sizeof(T) == 2)
		return __builtin_bswap16(value);
	else if constexpr (sizeof(T) == 4)
		return __builtin_bswap32(value);
	else if constexpr (sizeof(T) == 8)
		return __builtin_bswap64(value);
	static_assert(sizeof(T) <= 8, "Unsupported size for byteswap");
}

template<typename T>
static T betoh(T value)
{
	if constexpr (std::endian::native == std::endian::little)
		return byteswap(value);
	else
		return value;
}

template<typename T>
static T letoh(T value)
{
	if constexpr (std::endian::native == std::endian::big)
		return byteswap(value);
	else
		return value;
}

template<typename T>
static T htobe(T value)
{
	if constexpr (std::endian::native == std::endian::little)
		return byteswap(value);
	else
		return value;
}

template<typename T>
static T htole(T value)
{
	if constexpr (std::endian::native == std::endian::big)
		return byteswap(value);
	else
		return value;
}


template<typename T>
static T wordswap(T value)
{
	if constexpr (sizeof(T) == 4)
		return (value << 16) | (value >> 16);
	else if constexpr (sizeof(T) == 8)
		return (value << 32) | (value >> 32);
	else
		return value;
}

template<typename T>
static T to_host(T value, Endianness endianness)
{
	switch (endianness) {
	case Endianness::Big:
		return betoh(value);
	case Endianness::Little:
		return letoh(value);
	case Endianness::BigSwapped:
		return wordswap(betoh(value));
	case Endianness::LittleSwapped:
		return wordswap(letoh(value));
	default:
		return value;
	}
}

template<typename T>
static T from_host(T value, Endianness endianness)
{
	switch (endianness) {
	case Endianness::Big:
		return htobe(value);
	case Endianness::Little:
		return htole(value);
	case Endianness::BigSwapped:
		return htobe(wordswap(value));
	case Endianness::LittleSwapped:
		return htole(wordswap(value));
	default:
		return value;
	}
}
