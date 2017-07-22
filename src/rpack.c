
/*Since Python may define some pre-processor definitions which affect the standard headers on some systems, you must include Python.h before any standard headers are included.

"Python.h" includes a few standard header files: <stdio.h>, <string.h>, <errno.h>, and <stdlib.h>.
*/
#include <Python.h>
#include "rectangle_packer.h"
#include "algorithm.h"

static void result(Rectangle *list, int length)
{
    int i;
    for(i = 0; i < length; i++){
        printf("%d,%d,%d,%d\n", list[i].width, list[i].height, list[i].x, list[i].y);
    }
    return;
}

static Rectangle*
rectangle_list_alloc(PyObject* tuples){
	/* recpt will be the list of rectangles */
    Rectangle *recpt = NULL;
    Rectangle *recpt_temp = NULL;
    size_t size = 0;
	int id = 0;
	
	/* Get iterator and create rectangle of each tuple */
	PyObject *iterator = PyObject_GetIter(tuples);
	PyObject *item;
	if(iterator == NULL){
		return NULL;
	}
	while(item = PyIter_Next(iterator)){
		Rectangle r;
		unsigned long width, height;
        size++;
		id++;
        /* Reallocate memory for new rec entry in list */
        if( (recpt_temp = realloc(recpt, size*sizeof(*recpt))) == NULL ){
            fprintf(stderr, "Error. Could not reallocate memory for rec list.\n");
            /* Free all pointers if fail */
            free(recpt);
            free(item);
            return NULL;
        }
        else{
            recpt = recpt_temp;
        }
		PyObject* repr = PyObject_Repr(item);
		char* str = PyUnicode_AsUTF8(repr);
		printf("Item %d: %s\n", id, str);
		Py_DECREF(repr);
		PyObject* x = PySequence_GetItem(item, 0);
		PyObject* y = PySequence_GetItem(item, 1);
		width = PyLong_AsUnsignedLong(x);
		height = PyLong_AsUnsignedLong(y);
		Py_DECREF(x);
		Py_DECREF(y);
		Py_DECREF(item);
		
		printf("width: %d, height: %d\n", width, height);
		
        r.width = width;
        r.height = height;
        /* -1 to indicate that the rectangle don't have a position */
        r.x = -1; 
        r.y = -1;
        r.id = id;
        recpt[size - 1] = r;
	}
	Py_DECREF(iterator);
	
	return recpt;
}

static PyObject*
pack(PyObject* self, PyObject* arg)
{
	int n = PyObject_Length(arg);
	printf("Len = %d\n", n);
	Rectangle* r_list = rectangle_list_alloc(arg);
	
	result(r_list, n);
	
    Enclosing en;
    algorithm(r_list, n, &en);
	
	result(r_list, n);
	
	PyObject* output_list = PyList_New((Py_ssize_t) n);
	Rectangle r;
	for(Py_ssize_t i=0; i<n; i++){
		r = r_list[i];
		PyObject* rec = Py_BuildValue("i(ii)(ii)", r.id, r.width, r.height, r.x, r.y);
		PyList_SetItem(output_list, i, rec);
	}
	free(r_list);
	return output_list;
}

static char text[] = "Example text!";

static PyObject*
helloworld(PyObject* self)
{
    return Py_BuildValue("s", "Hello, World!");
}

/* The Module’s Method Table */
static PyMethodDef rpack_funcs[] = {
    {"helloworld", (PyCFunction)helloworld, METH_NOARGS, "return string 'Hello, World!'"},
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
