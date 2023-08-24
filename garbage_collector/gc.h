#ifndef PS_GC__GC_H
#define PS_GC__GC_H

#include <stdlib.h>
#include "structures.h"

/**
 * @brief Runs the garbage collector and frees unreachable items
 *
 * @param stack The stack of reachable variables
 * @param set The set of all heap allocated objects
 */
void PS_GC__garbage_collect(PS_GC__scopeRootVarsStack *stack, PS_GC__hashset *set);

/**
 * @brief Marks a GC object and all it's children (objects in fields) as reachable
 *
 * @param obj The object to mark
 */
void PS_GC__mark(PS_GC__object *obj);

/**
 * @brief Unmarks all GC objects in the hashset to prepare for future marking
 *
 * @param set The hashset containing GC objects
 */
void PS_GC__unmark_all(PS_GC__hashset *set);

/**
 * @brief Sweeps and frees unmarked GC objects in the hashset
 *
 * @param set The hashset containing GC objects
 */
void PS_GC__sweep(PS_GC__hashset *set);

/**
 * @brief Collects and frees a specific GC object
 *
 * @param obj The object to collect
 */
void PS_GC__collect_object(PS_GC__hashset *set, PS_GC__object *obj);

/**
 * @brief Edits the object pointed to by a variable after an assignment
 *
 * @param stack The stack of reachable variables
 * @param ptr The pointer to the new item assigned to the variable
 * @param depth The depth of the variable in the stack
 * @param index The index of the variable in the root variable list
 */
void PS_GC__assign_var(PS_GC__scopeRootVarsStack *stack, PS_GC__hashset *set,
                       void *ptr, int depth, int index);

/**
 * @brief Executed on function enter and adds its local object variables to the
 * root vars stack
 *
 * @param stack The stack of reachable variables
 * @param vars The list of object variables of the scope
 */
inline void PS_GC__enter_function(PS_GC__scopeRootVarsStack *stack,
                                  PS_GC__rootVarList *vars)
{
  PS_GC__stack_push(stack, vars);
}

/**
 * @brief Exits a function scope and removes its variables from the stack
 *
 * @param stack The stack of reachable variables
 */
inline void PS_GC__exit_function(PS_GC__scopeRootVarsStack *stack)
{
  PS_GC__stack_pop(stack);
}

/**
 * @brief Registers a new object created on the heap, adds it to the hashset and returns the item
 *
 * @param set The hashset to insert the item in
 * @param ptr The pointer to the object on the heap
 */
PS_GC__object *PC_GC__new_obj(PS_GC__hashset *set, void *ptr);

#endif /* PS_GC__GC_H */
