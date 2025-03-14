#ifndef PS_LANG_UTILS_H
#define PS_LANG_UTILS_H

#include <stdio.h>
#include <inttypes.h>
#include <stdint.h>
#include "gc.h"

void *__PS_DefaultToString(void* object);


void* __PS_GetPtrToArrayElement(void* array, int8_t element_size_in_bytes, int64_t index, char* filename, int32_t position_line, int32_t position_column);

#endif