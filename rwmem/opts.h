#pragma once

#include <optional>
#include <span>
#include <string>
#include <string_view>
#include <vector>

namespace rwmem
{

// Argument types returned by parser
enum class ArgType {
	OPTION,
	POSITIONAL
};

// Parsed argument
struct ParsedArg {
	ArgType type;
	int option_id; // For OPTION: user-defined ID from OptDef
	std::string_view option_value; // For OPTION with value
	std::string_view positional; // For POSITIONAL
};

// Argument requirements for options
enum class ArgReq {
	NONE, // No argument
	REQUIRED, // Argument required
	OPTIONAL // Argument optional
};

// Option definition
struct OptDef {
	int id; // User-defined ID for this option
	char short_opt; // '\0' if no short option
	const char* long_opt; // nullptr if no long option
	ArgReq arg_req; // Argument requirement
};

// Iterative argument parser
class ArgParser
{
public:
	ArgParser(const std::vector<std::string>& args);
	~ArgParser();

	// Get next argument (option or positional)
	// Pass array of valid options for this stage
	// Returns nullopt when no more arguments
	std::optional<ParsedArg> get_next(std::span<const OptDef> valid_opts);

	bool has_more() const;

private:
	std::vector<std::string> m_args;
	size_t m_current_idx;
	int m_short_opt_pos; // Position within combined short options (0 = not in combined mode)
	bool m_positional_only; // After "--", treat all as positional

	bool is_option(const char* arg) const;
	bool is_long_option(const char* arg) const;

	const OptDef* find_short_opt(char opt, std::span<const OptDef> valid_opts) const;
	const OptDef* find_long_opt(std::string_view opt, std::span<const OptDef> valid_opts) const;

	ParsedArg parse_short_option(std::span<const OptDef> valid_opts);
	ParsedArg parse_long_option(std::span<const OptDef> valid_opts);

	// Non-copyable
	ArgParser(const ArgParser&) = delete;
	ArgParser& operator=(const ArgParser&) = delete;
};

} // namespace rwmem
