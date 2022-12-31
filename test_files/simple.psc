int_16 x;
x = 2;

int_32 foo(int_16 x){
    int_32 a;
    a = 4;
    return x.value * a;
}

unsigned int_32 y;
y = foo(x);