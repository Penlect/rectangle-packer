#ifndef PARSE_REC_H
#define PARSE_REC_H

#include <stdio.h>

struct rec{
    int height;
    int width;
};

struct rec *rec_list_alloc(FILE *fp, int *nr_reces);

#endif
