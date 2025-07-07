#include <gtest/gtest.h>
#include <cstring>

#include "test_data_generator.h"
#include "../librwmem/regfiledata.h"

class RegisterFileDataTest : public ::testing::Test {
protected:
    void SetUp() override {
        // Create a test register file for most tests
        test_data = TestRegisterFileBuilder("test_chip")
            .add_block("gpio", 0x1000, 0x100)
            .add_register("direction", 0x00)
            .add_field("pin0", 0, 0)
            .add_field("pin1", 1, 1)
            .add_register("output", 0x04)
            .add_field("out0", 0, 0)
            .add_field("out1", 1, 1)
            .add_block("uart", 0x2000, 0x20)
            .add_register("control", 0x00)
            .add_field("enable", 0, 0)
            .add_field("baud", 7, 1)
            .build();

        rfd = reinterpret_cast<const RegisterFileData*>(test_data.data());
    }

    std::vector<uint8_t> test_data;
    const RegisterFileData* rfd;
};

TEST_F(RegisterFileDataTest, HeaderValidation) {
    EXPECT_EQ(rfd->magic(), 0x00e11554);
    EXPECT_EQ(rfd->version(), 2);
    EXPECT_EQ(rfd->num_blocks(), 2);
    EXPECT_EQ(rfd->num_regs(), 3);
    EXPECT_EQ(rfd->num_fields(), 6);
}

TEST_F(RegisterFileDataTest, FileNameAccess) {
    EXPECT_STREQ(rfd->name(), "test_chip");
}

TEST_F(RegisterFileDataTest, BlockAccess) {
    // Test first block (GPIO)
    const RegisterBlockData* gpio_block = rfd->block_at(0);
    ASSERT_NE(gpio_block, nullptr);
    EXPECT_STREQ(gpio_block->name(rfd), "gpio");
    EXPECT_EQ(gpio_block->offset(), 0x1000);
    EXPECT_EQ(gpio_block->size(), 0x100);
    EXPECT_EQ(gpio_block->num_regs(), 2);

    // Test second block (UART)
    const RegisterBlockData* uart_block = rfd->block_at(1);
    ASSERT_NE(uart_block, nullptr);
    EXPECT_STREQ(uart_block->name(rfd), "uart");
    EXPECT_EQ(uart_block->offset(), 0x2000);
    EXPECT_EQ(uart_block->num_regs(), 1);
}

TEST_F(RegisterFileDataTest, RegisterAccess) {
    const RegisterBlockData* gpio_block = rfd->block_at(0);
    ASSERT_NE(gpio_block, nullptr);

    // Test first register (direction)
    const RegisterData* dir_reg = gpio_block->register_at(rfd, 0);
    ASSERT_NE(dir_reg, nullptr);
    EXPECT_STREQ(dir_reg->name(rfd), "direction");
    EXPECT_EQ(dir_reg->offset(), 0x00);
    EXPECT_EQ(dir_reg->num_fields(), 2);

    // Test second register (output)
    const RegisterData* out_reg = gpio_block->register_at(rfd, 1);
    ASSERT_NE(out_reg, nullptr);
    EXPECT_STREQ(out_reg->name(rfd), "output");
    EXPECT_EQ(out_reg->offset(), 0x04);
    EXPECT_EQ(out_reg->num_fields(), 2);
}

TEST_F(RegisterFileDataTest, FieldAccess) {
    const RegisterBlockData* gpio_block = rfd->block_at(0);
    const RegisterData* dir_reg = gpio_block->register_at(rfd, 0);
    ASSERT_NE(dir_reg, nullptr);

    // Fields are sorted by high bit descending, so pin1 (1:1) comes before pin0 (0:0)
    const FieldData* first_field = dir_reg->field_at(rfd, 0);
    ASSERT_NE(first_field, nullptr);
    EXPECT_STREQ(first_field->name(rfd), "pin1");
    EXPECT_EQ(first_field->high(), 1);
    EXPECT_EQ(first_field->low(), 1);

    const FieldData* second_field = dir_reg->field_at(rfd, 1);
    ASSERT_NE(second_field, nullptr);
    EXPECT_STREQ(second_field->name(rfd), "pin0");
    EXPECT_EQ(second_field->high(), 0);
    EXPECT_EQ(second_field->low(), 0);
}

TEST_F(RegisterFileDataTest, FindBlock) {
    // Test successful find
    const RegisterBlockData* found_block = rfd->find_block("gpio");
    ASSERT_NE(found_block, nullptr);
    EXPECT_STREQ(found_block->name(rfd), "gpio");

    found_block = rfd->find_block("uart");
    ASSERT_NE(found_block, nullptr);
    EXPECT_STREQ(found_block->name(rfd), "uart");

    // Test unsuccessful find
    found_block = rfd->find_block("nonexistent");
    EXPECT_EQ(found_block, nullptr);
}

TEST_F(RegisterFileDataTest, FindRegister) {
    const RegisterBlockData* reg_block = nullptr;

    // Test successful find
    const RegisterData* found_reg = rfd->find_register("direction", &reg_block);
    ASSERT_NE(found_reg, nullptr);
    ASSERT_NE(reg_block, nullptr);
    EXPECT_STREQ(found_reg->name(rfd), "direction");
    EXPECT_STREQ(reg_block->name(rfd), "gpio");

    // Test another register
    found_reg = rfd->find_register("control", &reg_block);
    ASSERT_NE(found_reg, nullptr);
    ASSERT_NE(reg_block, nullptr);
    EXPECT_STREQ(found_reg->name(rfd), "control");
    EXPECT_STREQ(reg_block->name(rfd), "uart");

    // Test unsuccessful find
    found_reg = rfd->find_register("nonexistent", &reg_block);
    EXPECT_EQ(found_reg, nullptr);
}

TEST(RegisterFileDataGeneratorTest, EmptyFile) {
    auto empty_data = TestRegisterFileBuilder("empty").build();
    const RegisterFileData* rfd = reinterpret_cast<const RegisterFileData*>(empty_data.data());

    EXPECT_EQ(rfd->magic(), 0x00e11554);
    EXPECT_EQ(rfd->version(), 2);
    EXPECT_EQ(rfd->num_blocks(), 0);
    EXPECT_EQ(rfd->num_regs(), 0);
    EXPECT_EQ(rfd->num_fields(), 0);
    EXPECT_STREQ(rfd->name(), "empty");
}

TEST(RegisterFileDataGeneratorTest, ComplexFieldRanges) {
    auto test_data = TestRegisterFileBuilder("complex")
        .add_block("test", 0x0)
        .add_register("reg", 0x0)
        .add_field("wide_field", 31, 16)  // 16-bit field
        .add_field("mid_field", 15, 8)    // 8-bit field
        .add_field("narrow_field", 7, 0)  // 8-bit field
        .build();

    const RegisterFileData* rfd = reinterpret_cast<const RegisterFileData*>(test_data.data());
    const RegisterBlockData* block = rfd->block_at(0);
    const RegisterData* reg = block->register_at(rfd, 0);

    EXPECT_EQ(reg->num_fields(), 3);

    // Fields should be sorted by high bit descending
    const FieldData* field0 = reg->field_at(rfd, 0);
    EXPECT_STREQ(field0->name(rfd), "wide_field");
    EXPECT_EQ(field0->high(), 31);
    EXPECT_EQ(field0->low(), 16);

    const FieldData* field1 = reg->field_at(rfd, 1);
    EXPECT_STREQ(field1->name(rfd), "mid_field");
    EXPECT_EQ(field1->high(), 15);
    EXPECT_EQ(field1->low(), 8);

    const FieldData* field2 = reg->field_at(rfd, 2);
    EXPECT_STREQ(field2->name(rfd), "narrow_field");
    EXPECT_EQ(field2->high(), 7);
    EXPECT_EQ(field2->low(), 0);
}