#ifndef __RWMEM_H__
#define __RWMEM_H__

#include <inttypes.h>
#include <stdbool.h>

struct addr {
	uint64_t paddr;
	void *vaddr;
};

struct field_desc {
	unsigned shift;
	unsigned width;
	uint64_t mask;

	const char *name;
	const char *comment;
	uint64_t defval;
};

struct reg_desc {
	uint64_t address;
	unsigned width;

	const char *name;
	const char *comment;
	unsigned num_fields;
	struct field_desc fields[64];
	unsigned max_field_name_len;
};

struct rwmem_op {
	uint64_t address;
	uint64_t range;
	uint64_t value;

	bool write;

	const struct reg_desc *reg;
	const struct field_desc *field;
};

struct rwmem_opts_arg {
	const char *address;
	const char *range;
	const char *field;
	const char *value;

	bool range_is_offset;
};

struct rwmem_opts {
	const char *filename;
	unsigned regsize;
	bool write_only;

	const char *base;
	const char *aliasfile;
	const char *regfile;

	bool show_comments;
	bool show_defval;

	int num_args;
	struct rwmem_opts_arg *args;
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

/* parser */
void parse_base(const char *file, const char *arg, uint64_t *base,
		const char **regfile);
struct reg_desc *parse_address(const char *astr, const char *regfile);
struct field_desc *parse_field(const char *fstr, struct reg_desc *reg);
uint64_t parse_value(const char *vstr);

#endif /* __RWMEM_H__ */
