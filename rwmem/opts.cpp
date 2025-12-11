#include "opts.h"
#include <cstring>
#include <stdexcept>

using namespace std;

namespace rwmem
{

ArgParser::ArgParser(const std::vector<std::string>& args)
	: m_args(args), m_current_idx(1), m_short_opt_pos(0), m_positional_only(false) // Start at 1 to skip program name
{
}

ArgParser::~ArgParser()
{
}

bool ArgParser::has_more() const
{
	return m_current_idx < m_args.size();
}

bool ArgParser::is_option(const char* arg) const
{
	return arg[0] == '-' && arg[1] != '\0';
}

bool ArgParser::is_long_option(const char* arg) const
{
	return arg[0] == '-' && arg[1] == '-' && arg[2] != '\0';
}

const OptDef* ArgParser::find_short_opt(char opt, std::span<const OptDef> valid_opts) const
{
	for (const OptDef& opt_def : valid_opts) {
		if (opt_def.short_opt == opt)
			return &opt_def;
	}
	return nullptr;
}

const OptDef* ArgParser::find_long_opt(string_view opt, std::span<const OptDef> valid_opts) const
{
	for (const OptDef& opt_def : valid_opts) {
		if (opt_def.long_opt && opt == opt_def.long_opt)
			return &opt_def;
	}
	return nullptr;
}

ParsedArg ArgParser::parse_short_option(std::span<const OptDef> valid_opts)
{
	const char* arg = m_args[m_current_idx].c_str();

	// Determine which character to parse (considering combined options)
	int char_pos = (m_short_opt_pos > 0) ? m_short_opt_pos : 1;
	char opt_char = arg[char_pos];

	// Find option definition
	const OptDef* opt = find_short_opt(opt_char, valid_opts);
	if (!opt) {
		string err = "Unknown option -";
		err += opt_char;
		throw runtime_error(err);
	}

	// Handle argument based on requirement
	if (opt->arg_req == ArgReq::REQUIRED) {
		// Value could be directly after: -d32 or (in combined) -vd32
		if (arg[char_pos + 1] != '\0') {
			m_current_idx++;
			m_short_opt_pos = 0; // Reset combined mode
			return ParsedArg{
				.type = ArgType::OPTION,
				.option_id = opt->id,
				.option_value = &arg[char_pos + 1],
				.positional = {},
			};
		}
		// Or in next arg: -d 32
		else if (m_current_idx + 1 < m_args.size()) {
			m_current_idx++;
			const char* value = m_args[m_current_idx].c_str();
			m_current_idx++;
			m_short_opt_pos = 0;
			return ParsedArg{
				.type = ArgType::OPTION,
				.option_id = opt->id,
				.option_value = value,
				.positional = {},
			};
		} else {
			string err = "Option -";
			err += opt_char;
			err += " requires argument";
			throw runtime_error(err);
		}
	} else if (opt->arg_req == ArgReq::OPTIONAL) {
		// Value only if directly after: -d32
		if (arg[char_pos + 1] != '\0') {
			m_current_idx++;
			m_short_opt_pos = 0;
			return ParsedArg{
				.type = ArgType::OPTION,
				.option_id = opt->id,
				.option_value = &arg[char_pos + 1],
				.positional = {},
			};
		}
		// If next arg exists and doesn't start with '-', it could be the value
		// But only if we're not in combined mode
		else if (m_short_opt_pos == 0 && m_current_idx + 1 < m_args.size() && m_args[m_current_idx + 1][0] != '-') {
			m_current_idx++;
			const char* value = m_args[m_current_idx].c_str();
			m_current_idx++;
			m_short_opt_pos = 0;
			return ParsedArg{
				.type = ArgType::OPTION,
				.option_id = opt->id,
				.option_value = value,
				.positional = {},
			};
		} else {
			// No value provided, that's OK for optional
			// Check if more combined options follow
			if (arg[char_pos + 1] != '\0') {
				m_short_opt_pos = char_pos + 1; // Continue with next char
			} else {
				m_current_idx++;
				m_short_opt_pos = 0;
			}
			return ParsedArg{
				.type = ArgType::OPTION,
				.option_id = opt->id,
				.option_value = {},
				.positional = {},
			};
		}
	} else { // ArgReq::NONE
		// Check if more combined options follow
		if (arg[char_pos + 1] != '\0') {
			// Enter or continue combined mode
			m_short_opt_pos = char_pos + 1;
		} else {
			// No more combined options
			m_current_idx++;
			m_short_opt_pos = 0;
		}
		return ParsedArg{
			.type = ArgType::OPTION,
			.option_id = opt->id,
			.option_value = {},
			.positional = {},
		};
	}
}

ParsedArg ArgParser::parse_long_option(std::span<const OptDef> valid_opts)
{
	const char* arg = m_args[m_current_idx].c_str();
	string_view opt_str = arg + 2; // Skip "--"

	// Check for --option=value
	size_t eq_pos = opt_str.find('=');
	string_view opt_name = (eq_pos != string_view::npos) ? opt_str.substr(0, eq_pos) : opt_str;

	// Find option definition
	const OptDef* opt = find_long_opt(opt_name, valid_opts);
	if (!opt) {
		throw runtime_error(string("Unknown option --") + string(opt_name));
	}

	if (opt->arg_req == ArgReq::REQUIRED) {
		if (eq_pos != string_view::npos) {
			// --option=value
			m_current_idx++;
			return ParsedArg{
				.type = ArgType::OPTION,
				.option_id = opt->id,
				.option_value = opt_str.substr(eq_pos + 1),
				.positional = {},
			};
		} else if (m_current_idx + 1 < m_args.size()) {
			// --option value
			m_current_idx++;
			const char* value = m_args[m_current_idx].c_str();
			m_current_idx++;
			return ParsedArg{
				.type = ArgType::OPTION,
				.option_id = opt->id,
				.option_value = value,
				.positional = {},
			};
		} else {
			throw runtime_error(string("Option --") + string(opt_name) + " requires argument");
		}
	} else if (opt->arg_req == ArgReq::OPTIONAL) {
		if (eq_pos != string_view::npos) {
			// --option=value
			m_current_idx++;
			return ParsedArg{
				.type = ArgType::OPTION,
				.option_id = opt->id,
				.option_value = opt_str.substr(eq_pos + 1),
				.positional = {},
			};
		} else if (m_current_idx + 1 < m_args.size() && m_args[m_current_idx + 1][0] != '-') {
			// --option value (only if next doesn't start with '-')
			m_current_idx++;
			const char* value = m_args[m_current_idx].c_str();
			m_current_idx++;
			return ParsedArg{
				.type = ArgType::OPTION,
				.option_id = opt->id,
				.option_value = value,
				.positional = {},
			};
		} else {
			// No value provided, that's OK for optional
			m_current_idx++;
			return ParsedArg{
				.type = ArgType::OPTION,
				.option_id = opt->id,
				.option_value = {},
				.positional = {},
			};
		}
	} else { // ArgReq::NONE
		if (eq_pos != string_view::npos) {
			throw runtime_error(string("Option --") + string(opt_name) + " does not take an argument");
		}
		m_current_idx++;
		return ParsedArg{
			.type = ArgType::OPTION,
			.option_id = opt->id,
			.option_value = {},
			.positional = {},
		};
	}
}

std::optional<ParsedArg> ArgParser::get_next(std::span<const OptDef> valid_opts)
{
	if (m_current_idx >= m_args.size())
		return std::nullopt;

	const char* arg = m_args[m_current_idx].c_str();

	// Check for end of options marker "--"
	if (!m_positional_only && strcmp(arg, "--") == 0) {
		m_positional_only = true;
		m_current_idx++;
		// Continue parsing, but all remaining are positional
		if (m_current_idx >= m_args.size())
			return std::nullopt;
		arg = m_args[m_current_idx].c_str();
	}

	// Check if it's an option (and we're not in positional-only mode)
	if (!m_positional_only && is_option(arg)) {
		if (is_long_option(arg))
			return parse_long_option(valid_opts);
		else
			return parse_short_option(valid_opts);
	}

	// It's a positional argument
	m_current_idx++;
	return ParsedArg{
		.type = ArgType::POSITIONAL,
		.option_id = {},
		.option_value = {},
		.positional = arg,
	};
}

} // namespace rwmem
