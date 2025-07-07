#pragma once

#include <cstdint>
#include <stdexcept>
#include <map>
#include <string>
#include <vector>

#include "../librwmem/endianness.h"

/**
 * C++ Test Data Generator for Register Files
 *
 * Simple test data structures for creating register files in unit tests.
 * Mirrors the functionality of py/rwmem/gen.py with public fields for simplicity.
 */

struct TestField {
    std::string name;
    uint8_t high;
    uint8_t low;
    uint32_t name_offset = 0;

    TestField(const std::string& n, uint8_t h, uint8_t l)
        : name(n), high(h), low(l) {}
};

struct TestRegister {
    std::string name;
    uint64_t offset;
    std::vector<TestField> fields;
    uint32_t name_offset = 0;
    uint32_t first_field_index = 0;

    TestRegister(const std::string& n, uint64_t off)
        : name(n), offset(off) {}

    TestRegister& add_field(const std::string& name, uint8_t high, uint8_t low) {
        fields.emplace_back(name, high, low);
        return *this;
    }
};

struct TestRegisterBlock {
    std::string name;
    uint64_t offset;
    uint64_t size;
    Endianness addr_endianness;
    uint8_t addr_size;
    Endianness data_endianness;
    uint8_t data_size;
    std::vector<TestRegister> registers;
    uint32_t name_offset = 0;
    uint32_t first_reg_index = 0;

    TestRegisterBlock(const std::string& n, uint64_t off, uint64_t sz,
                     Endianness addr_end = Endianness::Little, uint8_t addr_sz = 4,
                     Endianness data_end = Endianness::Little, uint8_t data_sz = 4)
        : name(n), offset(off), size(sz), addr_endianness(addr_end), addr_size(addr_sz),
          data_endianness(data_end), data_size(data_sz) {}

    TestRegisterBlock& add_register(const std::string& name, uint64_t offset) {
        registers.emplace_back(name, offset);
        return *this;
    }
};

class TestRegisterFileBuilder {
public:
    std::string name;
    std::vector<TestRegisterBlock> blocks;

    explicit TestRegisterFileBuilder(const std::string& n) : name(n) {}

    TestRegisterFileBuilder& add_block(const std::string& name, uint64_t offset, uint64_t size = 0,
                                      Endianness addr_end = Endianness::Little, uint8_t addr_size = 4,
                                      Endianness data_end = Endianness::Little, uint8_t data_size = 4) {
        blocks.emplace_back(name, offset, size, addr_end, addr_size, data_end, data_size);
        return *this;
    }

    TestRegisterFileBuilder& add_register(const std::string& name, uint64_t offset) {
        if (blocks.empty()) {
            throw std::runtime_error("No blocks available - add a block first");
        }
        blocks.back().add_register(name, offset);
        return *this;
    }

    TestRegisterFileBuilder& add_field(const std::string& name, uint8_t high, uint8_t low) {
        if (blocks.empty() || blocks.back().registers.empty()) {
            throw std::runtime_error("No register available - add a register first");
        }
        blocks.back().registers.back().add_field(name, high, low);
        return *this;
    }

    // Build the binary register file
    std::vector<uint8_t> build();

private:
    uint32_t add_string(std::map<std::string, uint32_t>& string_table,
                       uint32_t& string_offset, const std::string& str);
};