# P#: A mix of python and C# but compiled #

## Highlight Feature mix ##

Note that many features are not yet implemented and may never be implemented. Currently available ones are marked with a checked tickbox [x] however unchecked boxes [ ] may just be wishful thinking at the moment.

- Python Features:
  - [ ] List/str Splicing
    - [ ] Example: `array[a:b]` gives the array of size *b-a*. Creates a new array object (special type with bounds checking) that contains a pointer to the same array as previously. Just with an offset start and end point)  
    **Note:** `array[0:array.Len]` will return a new array object but pointing to the identical

  - [ ] Lambda expressions (but cannot access variables outside its scope)

  - [ ]Special keywords:
    - [ ] `A in B`: A is contained in object B, can be overridden in B class description depending on implementation
    - [ ] `A is B`: A and B are pointers to the same object (Not the same as == which does an equality check). Cannot be overridden
    - [ ] `A and B / A or B / not A`: Boolean operator with short circuiting
  - [ ] All objects must have an explicit `ToString` method defined
  - [x] Can have code directly run without a *main* function
  - [ ] Some sort of `if __name__ == "__main__"` region  or definitions with preprocessor directives (`#module/#end` or `#main/#end`)
  - [ ] Optional (default) parameters for functions and constructors

- C# features:
  - [ ] Boolean type with it's own operators (`+` is equivalent to OR, `*` equivalent to AND)
  - [x] Brackets used for scope definition
  - [x] static typing
  - [x] Setting a variable value returns the set value : `x = (y *= 2)` sets both x and y to the same value
  - [ ] bounds checking on arrays
  - [ ] foreach
  - [ ] function overloading
  - [ ] Simple overloading of all operators
  - [x] increment++ decrement--
  - [x] implicit/explicit type casting
  - [x] ternary operator : `condition ? action if true : action if false`
  - [ ] readonly keyword
  - [ ] public/private keywords

- Other features:
  - [x] Implicit type conversion bool -> int8..64 -> float16..64 and unsigned -> signed.
  - [x] `+=, -=, *= \= ...` and similar. ex: `x += 3` is equivalent to `x = x + 3`
  - [ ] Type implication and casting `1 + 0.5 == float(1.5)` but `1 + (int32)0.5 == 1`
  - [ ] Simple management of threads and thread-safe memory????
  - [ ] Array object contains a pointer to the first element, the array length and pointers to special functions for arrays
  - [ ] `where` keyword to filter lists and iterables
  - [x] fields in classes?
  - [ ] Properties in classes

## Syntax description ##

Scopes are defined by brackets `{}` (like in C, C#...)  
A line or "statement" is terminated by a semicolon (like in C,C#...)

### Comments ###

Comments will keep the standard C format: `//` for single line comments and `/* */` for multiline comments

### Keywords ###

- **Primitive Types** are considered to be special keywords like in C#, they are objects (thus nullable!) they include:
  - `bool`
  - `int8`, `int16`, `int32`, `int64`
  - `float32`, `float64` (*Note:* The decimal included in c# will not be implemented here, and will be added as a library later)
  - `string`

- **NULL**
  `null` Not a type but a constant threadsafe readonly object kept in memory. It is handled differently depending if it is compiled in Release or Debug mode.
  
  In **Release** Mode:
  - [ ] It cannot be garbage collected.
  - [ ] It has the value of 0 (Zero)
  - [ ] Only access to its ToString method or Equal operator is allowed, all other attempts will lead to a NullPtrException
  In **Debug** Mode:
  - [ ] It can be garbage collected
  - [ ] Its value is line/col to where this null value was SET last. (Or linked list with last times Set? First element is the latest). This makes better error messages to help with nullptrexceptions.
  - [ ] Only access to its ToString method or Equal operator is allowed, all other attempts will lead to a NullPtrException

- **Control structures**
  - [x] `for`
  - [x] `while`
  - [x] `if`
  - [x] `else`
  - [ ] `switch`/`case` or `elif`? (depends on compiler complexity)
  - [ ] `where` for list filtering

- **Compiler handled**
  - [ ]`readonly` raises an exception at compile-time if an attempt is made to write to a readonly variable. Value must be set when variable is created

## Limitations ##

For now :

- No inheritance
- No overloading (includes constructors)
- No default values (optional parameters) in function definitions

## Conventions ##

*Name Case*:

- Classes should be *PascalCase*
- Public functions/methods and fields should be *PascalCase*
- Private functions/methods and fields should be *camelCase*
- Local scope variables should be *snake_case*

*Indentation*: should be a single tab or 4 spaces. Compiler/interpreter ignores blank space.
