#include <stdio.h>
#include <inttypes.h>
#include <stdint.h>
#include <string.h>
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

void* __PS_cstr_to_string(char* cstr){
    size_t string_len = strlen(cstr);
    // create object from string
    void* obj = __PS_AllocateValueArray(sizeof(char), string_len);
    // copy string value into object
    memcpy(obj+sizeof(ARRAY_LEN_TYPE), cstr, string_len);
    //return the string object
    return obj;
}

void* __PS_BoolToString(bool b){
    return __PS_cstr_to_string(b ? "true" : "false");
}

void* __PS_CharToString(uint8_t c){
    char cstr[2] = {c, 0};
    return __PS_cstr_to_string(cstr);
}

void* __PS_I8ToString(int8_t number){
    int max_size = 5;
    char cstr[max_size]; //biggest possible is "-100" 4 chars + null byte
    snprintf(cstr, max_size, "%" PRId8, number);
    return __PS_cstr_to_string(cstr);
}

void* __PS_U8ToString(uint8_t number){
    int max_size = 4;
    char cstr[max_size]; //biggest possible is "100" 3 chars + null byte
    snprintf(cstr, max_size, "%" PRIu8, number);
    return __PS_cstr_to_string(cstr);
}

void* __PS_I16oString(int16_t number){
    int max_size = 7;
    char cstr[max_size]; //biggest possible is "-10000" 6 chars + null byte
    snprintf(cstr, max_size, "%" PRId16, number);
    return __PS_cstr_to_string(cstr);
}

void* __PS_U16ToString(uint16_t number){
    int max_size = 6;
    char cstr[max_size]; //biggest possible is "10000" 5 chars + null byte
    snprintf(cstr, max_size, "%" PRIu16, number);
    return __PS_cstr_to_string(cstr);
}

void* __PS_I32oString(int32_t number){
    int max_size = 12;
    char cstr[max_size]; //biggest possible is "-1000000000" 11 chars + null byte
    snprintf(cstr, max_size, "%" PRId32, number);
    return __PS_cstr_to_string(cstr);
}

void* __PS_U32ToString(uint32_t number){
    int max_size = 11;
    char cstr[max_size]; //biggest possible is "1000000000" 10 chars + null byte
    snprintf(cstr, max_size, "%" PRIu32, number);
    return __PS_cstr_to_string(cstr);
}

void* __PS_I64oString(int64_t number){
    int max_size = 22;
    char cstr[max_size]; //biggest possible is "-10000000000000000000" 21 chars + null byte
    snprintf(cstr, max_size, "%" PRId64, number);
    return __PS_cstr_to_string(cstr);
}

void* __PS_U64ToString(uint64_t number){
    int max_size = 21;
    char cstr[max_size]; //biggest possible is "10000000000000000000" 20 chars + null byte
    snprintf(cstr, max_size, "%" PRIu64, number);
    return __PS_cstr_to_string(cstr);
}

void* __PS_F16ToString(_Float16 number){
    int max_size = 12;
    char cstr[max_size]; //biggest possible is "3.14159e+10" 11 chars + null byte
    snprintf(cstr, max_size, "%f", number);
    return __PS_cstr_to_string(cstr);
}

void* __PS_F32oString(_Float32 number){
    int max_size = 13;
    char cstr[max_size]; //biggest possible is "3.14159e+100" 12 chars + null byte
    snprintf(cstr, max_size, "%g", number);
    return __PS_cstr_to_string(cstr);
}

void* __PS_F64ToString(_Float64 number){
    int max_size = 14;
    char cstr[max_size]; //biggest possible is "3.14159e+1000" 13 chars + null byte
    snprintf(cstr, max_size, "%g", number);
    return __PS_cstr_to_string(cstr);
}

void* __PS_StringToString(void* s){
    return s;
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
    size_t string_length =(size_t) ((int64_t*)string)[0];
    char* cstring = string+sizeof(int64_t);
    return (int32_t) fwrite(cstring,        // start of the string
                            string_length,  // the number of chars in the string (includes explicit null chars)
                            sizeof(char),   // the size of each chars
                            stdout);        // print to stdout
}