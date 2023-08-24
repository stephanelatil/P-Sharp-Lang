#include <stdlib.h>
#include "structures.h"

PS_GC__scopeRootVarsStack *PS_GC__initialize_stack()
{
    PS_GC__scopeRootVarsStack *stack = malloc(sizeof(PS_GC__scopeRootVarsStack));
    if (stack == NULL)
        return NULL;
    stack->last = NULL;
    return stack;
}

PS_GC__scopeRootVarsStackItem *PS_GC__initialize_stack_item(PS_GC__scopeRootVarsStackItem *prev, PS_GC__rootVarList *vars)
{
    PS_GC__scopeRootVarsStackItem *item = malloc(sizeof(PS_GC__scopeRootVarsStackItem));
    if (item == NULL)
        return NULL;
    item->vars = vars;
    item->prev = prev;
    return item;
}

PS_GC__hashset *PS_GC__initialize_hashset(size_t size)
{
    if (size <= 0)
        return NULL;
    size_t num_buckets = 1;
    --size;
    while (size > 0)
    {
        size = size >> 1;
        num_buckets = num_buckets << 1;
    } // calculate ceil(log2(size))
    size = num_buckets;

    PS_GC__hashset *set = malloc(sizeof(PS_GC__hashset));
    if (set == NULL)
        return NULL;
    set->size = size;
    set->mask = size - 1;
    set->buckets = calloc(size, sizeof(PS_GC__hashset_bucket *));
    if (set->buckets == NULL)
    {
        free(set);
        return NULL;
    }
    return set;
}

PS_GC__hashset_bucket *PS_GC__create_hashset_bucket(PS_GC__object *obj)
{
    PS_GC__hashset_bucket *bucket = malloc(sizeof(PS_GC__hashset_bucket));
    if (bucket == NULL)
        return NULL;
    bucket->next = NULL;
    bucket->object = obj;
    return bucket;
}

PS_GC__object *PS_GC__create_obj(void *ptr)
{
    PS_GC__object *obj = malloc(sizeof(PS_GC__object));
    if (obj == NULL)
        return NULL;
    obj->ptr = ptr;
    obj->marked = 0;
    obj->children = NULL;
    obj->number_of_children = 0;
    return obj;
}

void PS_GC__add_children(PS_GC__object *parent,
                         PS_GC__object **children,
                         size_t number_of_children)
{
    parent->children = children;
    parent->number_of_children = number_of_children;
}

PS_GC__rootVarList *PS_GC__create_rootVarList(size_t size)
{
    PS_GC__rootVarList *list = malloc(sizeof(PS_GC__rootVarList));
    if (list == NULL)
        return NULL;
    list->number_of_vars = size;
    list->obj = calloc(size, sizeof(PS_GC__object *));
    if (list->obj == NULL)
    {
        free(list);
        return NULL;
    }
    return list;
}

void PS_GC__delete_hashset_bucket(PS_GC__hashset_bucket *bucket)
{
    free(bucket);
}

void PS_GC__delete_stack(PS_GC__scopeRootVarsStack *stack)
{
    while (!PS_GC__stack_is_empty(stack))
        PS_GC__delete_rootVarList(PS_GC__stack_pop(stack));
    free(stack);
}

void PS_GC__delete_stack_item(PS_GC__scopeRootVarsStackItem *item)
{
    free(item);
}

void PS_GC__delete_object(PS_GC__object *obj) { free(obj); }

void PS_GC__delete_hashSet(PS_GC__hashset *set)
{
    for (size_t i = 0; i < set->size; ++i)
        free(set->buckets[i]);
    free(set->buckets);
    free(set);
}

void PS_GC__delete_rootVarList(PS_GC__rootVarList *list)
{
    free(list->obj);
    free(list);
}

int PS_GC__stack_push(PS_GC__scopeRootVarsStack *stack, PS_GC__rootVarList *vars)
{
    if (vars == NULL)
        return 0;
    PS_GC__scopeRootVarsStackItem *item = malloc(sizeof(PS_GC__scopeRootVarsStackItem));
    if (item == NULL)
        return 0;
    item->vars = vars;
    item->prev = stack->last;
    stack->last = item;
    return 1;
}

PS_GC__rootVarList *PS_GC__stack_pop(PS_GC__scopeRootVarsStack *stack)
{
    if (stack->last == NULL)
        return NULL;
    PS_GC__scopeRootVarsStackItem *item = stack->last;
    stack->last = item->prev;
    PS_GC__rootVarList *vars = item->vars;
    PS_GC__delete_stack_item(item);
    return vars;
}

int PS_GC__stack_is_empty(PS_GC__scopeRootVarsStack *stack)
{
    return stack->last == NULL;
}

uintptr_t PS_GC__get_hash(void *obj)
{
    return ((uintptr_t)obj) >> 5;
}

int PS_GC__insertItem(PS_GC__hashset *set, PS_GC__object *object)
{
    void *ptr = object->ptr;
    // get hash and ensure it is within bounds [0,size-1];
    int idx = (int)(PS_GC__get_hash(ptr) & set->mask);

    // search if element is already in the set
    PS_GC__hashset_bucket *bucket = set->buckets[idx];
    while (bucket)
    {
        if (bucket->object->ptr == ptr)
            return 0; // item found return 0
        bucket = bucket->next;
    }
    // item not found add to set
    PS_GC__hashset_bucket *new_bucket = PS_GC__create_hashset_bucket(object);
    if (new_bucket == NULL)
        return -1; // unable to create bucket
    new_bucket->next = set->buckets[idx];
    set->buckets[idx] = new_bucket;
    return 1;
}

PS_GC__object *PS_GC__getItem(PS_GC__hashset *set, void *data)
{
    if (data == NULL)
        return NULL;
    int idx = (int)(PS_GC__get_hash(data) & set->mask);
    PS_GC__hashset_bucket *bucket = set->buckets[idx];
    while (bucket) // bucket not null
    {
        if (bucket->object->ptr == data)
            return bucket->object; // return the object
        bucket = bucket->next;
    }
    return NULL; // not found
}

int PS_GC__removeItem(PS_GC__hashset *set, PS_GC__object *object)
{
    int idx = (int)(PS_GC__get_hash(object->ptr) & set->mask);
    PS_GC__hashset_bucket *bucket = set->buckets[idx];
    if (!bucket)
        return 0; // empty bucket
    if (bucket->object->ptr == object->ptr)
    {
        set->buckets[idx] = bucket->next;
        PS_GC__delete_hashset_bucket(bucket);
        return 1; // found, removed and freed
    }
    PS_GC__hashset_bucket *prev = bucket;
    bucket = bucket->next;
    while (bucket) // while is not null (end of list)
    {
        if (bucket->object->ptr == object->ptr)
        {
            prev->next = bucket->next;
            PS_GC__delete_hashset_bucket(bucket);
            return 1; // found, removed and freed
        }
        prev = bucket;
        bucket = bucket->next;
    }
    return 0; // not found
}
