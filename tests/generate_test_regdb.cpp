#include "test_data_generator.h"
#include <fstream>
#include <iostream>

int main() {
    // Create a test register database with standard sizes and some data that aligns with data.bin
    TestRegisterFileBuilder builder("TestChip");

    // Block 1: 8-bit registers at offset 0x00
    builder.add_block("ByteRegs", 0x00, 0x10,
                     Endianness::Little, 4,  // address: little endian, 4 bytes
                     Endianness::Little, 1); // data: little endian, 1 byte

    builder.add_register("BYTE0", 0x00)
           .add_field("VAL", 7, 0);

    builder.add_register("BYTE1", 0x01)
           .add_field("VAL", 7, 0);

    builder.add_register("BYTE4", 0x04)
           .add_field("VAL", 7, 0);

    // Block 2: 16-bit registers at offset 0x10
    builder.add_block("WordRegs", 0x10, 0x20,
                     Endianness::Little, 4,  // address: little endian, 4 bytes
                     Endianness::Little, 2); // data: little endian, 2 bytes

    builder.add_register("WORD0", 0x10)
           .add_field("HIGH", 15, 8)
           .add_field("LOW", 7, 0);

    builder.add_register("WORD2", 0x12)
           .add_field("VAL", 15, 0);

    // Block 3: 32-bit registers at offset 0x20
    builder.add_block("DwordRegs", 0x20, 0x40,
                     Endianness::Little, 4,  // address: little endian, 4 bytes
                     Endianness::Little, 4); // data: little endian, 4 bytes

    builder.add_register("DWORD0", 0x20)
           .add_field("BITS31_24", 31, 24)
           .add_field("BITS23_16", 23, 16)
           .add_field("BITS15_8", 15, 8)
           .add_field("BITS7_0", 7, 0);

    builder.add_register("CONTROL", 0x24)
           .add_field("ENABLE", 31, 31)
           .add_field("MODE", 30, 28)
           .add_field("STATUS", 27, 24)
           .add_field("VALUE", 23, 0);

    // Block 4: 64-bit registers at offset 0x40
    builder.add_block("QwordRegs", 0x40, 0x60,
                     Endianness::Little, 4,  // address: little endian, 4 bytes
                     Endianness::Little, 8); // data: little endian, 8 bytes

    builder.add_register("QWORD0", 0x40)
           .add_field("HIGH32", 63, 32)
           .add_field("LOW32", 31, 0);

    builder.add_register("TIMESTAMP", 0x48)
           .add_field("SECONDS", 63, 32)
           .add_field("NANOSECS", 31, 0);

    // Generate the binary data
    std::vector<uint8_t> regdb_data = builder.build();

    // Write to file
    std::ofstream file("/home/tomba/work/rwmem/tests/data.regdb", std::ios::binary);
    if (!file) {
        std::cerr << "Failed to create data.regdb" << std::endl;
        return 1;
    }

    file.write(reinterpret_cast<const char*>(regdb_data.data()), regdb_data.size());
    file.close();

    std::cout << "Generated data.regdb with " << regdb_data.size() << " bytes" << std::endl;
    return 0;
}