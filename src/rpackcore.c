/* Core functions and data structures

This file was formmatted with:

$ indent -kr --no-tabs rpackcore.c

*/

#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <assert.h>
#include <limits.h>

#include "rpackcore.h"

/* Cell
   ====
*/

Cell _cell;
Cell *const COL_FULL = &_cell;

/* start_pos computes the starting position of a Cell by returning the
   end position of the previous cell. */
long start_pos(Cell * self)
{
    if (self == NULL) {
        return 0;
    } else if (self->prev == NULL) {
        return 0;
    } else {
        return self->prev->end_pos;
    }
}

/* CellLink
   ========

   The CellLink is used to handle the Grid's rows and columns. The
   CellLink is a doubly linked list and each cell corresponds to a row
   or column in the grid. Each cell has an end position which all
   together define the row and column widths. Each cell has a
   `jump_index`. These indecies are used when checking if a region,
   defined by a row-cell and column-cell, is occupied or not.

*/

/* clear_cell_link restores the CellLink to the "starting state".
   I.e. the CellLink will only have one cell which has the full
   size. */
static void clear_cell_link(CellLink * self)
{
    self->jump_index = 0;
    self->head = &self->cells[0];
    self->head->prev = NULL;
    self->head->next = NULL;
    self->head->end_pos = self->end_pos;
    self->head->jump_index = self->jump_index;
    self->jump_index++;
    return;
}

/* free_cell_link frees the memory allocated by CellLink */
static void free_cell_link(CellLink * cell_link)
{
    if (cell_link == NULL) {
        return;
    }
    if (cell_link->cells != NULL) {
        free(cell_link->cells);
    }
    free(cell_link);
    return;
}

/* alloc_cell_link allocates memory for a new CellLink. `size` refers
   to the maximum number of Cells the CellLink will contain. They are
   all allocated at this step, but only added to the linked-list when
   `cut` is called. */
static CellLink *alloc_cell_link(size_t size, long end_pos)
{
    CellLink *cl = NULL;
    Cell *cells = NULL;
    if ((cl = malloc(sizeof(*cl))) == NULL) {
        return NULL;
    }
    if ((cells = calloc(size, sizeof(*cells))) == NULL) {
        free(cl);
        return NULL;
    }
    if (size == 0) {
        size = 1;
    }
    if (end_pos == 0) {
        end_pos = 1;
    }
    cl->size = size;
    cl->end_pos = end_pos;
    cl->cells = cells;
    clear_cell_link(cl);
    return cl;
}

/* cut will 'split' an existing Cell and add another cell from the
   preallocated list of Cells after it. The end positions will be
   adjusted accordingly. */
static void
cut(CellLink * self, Cell * victim, long end_pos, size_t *src_i,
    size_t *dest_i)
{
    Cell *new_cell = NULL;
    new_cell = &self->cells[self->jump_index];
    new_cell->end_pos = victim->end_pos;
    new_cell->jump_index = *dest_i = self->jump_index;
    self->jump_index++;         /* May overflow size if called to many times */

    new_cell->prev = victim;
    new_cell->next = victim->next;
    victim->next = new_cell;
    victim->end_pos = end_pos;
    if (new_cell->next != NULL) {
        new_cell->next->prev = new_cell;
    }

    *src_i = victim->jump_index;
    return;
}

// =================================

/* JumpMatrix
   ==========

   The JumpMatrix works like a look-up table to check if a region
   defined by a row-cell and column-cell is free or not. If an element
   is NULL that region is free, else occupied.
*/

/* alloc_jump_matrix allocates memory for a new JumpMatrix */
static JumpMatrix alloc_jump_matrix(size_t size)
{
    size_t i, len = 0;
    Cell **ptr, ***arr;

    if (size == 0) {
        size = 1;
    }

    len = sizeof(Cell **) * size + sizeof(Cell *) * size * size;
    if ((arr = (Cell ***) malloc(len)) == NULL) {
        return NULL;
    }

    /* Ptr is now pointing to the first element in of 2D array  */
    ptr = (Cell **) (arr + size);

    /* For loop to point rows pointer to appropriate location in 2D array  */
    for (i = 0; i < size; i++) {
        arr[i] = (ptr + size * i);
    }
    arr[0][0] = NULL;
    return arr;
}

/* copy_row copies a range of elements decided by `jump_index_col`
   from src-row to dest-row. */
static void
copy_row(JumpMatrix self, size_t src_i, size_t dest_i,
         size_t jump_index_col)
{
    size_t index = 0;
    for (index = 0; index < jump_index_col; index++) {
        self[dest_i][index] = self[src_i][index];
    }
}

/* copy_col copies a range of elements decided by `jump_index_row`
   from src-col to dest-col. */
static void
copy_col(JumpMatrix self, size_t src_i, size_t dest_i,
         size_t jump_index_row)
{
    size_t index = 0;
    for (index = 0; index < jump_index_row; index++) {
        self[index][dest_i] = self[index][src_i];
    }
}

/* Grid
   ====

   The Grid contains two CellLinks - one for rows and one for
   columns. It also contains a JumpMatrix to keep track of which
   regions are free or not.
*/

/* grid_alloc allocates memory for a new Grid */
Grid *grid_alloc(size_t size, long width, long height)
{
    Grid *grid = NULL;
    if ((grid = malloc(sizeof(*grid))) == NULL) {
        return NULL;
    }
    if (size == 0) {
        size = 1;
    }
    grid->size = size;
    grid->width = width;
    grid->height = height;
    grid->cols = NULL;
    grid->rows = NULL;
    grid->jump_matrix = NULL;

    if ((grid->cols = alloc_cell_link(size, width)) == NULL) {
        grid_free(grid);
        return NULL;
    }
    if ((grid->rows = alloc_cell_link(size, height)) == NULL) {
        grid_free(grid);
        return NULL;
    }
    if ((grid->jump_matrix = alloc_jump_matrix(size)) == NULL) {
        grid_free(grid);
        return NULL;
    }

    return grid;
}

/* grid_free frees the memory allocated by Grid  */
void grid_free(Grid * grid)
{
    if (grid == NULL) {
        return;
    }
    if (grid->cols != NULL) {
        free_cell_link(grid->cols);
    }
    if (grid->rows != NULL) {
        free_cell_link(grid->rows);
    }
    if (grid->jump_matrix != NULL) {
        free(grid->jump_matrix);
    }
    free(grid);
}

/* grid_clear clears the CellLinks and JumpMatrix to "start state" */
void grid_clear(Grid * self)
{
    if (self == NULL) {
        return;
    }
    self->cols->end_pos = self->width;
    clear_cell_link(self->cols);
    self->rows->end_pos = self->height;
    clear_cell_link(self->rows);
    self->jump_matrix[0][0] = NULL;
}

/* grid_split will split the grid by cutting a column and a row in two
   in such a way that the region `reg` will fit the grid */
void grid_split(Grid * self, Region * reg)
{
    size_t src_i, dest_i;
    Cell *r_cell = NULL;
    Cell *c_cell = NULL;
    Cell *jump_target = NULL;
    assert(reg->row_end_pos <= reg->row_cell->end_pos);
    assert(reg->col_end_pos <= reg->col_cell->end_pos);

    if (reg->row_end_pos < reg->row_cell->end_pos) {
        cut(self->rows, reg->row_cell, reg->row_end_pos, &src_i, &dest_i);
        copy_row(self->jump_matrix, src_i, dest_i, self->cols->jump_index);
    }

    if (reg->col_end_pos < reg->col_cell->end_pos) {
        cut(self->cols, reg->col_cell, reg->col_end_pos, &src_i, &dest_i);
        copy_col(self->jump_matrix, src_i, dest_i, self->rows->jump_index);
    }

    /* Compute jump_target */
    if (reg->row_cell->next == NULL) {
        assert(reg->row_cell->end_pos == self->height);
        jump_target = COL_FULL;
    } else {
        jump_target = reg->row_cell->next;
    }

    for (r_cell = reg->row_cell_start; r_cell != NULL;
         r_cell = r_cell->next) {
        assert(self->jump_matrix[r_cell->jump_index]
               [reg->col_cell_start->jump_index] == NULL);
        self->jump_matrix[r_cell->jump_index][reg->
                                              col_cell_start->jump_index] =
            jump_target;
        if (r_cell == reg->row_cell) {
            break;
        }
    }

    if (reg->col_cell_start == reg->col_cell) {
        return;
    }

    for (c_cell = reg->col_cell_start->next; c_cell != NULL;
         c_cell = c_cell->next) {
        assert(self->jump_matrix[reg->row_cell_start->jump_index]
               [c_cell->jump_index] == NULL);
        self->jump_matrix[reg->row_cell_start->
                          jump_index][c_cell->jump_index] = jump_target;
        if (c_cell == reg->col_cell) {
            break;
        }
    }
    return;
}

/* grid_find_region searches the grid for a free space that can
   contain the region `reg`. */
int grid_find_region(Grid * grid, Rectangle * rectangle, Region * reg)
{
    long rec_col_end_pos, rec_row_end_pos;
    long delta = rectangle->height;
    long tmp;
    Cell *col_cell_start = NULL;
    Cell *col_cell = NULL;
    Cell *row_cell_start = NULL;
    Cell *row_cell = NULL;

    Cell *jump_first = NULL;
    Cell *jump_target = NULL;

    /* Loop over columns */
    rec_col_end_pos = rectangle->width;
    col_cell_start = grid->cols->head;
    while (col_cell_start != NULL) {

        /* Loop over rows */
        rec_row_end_pos = rectangle->height;
        row_cell_start = row_cell = grid->rows->head;
        jump_first = NULL;
        while (row_cell_start != NULL) {

            /* Check if cell is free. The cell is free if the
               jump_matrix element is NULL. If not NULL, it is a
               pointer to the next row cell to test. This is an
               optimization to prevent checking cells we already know
               are not free.  */
            jump_target =
                grid->jump_matrix[row_cell->
                                  jump_index][col_cell_start->jump_index];

            if (jump_target != NULL) {
                if (jump_first == NULL) {
                    jump_first = row_cell;
                } else {
                    /* This is an optimization to make bigger jumps */
                    grid->jump_matrix[jump_first->jump_index]
                        [col_cell_start->jump_index] = jump_target;
                }
            }

            /* Column full. Abort this column. */
            if (jump_target == COL_FULL) {
                break;
            }

            /* Normal jump */
            if (jump_target != NULL) {
                row_cell = row_cell_start = jump_target;
                rec_row_end_pos =
                    row_cell->prev->end_pos + rectangle->height;
                continue;
            }

            /* Free slot. Reset jump_first. */
            jump_first = NULL;

            /* Rectangle hight still doesn't fit; continue search */
            if (row_cell->end_pos < rec_row_end_pos) {
                row_cell = row_cell->next;
                if (row_cell == NULL) {
                    /* No more rows. Abort. */
                    if ((tmp = rec_row_end_pos - grid->height) < delta) {
                        delta = tmp;
                    }
                    break;
                }
                continue;
            }

            /* Free row-range found. Now we need to search column-wise
               to check if free space is available in that direction
               as well. */
            col_cell = col_cell_start;
            while (col_cell != NULL) {
                jump_target =
                    grid->
                    jump_matrix[row_cell_start->jump_index][col_cell->
                                                            jump_index];
                if (jump_target != NULL) {
                    break;
                }
                if (rec_col_end_pos <= col_cell->end_pos) {
                    /* Free region found */
                    reg->row_cell_start = row_cell_start;
                    reg->row_cell = row_cell;
                    reg->row_end_pos = rec_row_end_pos;
                    reg->col_cell_start = col_cell_start;
                    reg->col_cell = col_cell;
                    reg->col_end_pos = rec_col_end_pos;
                    return delta;
                }
                col_cell = col_cell->next;
            }
            /* Todo: Consider removing this break to continue the
               search further down the row. */
            break;
        }

        /* Prepare new iteration */
        rec_col_end_pos = col_cell_start->end_pos + rectangle->width;
        col_cell_start = col_cell_start->next;

        /* Too wide to fit in any remaining columns. Abort. */
        if (rec_col_end_pos > grid->width) {
            break;
        }
    }
    /* Failure! Couldn't find a free region. */
    reg->col_cell = NULL;       /* Used as fail signal */
    return delta;
}

/* grid_search_bbox will search for a bbox with smallest area that can
   contain all the rectangles, `sizes`, in the `grid`. The bounding
   box must also satisfy the bounding box restrictions `bbr`. */
long
grid_search_bbox(Grid * grid, Rectangle * sizes, BBoxRestrictions * bbr)
{
    size_t i = 0;
    long happy_area = 1;        /* Todo */
    long start_width, start_area, area, best_h, best_w, delta, d, grid_w;
    Region reg;

    grid->height = bbr->min_height;
    grid->width = bbr->max_area / grid->height;
    if (bbr->max_width < grid->width) {
        grid->width = bbr->max_width;
    }
    start_width = grid->width;

    start_area = area = bbr->max_area - 1;
    best_w = grid->width;
    best_h = grid->height;

    while (grid->height <= bbr->max_height
           && bbr->min_width <= grid->width) {
        grid_clear(grid);
        delta = bbr->max_height;
        grid_w = 0;
        /* Find position for all rectangles */
        for (i = 0; i < grid->size - 1; i++) {
            d = grid_find_region(grid, &sizes[i], &reg);
            if (d < delta) {
                delta = d;
            }
            /* Break if failure */
            if (reg.col_cell == NULL) {
                break;
            }
            /* Keep track of current grid width */
            if (grid_w < reg.col_end_pos) {
                grid_w = reg.col_end_pos;
            }
            assert(grid_w <= grid->width);
            grid_split(grid, &reg);
        }
        /* All rectangles successfully packed? Update area. */
        if (reg.col_cell != NULL) {
            best_h = grid->height;
            best_w = grid_w;
            assert(best_h * best_w < area);
            area = best_h * best_w;
            assert(area <= bbr->max_area);
            if (area <= happy_area) {
                /* We have found a solution the caller is happy
                   with. End search. */
                goto done;
            }
        }

        /* Inc height */
        grid->height += delta;

        /* Dec width limit */
        grid->width = area / grid->height;
	if (grid->width > bbr->max_width) {
	    grid->width = bbr->max_width;
	}
        if (grid->width * grid->height == area) {
            grid->width -= 1;
        }
        assert(grid->width * grid->height < area);
    }

    /* If the area hasn't changed from the start it means that we
       never found a successful packing in the while loop. We set the
       grid maximum with/height and return a negative value to
       indicate failure. */
    if (start_area == area) {
        grid->width = start_width;
        grid->height = bbr->min_height;
        return -1;
    }
    /* Success */
  done:grid->width = best_w;
    grid->height = best_h;
    return best_h;
}

/* ==========
 * TEST CASES
 * ==========
 */
#ifndef NDEBUG

static void test_cell_link(void)
{
    CellLink *cl = NULL;
    cl = alloc_cell_link(100, 1234);
    assert(cl != NULL);

    assert(cl->size == 100);
    assert(cl->end_pos == 1234);
    assert(cl->jump_index == 1);
    assert(cl->head == &cl->cells[0]);
    assert(cl->head->prev == NULL);
    assert(cl->head->next == NULL);
    assert(cl->head->end_pos == cl->end_pos);

    free_cell_link(cl);
}

static void test_cell_link_cut(void)
{
    CellLink *cl = NULL;
    cl = alloc_cell_link(100, 1000);
    assert(cl != NULL);

    size_t src_i, dest_i;
    cut(cl, cl->head, 111, &src_i, &dest_i);

    assert(cl->size == 100);
    assert(cl->end_pos == 1000);
    assert(cl->jump_index == 2);
    assert(cl->head == &cl->cells[0]);
    assert(cl->head->prev == NULL);
    assert(cl->head->next == &cl->cells[1]);
    assert(cl->head->end_pos == 111);

    assert(src_i == 0);
    assert(dest_i == 1);

    assert(cl->cells[1].prev == cl->head);
    assert(cl->cells[1].end_pos == 1000);

    cut(cl, cl->head, 11, &src_i, &dest_i);

    assert(src_i == 0);
    assert(dest_i == 2);
    assert(cl->head->end_pos == 11);
    assert(cl->head->next->jump_index == 2);
    assert(start_pos(cl->head->next) == 11);

    clear_cell_link(cl);
    assert(cl->jump_index == 1);

    free_cell_link(cl);
}

static void test_jump_matrix(void)
{
    Cell *cell = NULL;
    JumpMatrix jm = NULL;
    size_t i, j, size;

    size = 100;
    jm = alloc_jump_matrix(size);
    assert(jm != NULL);
    assert(jm[0][0] == NULL);

    for (i = 0; i < size; i++) {
        for (j = 0; j < size; j++) {
            jm[i][j] = cell;
        }
    }

    free(jm);
}

static void test_jump_matrix_copy(void)
{
    JumpMatrix jm = NULL;
    size_t i, j, size;

    size = 2;
    jm = alloc_jump_matrix(size);
    assert(jm != NULL);
    assert(jm[0][0] == NULL);

    copy_row(jm, 0, 1, 1);
    copy_col(jm, 0, 1, 2);

    for (i = 0; i < size; i++) {
        for (j = 0; j < size; j++) {
            assert(jm[i][j] == NULL);
        }
    }

    free(jm);
}

static void test_grid(void)
{
    Grid *grid = NULL;
    grid = grid_alloc(100, 120, 50);
    assert(grid != NULL);
    assert(grid->size == 100);
    assert(grid->width == 120);
    assert(grid->height == 50);
    assert(grid->cols != NULL);
    assert(grid->rows != NULL);
    assert(grid->jump_matrix != NULL);
    grid_free(grid);
}

static void test_grid_split(void)
{
    Grid *grid = NULL;
    Region reg;
    grid = grid_alloc(100, 120, 50);
    assert(grid != NULL);

    reg.row_cell_start = reg.row_cell = grid->rows->head;
    reg.row_end_pos = 30;
    reg.col_cell_start = reg.col_cell = grid->cols->head;
    reg.col_end_pos = 30;
    grid_split(grid, &reg);

    assert(grid->rows->head->end_pos == 30);
    assert(grid->cols->head->end_pos == 30);
    assert(grid->rows->head->next->end_pos == 50);
    assert(grid->cols->head->next->end_pos == 120);

    Cell _cell;
    Cell *test_cell = &_cell;
    grid->jump_matrix[0][0] = test_cell;

    reg.row_cell_start = reg.row_cell = grid->rows->head->next;
    reg.row_end_pos = 40;
    reg.col_cell_start = reg.col_cell = grid->cols->head;
    reg.col_end_pos = 10;
    grid_split(grid, &reg);

    assert(grid->jump_matrix[0][0] == test_cell);
    assert(grid->jump_matrix[0][1] == NULL);
    assert(grid->jump_matrix[0][2] == test_cell);

    assert(grid->jump_matrix[1][0] == grid->rows->head->next->next);
    assert(grid->jump_matrix[1][1] == NULL);
    assert(grid->jump_matrix[1][2] == NULL);

    assert(grid->jump_matrix[2][0] == NULL);
    assert(grid->jump_matrix[2][1] == NULL);
    assert(grid->jump_matrix[2][2] == NULL);

    grid_free(grid);
}

int main(void)
{
    test_cell_link();
    test_cell_link_cut();
    printf("CELL LINK: PASSED\n");
    test_jump_matrix();
    test_jump_matrix_copy();
    printf("JUMP MATRIX: PASSED\n");
    test_grid();
    test_grid_split();
    printf("GRID: PASSED\n");
    return 0;
}
#endif
