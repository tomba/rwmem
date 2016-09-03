#pragma once

#include <map>
#include <string>
#include <vector>

class INIReader
{
public:
	void load(std::string filename);

	std::string get(std::string section, std::string name) const;
	std::string get(std::string section, std::string name, std::string default_value) const;

	int get_int(std::string section, std::string name, int default_value) const;
	bool get_bool(std::string section, std::string name, bool default_value) const;

	std::vector<std::string> get_sections() const;
	std::vector<std::string> get_keys(const std::string section) const;


private:
	std::map<std::string, std::map<std::string, std::string>> m_values;
};
