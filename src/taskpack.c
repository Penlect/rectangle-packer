/* THIS FILE AND ITS CONTENT IS DEPRECATED. */

#include <stdlib.h>
#include <stdio.h>
#include <math.h>
#include <assert.h>
#include "taskpack.h"


typedef struct stackstate {
    double *group_sums;
    size_t nr_groups;
    size_t max_group;
} StackState;


static StackState *malloc_stack(size_t nr_groups){
    size_t i = 0;
    double *group_sums;
    StackState *output;
    group_sums = (double *)malloc(sizeof(double)*nr_groups);
    if (group_sums == NULL){
        return NULL;
    }
    output = (StackState *)malloc(sizeof(StackState)*nr_groups);
    if (output == NULL){
        free(group_sums);
        return NULL;
    }
    for (i = 0; i < nr_groups; i++){
        group_sums[i] = 0;
    }
    output->group_sums = group_sums;
    output->nr_groups = nr_groups;
    output->max_group = 0;
    return output;
}


static void free_stack(StackState *stack){
    free(stack->group_sums);
    free(stack);
}


static size_t stack_min_group(StackState *stack){
    size_t i = 0, min_group = 0;
    double min_sum = -1;
    for (i = 0; i < stack->nr_groups; i++){
        if (stack->group_sums[i] < min_sum || min_sum == -1 ){
            min_sum = stack->group_sums[i];
            min_group = i;
        }
    }
    return min_group;
}


static size_t stack_max_group(StackState *stack){
    size_t i = 0, max_group = 0;
    double max_sum = 0;
    for (i = 0; i < stack->nr_groups; i++){
        if (stack->group_sums[i] > max_sum ){
            max_sum = stack->group_sums[i];
            max_group = i;
        }
    }
    return max_group;
}


static int stack_add(StackState *stack, Task *task, size_t group){
    assert(group < stack->nr_groups);
    task->group = group;
    stack->group_sums[group] += task->duration;
    if (stack->group_sums[group] > stack->group_sums[stack->max_group]){
        stack->max_group = group;
        return 1;
    }
    return 0;
}


static int stack_move(StackState *stack, Task *task, size_t group){
    assert(group < stack->nr_groups);
    if (group == task->group){
        return 0;
    }

    stack->group_sums[task->group] -= task->duration;
    task->group = group;
    stack->group_sums[task->group] += task->duration;
    stack->max_group = stack_max_group(stack);
    return 1;
}


static int stack_swap(StackState *stack, Task *task_a, Task *task_b){
    size_t tmp = 0;
    if (task_a->group == task_b->group){
        return 0;
    }
    stack->group_sums[task_a->group] += (task_b->duration - task_a->duration);
    stack->group_sums[task_b->group] += (task_a->duration - task_b->duration);

    tmp = task_a->group;
    task_a->group = task_b->group;
    task_b->group = tmp;
    //printf("%ld <-> %ld. %f <-> %f\n", task_a->group, task_b->group, task_a->duration, task_b->duration);

    stack->max_group = stack_max_group(stack);

    return 1;
}


static int move_from_max_to_min(StackState *stack, Task *tasks, size_t nr_tasks){
    size_t i;
    size_t min_group = stack_min_group(stack);
    double min_sum = stack->group_sums[min_group];
    double max_sum = stack->group_sums[stack->max_group];
    for (i = 0; i < nr_tasks; i++){
        if (tasks[i].group != stack->max_group){
            continue;
        }
        if (tasks[i].duration + min_sum < max_sum){
            stack_move(stack, &tasks[i], min_group);
            return 1;
        }
    }
    return 0;
}


static int swap_from_max(StackState *stack, Task *tasks, size_t nr_tasks){
    size_t i, j;
    double max_sum = stack->group_sums[stack->max_group];
    for (i = 0; i < nr_tasks; i++){
        /* Find rectangle in max stack */
        if (tasks[i].group == stack->max_group){
            for (j = i + 1; j < nr_tasks; j++){
                /* Find smaller rectangle in other stack */
                if (tasks[j].group != stack->max_group && tasks[i].duration != tasks[j].duration){
                    assert(tasks[j].duration <= tasks[i].duration);
                    if (tasks[i].duration - tasks[j].duration + stack->group_sums[tasks[j].group] < max_sum){
                        stack_swap(stack, &tasks[i], &tasks[j]);
                        return 1;
                    }
                }

            }
        }
    }
    return 0;
}


int cmpfunc(const void *a, const void *b){
    if ( ((Task*)a)->duration > ((Task*)b)->duration ){
        return -1;
    }
    else if ( ((Task*)a)->duration < ((Task*)b)->duration ){
        return 1;
    }
    else {
        return 0;
    }
}


int taskpack_algorithm(Task* tasks, size_t nr_tasks, size_t nr_groups){
/*
Note: the tasks must be sorted by duration before calling this function.
      The first element should be the task with longest duration.

Step 0
======
Sort rectangles in decreasing order.

Step 1
======
For each rectangle (in decreasing order) put it in the smallest group.

Step 2
======
For the highest stack, try to move some of its rectangles to any of the
other stacks without making the other stack even higher.

Do this repeatedly until not possible (end condition always exist?).

Step 3
======
For the highest stack, try to swap one of its rectangles with any rectangle
in the other stacks without making the other stack even higher.

---

Keep group sums in a data structure. Also keep track of min group and max
group index.


*/
    size_t i = 0;
    size_t tmp = 0;
    int result = 0;
    StackState *stack = NULL;

    /* init */
    stack = malloc_stack(nr_groups);
    if (stack == NULL){
        return -1;
    }

    /* Step 0 */
    qsort(tasks, nr_tasks, sizeof(Task), cmpfunc);
    /* Step 1 */
    for (i = 0; i < nr_tasks; i++){
        tmp = stack_min_group(stack);
        stack_add(stack, &tasks[i], tmp);
    }
    /* Step 2 */
    unsigned long move_count = 0;
    for(;;){
        if (! move_from_max_to_min(stack, tasks, nr_tasks)){
            break;
        }
        move_count++;
    }

    /* Step 3 */
    unsigned long swap_count = 0;
    for(i = 0; i < nr_tasks; i++){
        if (! swap_from_max(stack, tasks, nr_tasks)){
            break;
        }
        swap_count++;
    }
    free_stack(stack);
    return result;
}