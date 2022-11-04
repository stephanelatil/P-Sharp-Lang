# P#: A mix of python and C# but compiled #

## Highlight Feature mix ##

- Python Features:
  - List/str Splicing
    - Example: `array[a:b]` gives the array of size *b-a*. Creates a new array object (special type with bounds checking) that contains a pointer to the same array as previously. Just with an offset start and end point)  
    **Note:** `array[0:array.Len]` will return a new array object but pointing to the identical
  
  - Multiple bounds checking: `a < b < c` translates to `a < b and b < c` but `(a < b) < c` is equivalent to `int(a < b) < c`. because `(a < b)` returns true or false which evaluates respectively to 1 or 0.

  - Lambda expressions (but cannot access variable outside it's scope)

  - Special keywords:
    - `A in B`: A is contained in object B, can be overridden in B class description depending on implementation
    - `A is B`: A and B are pointers to the same object (Not the same as == which does an equality check). Cannot be overridden
    - `A and B / A or B / not A`: Boolean operator with short circuiting
  - All objects must have an explicit to_string cast defined

- C# features:
  - Boolean type with it's own operators (`+` is equivalent to OR, `*` equivalent to AND, `-` equivalent to an implication (`A-B` is equivalent to A implies B, aka `(not A) or B`). Division is not defined). Note that boolean is the lowest
  - with brackets
  - No Function definition keyword:
    - Example
  - strong & static typing
  - Setting a variable value returns the set value : `x = (y *= 2)` sets both x and y to the same value
  - bounds checking on arrays
  - foreach
  - Simple overloading of all operators
  - increment++ decrement--
  - implicit/explicit type casting
  - ternary operator : `condition ? action if true : action if false`
  - readonly keyword

- Other features:
  - Implicit type conversion bool -> int8..64 -> float16..64 and unsigned -> signed.
  - `+=, -=, *= \= ...` and similar. ex: `x += 3` is equivalent to `x = x + 3`
  - Type implication and casting `1 + 0.5 == float(1.5)` but `1 + (int32)0.5 == 1`
  - Simple management of threads and thread-safe memory????
  - Array object contains a pointer to the first element, the array length and pointers to special functions for arrays
  - `where` keyword to filter lists and iterables
  - Properties and fields in classes?

## Syntax description ##

Scopes are defined by brackets `{}` (like in C, C#...)  
A line or "statement" is terminated by a semicolon (like in C,C#...)

### Keywords ###

- **Primitive Types** are considered to be special keywords like in C#, they are objects (thus nullable!) they include:
  - `bool`
  - `int8`, `int16`, `int32`, `int64`
  - `float32`, `float64` (*Note:* The decimal included in c# will not be implemented here, and will be added as a library later)
  - `string`

- **NULL**
  `null` Not a type but a constant threadsafe readonly object kept in memory. It is handled differently depending if ti is compiled in Release or Debug mode.
  
  In **Release** Mode:
  - It cannot be garbage collected.
  - It has the value of 0 (Zero)
  - Only access to its ToString method or Equal operator is allowed, all other attempts will lead to a NullPtrException
  In **Debug** Mode:
  - It can be garbage collected
  - Its value is line/col to where this null value was SET last. (Or linked list with last times Set? First element is the latest). This makes better error messages to help with nullptrexceptions.
  - Only access to its ToString method or Equal operator is allowed, all other attempts will lead to a NullPtrException

- **Control structures**
  - `for`
  - `while`
  - `if`
  - `else`
  - `switch`/`case` or `elif`? (depends on compiler complexity)
  - `where` for list filtering

- **Compiler handled**
  - `readonly` raises an exception at compile-time if an attempt is made to write to a readonly variable. Value must be set when variable is created

## Under the hood ##

Compiled to machine code vs byte-code+runtime environment vs interpreter?
all 3?

| Type | Pros | Cons |
| --- | --- | --- |
| **Compiled** | | |
| **Byte-code** | | |
| **Interpreted** | | |

### If code is ultimately compiled ###

- All objects contain a (hidden) field that indicates their type and size to be able to easily handle polymorphism.
- Switch/case builds a jumping table?

## Limitations ##

For now :

- Classes cannot contain methods except ToString. Classes can be made as data classes/structs
- and no inheritance

## Conventions ##

*Name Case*:

- Classes should be *PascalCase*
- Public functions/methods and fields should be *PascalCase*
- Private functions/methods and fields should be *camelCase*
- Local scope variables should be *snake_case* (this includes lambda functions used in a local scope)

*Indentation*: should be a single tab or 4 spaces. Compiler/interpreter ignores blank space. 