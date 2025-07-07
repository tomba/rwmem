#pragma once

// Note: values stored in the register file
enum class Endianness {
	Default = 0,
	Big = 1,
	Little = 2,
	BigSwapped = 3, // Big endian, 16/32 bit words swapped
	LittleSwapped = 4, // Little endian, 16/32 bit words swapped
};
