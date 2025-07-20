#include <gtest/gtest.h>
#include <cstring>
#include <sys/stat.h>
#include <unistd.h>
#include <fcntl.h>
#include <fstream>

#include "../librwmem/mmaptarget.h"
#include "../librwmem/endianness.h"

class MMapTargetTest : public ::testing::Test {
protected:
    void SetUp() override {
        test_filename = std::string(TEST_DATA_DIR) + "/test.bin";

        // Verify test file exists
        struct stat st;
        if (stat(test_filename.c_str(), &st) != 0) {
            FAIL() << "Test data file not found: " << test_filename;
        }

        // Create a writable copy for write tests
        writable_filename = "/tmp/rwmem_test_mmap_" + std::to_string(getpid()) + ".bin";
        std::ifstream src(test_filename, std::ios::binary);
        std::ofstream dst(writable_filename, std::ios::binary);
        dst << src.rdbuf();
        src.close();
        dst.close();
    }

    void TearDown() override {
        if (unlink(writable_filename.c_str()) == -1) {
            // File might not exist or already removed
        }
    }

    std::string test_filename;
    std::string writable_filename;
};

TEST_F(MMapTargetTest, Construction) {
    MMapTarget target(test_filename);
    // Constructor should succeed without throwing
}

TEST_F(MMapTargetTest, MapReadOnly) {
    MMapTarget target(test_filename);

    EXPECT_NO_THROW(target.map(0, 768, Endianness::Little, 4,
                               Endianness::Little, 4, MapMode::Read));

    // Should be able to read - test against known values from test.bin
    uint32_t value = target.read(0, 4, Endianness::Little);
    EXPECT_EQ(value, 0x7d8c0c39);  // Known value at offset 0 in test.bin
}

TEST_F(MMapTargetTest, MapReadWrite) {
    MMapTarget target(writable_filename);

    EXPECT_NO_THROW(target.map(0, 768, Endianness::Little, 4,
                               Endianness::Little, 4, MapMode::ReadWrite));

    // Should be able to read and write
    target.write(0, 0xDEADBEEF, 4, Endianness::Little);
    uint32_t new_value = target.read(0, 4, Endianness::Little);
    EXPECT_EQ(new_value, 0xDEADBEEF);
}

//TEST_F(MMapTargetTest, MapWriteOnly) {
//    MMapTarget target(writable_filename);
//
//    EXPECT_NO_THROW(target.map(0, 768, Endianness::Little, 4,
//                               Endianness::Little, 4, MapMode::Write));
//
//    // Should be able to write
//    EXPECT_NO_THROW(target.write(0, 0x12345678, 4, Endianness::Little));
//}

TEST_F(MMapTargetTest, WriteToReadOnlyMapping) {
    MMapTarget target(test_filename);
    target.map(0, 768, Endianness::Little, 4,
               Endianness::Little, 4, MapMode::Read);

    // Should throw when trying to write to read-only mapping
    EXPECT_THROW(target.write(0, 0x12345678, 4, Endianness::Little), std::runtime_error);
}

TEST_F(MMapTargetTest, Read8Bit) {
    MMapTarget target(test_filename);
    target.map(0, 256, Endianness::Little, 4,
               Endianness::Little, 4, MapMode::Read);

    // Test 8-bit reads - known values from test.bin
    uint8_t value = target.read(0, 1, Endianness::Little);
    EXPECT_EQ(value, 0x39);  // LSB of 0x7d8c0c39

    value = target.read(1, 1, Endianness::Little);
    EXPECT_EQ(value, 0x0c);  // Second byte of 0x7d8c0c39
}

TEST_F(MMapTargetTest, Read16Bit) {
    MMapTarget target(test_filename);
    target.map(0, 768, Endianness::Little, 4,
               Endianness::Little, 4, MapMode::Read);

    // Test 16-bit reads - little endian
    uint16_t value = target.read(0, 2, Endianness::Little);
    EXPECT_EQ(value, 0x0c39);  // Lower 16 bits of 0x7d8c0c39

    // Test 16-bit reads - big endian
    value = target.read(0, 2, Endianness::Big);
    EXPECT_EQ(value, 0x390c);  // Swapped bytes
}

TEST_F(MMapTargetTest, Read32Bit) {
    MMapTarget target(test_filename);
    target.map(0, 768, Endianness::Little, 4,
               Endianness::Little, 4, MapMode::Read);

    // Test 32-bit reads - little endian
    uint32_t value = target.read(0, 4, Endianness::Little);
    EXPECT_EQ(value, 0x7d8c0c39);  // Known value from test.bin

    value = target.read(4, 4, Endianness::Little);
    EXPECT_EQ(value, 0x2c344772);  // Known value from test.bin

    // Test 32-bit reads - big endian
    value = target.read(0, 4, Endianness::Big);
    EXPECT_EQ(value, 0x390c8c7d);  // Byte-swapped
}

TEST_F(MMapTargetTest, Read64Bit) {
    MMapTarget target(test_filename);
    target.map(0, 768, Endianness::Little, 4,
               Endianness::Little, 4, MapMode::Read);

    // Test 64-bit reads - little endian (combining known 32-bit values)
    uint64_t value = target.read(0, 8, Endianness::Little);
    uint64_t expected = 0x2c3447727d8c0c39ULL;  // Combines first two 32-bit values
    EXPECT_EQ(value, expected);
}

TEST_F(MMapTargetTest, Write8Bit) {
    MMapTarget target(writable_filename);
    target.map(0, 768, Endianness::Little, 4,
               Endianness::Little, 4, MapMode::ReadWrite);

    // Test 8-bit writes
    target.write(100, 0xAB, 1, Endianness::Little);
    uint8_t value = target.read(100, 1, Endianness::Little);
    EXPECT_EQ(value, 0xAB);
}

TEST_F(MMapTargetTest, Write16Bit) {
    MMapTarget target(writable_filename);
    target.map(0, 768, Endianness::Little, 4,
               Endianness::Little, 4, MapMode::ReadWrite);

    // Test 16-bit writes - little endian
    target.write(100, 0x1234, 2, Endianness::Little);
    uint16_t value = target.read(100, 2, Endianness::Little);
    EXPECT_EQ(value, 0x1234);

    // Test 16-bit writes - big endian
    target.write(102, 0x5678, 2, Endianness::Big);
    value = target.read(102, 2, Endianness::Big);
    EXPECT_EQ(value, 0x5678);
}

TEST_F(MMapTargetTest, Write32Bit) {
    MMapTarget target(writable_filename);
    target.map(0, 768, Endianness::Little, 4,
               Endianness::Little, 4, MapMode::ReadWrite);

    // Test 32-bit writes - little endian
    target.write(100, 0x12345678, 4, Endianness::Little);
    uint32_t value = target.read(100, 4, Endianness::Little);
    EXPECT_EQ(value, 0x12345678);

    // Test 32-bit writes - big endian
    target.write(104, 0x9ABCDEF0, 4, Endianness::Big);
    value = target.read(104, 4, Endianness::Big);
    EXPECT_EQ(value, 0x9ABCDEF0);
}

TEST_F(MMapTargetTest, Write64Bit) {
    MMapTarget target(writable_filename);
    target.map(0, 768, Endianness::Little, 4,
               Endianness::Little, 4, MapMode::ReadWrite);

    // Test 64-bit writes - little endian
    target.write(100, 0x123456789ABCDEF0ULL, 8, Endianness::Little);
    uint64_t value = target.read(100, 8, Endianness::Little);
    EXPECT_EQ(value, 0x123456789ABCDEF0ULL);

    // Test 64-bit writes - big endian
    target.write(108, 0xFEDCBA0987654321ULL, 8, Endianness::Big);
    value = target.read(108, 8, Endianness::Big);
    EXPECT_EQ(value, 0xFEDCBA0987654321ULL);
}

TEST_F(MMapTargetTest, DefaultDataSize) {
    MMapTarget target(test_filename);
    target.map(0, 768, Endianness::Little, 4,
               Endianness::Little, 4, MapMode::Read);

    // Test default data size (4 bytes)
    uint32_t value = target.read(0, 0, Endianness::Little);  // Should read 4 bytes by default
    EXPECT_EQ(value, 0x7d8c0c39);
}

TEST_F(MMapTargetTest, DefaultEndianness) {
    MMapTarget target(test_filename);
    target.map(0, 768, Endianness::Little, 4,
               Endianness::Big, 4, MapMode::Read);  // Default to big endian

    // Test default endianness
    uint32_t value = target.read(0, 4, Endianness::Default);  // Should use big endian by default
    EXPECT_EQ(value, 0x390c8c7d);
}

TEST_F(MMapTargetTest, OffsetMapping) {
    MMapTarget target(test_filename);

    // Map starting at offset 0x10 with 752 bytes (768 - 16)
    target.map(0x10, 752, Endianness::Little, 4,
               Endianness::Little, 4, MapMode::Read);

    // Reading at address 0x10 should give us the value at offset 0x10 in the file
    uint32_t value = target.read(0x10, 4, Endianness::Little);
    EXPECT_EQ(value, 0x8ee570d6);  // Known value at offset 0x10 in test.bin
}

TEST_F(MMapTargetTest, AddressRangeValidation) {
    MMapTarget target(test_filename);
    target.map(0, 768, Endianness::Little, 4,
               Endianness::Little, 4, MapMode::Read);

    // Reading below mapped range should throw
    EXPECT_THROW(target.read(0xFFFFFFFF, 1, Endianness::Little), std::runtime_error);

    // Reading above mapped range should throw
    EXPECT_THROW(target.read(768, 1, Endianness::Little), std::runtime_error);

    // Reading at the edge of mapped range should work
    EXPECT_NO_THROW(target.read(767, 1, Endianness::Little));

    // Reading beyond the edge should throw
    EXPECT_THROW(target.read(767, 4, Endianness::Little), std::runtime_error);
}

TEST_F(MMapTargetTest, UnmapAndRemap) {
    MMapTarget target(test_filename);

    // Initial mapping
    target.map(0, 768, Endianness::Little, 4,
               Endianness::Little, 4, MapMode::Read);

    uint32_t original_value = target.read(0, 4, Endianness::Little);

    // Unmap
    target.unmap();

    // Remap with different parameters
    target.map(0, 768, Endianness::Big, 8,
               Endianness::Big, 8, MapMode::Read);

    uint32_t new_value = target.read(0, 4, Endianness::Little);
    EXPECT_EQ(new_value, original_value);  // Data should still be there
}

TEST_F(MMapTargetTest, Sync) {
    MMapTarget target(writable_filename);
    target.map(0, 768, Endianness::Little, 4,
               Endianness::Little, 4, MapMode::ReadWrite);

    // Write some data
    target.write(0, 0x12345678, 4, Endianness::Little);

    // Sync should not throw
    EXPECT_NO_THROW(target.sync());
}

TEST_F(MMapTargetTest, InvalidFileAccess) {
    MMapTarget target("/nonexistent/path");

    // Should throw when trying to map non-existent file
    EXPECT_THROW(target.map(0, 768, Endianness::Little, 4,
                           Endianness::Little, 4, MapMode::ReadWrite),
                 std::runtime_error);
}

TEST_F(MMapTargetTest, PageAlignmentHandling) {
    MMapTarget target(test_filename);

    // Test mapping that's not page-aligned
    // This should work as the implementation handles page alignment internally
    EXPECT_NO_THROW(target.map(100, 100, Endianness::Little, 4,
                              Endianness::Little, 4, MapMode::Read));

    // Should be able to read at the specified offset
    EXPECT_NO_THROW(target.read(100, 1, Endianness::Little));
}

TEST_F(MMapTargetTest, DestructorCleanup) {
    // Test that destructor properly cleans up resources
    {
        MMapTarget target(test_filename);
        target.map(0, 768, Endianness::Little, 4,
                   Endianness::Little, 4, MapMode::Read);
        // target goes out of scope here, destructor should be called
    }

    // Should be able to create another target for the same file
    MMapTarget target2(test_filename);
    EXPECT_NO_THROW(target2.map(0, 768, Endianness::Little, 4,
                               Endianness::Little, 4, MapMode::Read));
}

TEST_F(MMapTargetTest, Read24Bit) {
    MMapTarget target(test_filename);
    target.map(0, 768, Endianness::Little, 4,
               Endianness::Little, 4, MapMode::Read);

    // Test 24-bit reads - little endian (first 3 bytes of 0x7d8c0c39)
    uint64_t value = target.read(0, 3, Endianness::Little);
    EXPECT_EQ(value, 0x8c0c39);  // Lower 24 bits of 0x7d8c0c39

    // Test 24-bit reads - big endian
    value = target.read(0, 3, Endianness::Big);
    EXPECT_EQ(value, 0x390c8c);  // Byte-swapped
}

TEST_F(MMapTargetTest, Read40Bit) {
    MMapTarget target(test_filename);
    target.map(0, 768, Endianness::Little, 4,
               Endianness::Little, 4, MapMode::Read);

    // Test 40-bit reads - little endian
    // Reading 5 bytes: 0x39, 0x0c, 0x8c, 0x7d, 0x72 (first byte of next value)
    uint64_t value = target.read(0, 5, Endianness::Little);
    EXPECT_EQ(value, 0x727d8c0c39ULL);  // 5 bytes in little endian order

    // Test 40-bit reads - big endian
    value = target.read(0, 5, Endianness::Big);
    EXPECT_EQ(value, 0x390c8c7d72ULL);  // Same bytes in big endian order
}

TEST_F(MMapTargetTest, Read48Bit) {
    MMapTarget target(test_filename);
    target.map(0, 768, Endianness::Little, 4,
               Endianness::Little, 4, MapMode::Read);

    // Test 48-bit reads - little endian
    // Reading 6 bytes: 0x39, 0x0c, 0x8c, 0x7d, 0x72, 0x47 (first 2 bytes of next value)
    uint64_t value = target.read(0, 6, Endianness::Little);
    EXPECT_EQ(value, 0x47727d8c0c39ULL);  // 6 bytes in little endian order

    // Test 48-bit reads - big endian
    value = target.read(0, 6, Endianness::Big);
    EXPECT_EQ(value, 0x390c8c7d7247ULL);  // Same bytes in big endian order
}

TEST_F(MMapTargetTest, Read56Bit) {
    MMapTarget target(test_filename);
    target.map(0, 768, Endianness::Little, 4,
               Endianness::Little, 4, MapMode::Read);

    // Test 56-bit reads - little endian
    // Reading 7 bytes: 0x39, 0x0c, 0x8c, 0x7d, 0x72, 0x47, 0x34 (first 3 bytes of next value)
    uint64_t value = target.read(0, 7, Endianness::Little);
    EXPECT_EQ(value, 0x3447727d8c0c39ULL);  // 7 bytes in little endian order

    // Test 56-bit reads - big endian
    value = target.read(0, 7, Endianness::Big);
    EXPECT_EQ(value, 0x390c8c7d724734ULL);  // Same bytes in big endian order
}

TEST_F(MMapTargetTest, Write24Bit) {
    MMapTarget target(writable_filename);
    target.map(0, 768, Endianness::Little, 4,
               Endianness::Little, 4, MapMode::ReadWrite);

    // Test 24-bit writes - little endian
    target.write(100, 0xABCDEF, 3, Endianness::Little);
    uint64_t value = target.read(100, 3, Endianness::Little);
    EXPECT_EQ(value, 0xABCDEF);

    // Test 24-bit writes - big endian
    target.write(104, 0x123456, 3, Endianness::Big);
    value = target.read(104, 3, Endianness::Big);
    EXPECT_EQ(value, 0x123456);
}

TEST_F(MMapTargetTest, Write40Bit) {
    MMapTarget target(writable_filename);
    target.map(0, 768, Endianness::Little, 4,
               Endianness::Little, 4, MapMode::ReadWrite);

    // Test 40-bit writes - little endian
    target.write(100, 0x123456789A, 5, Endianness::Little);
    uint64_t value = target.read(100, 5, Endianness::Little);
    EXPECT_EQ(value, 0x123456789A);

    // Test 40-bit writes - big endian
    target.write(106, 0xABCDEF0123, 5, Endianness::Big);
    value = target.read(106, 5, Endianness::Big);
    EXPECT_EQ(value, 0xABCDEF0123);
}

TEST_F(MMapTargetTest, Write48Bit) {
    MMapTarget target(writable_filename);
    target.map(0, 768, Endianness::Little, 4,
               Endianness::Little, 4, MapMode::ReadWrite);

    // Test 48-bit writes - little endian
    target.write(100, 0x123456789ABC, 6, Endianness::Little);
    uint64_t value = target.read(100, 6, Endianness::Little);
    EXPECT_EQ(value, 0x123456789ABC);

    // Test 48-bit writes - big endian
    target.write(107, 0xABCDEF012345, 6, Endianness::Big);
    value = target.read(107, 6, Endianness::Big);
    EXPECT_EQ(value, 0xABCDEF012345);
}

TEST_F(MMapTargetTest, Write56Bit) {
    MMapTarget target(writable_filename);
    target.map(0, 768, Endianness::Little, 4,
               Endianness::Little, 4, MapMode::ReadWrite);

    // Test 56-bit writes - little endian
    target.write(100, 0x123456789ABCDE, 7, Endianness::Little);
    uint64_t value = target.read(100, 7, Endianness::Little);
    EXPECT_EQ(value, 0x123456789ABCDE);

    // Test 56-bit writes - big endian
    target.write(108, 0xABCDEF01234567, 7, Endianness::Big);
    value = target.read(108, 7, Endianness::Big);
    EXPECT_EQ(value, 0xABCDEF01234567);
}

TEST_F(MMapTargetTest, ArbitrarySizeEndianness) {
    MMapTarget target(writable_filename);
    target.map(0, 768, Endianness::Little, 4,
               Endianness::Little, 4, MapMode::ReadWrite);

    // Test that byte-oriented access handles endianness correctly
    // Write a known pattern in little endian
    target.write(100, 0x12345678, 4, Endianness::Little);

    // Read as 3 bytes in different endiannesses
    uint64_t le_value = target.read(100, 3, Endianness::Little);
    uint64_t be_value = target.read(100, 3, Endianness::Big);

    EXPECT_EQ(le_value, 0x345678);  // Lower 3 bytes, little endian
    EXPECT_EQ(be_value, 0x785634);  // Same bytes, big endian order
}

TEST_F(MMapTargetTest, KnownDataValidation) {
    MMapTarget target(test_filename);
    target.map(0, 32, Endianness::Little, 4,
               Endianness::Little, 4, MapMode::Read);

    // Test known values from test.bin
    uint32_t value = target.read(0x00, 4, Endianness::Little);
    EXPECT_EQ(value, 0x7d8c0c39);

    value = target.read(0x04, 4, Endianness::Little);
    EXPECT_EQ(value, 0x2c344772);

    value = target.read(0x08, 4, Endianness::Little);
    EXPECT_EQ(value, 0x2f0f10d8);

    value = target.read(0x0c, 4, Endianness::Little);
    EXPECT_EQ(value, 0x650d776f);

    value = target.read(0x10, 4, Endianness::Little);
    EXPECT_EQ(value, 0x8ee570d6);

    value = target.read(0x14, 4, Endianness::Little);
    EXPECT_EQ(value, 0xaed85103);

    value = target.read(0x18, 4, Endianness::Little);
    EXPECT_EQ(value, 0xac6e4f8e);

    value = target.read(0x1c, 4, Endianness::Little);
    EXPECT_EQ(value, 0x31c22f34);
}
