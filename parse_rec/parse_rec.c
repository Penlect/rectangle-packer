
#include <stdio.h>
#include <stdlib.h>
#include <string.h>

#include "parse_rec.h"

/* Return allocated pointer to each line in file,
 * returns NULL pointer after EOF */
static char *line_alloc(FILE *fp)
{
    char *line = NULL;
    char *line_temp = NULL;
    size_t size = 0;
    int c = 0;

    /* Check that we didn't get a NULL file pointer */
    if( fp == NULL ){
        fprintf(stderr, "Error. File pointer is NULL.\n");
        return NULL;
    }
    while(1){
        /* Read a char.
         * Return NULL if file is already EOF.
         * Try to realloc line
         * Return if character is newline or EOF
         * Add the character to line. */
        c = fgetc(fp);
        if(c == EOF && size == 0){
            return NULL;
        }
        size++;
        if( (line_temp = realloc(line, size*sizeof(*line))) == NULL ){
            fprintf(stderr, "Error. Could not reallocate memory for line.\n");
            free(line);
            return NULL;
        }
        else{
            line = line_temp;
        }
        if(c == '\n' || c == EOF){
            line[size - 1] = '\0';
            return line;
        }
        else{
            line[size - 1] = c;
        }
    }
    return NULL;
}

/* Return allocated list of integers parsed from csv string */
static int *csvint_alloc(char *line, int *elements)
{
    int *csvint_alloc = NULL;
    char *tok = NULL;
    int i;

    /* Count elements = nr commas + 1 */
    *elements = 1;
    for(i = 0; line[i] != '\0'; i++){
        if(line[i] == ','){
            (*elements)++;
        }
    }
    /* Try to allocate *elements of int */
    if( (csvint_alloc = calloc((size_t)*elements, sizeof(int))) == NULL ){
        fprintf(stderr, "Error. Could not allocate memory for int list.\n");
        return NULL;
    }

    /* Use atoi to convert every string between commas to integers */
    tok = strtok(line, ",");
    for(i = 0; tok != NULL; i++){
        csvint_alloc[i] = atoi(tok);
        tok = strtok(NULL, ",");
    }

    return csvint_alloc;
}

/*Function used to sort rectangles by height, highest first */
int compare_rec_height(const void *p, const void *q)
{
    struct rec x = *(const struct rec *)p;
    struct rec y = *(const struct rec *)q;

    if(x.height == y.height){
        return 0;
    }
    else if(x.height > y.height){
        return -1;
    }
    else{
        return 1;
    }
}

/* Parse file for rectangles and return allocated list of rectangles
 * in sorted order. Format for input file needs to be: "height,width\n"
 * for each row in. */
struct rec *rec_list_alloc(FILE *fp, int *nr_reces)
{
    struct rec *recpt = NULL;
    struct rec *recpt_temp = NULL;
    size_t size = 0;
    char *line = NULL;
    int id = 0;

    /* Check that we didn't get a NULL file pointer */
    if(fp == NULL){
        fprintf(stderr, "Error. File pointer is null.\n");
        return NULL;
    }

    /* Loop over each line in inputfile */
    while( (line = line_alloc(fp)) != NULL ){
        int *csv_integers;
        struct rec temp;
        int elements;

        size++;
        /* Reallocate memory for new rec entry in list */
        if( (recpt_temp = realloc(recpt, size*sizeof(*recpt))) == NULL ){
            fprintf(stderr, "Error. Could not reallocate memory for rec list.\n");
            /* Free all pointers if fail */
            free(recpt);
            free(line);
            return NULL;
        }
        else{
            recpt = recpt_temp;
        }
        csv_integers = csvint_alloc(line, &elements);
        /* We need at least two integers: height and width */
        if(elements < 2){
            fprintf(stderr, "Error. There exists a row with less than two values.\n");
            /* Free all pointers if fail */
            free(csv_integers);
            free(recpt);
            free(line);
        }
        temp.height = csv_integers[0];
        temp.width = csv_integers[1];
        /* -1 to indicate that the rectangle don't have a position */
        temp.x = -1; 
        temp.y = -1;
        temp.id = ++id;
        recpt[size - 1] = temp;
        free(csv_integers);
        free(line);
    }
    *nr_reces = (int) size;
    qsort((void *)recpt, size, sizeof(*recpt), compare_rec_height);
    return recpt;
}
