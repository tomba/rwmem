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
	unsigned regsize;
};

struct field_desc {
	const char *name;
	unsigned shift;
	unsigned width;
	uint64_t mask;
	const char *comment;
	uint64_t defval;
};

struct reg_desc {
	const char *name;
	uint64_t address;
	unsigned width;
	const char *comment;
	unsigned num_fields;
	struct field_desc fields[64];
	unsigned max_field_name_len;
};

struct rwmem_opts {
	const char *filename;
	unsigned regsize;
	enum opmode mode;

	const char *address;
	const char *base;
	const char *field;
	const char *value;
	const char *regfile;

	bool show_comments;
	bool show_defval;
};

extern struct rwmem_opts rwmem_opts;

__attribute__ ((noreturn))
void myerr(const char* format, ... );

__attribute__ ((noreturn))
void myerr2(const char* format, ... );

uint64_t readmem(void *addr, int regsize);
void writemem(void *addr, int regsize, uint64_t value);

char *strip(char *str);
int split_str(char *str, const char *delim, char **arr, int num);

void parse_cmdline(int argc, char **argv);

void parse_base(const char *file, const char *arg, uint64_t *base,
		const char **regfile);
struct reg_desc *parse_address(const char *astr, const char *regfile);
struct field_desc *parse_field(const char *fstr, struct reg_desc *reg);
uint64_t parse_value(const char *vstr);

/* parser */
void find_base_address(const char *path, const char *basestr, uint64_t *base, const char **regfile);

#endif /* __RWMEM_H__ */
