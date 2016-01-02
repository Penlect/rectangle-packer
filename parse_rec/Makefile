CC = gcc
CFLAGS= -m64 -std=c99 -pedantic -Wall -Wshadow -Wpointer-arith -Wcast-qual -g

parse_rec.o: parse_rec.c parse_rec.h
	$(CC) $(CFLAGS) -c parse_rec.c

clean:
	rm -f *.o tester

test: test.c parse_rec.o
	$(CC) $(CFLAGS) test.c parse_rec.o -o tester
	@echo ----- INPUT FILE ------:
	@cat test.txt
	@echo ----- OUTPUT ------:
	./tester test.txt

