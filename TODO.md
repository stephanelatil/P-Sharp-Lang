# TODO

This is quick TODO list for me for my next steps. This does not guarantee that it will be done soon (or ever). It's mostly for personal reference and notes to self.

## [X] GC

## [ ] GC improvements

Cf. The garbage collector handbook to see how to improve the GC. Maybe cf. the [memory allocator](#[-]-memory-allocator) point

## [X] llvm_transpiler refactor

Need to simplify each function and what it does in the setup and compiling phase.
Need simpler functions and to more clearly define a code flow path for compiling. e.g:

1. Init CodeGen class
1. Lex, Parse and Type code
1. Init CodeGenContext
1. Init Type list/map
1. Init Function prototype list/map for builtin functions (Also need a new file with all constants to avoid magic strings/values)
1. Generate code for all defined functions, classes and globals (while keeping non-definition statements separate to place in the main function)
1. If not a library
    - Generate code for main function setup (potentially add places for pre-post setup code)
    - Generate code for the statements to place in the main function
    - Generate code for main function teardown (potentially add places for pre-post cleanup code)
    - Statically link to GC (and other builtins to add the runtime env to the executable)
1. Run llvm code verification
1. Run optimization passes
1. Output all code to a file (or pass to clang/compiler) to output .ll .bc or .o depending on params

## [ ] Add a proper compiler executable (or main.py) file with documentation, cli args etc.

## [ ] Add debug symbols in LLVM IR generation with metadata

This will help with program debugging. They should be added if a flag is given to the compiler

## [ ] Add (mandatory) namespaces to avoid linker conflicts with other libs

## [ ] Add Warnings and flags for any and all potentials issues

## [ ] Add "interpreter" to run compiled llvm code `main` function using ctypes

## [ ] `override` operator to override __PS_* methods (will be replaced with namespaces)

Should add the possibility to add specific functions to run before/after GC init and before/after program shutdown a bit like adding an `atexit` hook.

It will allow to override specific language internal functions for specific use like overriding `__PS_malloc` and `__PS_free`.

## [ ] Errors and ability to throw them instead of immediate crash

## [ ] Try/catch (finally) once errors are enabled

## [ ] Add explicit alignments in llvm IR code generation?

Check if necessary?

## [ ] Add `packed` keyword

This is still in debate whether it's useful. It can save memory (and may have slight perf gains cache wise) but may have a performance hit due to getting a non-aligned bit (or byte). 

**Note to self:** This feature is necessary in cases to handle network packets or protocols with bit-flags for example when packing then to be written/read. It should be a simple add but be *very careful* to add alignment specifiers in the LLVM IR generation

## [ ] Integer and Float literal suffixes to denote the expected size

Currently all integer literals (except chars) are i32. If I want to define a literal unsigned, or smaller int you have to cast it. Or defining a literal i64 (bigger than the 32bit max value) results in a truncated value. 

There should be a way to define unsigned (with a `u` suffix?) integers or of a different size (`b` for byte size, 8 bits, `w`, (or `s`? for short/small) for 16 bits word size, and `q` for a quad-word). None is given for the default 32bit integer as `d` (double-word) would conflict with 

Something similar should be done for floats (`h` for half size f16, `f` the default for floats (also explicit float even if only given as an int like 1f which is equivalent to 1.0) and `d` for double)

## [ ] Memory Allocator

Custom allocator to optimize allocation of objects. Here we use malloc for every single class and array when calling new. If we need to instantiate an array of objects (e.g. 100 objects) that's 100 calls to malloc (+1 for the array itself) which is very slow!

A solution could be to pre-allocate n classes of a type and keep unused ones in a collection somewhere. Directly return a pointer to it when one is requested. Only call malloc when the collection is empty.

## [ ] Object wrapper to convert from and to c structs 

c -> P# : It needs the structure definition to define an appropriate Class prototype with the same fields. It needs to be recursive for the properties!

## [ ] Object wrapper to convert from and to c++ classes?

Similar to C but more complex du to the c++ class system.

## [-] String object implementation & methods

Currently missing the string specific methods

## [ ] Default builtin functions like print

Print is already defined, Cf. "print" function. But it will have to be modified when using new namespace implementation

## [ ] Array splicing?

## [ ] Copy operator

## [ ] Add possiblitity to add `operator` keyword to write custom operators for operations with classes (like in c# or some python dunders)

## [ ] Add keywords `implicit` and `explicit` for casting classes

There is a potential for issues if class A defines an (ex/im)plicit cast to class B, and class B defined an (ex/im)plicit cast from A. Both technically do the same thing! 

Maybe only allowing (ex/im)plicit casts to de defined either *from* or *to* a class. 

## [ ] Function/Method overloading

## [ ] Add Class constructors?

This will need to have overloading implemented before!

Currently constructors set all non-instantiated fields to 0 or null and uses the currently defined default values

## [ ] Add `readonly` keyword 

Only allows class fields to be set in the class constructor (and?) or as a field default value when creating the class

## [ ] Add `property` keyword to have a read-only property method (like in python)

Properties can be used to return constants or computed values (like the current Length) field on a 

## [ ] Possible native CUDA integration (cf. llvm and cuda integration?)

Will need to add special syntax and keywords to enable this!
