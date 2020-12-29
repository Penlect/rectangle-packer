/* THIS FILE AND ITS CONTENT IS DEPRECATED. USE rpack._core.pyx INSTEAD.
 */

/*Since Python may define some pre-processor definitions which affect the standard headers on some systems, you must include Python.h before any standard headers are included.

"Python.h" includes a few standard header files: <stdio.h>, <string.h>, <errno.h>, and <stdlib.h>.
*/
#include <Python.h>
#include "areapack.h"
#include "taskpack.h"

static Rectangle*
rectangle_list_alloc(PyObject* tuples, size_t* length){
	/* Convert a tuple from Python to a list of Rectangles,
    don't forget to free the list when you are done with it. */
    Rectangle *rectangles = NULL;
    Rectangle *rectangles_temp = NULL;
    PyObject *iterator = NULL;
	PyObject *item = NULL;
    size_t size = 0;
    goto try;
try:
	
	/* Get iterator and create rectangle of each tuple */
	iterator = PyObject_GetIter(tuples);
	if (! iterator){
	    goto except;
	}
	while( (item = PyIter_Next(iterator)) ){
	    PyObject *x = NULL, *y = NULL;
		Rectangle r;
		long width, height;
        size++;
        /* Reallocate memory for new rectangle entry in list */
        rectangles_temp = realloc(rectangles, size*sizeof(*rectangles));
        if( ! rectangles_temp ){
            PyErr_SetString(PyExc_MemoryError, "Failed to reallocate memory for rectangle list.");
		    Py_DECREF(item);
            goto except;
        }
        else{
            rectangles = rectangles_temp;
        }
        /* Extract x and y from item */
		x = PySequence_GetItem(item, 0);
        if(! x){
		    Py_DECREF(item);
            goto except;
        }
		y = PySequence_GetItem(item, 1);
        if(! y){
		    Py_DECREF(x);
		    Py_DECREF(item);
            goto except;
        }
        /* The item is now not needed anymore */
		Py_DECREF(item);

		/* Check if integers */
		if (!PyLong_Check(x)) {
		    Py_DECREF(x);
		    Py_DECREF(y);
            PyErr_SetString(PyExc_TypeError, "Rectangle width must be an integer");
		    goto except;
		}
		if (!PyLong_Check(y)) {
		    Py_DECREF(x);
		    Py_DECREF(y);
            PyErr_SetString(PyExc_TypeError, "Rectangle height must be an integer");
		    goto except;
		}

		/* Convert x and y to width and height */
		width = PyLong_AsLong(x);
        if ((width == -1) && PyErr_Occurred()){
		    Py_DECREF(x);
		    Py_DECREF(y);
            goto except;
        }
		height = PyLong_AsLong(y);
        if ((height == -1) && PyErr_Occurred()){
		    Py_DECREF(x);
		    Py_DECREF(y);
		    /*if (PyErr_ExceptionMatches(PyExc_OverflowError)){
                PyErr_Clear();
                PyErr_SetString(PyExc_ValueError, "Rectangle height must be positive");
		    }*/
            goto except;
        }
		Py_DECREF(x);
		Py_DECREF(y);

		if (width <= 0){
		    PyErr_SetString(PyExc_ValueError, "Rectangle width must be positive integer");
		    goto except;
		}
		if (height <= 0){
		    PyErr_SetString(PyExc_ValueError, "Rectangle height must be positive integer");
		    goto except;
		}
		
		/* Set rectangle size. Todo: why not unsigned long?
		   Check if long fits in int.
		*/
		if (width >= INT_MAX ){
		    PyErr_SetString(PyExc_OverflowError, "Rectangle width exceeds INT_MAX");
		    goto except;
		}
		if (height >= INT_MAX ){
		    PyErr_SetString(PyExc_OverflowError, "Rectangle height exceeds INT_MAX");
		    goto except;
		}
        r.width = width;
        r.height = height;
        /* -1 to indicate that the rectangle don't have a position */
        r.x = -1; 
        r.y = -1;
        /* Each rectangle has an id that must be non-zero */
        r.id = size;
        rectangles[size - 1] = r;
	}
    if (PyErr_Occurred()){
        /* If an error occurs while retrieving the item (PyIter_Next) */
        goto except;
    }
	*length = size;

    assert(! PyErr_Occurred());
    if (*length > 0){
        assert( rectangles );
    }
    goto finally;
except:
	free(rectangles);
    rectangles = NULL;
finally:
    Py_XDECREF(iterator);
    return rectangles;
}

PyDoc_STRVAR(pack__doc__,
"Pack rectangles to minimum enclosing area\n\n"
"Takes a sequence of tuples (w, h) as input where w is the width\n"
"of the rectangle, and h the height (must be positive integers).\n"
"Returns a sequence of positions (x, y) of the corresponding\n"
"rectangles (upper left corner of rectangles). The rectangles\n"
"will be positioned to minimize the enclosing area.\n"
);

static PyObject*
pack(PyObject* self, PyObject* args)
{
    size_t nr_rectangles = 0; // Nr of rectangles in input
    Rectangle* r_list = NULL; // List of Rectangles
    Enclosing en = {0, 0}; // Enclosing area
    PyObject* position = NULL; // Tuple (x, y) position of rectangle
    PyObject* positions = NULL; // The result that will be returned
    long result = -1;
    Py_ssize_t index = 0;
    goto try;
try:
    assert(! PyErr_Occurred());
    assert(args);

    /* args should be an iterable of tuples */
	r_list = rectangle_list_alloc(args, &nr_rectangles);
    if(r_list == NULL && PyErr_Occurred()){
        goto except;
    }
    if( nr_rectangles == 0){
        /* This should happen when args was empty sequence,
        - return empty list. */
        positions = Py_BuildValue("[]");
        if (! positions){
            goto except;
        }
        else {
            goto finally;
        }
    }
    
    /* Run the algorithm with the provided rectangles, and
    raise an exception if it for some strange reason would fail */
    Py_BEGIN_ALLOW_THREADS
    result = areapack_algorithm(r_list, nr_rectangles, &en);
    Py_END_ALLOW_THREADS

    if(result == FAIL){
        PyErr_SetString(PyExc_RuntimeError, "Unexpected error in algorithm implementation");
        goto except;
    }
	
    /* Create empty positions' list */
	positions = PyList_New((Py_ssize_t) nr_rectangles);
    if(positions == NULL){
        goto except;
    }
	for(index=0; index < (Py_ssize_t)nr_rectangles; index++){
        /* Build tuple of x, y position of rectangle*/
		position = Py_BuildValue("(ii)", r_list[index].x, r_list[index].y);
        if(position == NULL){
            goto except;
        }
        /* Insert position tuple in the list */
        PyList_SET_ITEM(positions, index, position);
	}
    assert(! PyErr_Occurred());
    assert(positions);
    goto finally;
except:
    Py_XDECREF(positions);
    positions = NULL;
finally:
	free(r_list);
    return positions;
}

static Task*
_prepare_input(PyObject* list, Py_ssize_t nr_tasks){
    PyObject *item = NULL;
    Py_ssize_t i = 0;
    Task *tasks = NULL;
    double duration = 0;
    goto try;
try:
    assert(! PyErr_Occurred());
    assert(list);

    /* Allocate memory for the array of tasks */
    tasks = (Task *) malloc(sizeof(Task) * nr_tasks);
    if (! tasks){
        PyErr_NoMemory();
        goto except;
    }

    for(i = 0; i < nr_tasks; i++){
        /* Get item from list */
        item = PySequence_GetItem(list, i);
        if (! item){
            goto except;
        }
        /* convert item to C double */
        duration = PyFloat_AsDouble(item);
        if ((duration == -1) && PyErr_Occurred()){
            goto except;
        }
        /* Save the double as task duration and index as the task id */
        tasks[i] = (Task){.duration = duration, .group = (size_t)-1, .id = (size_t)i};
    }

    assert(! PyErr_Occurred());
    assert(tasks);
    goto finally;
except:
    free(tasks);
    tasks = NULL;
finally:
    return tasks;
}

static PyObject*
_prepare_output(PyObject* list, Task* tasks, Py_ssize_t nr_tasks, Py_ssize_t nr_groups){
    PyObject *output = NULL, *obj = NULL;
    PyObject *tmp_list = NULL;
    Py_ssize_t i = 0, j = 0;
    Py_ssize_t g = 0;
    Py_ssize_t group_size = 0;
    goto try;
try:
    assert(! PyErr_Occurred());
    assert(tasks);

    Py_INCREF(list);

    /* Create the output list which will contain lists: one for each list */
    output = PyList_New(nr_groups);
    if (! output){
        goto except;
    }

    /* Create a list for each group and add to "output" */
    for(g = 0; g < nr_groups; g++){

        /* Count the number of tasks assigned to this group.
         * This is needed so we know which size the list should have. */
        group_size = 0;
        for (i = 0; i < nr_tasks; i++){
            if ((Py_ssize_t)tasks[i].group == g){
                group_size++;
            }
        }
        /* Create group list */
        tmp_list = PyList_New(group_size);
        if (! tmp_list){
            goto except;
        }
        j = 0;
        /* Populate group list */
        for(i = 0; i < nr_tasks; i++){
            if ((Py_ssize_t)tasks[i].group == g){
                /* Get the original object based on index */
                obj = PyList_GetItem(list, (Py_ssize_t)tasks[i].id);
                if (! obj){
                    goto except;
                }
                Py_INCREF(obj);
                PyList_SET_ITEM(tmp_list, j, obj);
                j++;
            }
        }
        PyList_SET_ITEM(output, g, tmp_list);
    }

    assert(! PyErr_Occurred());
    assert(output);
    goto finally;
except:
    Py_XDECREF(output);
    Py_XDECREF(list);
    output = NULL;
finally:
    Py_DECREF(list);
    return output;
}

PyDoc_STRVAR(group__doc__,
"Tools for packing floats into groups.\n"
"\n"
"group(iterable, nr_groups) -> list of groups\n"
);
static PyObject *
_group_list(PyObject *module, PyObject *args) {
    PyObject *output = NULL;
    PyObject *list = NULL;
    Py_ssize_t nr_groups = 0, nr_tasks = 0;
    Task* tasks = NULL;
    int result = -1;
    goto try;
try:
    assert(! PyErr_Occurred());

    if (! PyArg_ParseTuple(args, "On", &list, &nr_groups)) {
        goto except;
    }

    if (nr_groups < 1){
        PyErr_SetString(PyExc_ValueError, "Number of groups must be positive.");
        goto except;
    }

    list = PySequence_List(list);
    if (! list){
        goto except;
    }

    nr_tasks = PyList_Size(list);
    if (nr_tasks == -1){
        goto except;
    }

    tasks = _prepare_input(list, nr_tasks);
    if (! tasks){
        goto except;
    }

    Py_BEGIN_ALLOW_THREADS
    result = taskpack_algorithm(tasks, (size_t)nr_tasks, (size_t)nr_groups);
    Py_END_ALLOW_THREADS

    if (result == -1){
        PyErr_SetString(PyExc_Exception, "Ooops. error in main algorithm");
        goto except;
    }

    output = _prepare_output(list, tasks, nr_tasks, nr_groups);
    if (! output){
        goto except;
    }

    Py_DECREF(list);

    assert(! PyErr_Occurred());
    assert(output);
    goto finally;
except:
    Py_XDECREF(output);
    output = NULL;
finally:
    free(tasks);
    return output;
}

/* module level code ********************************************************/

PyDoc_STRVAR(module_doc,
"C extension implementing rectangle packing utility functions.\n"
);

static PyMethodDef _rpack_functions[] = {
    {"pack", (PyCFunction)pack, METH_O, pack__doc__},
    {"group", (PyCFunction)_group_list, METH_VARARGS, group__doc__},
    {NULL, NULL, 0, NULL}
};

static struct PyModuleDef _rpack_module = {
	PyModuleDef_HEAD_INIT,
	"_rpack",
	module_doc,
	-1,
	_rpack_functions
};

PyMODINIT_FUNC
PyInit__rpack(void){
    if (PyErr_WarnEx(PyExc_DeprecationWarning,
		     "rpack._rpack is deprecated; "
		     "use rpack._core instead.", 1) < 0) {
	return NULL;
    }
    PyObject* m = PyModule_Create(&_rpack_module);
    return m;
}
