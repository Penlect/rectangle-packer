#include <stdio.h>
#include <stdlib.h>

#include "parse_rec.h"

int main(int argc, char *argv[])
{
    struct rec *list;
    int length;
    int i;

    if(argc != 2){
        fprintf(stderr, "No input file found!\n");
        return 1;
    }
    FILE *fp;
    if( (fp = fopen(argv[1], "r")) == NULL ){
        fprintf(stderr, "Error. File could not be opened.\n");
        return 1;
    }
    list = rec_list_alloc(fp, &length);
    for(i = 0; i < length; i++){
        printf("Element %3d: h = %d, w = %d\n", i, list[i].height, list[i].width);
    }
    free(list);
    fclose(fp);
    return 0;
}
