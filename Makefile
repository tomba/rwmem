ifdef CROSS_COMPILE
	CC=$(CROSS_COMPILE)gcc
endif

CFLAGS=-O2 -std=c99 -Wall -Wextra -D_XOPEN_SOURCE -D_BSD_SOURCE

rwmem: rwmem.c helpers.c cmdline.c rwmem.h

clean:
	rm -f rwmem
