SOURCE_FILE=gc.c
LIB_NAME=libps_gc.so
FLAGS=-Wall

gcc -shared ${FLAGS} -o ${LIB_NAME} -fPIC ${SOURCE_FILE}