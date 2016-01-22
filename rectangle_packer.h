#ifndef RECTANGLE_PACKER_H
#define RECTANGLE_PACKER_H

#define SUCCESS 1
#define FAIL 0

struct rec{
    int width;
    int height;
    int x;
    int y;
    int id;
};

typedef struct rec Rectangle;

typedef struct {
    int width;
    int height;
} Enclosing;

#endif
