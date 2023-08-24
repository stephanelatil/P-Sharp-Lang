#include <stddef.h>
#include <stdlib.h>
#include <stdint.h>
#include "structures.h"
#include "gc.h"

void PS_GC__mark(struct PS_GC__object *obj)
{
    if (obj && obj->marked == 0) // only mark and continue not marked to avoid loops
    {
        obj->marked = 1;
        for (size_t i = 0; i < obj->number_of_children; i++)
            PS_GC__mark(obj->children[i]);
    }
}

void PS_GC__unmark_all(PS_GC__hashset *set)
{
    for (size_t i = 0; i < set->size; i++)
    {
        struct PS_GC__hashset_bucket *bucket = set->buckets[i];
        while (bucket != NULL)
        {
            bucket->object->marked = 0;
            bucket = bucket->next;
        }
    }
}

void PS_GC__sweep(PS_GC__hashset *set)
{
    for (size_t i = 0; i < set->size; i++) // for every bucket
    {
        struct PS_GC__hashset_bucket *bucket = set->buckets[i];
        struct PS_GC__hashset_bucket *prev_bucket = NULL;
        while (bucket != NULL)
        {
            if (bucket->object->marked == 0) // Unreachable object
            {
                if (prev_bucket) // not null (bucket is not the first item in
                                 // linked list)
                {
                    prev_bucket->next = bucket->next;
                    PS_GC__collect_object(set, bucket->object);
                    PS_GC__delete_hashset_bucket(bucket);
                }
                else // first item in linked list handled slightly differently
                {
                    set->buckets[i] = bucket->next;
                    PS_GC__collect_object(set, bucket->object);
                    PS_GC__delete_hashset_bucket(bucket);
                }
            }
            else
            {
                prev_bucket = bucket;
            }
            bucket = bucket->next;
        }
    }
}

void PS_GC__collect_object(PS_GC__hashset *set, PS_GC__object *obj)
{
    PS_GC__removeItem(set, obj);
    free(obj->ptr);
    PS_GC__delete_object(obj);
}

void PS_GC__assign_var(PS_GC__scopeRootVarsStack *stack, PS_GC__hashset *set,
                       void *ptr, int depth, int index)
{
    PS_GC__scopeRootVarsStackItem *item = stack->last;
    while (depth > 0)
    {
        item = item->prev;
        --depth;
    }
    item->vars->obj[index] = PS_GC__getItem(set, ptr);
}

PS_GC__object *PC_GC__new_obj(PS_GC__hashset *set, void *ptr)
{
    PS_GC__object *obj = PS_GC__create_obj(ptr);
    PS_GC__insertItem(set, obj);
    return obj;
}
void PS_GC__garbage_collect(PS_GC__scopeRootVarsStack *stack,
                            PS_GC__hashset *set)
{
    // mark all reachable from stack
    int depth = 0;
    PS_GC__scopeRootVarsStackItem *stack_item = stack->last;
    while (stack_item != NULL)
    {
        for (size_t i = 0; i < stack_item->vars->number_of_vars; ++i)
        {
            PS_GC__mark(stack_item->vars->obj[i]);
        }
        stack_item = stack_item->prev;
        depth++;
    }
    // sweep
    PS_GC__sweep(set);
    // unmark all items
    PS_GC__unmark_all(set);
}
