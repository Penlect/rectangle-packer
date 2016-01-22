#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "rectangle_packer.h"
#include "parse_rec/parse_rec.h"
#include "algorithm/algorithm.h"

int main(int argc, char *argv[])
{
    if(argc != 2){
        fprintf(stderr, "No input file found!\n");
    }
    FILE *fp;
    if( (fp = fopen(argv[1], "r")) == NULL ){
        fprintf(stderr, "Error. File could not be opened.\n");
        return 0;
    }

    int length;
    Rectangle *list = rec_list_alloc(fp, &length);

    Enclosing en;
    algorithm(list, length, &en);

    free(list);
    fclose(fp);

    return 0;
}
