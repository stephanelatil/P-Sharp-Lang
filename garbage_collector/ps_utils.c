#include <stdio.h>
#include <inttypes.h>
#include <stdint.h>
#include "gc.h"
#include "ps_utils.h"

void *__PS_DefaultToString(void* object)
{
    __PS_ObjectHeader* header = (__PS_ObjectHeader*) (object - sizeof(__PS_ObjectHeader));
    const char* name = header->type->type_name;
    // Get the length of the type name
    int64_t string_length = (int64_t) strlen(name) + strlen("<Class >") + 1; //add 1 for the null terminator

    //allocate memory to store the string
    void* string_obj = __PS_AllocateValueArray(sizeof(char), string_length + sizeof(int64_t));
    
    // store its length
    ((int64_t*)string_obj)[0] = string_length;

    //get the start of the actual c_string
    char* string_start = ((char*)string_obj) + sizeof(int64_t);

    // Write the Class name to memory
    snprintf(string_start, string_length, "<Class %s>", name);

    return string_obj;
}

void* __PS_GetPtrToArrayElement(void* array, int8_t element_size_in_bytes, int64_t index, char* filename, int32_t position_line, int32_t position_column){
    __PS_NullCheckObject(array, filename, position_line, position_column);
    int64_t array_size = ((int64_t*)array)[0];
    if (index < 0)
        // implement negative indexing to access array from the end
        index = ((int64_t)array_size)-index;
    // here index is positive because if it was negative it is now (positive_value + (-index))
    if (index >= array_size)
    {
        //print error message if out of bounds
        fprintf(stderr,
                "Cannot access outside of the bounds of the array in file %s at line %" PRId32 ":%" PRId32 "\n",
                filename, position_line, position_column);
        //exit with crash
        exit(1);
        //TODO later this should raise an exception of some kind
    }
    // go to start of continuous array memory
    array = array + sizeof(int64_t);
    return array + element_size_in_bytes * index;
}

void __PS_NullCheckObject(void* object, char* filename, int32_t position_line, int32_t position_column)
{
    if (object == NULL)
    {
        //print error message if trying to access deref null
        fprintf(stderr,
            "Null Reference in file %s at line %" PRId32 ":%" PRId32 "\n",
            filename, position_line, position_column);
        //exit with crash
        exit(1);
        //TODO later this should raise an exception of some kind
    }
}

int32_t print(char* string)
{
    int64_t string_length = ((int64_t*)string)[0];
    char* cstring = string+sizeof(int64_t);
    cstring[string_length] = (char)0;
    return (int32_t) puts(cstring);
}