/* THIS FILE AND ITS CONTENT IS DEPRECATED. USE rpackcore.c INSTEAD.
 */

#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "areapack.h"


/* A Cell is a linked structure holding information about the cells.
 * height - the height of the cell.
 * occupied - if the cell is occupied this value will be nonzero.
 * next_cell - next cell right under the current cell. */
struct cell {
    long height;
    long occupied;
    struct cell *next_cell;
};
typedef struct cell Cell;

/* A Col is a linked structure holding information about the columns.
 * width - column width.
 * cell - pointer to the root cell in this column (heighest cell).
 * next_col - next column to the right of the current column */
struct col {
    long width;
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
    long enclosing_height;
    long enclosing_width;
    Col *cols;
} Placing;

typedef struct {
    long start_index;
    long end_index;
    long overshoot; /* Length overshoot in cell at end_index */
} Cell_range;

typedef struct {
    long start_index;
    long end_index;
    long overshoot;
} Col_range;

typedef struct {
    Col_range col_r;
    Cell_range cell_r;
} Region;

static Placing *alloc_placing(long enclosing_width, long enclosing_height)
{
    Placing *p_pt;
    Col *c_pt;
    Cell *r_pt;

    /* Allocate memory for the three pointers needed */
    if( (p_pt = malloc(sizeof(*p_pt))) == NULL){
        fprintf(stderr, "Error, could't allocate memory for Placing\n");
        return NULL;
    }
    if( (c_pt = malloc(sizeof(*c_pt))) == NULL){
        fprintf(stderr, "Error, could't allocate memory for Col\n");
        free(p_pt);
        return NULL;
    }
    if( (r_pt = malloc(sizeof(*r_pt))) == NULL){
        fprintf(stderr, "Error, could't allocate memory for Cell\n");
        free(c_pt);
        free(p_pt);
        return NULL;
    }

    /* Initialize Cell */
    r_pt->height = enclosing_height;
    r_pt->occupied = 0;
    r_pt->next_cell = NULL;

    /* Initialize Col */
    c_pt->width = enclosing_width;
    c_pt->next_col = NULL;
    c_pt->cell = r_pt;

    /* Initialize Placing */
    p_pt->enclosing_width = enclosing_width;
    p_pt->enclosing_height = enclosing_height;
    p_pt->cols = c_pt;

    return p_pt;
}

static void free_placing(Placing *placing)
{
    Col *col = NULL;

    /* Return if placing already is NULL */
    if(placing == NULL){
        return;
    }
    /* Loop over the columns and free them and the cells */
    col = placing->cols;
    while(col != NULL){
        /* Free all cells for this col */
        Cell *cell = col->cell;
        while(cell != NULL){
            Cell *temp_r = cell;
            cell = cell->next_cell;
            free(temp_r);
        }
        /* Save the next col and free the current one */
        Col *temp_c = col;
        col = col->next_col;
        free(temp_c);
    }
    free(placing);
    return;
}

static long try_fit_height_in_col(Col *col, long height, Cell_range *cell_r)
{
	/* Loop over the cells in the column to find a consecutive sequence of cells
	which is not occupied that have a hight greater than 'height'. Result is set
	in cell_r */
    long i; // Loop index
    Cell *cell = NULL; // Will point to each cell as we loop over col
    long sum_height = 0;

    if(col == NULL){
        fprintf(stderr, "Error. col pointer was NULL.\n");
        return 0;
    }
    else if(height <= 0){
        fprintf(stderr, "Error. height must be positive.\n");
        return 0;
    }

    cell_r->start_index = 0;
    /* Loop over the cells in the column */
    for(cell = col->cell, i = 0; cell != NULL; cell=cell->next_cell, i++){
        /* If the cell is occupied, reset sum and update start_index candidate
         * else, check if the accumulated sum cover the (rectangle) height */
        if(cell->occupied){
            sum_height = 0;
            cell_r->start_index = i + 1;
        }
        else{
            if(sum_height + cell->height > height){
                cell_r->end_index = i;
                cell_r->overshoot = height - sum_height;
                return 1;
            }
            else if(sum_height + cell->height == height){
                /* No splitting will be needed */
                cell_r->end_index = i;
                cell_r->overshoot = 0;
                return 1;
            }
            sum_height += cell->height;
        }
    }
    /* If we arrive here the rectangle did't fit in the column */
    return 0;
}

/* Jump forward 'offest' cells relative to base */
static Cell *step_offset(Cell *base, long offset)
{
    long i;
    Cell *cell = base;

    if(base == NULL){
        fprintf(stderr, "Error. Basepointer was NULL.\n");
        return NULL;
    }
    for(i = 0; i < offset; i++){
        cell = cell->next_cell;
        if(cell == NULL){
            fprintf(stderr, "Error. Offset to large.\n");
            return NULL;
        }
    }
    return cell;
}

/* Find region in which the rectangle can fit */
static long find_region(Placing *placing, Rectangle *rectangle, Region *reg)
{
    Col *col;
    long i;
    /* Loop over every column */
    for(col = placing->cols, i = 0; col != NULL; col=col->next_col, i++){
        Col_range col_r;
        Cell_range cell_r;
        long sum_width = 0;
        Col *temp;

        /* Check if this column can fit rectangle's height */
        if(!try_fit_height_in_col(col, rectangle->height, &cell_r)){
            /* Nope, did't fit */
            continue;
        }
        /* Loop over comming columns and check if cell at i
         * is empty for the whole rectangle width */
        col_r.start_index = i;
        col_r.end_index = i;
        for(temp = col; temp != NULL; temp=temp->next_col){
            Cell *cell = step_offset(temp->cell, cell_r.start_index);
            if(cell->occupied){
                /* Won't fit */
                break;
            }
            else{
                if(sum_width + temp->width > rectangle->width){
                    /* (Split will be needed )*/
                    col_r.overshoot = rectangle->width - sum_width;
                    reg->col_r = col_r;
                    reg->cell_r = cell_r;
                    return SUCCESS;
                }
                else if(sum_width + temp->width == rectangle->width){
                    /* (No split will be needed) */
                    col_r.overshoot = 0;
                    reg->col_r = col_r;
                    reg->cell_r = cell_r;
                    return SUCCESS;
                }
                sum_width += temp->width;
                col_r.end_index++;
            }
        }
    }
    return FAIL;
}

static long split(Placing *placing, Region *reg)
{
    Col *col = NULL;
    Cell *cell = NULL;
    long i;
    Col *col_split_me = NULL;

    /* Split cells horizontally */
    for(col = placing->cols, i = 0; col != NULL; col=col->next_col, i++){
        /* We only need to split if we have overshoot */
        if(reg->cell_r.overshoot > 0){
            cell = step_offset(col->cell, reg->cell_r.end_index);
            Cell *new_cell;

            if( (new_cell = malloc(sizeof(*new_cell))) == NULL ){
                fprintf(stderr, "Error. Failed to allocate memory for new cell.\n");
                return FAIL;
            }
            /* Set the fields for the new cell */
            new_cell->height = cell->height - reg->cell_r.overshoot;
            new_cell->occupied = cell->occupied;
            new_cell->next_cell = cell->next_cell;

            /* Update the old cell */
            cell->height = reg->cell_r.overshoot;
            cell->next_cell = new_cell;
        }

        /* Save the column that we want to split vertically */
        if(i == reg->col_r.end_index){
            col_split_me = col;
        }
    }

    /* We only need to split if we have overshoot */
    if(reg->col_r.overshoot > 0){
        /* Split cols vertically */
        if(col_split_me == NULL){
            fprintf(stderr, "Error. Failed to find column to split.\n");
            return FAIL;
        }

        Col *new_col;
        /* Allocate memory for new column */
        if( (new_col = malloc(sizeof(*new_col))) == NULL ){
            fprintf(stderr, "Error. Failed to allocate memory for new col.\n");
            return FAIL;
        }
        /* Allocate memory for new cell root */
        if( (new_col->cell = malloc(sizeof(*new_col->cell))) == NULL ){
            fprintf(stderr, "Error. Failed to allocate memory for new cell root.\n");
            return FAIL;
        }
        /* Set the fields for the new column */
        new_col->width = col_split_me->width - reg->col_r.overshoot;
        Cell *tail = new_col->cell;
        for(cell = col_split_me->cell; cell != NULL; cell=cell->next_cell){
            tail->height = cell->height;
            tail->occupied = cell->occupied;
            if(cell->next_cell == NULL){
                tail->next_cell = NULL;
                break;
            }
            if( (tail->next_cell = malloc(sizeof(*tail->next_cell))) == NULL ){
                fprintf(stderr, "Error. Failed to allocate memory for new cell.\n");
                return FAIL;
            }
            tail = tail->next_cell;
        }
        new_col->next_col = col_split_me->next_col;

        /* Update the old column */
        col_split_me->width = reg->col_r.overshoot;
        col_split_me->next_col = new_col;
    }

    return SUCCESS;
}

/* Update the cells in placing so that they are correctly occupied */
static long update(Placing *placing, Rectangle *rectangle, Region *reg)
{
    Col *col;
    Cell *cell;
    long i;
    long k;
    long x = 0;
    long y = 0;
    long done = 0;
    if(rectangle->id == 0){
        fprintf(stderr, "Error. Rectangle can't have id = 0.\n");
        return FAIL;
    }
    /* Loop over every column */
    for(col = placing->cols, i = 0; col != NULL; col=col->next_col, i++){
        if(i > reg->col_r.end_index){
            break;
        }
        if(i >= reg->col_r.start_index){
            /* Loop over every cell */
            for(cell = col->cell, k = 0; cell != NULL; cell=cell->next_cell, k++){
                if(k > reg->cell_r.end_index){
                    break;
                }
                if(k >= reg->cell_r.start_index){
                    cell->occupied = rectangle->id;
                    if(!done){
                        rectangle->x = x;
                        rectangle->y = y;
                        done = 1;
                    }
                }
                y += cell->height;
            }
        }
        x += col->width;
    }
    return SUCCESS;
}

static long add_rec(Placing *p, Rectangle *r)
{
    long status;
    Region reg;

    status = find_region(p, r, &reg);
    if(status == FAIL){
        return FAIL;
    }

    status = split(p, &reg);
    if(status == FAIL){
        fprintf(stderr, "Error in splitting.\n");
        return FAIL;
    }

    status = update(p, r, &reg);
    if(status == FAIL){
        fprintf(stderr, "Error in updating.\n");
        return FAIL;
    }

    return status;
}

static long do_placing(Rectangle *list, size_t length, long enclosing_width, long enclosing_height)
{
    size_t i = 0;

    Placing *p = alloc_placing(enclosing_width, enclosing_height);
    for(i = 0; i < length; i++){
        if(!add_rec(p, list + i)){
            free_placing(p);
            return FAIL;
        }
    }
    free_placing(p);
    return SUCCESS;
}

/* Finds the sum of all the rectangles' widths */
static void sum_wh(Rectangle *list, size_t length, long *width, long *height)
{
    size_t i = 0;
    *width = 0;
    *height = 0;
    for(i = 0; i < length; i++){
        *width += list[i].width;
        *height += list[i].height;
    }
    return;
}

/* Finds the max width of all the rectangles in list */
static void max_wh(Rectangle *list, size_t length, long *width, long *height)
{
    size_t i = 0;
    *width = 0;
    *height = 0;
    for(i = 0; i < length; i++){
        if(list[i].width >= *width){
            *width = list[i].width;
        }
        if(list[i].height >= *height){
            *height = list[i].height;
        }
    }
    return;
}

/* Compute the total area of all the rectangles in list */
static long total_area(Rectangle *list, size_t length)
{
    long area = 0;
    size_t i = 0;
    for(i = 0; i < length; i++){
        area += list[i].height*list[i].width;
    }
    return area;
}

static long placing_width(Rectangle *list, size_t length)
{
    size_t i = 0;
    long width = 0;
    for(i = 0; i < length; i++){
        if(list[i].x == -1){
            fprintf(stderr, "Error. Can't compute placing_width if not all rectangles have been placed.\n");
            return -1;
        }
        if(list[i].width + list[i].x >= width){
            width = list[i].width + list[i].x;
        }
    }
    return width;
}


long areapack_algorithm(Rectangle *list, size_t length, Enclosing *en)
{
    long max_width, max_height, sum_width, sum_height;
    long area = -1;
    long min_w = -1, min_h = -1;
    long status;
    enum theState {DO_PLACING, DEC_WIDTH, INC_HEIGHT, STOP} state;
    long tot_area = total_area(list, length);

    sum_wh(list, length, &sum_width, &sum_height);
    max_wh(list, length, &max_width, &max_height);
    /* Set initial enc. height to max height */
    en->height = max_height;
    en->width = sum_width;

    area = en->height*en->width;
    state = DO_PLACING;

    /* Find start enclosing w = sum, h = max
     * do placing
     * - if success save area
     * - if fail try a new enclosing
     *
     * decrease width, else increase height until sucess
     *
     * if en width = max: stop
     *
     *   */

    long loop = 1;
    while(loop){
        switch(state){
            case DO_PLACING:
                /* Try to place the rectangles in enclosing rectangle.
                 * If success, save the area and try again with enc. width dec.
                 * If fail, increase height and try again. */
                status = do_placing(list, length, en->width, en->height);
                if(status == 1){
                    en->width = placing_width(list, length);

                    area = en->height*en->width;
                    min_w = en->width;
                    min_h = en->height;

                    state = DEC_WIDTH;
                }
                else{
                    state = INC_HEIGHT;
                }
                break;
            case DEC_WIDTH:
                /* Decrease enclosing width and try do placing again. But if the
                 * new width is smaller than the rectangles' maximum width
                 * - stop the algorithm and present the best solution */

                en->width--;
                if(en->width < max_width){
                    state = STOP;
                }
                else{
                    state = DO_PLACING;
                }
                break;
            case INC_HEIGHT:
                /* Increase enclosing height and try do placing again. But if the
                 * new height makes the enclosing area smaller than the total
                 * area of all the rectangles - increase enclosing height and
                 * start over. If enclsing area is grather than the best enclosing
                 * area so-far - decrease the enclosing width and start over. */
                en->height++;
                if(en->height*en->width < tot_area){
                    state = INC_HEIGHT;
                }
                else if(en->height*en->width >= area){
                    state = DEC_WIDTH;
                }
                else{
                    state = DO_PLACING;
                }
                break;
            case STOP:
                /* Algorithm stops. */
                loop = 0;
                break;
        }
    }
    if(min_w == -1 || min_h == -1){
        return FAIL;
    }
    /* Do a final placing with the opimal found widht and height
      (To erase dirty x,y values on rectangles) */
    status = do_placing(list, length, min_w, min_h);

    return SUCCESS;
}
