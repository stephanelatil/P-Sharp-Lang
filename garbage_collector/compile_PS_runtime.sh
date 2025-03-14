#!/usr/bin/bash

GC_FILENAME=gc
UTILS_FILENAME=ps_utils
COMBINED_FILENAME=ps_re
LIB_NAME=libps_re.so
LIB_NAME_BC=libps_re.bc
FLAGS=-Wall
COMPILER=clang-15
LLVM_LINKER=llvm-link-15

${COMPILER} -O3 -emit-llvm -c ${FLAGS} -o "${GC_FILENAME}.bc" "${GC_FILENAME}.c"
${COMPILER} -O3 -emit-llvm -c ${FLAGS} -o "${UTILS_FILENAME}.bc" "${UTILS_FILENAME}.c"

${LLVM_LINKER} "${GC_FILENAME}.bc" "${UTILS_FILENAME}.bc" -o "${COMBINED_FILENAME}.bc"
${COMPILER} -c  -o "${COMBINED_FILENAME}.o" "${COMBINED_FILENAME}.bc"

${COMPILER} -shared ${FLAGS} -o ${LIB_NAME} -fPIC "${COMBINED_FILENAME}.o"