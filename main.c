#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "parse_rec/parse_rec.h"
#include "placing/placing.h"
#include "visualisation/visualisation.h"


void sum_w(struct rec *list, int length, int *width)
{
    int i;
    *width = 0;
    for(i = 0; i < length; i++){
        *width += list[i].width;
    }
    return;
}

void max_w(struct rec *list, int length, int *width)
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

int total_area(struct rec *list, int length)
{
    int area = 0;
    int i;
    for(i = 0; i < length; i++){
        area += list[i].height*list[i].width;
    }
    return area;
}

void result(struct rec *list, int length)
{
    int i;
    for(i = 0; i < length; i++){
        printf("%d,%d,%d,%d\n", list[i].width, list[i].height, list[i].x, list[i].y);
    }
    return;
}

int algorithm(struct rec *list, int length)
{
    int enclosing_width, enclosing_height;
    int max_width;
    int area;
    int status;
    enum theState {DO_PLACING, DEC_WIDTH, INC_HEIGHT, STOP} state;

    sum_w(list, length, &enclosing_width); 
    max_w(list, length, &max_width);
    enclosing_height = list[0].height;
    area = enclosing_height*enclosing_width;
    state = DO_PLACING;

    printf("en_w = %d, en_h = %d\n", enclosing_width, enclosing_height);

    int loop = 1;
    int a, b;
    while(loop){
        switch(state){
            case DO_PLACING:
                status = do_placing(list, length, enclosing_width, enclosing_height);
                if(status == 1){
                    a = enclosing_width;
                    b = enclosing_height;
                    area = enclosing_height*enclosing_width;
                    printf("area = %d\n", area);
                    state = DEC_WIDTH;
                }
                else{
                    state = INC_HEIGHT;
                }
                break;
            case DEC_WIDTH:
                enclosing_width--;
                if(enclosing_width < max_width){
                    state = STOP;
                }
                else{
                    state = DO_PLACING;
                }
                break;
            case INC_HEIGHT:
                enclosing_height++;
                if(enclosing_height*enclosing_width >= area){
                    state = DEC_WIDTH;
                }
                else{ 
                    state = DO_PLACING;
                }
                break;
            case STOP:
                printf("Klart\n");
                do_placing(list, length, a, b);
                plot(list, length, a, b);
                loop = 0;
                break;
        }
    }
    return 0;
}


int main(int argc, char *argv[]){
    if(argc != 2){
        fprintf(stderr, "No input file found!\n");
    }
    FILE *fp;
    if( (fp = fopen(argv[1], "r")) == NULL ){
        fprintf(stderr, "Error. File could not be opened.\n");
        return 0;
    }

    int length;
    struct rec *list = rec_list_alloc(fp, &length);

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
    algorithm(list, length);

    free(list);
    fclose(fp);

    return 0;
}
