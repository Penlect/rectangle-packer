#ifndef CORE_H
#define CORE_H

#include <stdlib.h>

// Cell
struct cell {
    long end_pos;
    size_t jump_index;
  
    struct cell *prev;
    struct cell *next;
};
typedef struct cell Cell;

long start_pos(Cell *cell);

// CellLink
struct cell_link {
    size_t size;
    long end_pos;
    size_t jump_index;
    Cell *cells;
    Cell *head;
};
typedef struct cell_link CellLink;

// JumpMatrix
typedef Cell ***JumpMatrix;

// Region
struct region {
    Cell *row_cell_start;
    Cell *row_cell;
    long row_end_pos;
    Cell *col_cell_start;
    Cell *col_cell;
    long col_end_pos;
};
typedef struct region Region;

// Rectangle
struct rectangle {
    long width;
    long height;
    long x;
    long y;
    size_t index;
    long area;
    int wide;
    int rotated;
};
typedef struct rectangle Rectangle;

// BBoxRestrictions
struct bbox_restrictions {
    long min_width;
    long max_width;
    long min_height;
    long max_height;
    long max_area;
};
typedef struct bbox_restrictions BBoxRestrictions;

// Grid
struct grid {
    size_t size;
    long width;
    long height;

    CellLink *cols;
    CellLink *rows;

    JumpMatrix jump_matrix;
};
typedef struct grid Grid;

Grid *grid_alloc(size_t size, long width, long height);
void grid_free(Grid *grid);
void grid_clear(Grid *self);
int grid_find_region(Grid *grid, Rectangle *rectangle, Region *reg);
void grid_split(Grid *self, Region *reg);
long grid_search_bbox(Grid *grid, Rectangle *sizes, BBoxRestrictions *bbr);

#endif
