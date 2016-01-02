CC=gcc
CFLAGS= -m64 -std=c99 -pedantic -Wall -Wshadow -Wpointer-arith -Wcast-qual
PROG=packer
packer: main.o
	$(CC) $(CFLAGS) -o $(PROG) $?

main.o: main.c
	$(CC) $(CFLAGS) -c $?

clean:
	-rm *.o $(PROG)

install:
	@echo Test test daniel


