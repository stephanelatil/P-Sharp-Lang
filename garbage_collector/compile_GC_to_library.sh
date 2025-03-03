SOURCE_FILE=gc.c
LIB_NAME=libps_gc.so
LIB_NAME_LL=libps_gc.ll
LIB_NAME_BC=libps_gc.bc
FLAGS=-Wall
COMPILER=clang-15

${COMPILER} -shared ${FLAGS} -o ${LIB_NAME} -fPIC ${SOURCE_FILE}
${COMPILER} -O3 -emit-llvm ${SOURCE_FILE} -S -o ${LIB_NAME_LL}
${COMPILER} -O3 -emit-llvm ${SOURCE_FILE} -c -o ${LIB_NAME_BC}