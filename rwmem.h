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
	bool writeonly;
};

extern struct rwmem_opts rwmem_opts;

__attribute__ ((noreturn))
void myerr(const char* format, ... );

__attribute__ ((noreturn))
void myerr2(const char* format, ... );


#endif /* __RWMEM_H__ */
