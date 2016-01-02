CC=gcc
CFLAGS= -m64 -std=c99 -pedantic -Wall -Wshadow -Wpointer-arith -Wcast-qual -g
PROG=packer

packer: main.o parse_rec/parse_rec.o
	$(CC) $(CFLAGS) -o $(PROG) $?

main.o: main.c
	$(CC) $(CFLAGS) -c $?

parse_rec/parse_rec.o:
	cd parse_rec; make

clean:
	cd parse_rec; make clean
	rm -f *.o $(PROG)

install:
	@echo Test test daniel


