#include <gtest/gtest.h>
#include <vector>
#include <string>
#include "../rwmem/opts.h"
using namespace rwmem;
// Test fixture
class OptsTest : public ::testing::Test {
protected:
	enum OptId {
		OPT_VERBOSE = 1,
		OPT_HELP,
		OPT_DATA,
		OPT_OUTPUT,
		OPT_RAW,
		OPT_FORMAT,
	};
	const std::vector<OptDef> basic_opts = {
		{ OPT_VERBOSE, 'v', "verbose", ArgReq::NONE },
		{ OPT_HELP, 'h', "help", ArgReq::NONE },
		{ OPT_DATA, 'd', "data", ArgReq::REQUIRED },
		{ OPT_OUTPUT, 'o', "output", ArgReq::OPTIONAL },
		{ OPT_RAW, 'R', "raw", ArgReq::NONE },
		{ OPT_FORMAT, 'f', "format", ArgReq::REQUIRED },
	};
};
TEST_F(OptsTest, NoArguments) {
	ArgParser parser({"program"});
	auto arg = parser.get_next(basic_opts);
	EXPECT_FALSE(arg.has_value());
	EXPECT_FALSE(parser.has_more());
}
TEST_F(OptsTest, SingleShortOptionNoArg) {
	ArgParser parser({"program", "-v"});
	auto arg = parser.get_next(basic_opts);
	ASSERT_TRUE(arg.has_value());
	EXPECT_EQ(arg->type, ArgType::OPTION);
	EXPECT_EQ(arg->option_id, OPT_VERBOSE);
	EXPECT_TRUE(arg->option_value.empty());
	arg = parser.get_next(basic_opts);
	EXPECT_FALSE(arg.has_value());
}
TEST_F(OptsTest, SingleLongOptionNoArg) {
	ArgParser parser({"program", "--verbose"});
	auto arg = parser.get_next(basic_opts);
	ASSERT_TRUE(arg.has_value());
	EXPECT_EQ(arg->type, ArgType::OPTION);
	EXPECT_EQ(arg->option_id, OPT_VERBOSE);
	EXPECT_TRUE(arg->option_value.empty());
	arg = parser.get_next(basic_opts);
	EXPECT_FALSE(arg.has_value());
}
TEST_F(OptsTest, ShortOptionWithRequiredArgSpaceSeparated) {
	ArgParser parser({"program", "-d", "32"});
	auto arg = parser.get_next(basic_opts);
	ASSERT_TRUE(arg.has_value());
	EXPECT_EQ(arg->type, ArgType::OPTION);
	EXPECT_EQ(arg->option_id, OPT_DATA);
	EXPECT_EQ(arg->option_value, "32");
	arg = parser.get_next(basic_opts);
	EXPECT_FALSE(arg.has_value());
}
TEST_F(OptsTest, ShortOptionWithRequiredArgConcatenated) {
	ArgParser parser({"program", "-d32"});
	auto arg = parser.get_next(basic_opts);
	ASSERT_TRUE(arg.has_value());
	EXPECT_EQ(arg->type, ArgType::OPTION);
	EXPECT_EQ(arg->option_id, OPT_DATA);
	EXPECT_EQ(arg->option_value, "32");
	arg = parser.get_next(basic_opts);
	EXPECT_FALSE(arg.has_value());
}
TEST_F(OptsTest, LongOptionWithRequiredArgEquals) {
	ArgParser parser({"program", "--data=32"});
	auto arg = parser.get_next(basic_opts);
	ASSERT_TRUE(arg.has_value());
	EXPECT_EQ(arg->type, ArgType::OPTION);
	EXPECT_EQ(arg->option_id, OPT_DATA);
	EXPECT_EQ(arg->option_value, "32");
	arg = parser.get_next(basic_opts);
	EXPECT_FALSE(arg.has_value());
}
TEST_F(OptsTest, LongOptionWithRequiredArgSpaceSeparated) {
	ArgParser parser({"program", "--data", "32"});
	auto arg = parser.get_next(basic_opts);
	ASSERT_TRUE(arg.has_value());
	EXPECT_EQ(arg->type, ArgType::OPTION);
	EXPECT_EQ(arg->option_id, OPT_DATA);
	EXPECT_EQ(arg->option_value, "32");
	arg = parser.get_next(basic_opts);
	EXPECT_FALSE(arg.has_value());
}
TEST_F(OptsTest, OptionalArgWithValue) {
	ArgParser parser({"program", "-o", "file.txt"});
	auto arg = parser.get_next(basic_opts);
	ASSERT_TRUE(arg.has_value());
	EXPECT_EQ(arg->type, ArgType::OPTION);
	EXPECT_EQ(arg->option_id, OPT_OUTPUT);
	EXPECT_EQ(arg->option_value, "file.txt");
	arg = parser.get_next(basic_opts);
	EXPECT_FALSE(arg.has_value());
}
TEST_F(OptsTest, OptionalArgWithoutValue) {
	ArgParser parser({"program", "-o"});
	auto arg = parser.get_next(basic_opts);
	ASSERT_TRUE(arg.has_value());
	EXPECT_EQ(arg->type, ArgType::OPTION);
	EXPECT_EQ(arg->option_id, OPT_OUTPUT);
	EXPECT_TRUE(arg->option_value.empty());
	arg = parser.get_next(basic_opts);
	EXPECT_FALSE(arg.has_value());
}
TEST_F(OptsTest, OptionalArgFollowedByOption) {
	ArgParser parser({"program", "-o", "-v"});
	auto arg = parser.get_next(basic_opts);
	ASSERT_TRUE(arg.has_value());
	EXPECT_EQ(arg->type, ArgType::OPTION);
	EXPECT_EQ(arg->option_id, OPT_OUTPUT);
	EXPECT_TRUE(arg->option_value.empty());
	arg = parser.get_next(basic_opts);
	ASSERT_TRUE(arg.has_value());
	EXPECT_EQ(arg->type, ArgType::OPTION);
	EXPECT_EQ(arg->option_id, OPT_VERBOSE);
	arg = parser.get_next(basic_opts);
	EXPECT_FALSE(arg.has_value());
}
TEST_F(OptsTest, CombinedShortOptions) {
	ArgParser parser({"program", "-vRh"});
	auto arg = parser.get_next(basic_opts);
	ASSERT_TRUE(arg.has_value());
	EXPECT_EQ(arg->type, ArgType::OPTION);
	EXPECT_EQ(arg->option_id, OPT_VERBOSE);
	arg = parser.get_next(basic_opts);
	ASSERT_TRUE(arg.has_value());
	EXPECT_EQ(arg->type, ArgType::OPTION);
	EXPECT_EQ(arg->option_id, OPT_RAW);
	arg = parser.get_next(basic_opts);
	ASSERT_TRUE(arg.has_value());
	EXPECT_EQ(arg->type, ArgType::OPTION);
	EXPECT_EQ(arg->option_id, OPT_HELP);
	arg = parser.get_next(basic_opts);
	EXPECT_FALSE(arg.has_value());
}
TEST_F(OptsTest, CombinedShortOptionsWithArgAtEnd) {
	ArgParser parser({"program", "-vd32"});
	auto arg = parser.get_next(basic_opts);
	ASSERT_TRUE(arg.has_value());
	EXPECT_EQ(arg->type, ArgType::OPTION);
	EXPECT_EQ(arg->option_id, OPT_VERBOSE);
	arg = parser.get_next(basic_opts);
	ASSERT_TRUE(arg.has_value());
	EXPECT_EQ(arg->type, ArgType::OPTION);
	EXPECT_EQ(arg->option_id, OPT_DATA);
	EXPECT_EQ(arg->option_value, "32");
	arg = parser.get_next(basic_opts);
	EXPECT_FALSE(arg.has_value());
}
TEST_F(OptsTest, PositionalArgument) {
	ArgParser parser({"program", "positional"});
	auto arg = parser.get_next(basic_opts);
	ASSERT_TRUE(arg.has_value());
	EXPECT_EQ(arg->type, ArgType::POSITIONAL);
	EXPECT_EQ(arg->positional, "positional");
	arg = parser.get_next(basic_opts);
	EXPECT_FALSE(arg.has_value());
}
TEST_F(OptsTest, MixedOptionsAndPositionals) {
	ArgParser parser({"program", "-v", "file1", "-d", "32", "file2"});
	auto arg = parser.get_next(basic_opts);
	ASSERT_TRUE(arg.has_value());
	EXPECT_EQ(arg->type, ArgType::OPTION);
	EXPECT_EQ(arg->option_id, OPT_VERBOSE);
	arg = parser.get_next(basic_opts);
	ASSERT_TRUE(arg.has_value());
	EXPECT_EQ(arg->type, ArgType::POSITIONAL);
	EXPECT_EQ(arg->positional, "file1");
	arg = parser.get_next(basic_opts);
	ASSERT_TRUE(arg.has_value());
	EXPECT_EQ(arg->type, ArgType::OPTION);
	EXPECT_EQ(arg->option_id, OPT_DATA);
	EXPECT_EQ(arg->option_value, "32");
	arg = parser.get_next(basic_opts);
	ASSERT_TRUE(arg.has_value());
	EXPECT_EQ(arg->type, ArgType::POSITIONAL);
	EXPECT_EQ(arg->positional, "file2");
	arg = parser.get_next(basic_opts);
	EXPECT_FALSE(arg.has_value());
}
TEST_F(OptsTest, EndOfOptionsMarker) {
	ArgParser parser({"program", "-v", "--", "-d", "file"});
	auto arg = parser.get_next(basic_opts);
	ASSERT_TRUE(arg.has_value());
	EXPECT_EQ(arg->type, ArgType::OPTION);
	EXPECT_EQ(arg->option_id, OPT_VERBOSE);
	// After --, everything should be positional
	arg = parser.get_next(basic_opts);
	ASSERT_TRUE(arg.has_value());
	EXPECT_EQ(arg->type, ArgType::POSITIONAL);
	EXPECT_EQ(arg->positional, "-d");
	arg = parser.get_next(basic_opts);
	ASSERT_TRUE(arg.has_value());
	EXPECT_EQ(arg->type, ArgType::POSITIONAL);
	EXPECT_EQ(arg->positional, "file");
	arg = parser.get_next(basic_opts);
	EXPECT_FALSE(arg.has_value());
}
TEST_F(OptsTest, UnknownShortOption) {
	ArgParser parser({"program", "-x"});
	EXPECT_THROW({
		parser.get_next(basic_opts);
	}, std::runtime_error);
}
TEST_F(OptsTest, UnknownLongOption) {
	ArgParser parser({"program", "--unknown"});
	EXPECT_THROW({
		parser.get_next(basic_opts);
	}, std::runtime_error);
}
TEST_F(OptsTest, RequiredArgMissing) {
	ArgParser parser({"program", "-d"});
	EXPECT_THROW({
		parser.get_next(basic_opts);
	}, std::runtime_error);
}
TEST_F(OptsTest, LongOptionWithEqualsButNoArg) {
	ArgParser parser({"program", "--verbose="});
	EXPECT_THROW({
		parser.get_next(basic_opts);
	}, std::runtime_error);
}
TEST_F(OptsTest, DynamicOptionSets) {
	const std::vector<OptDef> first_opts = {
		{ 1, 'a', "alpha", ArgReq::NONE },
		{ 2, 'b', "beta", ArgReq::NONE },
	};
	const std::vector<OptDef> second_opts = {
		{ 3, 'c', "charlie", ArgReq::NONE },
		{ 4, 'd', "delta", ArgReq::NONE },
	};
	ArgParser parser({"program", "-a", "pos", "-c"});
	// Parse with first option set
	auto arg = parser.get_next(first_opts);
	ASSERT_TRUE(arg.has_value());
	EXPECT_EQ(arg->type, ArgType::OPTION);
	EXPECT_EQ(arg->option_id, 1);
	// Get positional
	arg = parser.get_next(first_opts);
	ASSERT_TRUE(arg.has_value());
	EXPECT_EQ(arg->type, ArgType::POSITIONAL);
	EXPECT_EQ(arg->positional, "pos");
	// Parse with second option set
	arg = parser.get_next(second_opts);
	ASSERT_TRUE(arg.has_value());
	EXPECT_EQ(arg->type, ArgType::OPTION);
	EXPECT_EQ(arg->option_id, 3);
	arg = parser.get_next(second_opts);
	EXPECT_FALSE(arg.has_value());
}
TEST_F(OptsTest, EmptyStringValue) {
	ArgParser parser({"program", "--data="});
	auto arg = parser.get_next(basic_opts);
	ASSERT_TRUE(arg.has_value());
	EXPECT_EQ(arg->type, ArgType::OPTION);
	EXPECT_EQ(arg->option_id, OPT_DATA);
	EXPECT_EQ(arg->option_value, "");
	arg = parser.get_next(basic_opts);
	EXPECT_FALSE(arg.has_value());
}
TEST_F(OptsTest, ValueWithSpecialCharacters) {
	ArgParser parser({"program", "-d", "foo=bar:baz"});
	auto arg = parser.get_next(basic_opts);
	ASSERT_TRUE(arg.has_value());
	EXPECT_EQ(arg->type, ArgType::OPTION);
	EXPECT_EQ(arg->option_id, OPT_DATA);
	EXPECT_EQ(arg->option_value, "foo=bar:baz");
	arg = parser.get_next(basic_opts);
	EXPECT_FALSE(arg.has_value());
}
TEST_F(OptsTest, LongOptionOnlyWithNoShort) {
	const std::vector<OptDef> opts = {
		{ 1, '\0', "long-only", ArgReq::NONE },
	};
	ArgParser parser({"program", "--long-only"});
	auto arg = parser.get_next(opts);
	ASSERT_TRUE(arg.has_value());
	EXPECT_EQ(arg->type, ArgType::OPTION);
	EXPECT_EQ(arg->option_id, 1);
	arg = parser.get_next(opts);
	EXPECT_FALSE(arg.has_value());
}
TEST_F(OptsTest, ShortOptionOnlyWithNoLong) {
	const std::vector<OptDef> opts = {
		{ 1, 's', nullptr, ArgReq::NONE },
	};
	ArgParser parser({"program", "-s"});
	auto arg = parser.get_next(opts);
	ASSERT_TRUE(arg.has_value());
	EXPECT_EQ(arg->type, ArgType::OPTION);
	EXPECT_EQ(arg->option_id, 1);
	arg = parser.get_next(opts);
	EXPECT_FALSE(arg.has_value());
}
TEST_F(OptsTest, MultiplePositionals) {
	ArgParser parser({"program", "pos1", "pos2", "pos3"});
	auto arg = parser.get_next(basic_opts);
	ASSERT_TRUE(arg.has_value());
	EXPECT_EQ(arg->type, ArgType::POSITIONAL);
	EXPECT_EQ(arg->positional, "pos1");
	arg = parser.get_next(basic_opts);
	ASSERT_TRUE(arg.has_value());
	EXPECT_EQ(arg->type, ArgType::POSITIONAL);
	EXPECT_EQ(arg->positional, "pos2");
	arg = parser.get_next(basic_opts);
	ASSERT_TRUE(arg.has_value());
	EXPECT_EQ(arg->type, ArgType::POSITIONAL);
	EXPECT_EQ(arg->positional, "pos3");
	arg = parser.get_next(basic_opts);
	EXPECT_FALSE(arg.has_value());
}
TEST_F(OptsTest, HasMore) {
	ArgParser parser({"program", "-v", "pos"});
	EXPECT_TRUE(parser.has_more());
	auto arg = parser.get_next(basic_opts);
	EXPECT_TRUE(parser.has_more());
	arg = parser.get_next(basic_opts);
	EXPECT_FALSE(parser.has_more());
}
TEST_F(OptsTest, HyphenAsPositional) {
	ArgParser parser({"program", "-"});
	auto arg = parser.get_next(basic_opts);
	ASSERT_TRUE(arg.has_value());
	EXPECT_EQ(arg->type, ArgType::POSITIONAL);
	EXPECT_EQ(arg->positional, "-");
	arg = parser.get_next(basic_opts);
	EXPECT_FALSE(arg.has_value());
}
TEST_F(OptsTest, ValueStartingWithHyphen) {
	ArgParser parser({"program", "-d", "-123"});
	// With required arg, next arg is consumed even if it starts with '-'
	auto arg = parser.get_next(basic_opts);
	ASSERT_TRUE(arg.has_value());
	EXPECT_EQ(arg->type, ArgType::OPTION);
	EXPECT_EQ(arg->option_id, OPT_DATA);
	EXPECT_EQ(arg->option_value, "-123");
	arg = parser.get_next(basic_opts);
	EXPECT_FALSE(arg.has_value());
}
TEST_F(OptsTest, OptionalArgValueStartingWithHyphen) {
	ArgParser parser({"program", "-o", "-v"});
	// With optional arg, next arg starting with '-' is NOT consumed
	auto arg = parser.get_next(basic_opts);
	ASSERT_TRUE(arg.has_value());
	EXPECT_EQ(arg->type, ArgType::OPTION);
	EXPECT_EQ(arg->option_id, OPT_OUTPUT);
	EXPECT_TRUE(arg->option_value.empty());
	arg = parser.get_next(basic_opts);
	ASSERT_TRUE(arg.has_value());
	EXPECT_EQ(arg->type, ArgType::OPTION);
	EXPECT_EQ(arg->option_id, OPT_VERBOSE);
	arg = parser.get_next(basic_opts);
	EXPECT_FALSE(arg.has_value());
}
