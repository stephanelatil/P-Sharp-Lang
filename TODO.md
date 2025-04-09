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

## [X] Add negative indexing for arrays

Like in python, when you have an array `i32[] arr = new i32[10]`. Indexing it with a negative value is identical to indexing it from the end. 

`arr[-1]` is equivalent to `arr[arr.Length - 1]` or for any `N > 0` then `arr[-N] == arr[arr.Length - N]`

## [-] Add a proper compiler executable (or main.py) file with documentation, cli args etc.

## [ ] Add `unsafe` context allowing for interacting directly with pointers, arrays without runtime checks etc.

This should allow you to build HAL drivers or build wrappers to C libs more easily and directly in P# instead of in C to then need linking and possible function name translation.

This should have:

- Direct access to allocator methods (alloc-object and alloc-arrays)
- Direct access to some registers (not frame/stack pointers)
- Direct pointer access, dereference
- Unchecked type casts
- Array access without bounds checks
- Placing objects on the stack for quick access (no malloc/free)
- Access to c-functions

## [ ] Fix type IDs for libraries

Currently type IDs are set when initializing the GC. Which means that when compiling libraries, types don't have type IDs! When allocating a new object, the `CodeGenContext` has no type id for the type and it will thus fail. 

For info, at the time of writing a TypeInfo struct:
```c
struct __PS_TypeInfo {
    size_t id;                 // Unique type ID
    size_t size;               // Total size of object's data (excluding header) in bytes
    size_t num_pointers;       // Number of pointer fields (all at start of data)
    const char* type_name;     // Name of type (for debugging)
};
```

Solutions to this include:

- Setting a type_id to the hash of `Namespace.__Types__.type_name`. Using 64 bits for the hash minimizes collisions (but does not eliminate them, especially for large projects!) and requires all types of the library to be exposed in the `.o` file is some way. Also types only used internally so the GC knows how to allocated them.

This does keep the info for the `name`, `size` and `number_of_pointers` available, ensuring the total executable size is minimized as we don't have to duplicate the default `ToString()` method for all types. A single default one can be used and just copy the name from the type_info reference.

- Setting the type_id to a hash (similar to above) but we only need 45 bits (or more/less?), with the remaining 19 used for type size data: (8 for number of pointers and 11 for type size). This limits a type size to having 255 pointers (reference types as fields) and a total size (sum of of all fields value-types) <= 2048 bytes.

This eliminates the need of exposing all types and enables a type to just have it's size/num_pointers exposed in its 64bit int. It still needs to expose the type_info of all types not only used internally.

- If we eliminate the need to have the type name and ID we can use the 64bit number to host all the needed info. 12 bits for the number of pointers (`2^12-1 = 4095` which is plenty for a single type) and 16 bits for the size (`2^16-1 = 65535` bytes for the sum of the size of all fields value. Should be fine). That leaves 36 bytes for any other info or reduce it to 32 bit for compatibility with embedded systems.

This does add the need for a default `ToString` method for every individual type (optimized out if unused when linked and optimized).

## [ ] Add debug symbols in LLVM IR generation with metadata

This will help with program debugging. They should be added if a flag is given to the compiler

## [ ] Don't stop compiler on first Lexer/Parser/Typer error but keep going with assumptions to print as many errors together as possible

## [ ] Add (mandatory) namespaces to avoid linker conflicts with other libs

This will simplify the separation of builtins (and functions used for internal use). Everything will be inside a namespace (including builtins, using a namespace starting with `__PS_`)

If a user does not state a namespace il should use the `Default` namespace. This will raise a warning and should not be allowed for libraries!

This can simplify importing of code as well: just import a namespace and you het access to its types & functions (not marked internal). 

## [ ] Add Warnings and flags for any and all potentials issues

## [ ] Add Properties getters (and setters) for fields with new keywords?

Will be able to use properties to get quick calculations for simple inlined methods like getting an array's length or a flag on a particular element (i.e. `someStack.IsEmpty` is a calculated value check on each call. Properties instead of methods)

## [ ] Add `extend` keyword to add new methods to existing types

## [ ] Add "interpreter" to run compiled llvm code `main` function using ctypes ?

## [ ] Add `override` operator to override __PS_* methods (will be replaced with namespaces)

Should add the possibility to add specific functions to run before/after GC init and before/after program shutdown a bit like adding an `atexit` hook.

It will allow to override specific language internal functions for specific use like overriding `__PS_malloc` and `__PS_free`.

## [ ] Errors and ability to throw them instead of immediate crash

## [ ] Try/catch (finally) once errors are enabled

## [ ] Add Abstract keyword and/or interfaces

This will need a complete redesign of method-fetching/calling. Polymorphism adds overhead and it is in discussion what should be added:
    - Multiple inheritance, like in c# (or worse like in python with the MRO issues)
    - If classes can only inherit from one abstract class and not non-abstract classes (and are abstract classes allowed to define methods or only declare them?). This will simplify greatly the v-table lookup. With/without interface support?
    - Only allow interfaces. Classes can only inherit interfaces which all only have a methods declarations?

## [ ] Add explicit alignments in llvm IR code generation?

Check if necessary?

## [ ] Add `packed` keyword

This is still in debate whether it's useful. It can save memory (and may have slight perf gains cache wise) but may have a performance hit due to getting a non-aligned bit (or byte). 

**Note to self:** This feature is necessary in cases to handle network packets or protocols with bit-flags for example when packing then to be written/read. It should be a simple add but be *very careful* to add alignment specifiers in the LLVM IR generation

## [ ] Integer binary literals (and octal?)

Being able to have binary literals like `0b110` which will simplify embedded and low level development. Should be a quick add in the Lexer!

## [ ] Integer and Float literal suffixes to denote the expected size

Currently all integer literals (except chars) are i32. If I want to define a literal unsigned, or smaller int you have to cast it. Or defining a literal i64 (bigger than the 32bit max value) results in a truncated value. 

There should be a way to define unsigned (with a `u` suffix?) integers or of a different size (`b` for byte size, 8 bits, `w`, (or `s`? for short/small) for 16 bits word size, and `q` for a quad-word). None is given for the default 32bit integer as `d` (double-word) would conflict with 

Something similar should be done for floats (`h` for half size f16, `f` the default for floats (also explicit float even if only given as an int like 1f which is equivalent to 1.0) and `d` for double)

## [ ] Memory Allocator

Custom allocator to optimize allocation of objects. Here we use malloc for every single class and array when calling new. If we need to instantiate an array of objects (e.g. 100 objects) that's 100 calls to malloc (+1 for the array itself) which is very slow!

A solution could be to pre-allocate n classes of a type and keep unused ones in a collection somewhere. Directly return a pointer to it when one is requested. Only call malloc when the collection is empty.

This will be very useful when working in embedded contexts. It will also maybe need some static analysis passes to see how to optimize the GC as much as possible.

## [ ] Object wrapper to convert from and to c structs 

c -> P# : It needs the structure definition to define an appropriate Class prototype with the same fields. It needs to be recursive for the properties!

## [ ] Object wrapper to convert from and to c++ classes?

Similar to C but more complex du to the c++ class system.

## [-] String object implementation & methods

Currently missing some string specific methods

## [ ] Default builtin functions like print

Print is already defined, Cf. "print" function. But it will have to be modified when using new namespace implementation. All other methods should be implemented as well like value type methods and (parse etc.) and 

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

## [ ] Possible native CUDA integration (cf. llvm and cuda integration?)

Will need to add special syntax and keywords to enable this!
