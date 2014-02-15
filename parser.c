#include <ctype.h>
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

static struct reg_desc *parse_symbolic_address(const char *regname,
		const char *regfile)
{
	char str[1024];
	size_t regnamelen = strlen(regname);
	bool found = false;
	int r;
	struct reg_desc *reg;

	reg = malloc(sizeof(struct reg_desc));
	memset(reg, 0, sizeof(*reg));

	FILE *f = fopen(regfile, "r");

	if (f == NULL)
		myerr2("Failed to open regfile %s", regfile);

	bool next_is_reg = true;

	while (fgets(str, sizeof(str), f)) {
		if (str[0] == 0 || isspace(str[0])) {
			next_is_reg = true;
			continue;
		}

		if (next_is_reg == false)
			continue;

		if (strncmp(regname, str, regnamelen) != 0 ||
				str[regnamelen] != ',') {
			next_is_reg = false;
			continue;
		}

		char *parts[4] = { 0 };

		r = split_str(str, ",", parts, 4);
		if (r < 3)
			myerr("Failed to parse register description: '%s'", str);
		reg->name = strdup(parts[0]);
		reg->address = strtoull(parts[1], NULL, 0);
		reg->width = strtoul(parts[2], NULL, 0);
		if (parts[3])
			reg->comment = strdup(parts[3]);

		found = true;
		break;
	}

	if (!found) {
		fclose(f);
		myerr("Register not found");
	}

	unsigned field_num = 0;

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

		fd->shift = fl;
		fd->width = fh - fl + 1;
		fd->mask = ((1ULL << fd->width) - 1) << fd->shift;

		field_num++;
	}

	reg->num_fields = field_num;

	fclose(f);

	return reg;
}

static struct reg_desc *parse_numeric_address(const char *astr)
{
	char *endptr;
	uint64_t paddr;
	struct reg_desc *reg;

	paddr = strtoull(astr, &endptr, 0);

	if (*endptr != 0)
		return NULL;

	reg = malloc(sizeof(struct reg_desc));
	memset(reg, 0, sizeof(*reg));
	reg->name = NULL;
	reg->address = paddr;
	reg->num_fields = 0;

	return reg;
}

struct reg_desc *parse_address(const char *astr, const char *regfile)
{
	struct reg_desc *reg;

	reg = parse_numeric_address(astr);
	if (reg)
		return reg;

	if (regfile) {
		reg = parse_symbolic_address(astr, regfile);
		if (reg)
			return reg;
	}

	myerr("Invalid address '%s'", astr);
}

struct field_desc *parse_field(const char *fstr, struct reg_desc *reg)
{
	unsigned fl, fh;
	char *endptr;

	if (!fstr)
		return NULL;

	for (unsigned i = 0; i < reg->num_fields; ++i) {
		struct field_desc *field = &reg->fields[i];

		if (strcmp(fstr, field->name) == 0)
			return field;
	}

	if (sscanf(fstr, "%i:%i", &fh, &fl) != 2) {
		fl = fh = strtoull(fstr, &endptr, 0);
		if (*endptr != 0)
			myerr("Invalid field '%s'", fstr);
	}

	if (fh < fl) {
		unsigned tmp = fh;
		fh = fl;
		fl = tmp;
	}

	struct field_desc *field = malloc(sizeof(struct field_desc));
	memset(field, 0, sizeof(*field));
	field->name = NULL;
	field->shift = fl;
	field->width = fh - fl + 1;
	field->mask = ((1ULL << field->width) - 1) << field->shift;

	return field;
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

uint64_t parse_value(const char *vstr)
{
	if (!vstr)
		return 0;

	char *endptr;

	uint64_t val = strtoull(vstr, &endptr, 0);
	if (*endptr != 0)
		myerr("Invalid value '%s'", vstr);

	return val;
}
