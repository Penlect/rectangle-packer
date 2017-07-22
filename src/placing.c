#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "placing.h"
#include "rectangle_packer.h"

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

static Placing *alloc_placing(int enclosing_width, int enclosing_height)
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

static int try_fit_height_in_col(Col *col, int height, Cell_range *cell_r)
{
	/* Loop over the cells in the column to find a consecutive sequence of cells
	which is not occupied that have a hight greater than 'height'. Result is set
	in cell_r */
    int i; // Loop index
    Cell *cell = NULL; // Will point to each cell as we loop over col
    int sum_height = 0;

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
static Cell *step_offset(Cell *base, int offset)
{
    int i;
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
static int find_region(Placing *placing, Rectangle *rectangle, Region *reg)
{
    Col *col;
    int i;
    /* Loop over every column */
    for(col = placing->cols, i = 0; col != NULL; col=col->next_col, i++){
        Col_range col_r;
        Cell_range cell_r;
        int sum_width = 0;
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

static int split(Placing *placing, Region *reg)
{
    Col *col = NULL;
    Cell *cell = NULL;
    int i;
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
static int update(Placing *placing, Rectangle *rectangle, Region *reg)
{
    Col *col;
    Cell *cell;
    int i;
    int k;
    int x = 0;
    int y = 0;
    int done = 0;
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

static int add_rec(Placing *p, Rectangle *r)
{
    int status;
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

int do_placing(Rectangle *list, int length, int enclosing_width, int enclosing_height)
{
    int i;

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
/*
static void print_placing(Placing *placing)
{
    Col *col = NULL;
    Cell *cell = NULL;
    int i, k;
    printf("-------- PLACEMENT --------\n");
    printf("---Enclosing height:%d\n", placing->enclosing_height);
    printf("---Enclosing width:%d\n", placing->enclosing_width);
    for(col = placing->cols, i = 0; col != NULL; col = col->next_col, i++){
        printf("C%3d, w%3d: ", i, col->width);
        for(cell = col->cell, k = 0; cell != NULL; cell = cell->next_cell, k++){
            if(cell->occupied){
                printf("%3dX%d, ", cell->height, cell->occupied);
            }
            else{
                printf("%3d__, ", cell->height);
            }
        }
        printf("\n");
    }
    printf("\n");
    return;
}

static void print_region(Region *reg)
{
    printf("-------- REGION --------\n");
    printf("Col start:%d\n", reg->col_r.start_index);
    printf("Col end:  %d\n", reg->col_r.end_index);
    printf("Col overshoot:%d\n", reg->col_r.overshoot);
    printf("Cell start:%d\n", reg->cell_r.start_index);
    printf("Cell end:  %d\n", reg->cell_r.end_index);
    printf("Cell overshoot:%d\n\n", reg->cell_r.overshoot);
    return;
}
*/

