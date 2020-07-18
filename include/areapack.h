/* THIS FILE AND ITS CONTENT IS DEPRECATED. USE rpackcore.h INSTEAD.
 */
#ifndef AREAPACK_H
#define AREAPACK_H

#define SUCCESS 1
#define FAIL 0

struct rec{
    long width;
    long height;
    long x;
    long y;
    long id;
};

typedef struct rec Rectangle;

typedef struct {
    long width;
    long height;
} Enclosing;

long areapack_algorithm(Rectangle *list, size_t length, Enclosing *en);

#endif
