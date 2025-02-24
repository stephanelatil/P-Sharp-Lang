# TODO

This is quick TODO list for me for my next steps. This does not guarantee that it will be done soon (or ever). It's mostly for personal reference and notes to self.

## [X] GC

## Integer and Float literal suffixes to denote the expected size

Currently all integer literals (except chars) are i32. If I want to define a literal unsigned, or smaller int you have to cast it. Or defining a literal i64 (bigger than the 32bit max value) results in a truncated value. 

There should be a way to define unsigned (with a `u` suffix?) integers or of a different size (`b` for byte size, 8 bits, `w`, (or `s`? for short/small) for 16 bits word size, and `q` for a quad-word). None is given for the default 32bit integer as `d` (double-word) would conflict with 

Something similar should be done for floats (`h` for half size f16, `f` the default for floats (also explicit float even if only given as an int like 1f which is equivalent to 1.0) and `d` for double)

## [ ] Memory Allocator

## [ ] Object wrapper to convert from and to c structs 

c -> P# : It needs the structure definition to define an appropriate Class prototype with the same fields. It needs to be recursive for the properties!

## [ ] Object wrapper to convert from and to c++ classes?

## [ ] String object implementation & methods

## [ ] Default builtin functions like print

## [ ] Array splicing?

## [ ] Copy operator

## [ ] `override` operator to override __PS_* methods

Should add the possibility to add specific functions to run before/after GC init and before/after program shutdown a bit like adding an `atexit` hook.

It will allow to override specific language internal functions for specific use like overriding `__PS_malloc` and `__PS_free`.

## [ ] Add possiblitity to add `operator` keyword to write custom operators for operations with classes (like in c# or some python dunders)

## [ ] Add keywords `implicit` and `explicit` for casting classes

There is a potential for issues if class A defines an (ex/im)plicit cast to class B, and class B defined an (ex/im)plicit cast from A. Both technically do the same thing! 

Maybe only allowing (ex/im)plicit casts to de defined either *from* or *to* a class. 

## [ ] Function/Method overloading

## [ ] Add method constructors

## [ ] Add `readonly` keyword 

Only allows class fields to be set in the class constructor (and?) or as a field default value when creating the class

## [ ] Add `property` keyword to have a read-only property method (like in python)

Properties can be used to return constants or computed values (like the current Length) field on a 
