#include <stdio.h>
#include <stdlib.h>
#include "../gc.h"
#include "../structures.h"

static PS_GC__hashset *set;
static PS_GC__scopeRootVarsStack *stack;

// Simulated object structure
typedef struct Object
{
  int value;
  struct Object *next;
} Object;

static int count_objects_in_set(int print)
{
  int count = 0;
  for (size_t i = 0; i < set->size; ++i)
  {
    int bucketCount = 0;
    PS_GC__hashset_bucket *bucket = set->buckets[i];
    while (bucket != NULL)
    {
      bucket = bucket->next;
      bucketCount++;
    }
    if (print)
      printf("Bucket %zu conatains %d elements\n", i, bucketCount);
    count += bucketCount;
  }
  return count;
}

// Simulated garbage collector APIs
static Object *gc_alloc(int value)
{
  Object *obj = (Object *)malloc(sizeof(Object));
  PC_GC__new_obj(set, obj);
  obj->value = value;
  obj->next = NULL;
  return obj;
}

static void gc_collect()
{
  PS_GC__garbage_collect(stack, set);
}

// Simulated function calls
static Object *add(Object *a, Object *b)
{
  PS_GC__rootVarList *vars = PS_GC__create_rootVarList(3);
  PS_GC__assign_var(stack, set, a, 0, 0);
  PS_GC__assign_var(stack, set, b, 0, 1);
  PS_GC__enter_function(stack, vars);
  Object *ret = gc_alloc(a->value + b->value);
  PS_GC__assign_var(stack, set, ret, 0, 2);
  PS_GC__exit_function(stack);
  return ret;
}

// Simulated recursive function
static Object *factorial(Object *n)
{
  PS_GC__enter_function(stack, PS_GC__create_rootVarList(3));
  PS_GC__assign_var(stack, set, n, 0, 0);
  Object *ret = gc_alloc(1);
  PS_GC__assign_var(stack, set, ret, 0, 2);
  if (n->value != 0)
  {
    Object *n_1 = gc_alloc(n->value - 1);
    PS_GC__assign_var(stack, set, n_1, 0, 1);
    ret = gc_alloc(n->value * factorial(n_1)->value);
    PS_GC__assign_var(stack, set, ret, 0, 2);
  }
  PS_GC__exit_function(stack);
  return ret;
}

// Simulated code execution function
static void execute_code()
{
  // Simulate code execution
  PS_GC__stack_push(stack, PS_GC__create_rootVarList(5));
  Object *obj5 = gc_alloc(5);
  PS_GC__assign_var(stack, set, obj5, 0, 0);
  Object *obj2 = gc_alloc(2);
  PS_GC__assign_var(stack, set, obj2, 0, 1);

  Object *result = add(obj5, obj2);
  PS_GC__assign_var(stack, set, result, 0, 2);

  printf("add: Expected 7 got %d\n", result->value);

  // Simulated loop
  for (int i = 0; i < 3; i++)
  {
    obj2 = gc_alloc(i * 10);
    PS_GC__assign_var(stack, set, obj2, 0, 3);
  }

  Object *fact_result = factorial(result);
  PS_GC__assign_var(stack, set, fact_result, 0, 4);
  printf("Fact result Expected 5040, found %d\n", fact_result->value);

  // Simulate garbage collection after code execution

  obj5->next = gc_alloc(5);
  PS_GC__object *child = PS_GC__getItem(set, obj5->next);
  PS_GC__add_children(PS_GC__getItem(set, obj5), &child, 1);
  printf("********************\nBefore GC\n\n");
  printf("Total count %d\n\n", count_objects_in_set(1));
  gc_collect();
  printf("********************\nAfter GC\n\n");
  int num_obj = count_objects_in_set(1);
  printf("Objects before dealloc %d", num_obj);

  PS_GC__assign_var(stack, set, NULL, 0, 0);
  // deallocate local vars and all children
  gc_collect();
  printf("After dealloc there should be: %d found: %d\n", num_obj - 2, count_objects_in_set(0));

  PS_GC__exit_function(stack);
}

int main()
{
  // Initialize your runtime environment here
  stack = PS_GC__initialize_stack();
  set = PS_GC__initialize_hashset(16);
  printf("********************\nInit GC\n\n");
  printf("Num allocated objects Expected 0, found %d\n\n", count_objects_in_set(0));
  // Execute the code and test the garbage collector
  execute_code();
  // Clean up your runtime environment here

  PS_GC__exit_function(stack);
  // deallocate local vars and all children
  gc_collect();

  printf("End of program all should be GC'd: Remaining items %d\n", count_objects_in_set(0));
  return 0;
}
