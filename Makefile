ifdef CROSS_COMPILE
	CC=$(CROSS_COMPILE)gcc
endif

CFLAGS=-O2 -g -std=c11 -Wall -Wextra -D_XOPEN_SOURCE -D_DEFAULT_SOURCE -D_GNU_SOURCE

rwmem: rwmem.c helpers.c cmdline.c parser.c rwmem.h

clean:
	rm -f rwmem
