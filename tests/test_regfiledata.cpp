#include <gtest/gtest.h>
#include <cstring>
#include <fstream>
#include <vector>

#include "../librwmem/regfiledata.h"

class RegisterFileDataTest : public ::testing::Test {
protected:
    void SetUp() override {
        // Load the test.regdb file using TEST_DATA_DIR
        test_regdb_filename = std::string(TEST_DATA_DIR) + "/test.regdb";
        std::ifstream file(test_regdb_filename, std::ios::binary);
        ASSERT_TRUE(file.is_open()) << "Failed to open " << test_regdb_filename;

        // Get file size
        file.seekg(0, std::ios::end);
        size_t file_size = file.tellg();
        file.seekg(0, std::ios::beg);

        // Read file into memory
        test_data.resize(file_size);
        file.read(reinterpret_cast<char*>(test_data.data()), file_size);
        file.close();

        rfd = reinterpret_cast<const RegisterFileData*>(test_data.data());
    }

    std::vector<uint8_t> test_data;
    const RegisterFileData* rfd;
    std::string test_regdb_filename;
};

TEST_F(RegisterFileDataTest, HeaderValidation) {
    EXPECT_EQ(rfd->magic(), 0x00e11555);
    EXPECT_EQ(rfd->version(), 3);
    EXPECT_EQ(rfd->num_blocks(), 3);  // SENSOR_A, SENSOR_B, MEMORY_CTRL
    EXPECT_EQ(rfd->num_regs(), 14);   // 9 + 9 - 9 (due to deduplication) = 14
    EXPECT_EQ(rfd->num_fields(), 24); // Based on generate_test_data.py
}

TEST_F(RegisterFileDataTest, FileNameAccess) {
    EXPECT_STREQ(rfd->name(), "TEST_V3");
}

TEST_F(RegisterFileDataTest, BlockAccess) {
    // Test first block (SENSOR_A)
    const RegisterBlockData* sensor_a_block = rfd->block_at(0);
    ASSERT_NE(sensor_a_block, nullptr);
    EXPECT_STREQ(sensor_a_block->name(rfd), "SENSOR_A");
    EXPECT_EQ(sensor_a_block->offset(), 0x000);
    EXPECT_EQ(sensor_a_block->size(), 0x100);
    EXPECT_EQ(sensor_a_block->num_regs(), 9);

    // Test second block (SENSOR_B)
    const RegisterBlockData* sensor_b_block = rfd->block_at(1);
    ASSERT_NE(sensor_b_block, nullptr);
    EXPECT_STREQ(sensor_b_block->name(rfd), "SENSOR_B");
    EXPECT_EQ(sensor_b_block->offset(), 0x100);
    EXPECT_EQ(sensor_b_block->size(), 0x100);
    EXPECT_EQ(sensor_b_block->num_regs(), 9);

    // Test third block (MEMORY_CTRL)
    const RegisterBlockData* memory_ctrl_block = rfd->block_at(2);
    ASSERT_NE(memory_ctrl_block, nullptr);
    EXPECT_STREQ(memory_ctrl_block->name(rfd), "MEMORY_CTRL");
    EXPECT_EQ(memory_ctrl_block->offset(), 0x200);
    EXPECT_EQ(memory_ctrl_block->size(), 0x100);
    EXPECT_EQ(memory_ctrl_block->num_regs(), 5);
}

TEST_F(RegisterFileDataTest, RegisterAccess) {
    const RegisterBlockData* sensor_a_block = rfd->block_at(0);
    ASSERT_NE(sensor_a_block, nullptr);

    // Test first register (STATUS_REG)
    const RegisterData* status_reg = sensor_a_block->register_at(rfd, 0);
    ASSERT_NE(status_reg, nullptr);
    EXPECT_STREQ(status_reg->name(rfd), "STATUS_REG");
    EXPECT_EQ(status_reg->offset(), 0x00);
    EXPECT_EQ(status_reg->num_fields(), 3);

    // Test second register (CONTROL_REG)
    const RegisterData* control_reg = sensor_a_block->register_at(rfd, 1);
    ASSERT_NE(control_reg, nullptr);
    EXPECT_STREQ(control_reg->name(rfd), "CONTROL_REG");
    EXPECT_EQ(control_reg->offset(), 0x01);
    EXPECT_EQ(control_reg->num_fields(), 3);
}

TEST_F(RegisterFileDataTest, FieldAccess) {
    const RegisterBlockData* sensor_a_block = rfd->block_at(0);
    const RegisterData* status_reg = sensor_a_block->register_at(rfd, 0);
    ASSERT_NE(status_reg, nullptr);

    // Fields are sorted by high bit descending, so MODE (7:3) comes first, ERROR (2:1), then READY (0:0)
    const FieldData* first_field = status_reg->field_at(rfd, 0);
    ASSERT_NE(first_field, nullptr);
    EXPECT_STREQ(first_field->name(rfd), "MODE");
    EXPECT_EQ(first_field->high(), 7);
    EXPECT_EQ(first_field->low(), 3);

    const FieldData* second_field = status_reg->field_at(rfd, 1);
    ASSERT_NE(second_field, nullptr);
    EXPECT_STREQ(second_field->name(rfd), "ERROR");
    EXPECT_EQ(second_field->high(), 2);
    EXPECT_EQ(second_field->low(), 1);

    const FieldData* third_field = status_reg->field_at(rfd, 2);
    ASSERT_NE(third_field, nullptr);
    EXPECT_STREQ(third_field->name(rfd), "READY");
    EXPECT_EQ(third_field->high(), 0);
    EXPECT_EQ(third_field->low(), 0);
}

TEST_F(RegisterFileDataTest, FindBlock) {
    // Test successful find
    const RegisterBlockData* found_block = rfd->find_block("SENSOR_A");
    ASSERT_NE(found_block, nullptr);
    EXPECT_STREQ(found_block->name(rfd), "SENSOR_A");

    found_block = rfd->find_block("SENSOR_B");
    ASSERT_NE(found_block, nullptr);
    EXPECT_STREQ(found_block->name(rfd), "SENSOR_B");

    found_block = rfd->find_block("MEMORY_CTRL");
    ASSERT_NE(found_block, nullptr);
    EXPECT_STREQ(found_block->name(rfd), "MEMORY_CTRL");

    // Test unsuccessful find
    found_block = rfd->find_block("nonexistent");
    EXPECT_EQ(found_block, nullptr);
}

TEST_F(RegisterFileDataTest, FindRegister) {
    const RegisterBlockData* reg_block = nullptr;

    // Test successful find
    const RegisterData* found_reg = rfd->find_register("STATUS_REG", &reg_block);
    ASSERT_NE(found_reg, nullptr);
    ASSERT_NE(reg_block, nullptr);
    EXPECT_STREQ(found_reg->name(rfd), "STATUS_REG");
    EXPECT_STREQ(reg_block->name(rfd), "SENSOR_A");

    // Test another register
    found_reg = rfd->find_register("CONFIG_REG", &reg_block);
    ASSERT_NE(found_reg, nullptr);
    ASSERT_NE(reg_block, nullptr);
    EXPECT_STREQ(found_reg->name(rfd), "CONFIG_REG");
    EXPECT_STREQ(reg_block->name(rfd), "SENSOR_A");  // Should find first occurrence

    // Test unsuccessful find
    found_reg = rfd->find_register("nonexistent", &reg_block);
    EXPECT_EQ(found_reg, nullptr);
}

TEST_F(RegisterFileDataTest, ComplexFieldRanges) {
    // Test MEMORY_CTRL block's DATA_LO_REG which has a single wide field
    const RegisterBlockData* memory_ctrl_block = rfd->block_at(2);
    ASSERT_NE(memory_ctrl_block, nullptr);

    const RegisterData* data_lo_reg = memory_ctrl_block->register_at(rfd, 3);  // DATA_LO_REG
    ASSERT_NE(data_lo_reg, nullptr);
    EXPECT_STREQ(data_lo_reg->name(rfd), "DATA_LO_REG");
    EXPECT_EQ(data_lo_reg->num_fields(), 1);

    // Test the wide DATA field (31:0)
    const FieldData* data_field = data_lo_reg->field_at(rfd, 0);
    ASSERT_NE(data_field, nullptr);
    EXPECT_STREQ(data_field->name(rfd), "DATA");
    EXPECT_EQ(data_field->high(), 31);
    EXPECT_EQ(data_field->low(), 0);
}

TEST_F(RegisterFileDataTest, RegisterSharing) {
    // Test that SENSOR_A and SENSOR_B blocks have registers with the same names but different block contexts
    const RegisterBlockData* sensor_a_block = rfd->block_at(0);
    const RegisterBlockData* sensor_b_block = rfd->block_at(1);

    ASSERT_NE(sensor_a_block, nullptr);
    ASSERT_NE(sensor_b_block, nullptr);

    // Both blocks should have STATUS_REG
    const RegisterData* status_a = sensor_a_block->register_at(rfd, 0);
    const RegisterData* status_b = sensor_b_block->register_at(rfd, 0);

    ASSERT_NE(status_a, nullptr);
    ASSERT_NE(status_b, nullptr);

    EXPECT_STREQ(status_a->name(rfd), "STATUS_REG");
    EXPECT_STREQ(status_b->name(rfd), "STATUS_REG");

    // Both should have the same offset within their respective blocks
    EXPECT_EQ(status_a->offset(), 0x00);
    EXPECT_EQ(status_b->offset(), 0x00);
}
