#include <ctype.h>
#include <errno.h>
#include <inttypes.h>
#include <stdio.h>
#include <stdlib.h>
#include <stdbool.h>
#include <stdarg.h>
#include <string.h>

__attribute__ ((noreturn))
void myerr(const char* format, ... )
{
	va_list args;

	va_start(args, format);
	vfprintf(stderr, format, args);
	va_end(args);

	fputs("\n", stderr);

	exit(1);
}

__attribute__ ((noreturn))
void myerr2(const char* format, ... )
{
	va_list args;

	va_start(args, format);
	vfprintf(stderr, format, args);
	va_end(args);

	fprintf(stderr, ": %s\n", strerror(errno));

	exit(1);
}

uint64_t readmem(void *addr, int regsize)
{
	switch(regsize) {
	case 8:
		return *((uint8_t *)addr);
	case 16:
		return *((uint16_t *)addr);
	case 32:
		return *((uint32_t *)addr);
	case 64:
		return *((uint64_t *)addr);
	default:
		myerr("Illegal data regsize '%c'", regsize);
	}
}

void writemem(void *addr, int regsize, uint64_t value)
{
	switch(regsize) {
	case 8:
		*((uint8_t *)addr) = value;
		break;
	case 16:
		*((uint16_t *)addr) = value;
		break;
	case 32:
		*((uint32_t *)addr) = value;
		break;
	case 64:
		*((uint64_t *)addr) = value;
		break;
	}
}

char *strip(char *str)
{
	while (isspace(*str))
		str++;

	int len = strlen(str);

	while (isspace(*(str + len - 1)))
		len--;

	str[len] = 0;

	return str;
}

int split_str(char *str, const char *delim, char **arr, int num)
{
	char *token;
	int i;

	str = strip(str);

	for (i = 0; i < num; ++i) {
		if (i == num - 1)
			token = str;
		else
			token = strsep(&str, delim);

		if (!token)
			break;

		arr[i] = token[0] ? token : NULL;
	}

	return i;
}
