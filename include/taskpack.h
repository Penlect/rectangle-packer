/* THIS FILE AND ITS CONTENT IS DEPRECATED. */
#ifndef TASKPACK_H
#define TASKPACK_H

#include <stdlib.h>

typedef struct dataunit {
    double duration;
    size_t group; /* Special value: (size_t)-1 <=> belongs to no group*/
    size_t id;
} Task;

/*
 * Function:  taskpack_algorithm
 * --------------------
 * Given a collection of tasks with known durations and given a set of
 * groups: Divide the tasks into the different groups in such a way,
 * that the total duration of a group is minimized.
 *
 *  tasks: An array of Task structs. A Task has a duration, assigned
 *         group and an id.
 *  nr_tasks: The number of tasks in `tasks` array.
 *  nr_groups: The number of groups available.
 *
 *  returns: Status. Error is indicated by -1.
 */
int taskpack_algorithm(Task* tasks, size_t nr_tasks, size_t nr_groups);

#endif