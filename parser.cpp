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
#include <inttypes.h>

#include "helpers.h"

using namespace std;

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
