#include "test_data_generator.h"

#include <algorithm>
#include <cstring>

// Constants from regfiledata.h
static const uint32_t RWMEM_MAGIC = 0x00e11554;
static const uint32_t RWMEM_VERSION = 2;

uint32_t TestRegisterFileBuilder::add_string(std::map<std::string, uint32_t>& string_table,
                                            uint32_t& string_offset, const std::string& str) {
    auto it = string_table.find(str);
    if (it != string_table.end()) {
        return it->second;
    }

    uint32_t offset = string_offset;
    string_table[str] = offset;
    string_offset += str.length() + 1; // +1 for null terminator
    return offset;
}

std::vector<uint8_t> TestRegisterFileBuilder::build() {
    std::vector<uint8_t> data;

    // Sort blocks by offset (like Python version)
    std::sort(blocks.begin(), blocks.end(),
              [](const TestRegisterBlock& a, const TestRegisterBlock& b) {
                  return a.offset < b.offset;
              });

    // Count totals
    uint32_t num_blocks = blocks.size();
    uint32_t num_regs = 0;
    uint32_t num_fields = 0;

    for (auto& block : blocks) {
        num_regs += block.registers.size();
        for (auto& reg : block.registers) {
            num_fields += reg.fields.size();
        }
    }

    // Build string table
    std::map<std::string, uint32_t> string_table;
    uint32_t string_offset = 0;

    // Add empty string first (like Python version)
    add_string(string_table, string_offset, "");

    // Assign offsets and build string table
    uint32_t name_offset = add_string(string_table, string_offset, name);

    uint32_t reg_index = 0;
    uint32_t field_index = 0;

    for (auto& block : blocks) {
        // Sort registers by offset
        std::sort(block.registers.begin(), block.registers.end(),
                  [](const TestRegister& a, const TestRegister& b) {
                      return a.offset < b.offset;
                  });

        block.name_offset = add_string(string_table, string_offset, block.name);
        block.first_reg_index = reg_index;
        reg_index += block.registers.size();

        // Auto-calculate block size if not set
        if (block.size == 0 && !block.registers.empty()) {
            auto& last_reg = *std::max_element(block.registers.begin(), block.registers.end(),
                                             [](const TestRegister& a, const TestRegister& b) {
                                                 return a.offset < b.offset;
                                             });
            block.size = last_reg.offset + (block.data_size ? block.data_size : 4);
        }

        for (auto& reg : block.registers) {
            // Sort fields by high bit (descending, like Python)
            std::sort(reg.fields.begin(), reg.fields.end(),
                      [](const TestField& a, const TestField& b) {
                          return a.high > b.high;
                      });

            reg.name_offset = add_string(string_table, string_offset, reg.name);
            reg.first_field_index = field_index;
            field_index += reg.fields.size();

            for (auto& field : reg.fields) {
                field.name_offset = add_string(string_table, string_offset, field.name);
            }
        }
    }

    // Calculate section offsets
    uint32_t header_size = 6 * sizeof(uint32_t);
    uint32_t blocks_size = num_blocks * (4 + 8 + 8 + 4 + 4 + 4); // RegisterBlockData size
    uint32_t registers_size = num_regs * (4 + 8 + 4 + 4); // RegisterData size
    uint32_t fields_size = num_fields * (4 + 1 + 1); // FieldData size

    data.reserve(header_size + blocks_size + registers_size + fields_size + string_offset);

    // Write header (RegisterFileData)
    auto write_be32 = [&](uint32_t val) {
        uint32_t be_val = htobe32(val);
        data.insert(data.end(), (uint8_t*)&be_val, (uint8_t*)&be_val + 4);
    };

    auto write_be64 = [&](uint64_t val) {
        uint64_t be_val = htobe64(val);
        data.insert(data.end(), (uint8_t*)&be_val, (uint8_t*)&be_val + 8);
    };

    auto write_u8 = [&](uint8_t val) {
        data.push_back(val);
    };

    // Header
    write_be32(RWMEM_MAGIC);
    write_be32(RWMEM_VERSION);
    write_be32(name_offset);
    write_be32(num_blocks);
    write_be32(num_regs);
    write_be32(num_fields);

    // Blocks
    for (const auto& block : blocks) {
        write_be32(block.name_offset);
        write_be64(block.offset);
        write_be64(block.size);
        write_be32(block.registers.size());
        write_be32(block.first_reg_index);
        write_u8(static_cast<uint8_t>(block.addr_endianness));
        write_u8(block.addr_size);
        write_u8(static_cast<uint8_t>(block.data_endianness));
        write_u8(block.data_size);
    }

    // Registers
    for (const auto& block : blocks) {
        for (const auto& reg : block.registers) {
            write_be32(reg.name_offset);
            write_be64(reg.offset);
            write_be32(reg.fields.size());
            write_be32(reg.first_field_index);
        }
    }

    // Fields
    for (const auto& block : blocks) {
        for (const auto& reg : block.registers) {
            for (const auto& field : reg.fields) {
                write_be32(field.name_offset);
                write_u8(field.high);
                write_u8(field.low);
            }
        }
    }

    // Strings - write in offset order, not alphabetical order
    std::vector<std::pair<uint32_t, std::string>> ordered_strings;
    for (const auto& [str, offset] : string_table) {
        ordered_strings.emplace_back(offset, str);
    }
    std::sort(ordered_strings.begin(), ordered_strings.end());

    for (const auto& [offset, str] : ordered_strings) {
        data.insert(data.end(), str.begin(), str.end());
        data.push_back('\0');
    }

    return data;
}