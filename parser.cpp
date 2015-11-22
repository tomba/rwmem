#include <string>
#include <ctype.h>
#include <errno.h>
#include <fcntl.h>
#include <stdio.h>
#include <stdlib.h>
#include <stdint.h>
#include <stdarg.h>
#include <string.h>
#include <sys/mman.h>
#include <sys/types.h>
#include <termios.h>
#include <unistd.h>

#include "rwmem.h"

using namespace std;

static void parse_reg_fields(FILE *f, RegDesc *reg)
{
	char str[1024];

	vector<FieldDesc> fields;

	while (fgets(str, sizeof(str), f)) {
		unsigned fh, fl;

		if (str[0] == 0 || isspace(str[0]))
			break;

		vector<string> parts = split(str, ',');
		if (parts.size() != 3)
			myerr("Failed to parse field description: '%s'", str);

		FieldDesc fd;

		fd.name = parts[0];
		fh = stoul(parts[1], 0, 0);
		fl = stoul(parts[2], 0, 0);

		size_t len = fd.name.length();
		if (len > reg->max_field_name_len)
			reg->max_field_name_len = len;

		fd.low = fl;
		fd.high = fh;

		fields.push_back(fd);
	}

	reg->fields = fields;
}

static bool seek_to_next_reg(FILE *f)
{
	char str[1024];

	while (fgets(str, sizeof(str), f)) {
		if (str[0] == 0 || isspace(str[0]))
			return true;
	}

	return false;
}

static bool seek_to_regname(FILE *f, const char *regname)
{
	char str[1024];

	while (true) {
		fpos_t pos;
		int r;

		r = fgetpos(f, &pos);
		if (r)
			myerr2("fgetpos failed");

		if (!fgets(str, sizeof(str), f))
			return false;

		vector<string> parts = split(str, ',');
		if (parts.size() != 3)
			myerr("Failed to parse register description: '%s'", str);

		if (parts[0] == regname) {
			r = fsetpos(f, &pos);
			if (r)
				myerr2("fsetpos failed");

			return true;
		}

		if (!seek_to_next_reg(f))
			return false;
	}

	return false;
}

RegDesc *find_reg_by_name(const char *regfile, const char *regname)
{
	char str[1024];

	FILE *f = fopen(regfile, "r");

	ERR_ON_ERRNO(f == NULL , "Failed to open regfile %s", regfile);

	if (!seek_to_regname(f, regname))
		return NULL;

	if (!fgets(str, sizeof(str), f))
		ERR("Failed to parse register");

	vector<string> parts = split(str, ',');
	ERR_ON(parts.size() != 3, "Failed to parse register description: '%s'", str);

	RegDesc *reg;
	reg = (RegDesc *)malloc(sizeof(RegDesc));
	memset(reg, 0, sizeof(*reg));
	reg->name = parts[0];
	reg->offset = stoul(parts[1], 0, 0);
	reg->width = stoul(parts[2], 0, 0);

	parse_reg_fields(f, reg);

	fclose(f);

	return reg;
}

static bool seek_to_regaddr(FILE *f, uint64_t addr)
{
	char str[1024];

	while (true) {
		fpos_t pos;
		int r;

		r = fgetpos(f, &pos);
		if (r)
			myerr2("fgetpos failed");

		if (!fgets(str, sizeof(str), f))
			return false;

		vector<string> parts = split(str, ',');
		if (parts.size() != 3)
			myerr("Failed to parse register description: '%s'", str);

		uint64_t a = stoul(parts[1], 0, 0);

		if (addr == a) {
			r = fsetpos(f, &pos);
			if (r)
				myerr2("fsetpos failed");

			return true;
		}

		if (!seek_to_next_reg(f))
			return false;
	}

	return false;
}

RegDesc *find_reg_by_address(const char *regfile, uint64_t addr)
{
	char str[1024];

	FILE *f = fopen(regfile, "r");

	ERR_ON_ERRNO(f == NULL , "Failed to open regfile %s", regfile);

	if (!seek_to_regaddr(f, addr))
		return NULL;

	if (!fgets(str, sizeof(str), f))
		ERR("Failed to parse register");

	vector<string> parts = split(str, ',');
	ERR_ON(parts.size() != 3, "Failed to parse register description: '%s'", str);

	RegDesc *reg;
	reg = (RegDesc *)malloc(sizeof(RegDesc));
	memset(reg, 0, sizeof(*reg));
	reg->name = parts[0];
	reg->offset = stoul(parts[1], 0, 0);
	reg->width = stoul(parts[2], 0, 0);

	parse_reg_fields(f, reg);

	fclose(f);

	return reg;
}

/*
 * Find 'basestr' from the given file.
 * Return found base address and (optional) register file name
 */
static void find_base_address(const char *path, const char *basestr,
			      uint64_t *base, const char **regfile)
{
	char str[256];
	int r;

	FILE *f = fopen(path, "r");
	if (f == NULL)
		myerr2("Failed to open '%s'", path);

	size_t arglen = strlen(basestr);

	while (fgets(str, sizeof(str), f)) {
		if (str[0] == 0 || isspace(str[0]))
			continue;

		if (strncmp(basestr, str, arglen) != 0)
			continue;

		if (!isblank(str[arglen]))
			continue;

		r = sscanf(str, "%*s %" SCNx64 " %ms", base, regfile);
		if (r == 2) {
			fclose(f);
			return;
		}

		regfile = NULL;

		r = sscanf(str, "%*s %" SCNx64 "", base);
		if (r == 1) {
			fclose(f);
			return;
		}

		myerr("Failed to parse offset");
	}

	myerr("Failed to find base");
}

void parse_base(const char *cfgfile, const char *basestr, uint64_t *base,
		const char **regfile)
{
	char *endptr;

	*base = strtoull(basestr, &endptr, 0);
	if (*endptr == 0) {
		regfile = NULL;
		return;
	}

	char path[256];

	if (!cfgfile) {
		const char *home = getenv("HOME");
		if (!home)
			myerr("No $HOME");

		sprintf(path, "%s/.rwmem/%s", home, "rwmemrc");
	} else {
		strcpy(path, cfgfile);
	}

	find_base_address(path, basestr, base, regfile);

	/* regfile is relative to the cfgfile, so fix the path */
	strcpy(rindex(path, '/') + 1, *regfile);

	*regfile = strdup(path);
}

int parse_u64(const char *str, uint64_t *value)
{
	uint64_t v;
	char *endptr;

	v = strtoull(str, &endptr, 0);
	if (*endptr != 0)
		return -EINVAL;

	*value = v;
	return 0;
}
