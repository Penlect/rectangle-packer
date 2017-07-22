
/*Since Python may define some pre-processor definitions which affect the standard headers on some systems, you must include Python.h before any standard headers are included.

"Python.h" includes a few standard header files: <stdio.h>, <string.h>, <errno.h>, and <stdlib.h>.
*/
#include <Python.h>
#include "rectangle_packer.h"
#include "algorithm.h"

static Rectangle*
rectangle_list_alloc(PyObject* tuples, int* length){
	/* Convert a tuple from Python to a list of Rectangles,
    don't forget to free the list when you are done with it. */
    Rectangle *rectangles = NULL;
    Rectangle *rectangles_temp = NULL;
    size_t size = 0;
	int id = 0;
	
	/* Get iterator and create rectangle of each tuple */
	PyObject *iterator = PyObject_GetIter(tuples);
	PyObject *item;
	if(iterator == NULL){
		return NULL;
	}
	while( (item = PyIter_Next(iterator)) ){
		Rectangle r;
		unsigned long width, height;
        size++;
		id++;
        /* Reallocate memory for new rectangle entry in list */
        if( (rectangles_temp = realloc(rectangles, size*sizeof(*rectangles))) == NULL ){
            fprintf(stderr, "Error. Could not reallocate memory for rectangle list.\n");
            /* Free all pointers if fail */
            free(rectangles);
            Py_DECREF(item);
            Py_DECREF(iterator);
            return NULL;
        }
        else{
            rectangles = rectangles_temp;
        }
		PyObject* x = PySequence_GetItem(item, 0);
        if(x == NULL){
            return NULL;
        }
		PyObject* y = PySequence_GetItem(item, 1);
        if(y == NULL){
            return NULL;
        }
		width = PyLong_AsUnsignedLong(x);
		height = PyLong_AsUnsignedLong(y);
		Py_DECREF(x);
		Py_DECREF(y);
		Py_DECREF(item);
		
		/* Set rectangle size */
        r.width = (int) width;
        r.height = (int) height;
        /* -1 to indicate that the rectangle don't have a position */
        r.x = -1; 
        r.y = -1;
        /* Each rectangle has an id that must be non-zero */
        r.id = id;
        rectangles[size - 1] = r;
	}
	Py_DECREF(iterator);
	*length = id;
	return rectangles;
}

static PyObject*
pack(PyObject* self, PyObject* args)
{
    int length; // Nr of rectangles in input
    Rectangle* r_list; // List of Rectangles
    Enclosing en; // Enclosing area
    PyObject* position; // Tuple (x, y) position of rectangle
    PyObject* positions; // The result that will be returned
    
    /* args should be an iterable of tuples */
    
	r_list = rectangle_list_alloc(args, &length);
    if(r_list == NULL){
        return NULL;
    }
    
    /* Run the algorithm with the provided rectangles, and
    raise an exception if it for some strange reason would fail */
    if(algorithm(r_list, length, &en) == FAIL){
        free(r_list);
        PyErr_SetString(PyExc_RuntimeError, "Unexpected error in algorithm implementation");
        return NULL;
    }
	
    /* Create empty positions' list */
	positions = PyList_New((Py_ssize_t) length);
    if(positions == NULL){
        free(r_list);
        return NULL;
    }
	for(Py_ssize_t index=0; index<length; index++){
        /* Build tuple of x, y position of rectangle*/
		position = Py_BuildValue("(ii)", r_list[index].x, r_list[index].y);
        if(position == NULL){
            free(r_list);
            return NULL;
        }
        /* Insert position tuple in the list */
		if(PyList_SetItem(positions, index, position) == -1){
            free(r_list);
            return NULL;
        }
	}
	free(r_list);
	return positions;
}

/* The Module’s Method Table */
static PyMethodDef rpack_funcs[] = {
    {"pack", (PyCFunction)pack, METH_O, "Pack rectangles"},
    {NULL}
};

static char rpack_module_docs[] = "Module used to pack rectangles";

static struct PyModuleDef rpack_module = {
	PyModuleDef_HEAD_INIT,
	"rpack",
	rpack_module_docs,
	-1,
	rpack_funcs
};

PyMODINIT_FUNC
PyInit_rpack(void){
    PyObject* m = PyModule_Create(&rpack_module);
    return m;
}
