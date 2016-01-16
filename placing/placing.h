#define SUCCESS 1
#define FAIL 0

#include "../parse_rec/parse_rec.h"

/* A Cell is a linked structure holding information about the cells.
 * height - the height of the cell.
 * occupied - if the cell is occupied this value will be nonzero.
 * next_cell - next cell right under the current cell. */
struct cell {
    int height;
    int occupied;
    struct cell *next_cell;
};
typedef struct cell Cell;

/* A Col is a linked structure holding information about the columns.
 * width - column width.
 * cell - pointer to the root cell in this column (heighest cell).
 * next_col - next column to the right of the current column */
struct col {
    int width;
    Cell *cell;
    struct col *next_col;
};
typedef struct col Col;

/* A Placing will represent an instance of rectangles placed on an
 * rectangular surface.
 * enclosing_height - enclosing height of the Placing, the sum of all cell
 * heights in any of the colums must be equal to this value.
 * enclosing_width - enclosing width of the Placing, the sum of all column
 * widhts must be equal to this value.
 * cols - pointer to the column positioned farthest to the left.
 * */
typedef struct {
    int enclosing_height;
    int enclosing_width;
    Col *cols;
} Placing;

typedef struct {
    int start_index;
    int end_index;
    int overshoot; /* Length overshoot in cell at end_index */
} Cell_range; 

typedef struct {
    int start_index;
    int end_index;
    int overshoot;
} Col_range;

typedef struct {
    Col_range col_r;
    Cell_range cell_r;
} Region;


Placing *alloc_placing(int enclosing_height,int enclosing_width);
void free_placing(Placing *placing);
int add_rec(Placing *p, struct rec *r);
void print_placing(Placing *placing);
void print_region(Region *reg);

