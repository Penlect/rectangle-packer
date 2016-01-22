#include <stdio.h>

#include "../rectangle_packer.h"
#include "placing/placing.h"
#include "../visualisation/visualisation.h"

#include "algorithm.h"

/* Finds the sum of all the rectangles' widths */
static void sum_w(Rectangle *list, int length, int *width)
{
    int i;
    *width = 0;
    for(i = 0; i < length; i++){
        *width += list[i].width;
    }
    return;
}

/* Finds the max with of all the rectangles in list */
static void max_w(Rectangle *list, int length, int *width)
{
    int i;
    *width = 0;
    for(i = 0; i < length; i++){
        if(list[i].width >= *width){
            *width = list[i].width;
        }
    }
    return;
}

/* Compute the total area of all the rectangles in list */
static int total_area(Rectangle *list, int length)
{
    int area = 0;
    int i;
    for(i = 0; i < length; i++){
        area += list[i].height*list[i].width;
    }
    return area;
}

/*
static void result(Rectangle *list, int length)
{
    int i;
    for(i = 0; i < length; i++){
        printf("%d,%d,%d,%d\n", list[i].width, list[i].height, list[i].x, list[i].y);
    }
    return;
}
*/

int algorithm(Rectangle *list, int length, Enclosing *en)
{
    int max_width;
    int area;
    int status;
    enum theState {DO_PLACING, DEC_WIDTH, INC_HEIGHT, STOP} state;
    int tot_area = total_area(list, length);

    sum_w(list, length, &en->width); 
    max_w(list, length, &max_width);
    en->height = list[0].height;
    area = en->height*en->width;
    state = DO_PLACING;

    int loop = 1;
    int a, b;
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
    while(loop){
        switch(state){
            case DO_PLACING:
                /* Try to place the rectangles in enclosing rectangle.
                 * If success, save the area and try again with enc. width dec.
                 * If fail, increase height and try again. */
                status = do_placing(list, length, en->width, en->height);
                if(status == 1){
                    a = en->width;
                    b = en->height;
                    area = en->height*en->width;
                    printf("area = %d\n", area);
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
                /* Decrease enclosing height and try do placing again. But if the
                 * new height makes the total area greather than the total
                 * area of all the rectangles - decrease enclosing width and
                 * start over */
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
                /* Algorithm stops. Present best solution. */
                printf("Klart\n");
                do_placing(list, length, a, b);
                plot(list, length, a, b);
                loop = 0;
                break;
        }
    }
    return SUCCESS;
}
