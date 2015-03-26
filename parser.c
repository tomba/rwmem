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

static void parse_reg_fields(FILE *f, struct reg_desc *reg)
{
	char str[1024];
	unsigned field_num = 0;
	int r;

	while (fgets(str, sizeof(str), f)) {
		unsigned fh, fl;

		if (str[0] == 0 || isspace(str[0]))
			break;

		char *parts[6] = { 0 };

		r = split_str(str, ",", parts, 6);
		if (r < 3)
			myerr("Failed to parse field description: '%s'", str);

		struct field_desc *fd = &reg->fields[field_num];

		fd->name = strdup(parts[0]);
		fh = strtoul(parts[1], NULL, 0);
		fl = strtoul(parts[2], NULL, 0);
		// parts[3] is mode
		if (parts[4])
			fd->defval = strtoull(parts[4], NULL, 0);
		if (parts[5])
			fd->comment = strdup(parts[5]);

		size_t len = strlen(fd->name);
		if (len > reg->max_field_name_len)
			reg->max_field_name_len = len;

		fd->low = fl;
		fd->high = fh;
		fd->width = fh - fl + 1;
		fd->mask = GENMASK(fh, fl);

		field_num++;
	}

	reg->num_fields = field_num;
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

		char *parts[4] = { 0 };

		r = split_str(str, ",", parts, 4);
		if (r < 3)
			myerr("Failed to parse register description: '%s'", str);

		if (strcmp(regname, parts[0]) == 0) {
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

struct reg_desc *find_reg_by_name(const char *regfile, const char *regname)
{
	char str[1024];

	FILE *f = fopen(regfile, "r");

	ERR_ON_ERRNO(f == NULL , "Failed to open regfile %s", regfile);

	if (!seek_to_regname(f, regname))
		return NULL;

	if (!fgets(str, sizeof(str), f))
		ERR("Failed to parse register");

	char *parts[4] = { 0 };

	int r = split_str(str, ",", parts, 4);

	ERR_ON(r < 3, "Failed to parse register description: '%s'", str);

	struct reg_desc *reg;
	reg = malloc(sizeof(struct reg_desc));
	memset(reg, 0, sizeof(*reg));
	reg->name = strdup(parts[0]);
	reg->offset = strtoull(parts[1], NULL, 0);
	reg->width = strtoul(parts[2], NULL, 0);
	if (parts[3])
		reg->comment = strdup(parts[3]);

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

		char *parts[4] = { 0 };

		r = split_str(str, ",", parts, 4);
		if (r < 3)
			myerr("Failed to parse register description: '%s'", str);

		uint64_t a = strtoull(parts[1], NULL, 0);

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

struct reg_desc *find_reg_by_address(const char *regfile, uint64_t addr)
{
	char str[1024];

	FILE *f = fopen(regfile, "r");

	ERR_ON_ERRNO(f == NULL , "Failed to open regfile %s", regfile);

	if (!seek_to_regaddr(f, addr))
		return NULL;

	if (!fgets(str, sizeof(str), f))
		ERR("Failed to parse register");

	char *parts[4] = { 0 };

	int r = split_str(str, ",", parts, 4);

	ERR_ON(r < 3, "Failed to parse register description: '%s'", str);

	struct reg_desc *reg;
	reg = malloc(sizeof(struct reg_desc));
	memset(reg, 0, sizeof(*reg));
	reg->name = strdup(parts[0]);
	reg->offset = strtoull(parts[1], NULL, 0);
	reg->width = strtoul(parts[2], NULL, 0);
	if (parts[3])
		reg->comment = strdup(parts[3]);

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