#include <algorithm>
#include <cctype>
#include <cstdlib>
#include <string>
#include <exception>
#include <stdexcept>

#include "inih/ini.h"
#include "inireader.h"

using namespace std;

static string to_lower(string str)
{
	transform(str.begin(), str.end(), str.begin(), ::tolower);
	return str;
}

static int value_handler(void* user, const char* section, const char* name, const char* value)
{
	auto& map = *(std::map<std::string, std::map<std::string, std::string>>*)user;

	map[to_lower(section)][to_lower(name)] = value;

	return 1;
}

static std::map<std::string, std::map<std::string, std::string>> parse_file(string filename)
{
	std::map<std::string, std::map<std::string, std::string>> map;

	int r = ini_parse(filename.c_str(), value_handler, &map);
	if (r > 0)
		throw exception(); // parse error

	return map;
}

void INIReader::load(std::string filename)
{
	m_values = parse_file(filename);
}

string INIReader::get(string section, string name) const
{
	return m_values.at(to_lower(section)).at(to_lower(name));
}

string INIReader::get(string section, string name, string default_value) const
{
	try {
		return get(section, name);
	} catch (...) {
		return default_value;
	}
}

int INIReader::get_int(string section, string name, int default_value) const
{
	try {
		string valstr = get(section, name);
		return stoi(valstr, nullptr, 0);
	} catch (...) {
		return default_value;
	}
}

bool INIReader::get_bool(string section, string name, bool default_value) const
{
	try {
		string valstr = get(section, name);
		valstr = to_lower(valstr);
		if (valstr == "true" || valstr == "yes" || valstr == "on" || valstr == "1")
			return true;
		else if (valstr == "false" || valstr == "no" || valstr == "off" || valstr == "0")
			return false;
		else
			return default_value;
	} catch (...) {
		return default_value;
	}
}

vector<string> INIReader::get_sections() const
{
	vector<string> sections;

	for (const auto& section : m_values)
		sections.push_back(section.first);

	return sections;
}

vector<string> INIReader::get_keys(const string section) const
{
	vector<string> keys;

	for (const auto& sec : m_values) {
		if (sec.first != section)
			continue;

		for (const auto& key : sec.second)
			keys.push_back(key.first);

		break;
	}

	return keys;
}
