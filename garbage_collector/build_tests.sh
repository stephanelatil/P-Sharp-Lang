COMPILER=clang-15

GC_OBJ=gc.o
TESTS_OBJ=tests.o

TESTS_EXEC=tests.out

${COMPILER} -Wall -g -O0 -c -o ${GC_OBJ} gc.c
${COMPILER} -Wall -g -O0 -c -o ${TESTS_OBJ} tests/tests.c
${COMPILER} -g -O0 ${GC_OBJ} ${TESTS_OBJ} -o ${TESTS_EXEC}
rm ${GC_OBJ} ${TESTS_OBJ}