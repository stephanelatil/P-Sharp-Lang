#!/usr/bin/bash
set -e

GC_FILENAME=gc
UTILS_FILENAME=ps_utils
COMBINED_FILENAME=ps_re
RENAME_PASS_PY=rename_pass.py
RENAME_MAPPING_CSV=rename_mapping.csv
FLAGS=-Wall

PY="../.venv/bin/python3"
COMPILER=clang-15
LLVM_LIB_INCLUDES="-I /usr/include/llvm-15 -I /usr/include/llvm-c-15"
LLVM_LINKER=llvm-link-15

${COMPILER} -O3 -emit-llvm -c ${FLAGS} -o "${GC_FILENAME}.bc" "${GC_FILENAME}.c"
${COMPILER} -O3 -emit-llvm -c ${FLAGS} -o "${UTILS_FILENAME}.bc" "${UTILS_FILENAME}.c"

# merge all .bc to a single runtime .bc object
${LLVM_LINKER} "${GC_FILENAME}.bc" "${UTILS_FILENAME}.bc" -o "${COMBINED_FILENAME}.bc"

# rename symbols to adhere to standard naming
${PY} "${RENAME_PASS_PY}" "${COMBINED_FILENAME}.bc" "${RENAME_MAPPING_CSV}"

rm "${GC_FILENAME}.bc" "${UTILS_FILENAME}.bc"
