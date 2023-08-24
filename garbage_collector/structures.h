#ifndef PS_GC__STRUCTURES_H
#define PS_GC__STRUCTURES_H

#include <stdint.h>
// TODO: convert stack to Vector with pointer to the start & end of the current vector?

/**
 * @brief Struct representing an object for the GC on the heap
 */
typedef struct PS_GC__object
{
    /**
     * @brief A pointer to the variable's object on the heap
     */
    void *ptr;

    /**
     * @brief 0 is unmarked, 1 or greater if marked (used large number for alignment to 8 bytes and future ref counting?)
     */
    long long int marked;

    /**
     * @brief An array with pointers to the object's children
     */
    struct PS_GC__object **children;

    size_t number_of_children;
} PS_GC__object;

/**
 * @brief The list of objects accessible from variables defined in this scope
 */
typedef struct PS_GC__rootVarList
{
    /**
     * @brief The length of the $obj array
     */
    size_t number_of_vars;

    /**
     * @brief The array containing the accessible variables
     */
    struct PS_GC__object **obj;
} PS_GC__rootVarList;

/**
 * @brief The stack object of accessible variables
 */
typedef struct PS_GC__scopeRootVarsStack
{
    /**
     * @brief The last item on the stack (equal to first if of size 0 or 1)
     */
    struct PS_GC__scopeRootVarsStackItem *last;
} PS_GC__scopeRootVarsStack;

/**
 * @brief An item on the stack of accessible variables (Structure of double linked list)
 */
typedef struct PS_GC__scopeRootVarsStackItem
{
    /**
     * @brief The list struct with the objects accessible with the variables defined in this scope
     */
    PS_GC__rootVarList *vars;

    /**
     * @brief The item lower on the stack (pushed before). If the item is NULL, then the current element is the first on the stack
     */
    struct PS_GC__scopeRootVarsStackItem *prev;
} PS_GC__scopeRootVarsStackItem;

/**
 * @brief A bucket (structured as a linked list) containing the objects
 */
typedef struct PS_GC__hashset_bucket
{
    /**
     * @brief The object pointed to by the variable
     */
    PS_GC__object *object;

    /**
     * @brief The next item in the bucket (if NULL then there is no other item)
     */
    struct PS_GC__hashset_bucket *next;
} PS_GC__hashset_bucket;

/**
 * @brief A hashset made to contain GC_objects
 */
typedef struct PS_GC__hashset
{
    /**
     * @brief The gc buckets
     */
    PS_GC__hashset_bucket **buckets;

    /**
     * @brief The total number of buckets in the hashset. It is rounded to the next power of 2 for performance reasons
     */
    size_t size;

    /**
     * @brief The mask to apply to the hash to get the bucket index. Equal to size-1;
     */
    uintptr_t mask;
} PS_GC__hashset;

/**
 * @brief Creates a new empty stack
 * @returns The newly created stack
 */
PS_GC__scopeRootVarsStack *PS_GC__initialize_stack(void);

/**
 * @brief Creates a new empty stack item
 * @param prev The previous item on the stack
 * @param vars The list of variable objects
 * @returns The newly created item on the stack
 */
PS_GC__scopeRootVarsStackItem *PS_GC__initialize_stack_item(PS_GC__scopeRootVarsStackItem *prev, PS_GC__rootVarList *vars);

/**
 * @brief Creates a new empty hashset with the given number of buckets
 * @param size The number of buckets in the stack (Will be rounded to the power of 2 above or equal)
 * @returns The newly created hashset or NULL if size < 1 or if there is a malloc issue
 */
PS_GC__hashset *PS_GC__initialize_hashset(size_t size);

/**
 * @brief Creates a new bucket containing the given object
 *
 * @param obj The object the bucket should contain
 * @return The newly created bucket
 */
PS_GC__hashset_bucket *PS_GC__create_hashset_bucket(PS_GC__object *obj);

/**
 * @brief Destructor for a bucket. Note that the underlying bucket->object is not freed
 *
 * @param bucket The bucket to be freed
 */
void PS_GC__delete_hashset_bucket(PS_GC__hashset_bucket *bucket);

/**
 * @brief Adds the children to the object. Ensure that the child array is fully populated (or will be soon) without blank spots
 *
 * @param parent The parent object
 * @param children An array of child objects
 * @param length The length of the array
 */
void PS_GC__add_children(PS_GC__object *parent, PS_GC__object **children, size_t length);

/**
 * @brief Creates a new object with the given pointer to the object. It is unmarked by default and with no children
 * @param ptr The pointer to the object on the heap
 * @returns The newly created object
 */
PS_GC__object *PS_GC__create_obj(void *ptr);

/**
 * @brief Creates a new rootVarList with the given size
 * @param size The size of the list
 * @returns The newly created rootVarList
 */
PS_GC__rootVarList *PS_GC__create_rootVarList(size_t size);

/**
 * @brief Destructor for the stack. It also frees all remaining items on the stack
 * @param stack A pointer to the stack to be freed
 */
void PS_GC__delete_stack(PS_GC__scopeRootVarsStack *stack);

/**
 * @brief Destructor for a stack item. It does NOT free the linked item (below) nor the $vars object
 * @param item A pointer to the stack to be freed
 */
void PS_GC__delete_stack_item(PS_GC__scopeRootVarsStackItem *item);

/**
 * @brief Destructor for a GC_object
 * @param obj A pointer to the object to be freed
 */
void PS_GC__delete_object(PS_GC__object *obj);

/**
 * @brief Destructor for the hashset. It also deletes all the buckets
 * @param set A pointer to the hashset to be freed
 */
void PS_GC__delete_hashSet(PS_GC__hashset *set);

/**
 * @brief Destructor for a rootVarList
 * @param list A pointer to the list to be freed
 */
void PS_GC__delete_rootVarList(PS_GC__rootVarList *list);

/**
 * @brief Pushes a new item on the stack and returns a pointer to the top element
 * @param stack The previous top element of the stack
 * @param vars The item to push on the stack
 * @returns 1 if pushed successfully or 0 if an error during malloc or if $vars is NULL
 */
int PS_GC__stack_push(PS_GC__scopeRootVarsStack *stack, PS_GC__rootVarList *vars);

/**
 * @brief Pops an item off the stack and returns the new top item of the stack
 * @param stack The stack object to pop from
 * @returns The popped item. It's the user's responsability to free this object later
 */
PS_GC__rootVarList *PS_GC__stack_pop(PS_GC__scopeRootVarsStack *stack);

/**
 * @brief Checks whether the stack is empty
 *
 * @param stack The stack to check
 * @return 1 if the stack is empty, 0 if it contains items
 */
int PS_GC__stack_is_empty(PS_GC__scopeRootVarsStack *stack);

/**
 * @brief Calculates the object's hash. To be used for the hashset
 *
 * @param obj The object to hash
 * @return An integer representation of the hash
 */
inline uintptr_t PS_GC__get_hash(void *obj);

/**
 * @brief Inserts an item into the hashset
 * @param set The hashset to insert into
 * @param object The object to insert
 * @returns 1 if the item was added, 0 if the item is already in the set or -1 if there was an issue adding the item in the set (malloc error)
 */
int PS_GC__insertItem(PS_GC__hashset *set, PS_GC__object *object);

/**
 * @brief Retrieves an item from the hashset
 * @param set The hashset to retrieve from
 * @param data The data to retrieve
 * @returns The retrieved object, or NULL if not found
 */
PS_GC__object *PS_GC__getItem(PS_GC__hashset *set, void *data);

/**
 * @brief Removes an item from the hashset and frees it, if it is found
 * @param set The hashset to remove from
 * @param object The object to remove
 * @returns 1 if the items was removed. 0 if it was not found.
 */
int PS_GC__removeItem(PS_GC__hashset *set, PS_GC__object *object);

#endif /* PS_GC__STRUCTURES_H */
