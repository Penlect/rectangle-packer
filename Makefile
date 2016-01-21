CC=gcc
CFLAGS= -m64 -std=c99 -pedantic -Wall -Wshadow -Wpointer-arith -Wcast-qual
PROG=packer

packer: main.c parse_rec/parse_rec.c placing/placing.c visualisation/visualisation.c
	$(CC) $(CFLAGS) -o $(PROG) $? -lSDL2

clean:
	rm packer

#main.o: main.c
#	$(CC) $(CFLAGS) -c $?
#
#parse_rec/parse_rec.o: parse_rec/parse_rec.c
#	cd parse_rec; make
#
#clean:
#	cd parse_rec; make clean
#	rm -f *.o $(PROG)
#
#install:
#	@echo Test test daniel

