#include <stdio.h>
#include <stdlib.h>
#include "../gc.h"
#include "../structures.h"

static int count_objects_in_set(PS_GC__hashset* set)
{
  int count = 0;
  for (size_t i = 0; i < set->size; ++i)
  {
    PS_GC__hashset_bucket *bucket = set->buckets[i];
    while (bucket != NULL)
    {
      bucket = bucket->next;
      count++;
    }
  }
  return count;
}

static void test_set()
{
  PS_GC__hashset *set = PS_GC__initialize_hashset(8);

  PS_GC__object *obj1 = PS_GC__create_obj((void *)1200);
  PS_GC__object *obj2 = PS_GC__create_obj((void *)1234);
  PS_GC__object *obj3 = PS_GC__create_obj((void *)1235);
  PS_GC__object *obj4 = PS_GC__create_obj((void *)1236);
  PS_GC__object *obj5 = PS_GC__create_obj((void *)1300);

  count_objects_in_set(set) ? printf("Error: Cleared set has elements remaining.\n") 
                            : printf("Ok   : Cleared set is empty.\n");
  PS_GC__insertItem(set, obj1);
  PS_GC__insertItem(set, obj1);
  count_objects_in_set(set) == 1 ? printf("Ok   : Double add creates single item.\n")
                                 : printf("Error: Double add created multiple items.\n");
  PS_GC__insertItem(set, obj2);
  PS_GC__insertItem(set, obj3);
  PS_GC__insertItem(set, obj4);
  PS_GC__insertItem(set, obj5);
  count_objects_in_set(set) == 5 ? printf("Ok   : Multiple items added successfully.\n")
                                 : printf("Error: Adding multiple items.\n");

  PS_GC__getItem(set,obj1->ptr) == obj1 ? printf("Ok   : Successfully retrieved item from set.\n")
                                        : printf("Error: Unable to get item from set.\n");

  PS_GC__removeItem(set, obj1) ? printf("Ok   : Remove single in bucket item successfully.\n")
                               : printf("Error: Removing single item in bucket.\n");

  PS_GC__getItem(set, obj1->ptr) == obj1 ? printf("Error: Item found after being removed.\n")
                                         : printf("Ok   : Removed item not found.\n");

  PS_GC__removeItem(set, obj1) ? printf("Error: Item removed twice.\n")
                               : printf("Ok   : Not found after double remove.\n");

  PS_GC__getItem(set, obj3->ptr) == obj3 ? printf("Ok   : Successfully retrieved item from set (middle bucket).\n")
                                         : printf("Error: Unable to get item from middle of bucket in set.\n");

  PS_GC__getItem(set, obj4->ptr) == obj4 ? printf("Ok   : Successfully retrieved item from set (last bucket).\n")
                                         : printf("Error: Unable to get item from last bucket in set.\n");

  PS_GC__removeItem(set, obj3) ? printf("Ok   : Successfully removed item from middle bucket.\n")
                               : printf("Error: Unable to remove item from middle bucket.\n");

  PS_GC__removeItem(set, obj4) ? printf("Ok   : Successfully removed item from last bucket.\n")
                               : printf("Error: Unable to remove item from last bucket.\n");

  PS_GC__getItem(set, (void *)0xdeadbeef) ? printf("Error: Get item not in set returns a non NULL item.\n")
                                          : printf("Ok   : Get item not in set returns NULL.\n");

  free(set);
}

static void test_stack()
{
  PS_GC__scopeRootVarsStack *stack = PS_GC__initialize_stack();

  PS_GC__stack_is_empty(stack) ? printf("Ok   : New stack reports as empty.\n")
                               : printf("Error: New stack reports as not empty.\n");

  PS_GC__stack_pop(stack) ? printf("Error: Pop empty stack returns non NULL item.\n")
                          : printf("Ok   : Pop empty stack returns NULL.\n");

  PS_GC__rootVarList *vars1 = PS_GC__create_rootVarList(3);
  PS_GC__rootVarList *vars2 = PS_GC__create_rootVarList(4);
  PS_GC__stack_push(stack, vars1) ? printf("Ok   : Pushed first item sucessfully.\n")
                                 : printf("Error: Unable to push first item.\n");
  PS_GC__stack_push(stack, vars2) ? printf("Ok   : Pushed second item sucessfully.\n")
                                  : printf("Error: Unable to push second item.\n");

  PS_GC__stack_is_empty(stack) ? printf("Error: Non-empty reports as empty.\n")
                               : printf("Ok   : Non-empty stack reports as non-empty.\n");

  stack->last->vars == vars2 ? printf("Ok   : Last item == pushed item.\n")
                             : printf("Error: Last item different from pushed item.\n");

  PS_GC__stack_pop(stack) == vars2 ? printf("Ok   : Popped item == pushed item.\n")
                                   : printf("Error: Popped item different from pushed item.\n");

  PS_GC__stack_pop(stack) == vars1 ? printf("Ok   : Second popped item == pushed item.\n")
                                   : printf("Error: Second popped item different from pushed item.\n");

  PS_GC__stack_is_empty(stack) ? printf("Ok   : Now empty stack reports as empty.\n")
                               : printf("Error: Now empty stack reports as not empty.\n");

  PS_GC__stack_pop(stack) ? printf("Error: Pop empty stack returns non NULL item.\n")
                          : printf("Ok   : Pop empty stack returns NULL.\n");
  free(vars2);
  free(vars1);

  free(stack);
}
int main()
{
  test_stack();
  test_set();
  return 0;
}
