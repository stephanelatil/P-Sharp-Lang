i32 x = 0;

if (true){
    if (x){}
    else {x++;}
}
if (x == 1){
    x++;
}

assert(x==2);