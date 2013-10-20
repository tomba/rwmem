#ifndef __RWMEM_H__
#define __RWMEM_H__

#include <inttypes.h>
#include <stdbool.h>

enum opmode {
	MODE_R,
	MODE_W,
	MODE_RW,
};

struct addr {
	uint64_t paddr;
	void *vaddr;
	int regsize;
};

struct field_desc {
	int shift;
	int width;
	uint64_t mask;
};

struct rwmem_opts {
	const char *filename;
	int regsize;
	enum opmode mode;

	const char *address;
	const char *field;
	const char *value;
};

extern struct rwmem_opts rwmem_opts;

__attribute__ ((noreturn))
void myerr(const char* format, ... );

__attribute__ ((noreturn))
void myerr2(const char* format, ... );

uint64_t readmem(void *addr, int regsize);
void writemem(void *addr, int regsize, uint64_t value);

void parse_cmdline(int argc, char **argv);
uint64_t parse_address(const char *astr);
void parse_field(const char *fstr, struct field_desc *field, int regsize);
uint64_t parse_value(const char *vstr, const struct field_desc *field);

#endif /* __RWMEM_H__ */
