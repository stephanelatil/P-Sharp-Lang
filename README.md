# P# Programming Language

## **NOTE:**

**This project is currently being rewritten**. A beta is available and functional. A first release is planned soon as most features are functional-ish and simple programs execute correctly already.

<img src="assets/img/psharp_logo.png" alt="P# Logo" width="128"/>

P# is a programming language designed for developers who want the best of both worlds: the simplicity and expressiveness of Python, combined with the power and performance of C#. With a focus on static typing, efficient memory management, and seamless integration with C libraries, P# opens up new possibilities for building high-performance applications and scripting tasks.

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

1. **Installation**: Download the P# compiler by cloning the github repo [github.com/TheD0ubleT/P-Sharp-Lang](https://github.com/TheD0ubleT/P-Sharp-Lang).

2. **Hello, World!**: Write your first P# program by printing "Hello, World!" to the console:

```rust
i32 main(){
    print("Hello, World!");
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

P#'s syntax draws inspiration from C#, Python (and Rust types) to provide a familiar environment for developers. Here's a quick example of variable declaration, function definition and function call:

```rust
//classes with fields and methods
class Fibonacci{
    u64 ArrLen = (u64)100;
    //Classes have fields
    u64[] Cache = new u64[100]; 

    // Methods
    u64 Fib(i32 n){
        //check cache
        if (n < this.ArrLen and this.Cache[n] != 0)
            return this.Cache[n];
        //base case
        if (n <= 1)
            return (u64) n;
        // calculate value (second call uses cache built by the first)
        u64 result = this.Fib(n-1) + this.Fib(n-2);
        //cache result
        if (n < this.ArrLen)
            this.Cache[n] = result;
        return result;
    }
}


// Variable declaration
i32 x = 42;

// Function definition
i32 min(i32 a, i32 b) {
    return a < b ? a : b; //ternary operators
}

i32 main(){
    // new handles allocation and garbage collection
    Fibonacci f = new Fibonacci();

    //function calls & casts
    return (i32) f.Fib(10);
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
