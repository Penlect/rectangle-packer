#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "parse_rec/parse_rec.h"
#include "placing/placing.h"


void sum_hw(struct rec *list, int length, int *height, int *width)
{
    int i;
    *height = 0;
    *width = 0;
    for(i = 0; i < length; i++){
        *height += list[i].height;
        *width += list[i].width;
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

int main(int argc, char *argv[]){
    if(argc != 2){
        fprintf(stderr, "No input file found!\n");
    }
    FILE *fp;
    if( (fp = fopen(argv[1], "r")) == NULL ){
        fprintf(stderr, "Error. File could not be opened.\n");
        return 0;
    }

    struct rec *list;
    int length;
    int i;
    list = rec_list_alloc(fp, &length);
    printf("reclist_alloc length %d\n", length);
    int h;
    int w;
    sum_hw(list, length, &h, &w);
    printf("sum h: %d, sum w: %d\n", h, w);

    Placing *p;
    p = alloc_placing(h, w);

    for(i = 0; i < length; i++){
        printf("h = %d, w = %d\n", list[i].height, list[i].width);
        /* id == 0 => empty! */
        printf("Status:%d\n", add_rec(p, list[i], i + 1));
        print_placing(p);
    }
    i = 0;
    printf("h = %d, w = %d\n", list[i].height, list[i].width);
    /* id == 0 => empty! */
    printf("Status:%d\n", add_rec(p, list[i], 9));
    print_placing(p);

    free(list);
    fclose(fp);

    free_placing(p);

    return 0;
}
