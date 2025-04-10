# P# Programming Language

<img src="assets/img/psharp_logo.png" alt="P# Logo" width="128"/>

P# is a embedded programming language designed for developers who want the best of both worlds: the simplicity and expressiveness of Python, combined with the power and performance of C#. With a focus on static typing, efficient memory management, and seamless integration with C libraries, P# opens up new possibilities for building high-performance embedded systems.

**NOTE:** Currently the language can only be compiled for Linux. Bare metal support for Arduino and other systems will be added as the language evolves, as well as other planned features (c.f. the [TODO](./TODO.md))

## Table of Contents

- [Introduction](#introduction)
- [Key Features](#key-features)
- [Quick Start](#quick-start)
- [Language Syntax](#language-syntax)
- [Memory Management](#memory-management)
- [Custom Classes](#custom-classes)
- [Integration with C Libraries](#integration-with-c-libraries)
- [Scripting Capabilities](#scripting-capabilities)
- [Contributing](#contributing)
- [License](#license)

## Introduction

P# combines the readability and ease of use of Python with C#'s performance and type system. This unique blend allows developers to write code that is both elegant and efficient, whether they're working on complex applications or quick scripting tasks.

The goal is to build a language for **embedded devices** and bare metal without having to think about memory management. The GC will have a small performance overhead compared to rust or C.

**Note** that many features and some syntax quirks may change over time as this is still in early development.

Notably the parser is being reworked from a Yacc parser to a custom parser to handle syntax sugar and reduction prioritization more robustly. Everything else if being thoroughly reworked for a faster compiler and added features.

## Key Features

### Static Typing

P# enforces static typing to catch errors at compile-time, providing increased reliability and improved performance. This ensures that type-related issues are caught early in the development process and ensured a smaller memory footprint and faster code.

### Hybrid Memory Management

P# utilizes a hybrid memory management system to optimize memory usage. It employs static memory management whenever possible, while resorting to a garbage collector for other objects. This approach strikes a balance between performance and memory efficiency.

### Seamless C Library Integration

**NOTE:** *Not yet implemented*

Developers can harness the power of existing C libraries by seamlessly linking them with P# code. This allows you to leverage a vast array of libraries for various purposes, enhancing the language's capabilities and reducing development time.

### Scripting Simplicity

P# stands out as a scripting-friendly language by eliminating the need for a main class or function. This makes it perfect for quick scripts, automation tasks, and prototyping, reducing boilerplate code and streamlining the development process.

## Quick Start

To start using P#, follow these simple steps:

1. **Installation**: 
    - Download the P# compiler by cloning the github repo [github.com/TheD0ubleT/P-Sharp-Lang](https://github.com/TheD0ubleT/P-Sharp-Lang)<br/><br/>
    - Install the llvm & clang toolchain (>=llvm-15 and >=clang-15). Install using `sudo apt install llvm clang -y`<br/><br/>
    - Install python requirements with `python3 -m venv .venv && . .venv/bin/activate && python3 -m pip install -r requirements.txt`. <br/>**Note** that to use the compiler you need to have python linked to the venv here currently! Make sure to use the `. .venv/bin/activate` command when compiling from a new shell!
    - Make sure `pscc` is executable with `chmod +x pscc`

2. **Hello, World!**: Write your first P# program by printing "Hello, World!" to the console:

```rust
i32 main(){
    print("Hello, World!\n");
    return 0;
}
```

### Compile and Run: Use the P# compiler to compile your program

```sh
pscc -o output_executable your_program_source.psc
```

### Run code

```sh
./output_executable
```

## Language Syntax

P#'s syntax draws inspiration from C#, Python (and Rust types) to provide a familiar environment for developers. Here's a quick example of variable, function and class definitions as well as their use:

```rust
// Global variable declaration
i32 CACHE_SIZE = 10;

class Fibonacci{
    // field default values
    // garbage collected arrays
    u64[] Cache = new u64[CACHE_SIZE]; 

    // Methods
    u64 Fib(i32 n){
        //base case
        if (n <= 1)
            return (u64) n;
        //check cache
        if (n < this.Cache.Length and this.Cache[n] != 0)
            return this.Cache[n];
        // calculate value (second call uses cache built by the first)
        u64 result = this.Fib(n-1) + this.Fib(n-2);
        //cache result
        if (n < this.Cache.Length)
            this.Cache[n] = result;
        return result;
    }
}

// Function definition
i32 Min(i32 a, i32 b) {
    return a < b ? a : b; //ternary operators
} //raises warning for unused function


//recursive fucntion
i32 Factorial(i32 n){
    if (n <=1)
        return 1;
    return n * Factorial(n-1);
}

void IsNotZeroAssertion(i32 number){
    //Assertions with error messages (also includes filename, line number and column)
    assert number != 0, "Number is Zero!";
}

i32 main(){
    // "new" keyword handles object allocation
    Fibonacci f = new Fibonacci();

    //function calls & casts
    i32 result = (i32) f.Fib(10);
    // method calls on value types
    IsNotZeroAssertion(result);
    // Builtin string type
    string stringResult = result.ToString();
    // built-in print method (only accepts strings at the moment)
    print(stringResult);
    //return codes
    return 0;
    //Auto garbage collection
}
```

## Memory Management

P# employs a hybrid memory management system to optimize ease of use and performance. It employs static memory management for efficiency when possible and uses a garbage collector for all other objects which don't have easy deterministic lifespan to prevent memory leaks and ensure robustness.

## Custom Classes

Create your own custom classes in P# to encapsulate data and behavior:

```csharp
class Point {
    f32 x;
    f32 y;

    /* Currently constructors are not yet supported
    Point(f32 x, f32 y) {
        this.x = x;
        this.y = y;
    }
    */

    f32 squareNorm(){
        return x * x + y * y;
    }
}
```

## Integration with C Libraries

*Coming soon (?)*

P# will enable easy integration with C libraries to enhance functionality while keeping everything safe of memory leaks. Declare external functions using the `extern` keyword:

```c
extern i32 rand(void);
extern i16 atos(char[] s);
```

## Scripting Capabilities

Thanks to its lightweight runtime (<50kb) and almost no nature and absence of main class requirements, P# excels as a scripting language. Perform quick tasks without unnecessary setup or classes.

## Contributing

We welcome contributions to P# from the community. Feel free to submit issues, feature requests, and pull requests on our GitHub repository.

### Help me work faster!

To encourage me to complete the compiler and add new features feel free to <a href="https://www.buymeacoffee.com/stephanelatil" target="_blank"><img src="https://cdn.buymeacoffee.com/buttons/default-orange.png" alt="Buy Me A Coffee" height="41" width="174"></a>

## License

P# is released under the MIT License, making it open and accessible for both personal and commercial projects.

Get started with P# today and experience the power of a language that marries the elegance of Python with the efficiency of C#.

Happy coding!
