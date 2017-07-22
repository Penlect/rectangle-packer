#ifndef PLACING_H
#define PLACING_H

#include "rectangle_packer.h"

/* Test if it is possible to place all the rectangles in list in the enclosing rectangle */
int do_placing(Rectangle *list, int length, int enclosing_width, int enclosing_height);

#endif
