#ifndef PS_LANG_UTILS_H
#define PS_LANG_UTILS_H

#include <stdio.h>
#include <inttypes.h>
#include <float.h>
#include <stdint.h>
#include "gc.h"

int32_t print(char* string);

void *__PS_DefaultToString(void* object);

void *__PS_DefaultToString(void* object);

void* __PS_BoolToString(bool);
void* __PS_CharToString(uint8_t);
void* __PS_I8ToString(int8_t);
void* __PS_U8ToString(uint8_t);
void* __PS_I16oString(int16_t);
void* __PS_U16ToString(uint16_t);
void* __PS_I32oString(int32_t);
void* __PS_U32ToString(uint32_t);
void* __PS_I64oString(int64_t);
void* __PS_U64ToString(uint64_t);
void* __PS_F16ToString(_Float16);
void* __PS_F32oString(_Float32);
void* __PS_F64ToString(_Float64);
void* __PS_StringToString(void*);

void __PS_NullCheckObject(void* object, char* filename, int32_t position_line, int32_t position_column);

void* __PS_GetPtrToArrayElement(void* array, int8_t element_size_in_bytes, int64_t index, char* filename, int32_t position_line, int32_t position_column);

#endif