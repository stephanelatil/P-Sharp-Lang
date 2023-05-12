int_16 x = 5;
unsigned int_32 y = 2;

x = 5;
y = 1+y*x+1;

assert(y == 12);