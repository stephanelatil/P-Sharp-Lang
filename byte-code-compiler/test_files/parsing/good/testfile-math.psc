int_32 m() {
    int_32 x=1;
    int_32 y=2;
    x = 1 + 2 + 3 * -x;
    y = (((4/y) << 1) >> 2 + 1) % 2;
    return x^y;
}
