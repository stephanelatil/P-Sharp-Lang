#include <stdio.h>
#include <stdlib.h>
#include <stdbool.h>
#include <stdint.h>
#include <pthread.h>
#include "gc.h"

#define REFERENCE_ARRAY_TYPE_ID 0
#define VALUE_ARRAY_TYPE_ID 1

#define GC_After_N_Allocs 20

/// Global type registry
static __PS_TypeRegistry __PS_type_registry = {0}; //initialize to 0

/// The function used to allocate memory on the heap
static void* (*__PS_malloc)(size_t) = malloc;
static void (*__PS_free)(void*) = free;

// Global variables
static __PS_ObjectHeader* __PS_first_obj_header = NULL; //TODO add mutex for this element as well?
static __PS_ScopeStack __PS_scope_stack = {0}; //the stack of roots
static uint32_t __PS_partial_alloc_count = 0;

/// @brief Initializes the ScopeStack to handle root variables on the stack
/// @param max_scope_depth The max scope depth before hitting the GC stack overflow limit (independent from the actual stack size)
void __PS_InitScopeStack(size_t max_scope_depth) {
    __PS_scope_stack.scopes = __PS_malloc(sizeof(__PS_Scope) * max_scope_depth);
    __PS_scope_stack.capacity = max_scope_depth;
    __PS_scope_stack.count = 0;
}


/// @brief Decides whether to run the garbage collector now or not, depending on some heuristic data obtained from the global scope vars
/// @return true (1) if the heuristic decides to run the GC now else false (0)
inline bool __PS_Collect_Garbage_Now_Heuristic(void){
    return __PS_partial_alloc_count >= GC_After_N_Allocs;
}

/// @brief Tells the GC we're entering a new scope that will contain $num_roots variables
/// @param num_roots The number of variables defined in this scope
void __PS_EnterScope(size_t num_roots) {
    if (__PS_scope_stack.count >= __PS_scope_stack.capacity) {
        fprintf(stderr, "Maximum scope nesting depth exceeded\n");
        exit(1);
    }

    // Add new scope to stack
    __PS_Scope* new_scope = &__PS_scope_stack.scopes[__PS_scope_stack.count++];
    new_scope->roots = (__PS_Root*) __PS_malloc(sizeof(__PS_Root) * num_roots);
    new_scope->num_roots = 0;
    new_scope->capacity = num_roots;
}

/// @brief Tells the GC we're leaving the current scope. It will destroy the current scope and associated roots. The GC will be run if it deems relevant.
void __PS_LeaveScope(void) {
    if (__PS_scope_stack.count == 0) {
        fprintf(stderr, "No active scope to leave: program has terminated\n");
        exit(1);
    }

    // Get the current scope
    __PS_Scope* current_scope = &__PS_scope_stack.scopes[__PS_scope_stack.count - 1];

    // Remove the last scope
    pthread_mutex_lock(&__PS_scope_stack.lock);
    __PS_free(current_scope->roots);
    pthread_mutex_unlock(&__PS_scope_stack.lock);

    // Remove scope from stack
    __PS_scope_stack.count--;

    //Collect garbage if necessary
    if (__PS_Collect_Garbage_Now_Heuristic())
        __PS_CollectGarbage();
}

/// @brief Frees all remaining scopes and prepares for program termination
void __PS_CleanupScopeStack(void) {
    __PS_Scope* current_scope = NULL;
    pthread_mutex_lock(&__PS_scope_stack.lock);
    
    while (__PS_scope_stack.count > 0){
        // Get the current scope
        current_scope= &__PS_scope_stack.scopes[__PS_scope_stack.count - 1];
        // Remove the scope
        __PS_free(current_scope->roots);
        __PS_scope_stack.count--;
    }
    pthread_mutex_unlock(&__PS_scope_stack.lock);

    __PS_free(__PS_scope_stack.scopes);
    __PS_scope_stack.scopes = NULL;
    __PS_scope_stack.capacity = 0;
    __PS_scope_stack.count = 0;
}

// // TODO: Ignore variables that host temporary items that can in the future be handled by static memory management.
/// @brief Register a root variable (reference types only!). Done when entering a scope and registering all reference type variables
/// @param address The address of the variable location in memory (ptr to the variable's memory location)
/// @param type_id The TypeInfo id of the variable
/// @param name The variable's name in the current scope
void __PS_RegisterRoot(void** address, size_t type_id, const char* name) {
    __PS_TypeInfo* type = __PS_GetTypeInfo(type_id);
    if (!type)
    {
        fprintf(stderr, "Unable to find type with id: %zu\nThe program will now exit", type_id);
        exit(1);
    }

    pthread_mutex_lock(&__PS_scope_stack.lock);
    
    // Ensure we have an active scope
    if (__PS_scope_stack.count == 0) {
        fprintf(stderr, "Cannot register root outside of a scope\n");
        pthread_mutex_unlock(&__PS_scope_stack.lock);
        exit(1);
    }

    // Get current scope
    __PS_Scope* current_scope = &__PS_scope_stack.scopes[__PS_scope_stack.count - 1];
    
    // Check if we've exceeded the number of roots allowed in this scope
    if (current_scope->num_roots >= current_scope->capacity) {
        fprintf(stderr, "Exceeded maximum number of roots for current scope\n");
        pthread_mutex_unlock(&__PS_scope_stack.lock);
        exit(1);
    }

    // Register the root
    __PS_Root* root = &(current_scope->roots[current_scope->num_roots]);
    root->address = address;
    root->type = type;
    root->name = name;
    current_scope->num_roots++;

    pthread_mutex_unlock(&__PS_scope_stack.lock);
}

// Initialize the type registry
void __PS_InitTypeRegistry(size_t initial_capacity) {
    initial_capacity += 2;
    __PS_type_registry.types = __PS_malloc(sizeof(__PS_TypeInfo*) * initial_capacity);
    // First one is set to be continuous memory for arrays!
    __PS_TypeInfo* contiguous_mem = __PS_type_registry.types;
    contiguous_mem->type_name = "__array_of_ref_types";
    contiguous_mem->id=REFERENCE_ARRAY_TYPE_ID;
    contiguous_mem->num_pointers=0;
    contiguous_mem->size=0;
    __PS_TypeInfo* contiguous_mem = &(__PS_type_registry.types[1]);
    contiguous_mem->type_name = "___array_of_value_types";
    contiguous_mem->id=VALUE_ARRAY_TYPE_ID;
    contiguous_mem->num_pointers=0;
    contiguous_mem->size=0;

    __PS_type_registry.capacity = initial_capacity;
    __PS_type_registry.count = 2;
}

// Register a new type
// Called during program initialization for each type in the program
size_t __PS_RegisterType(size_t size, size_t num_pointers, const char* type_name) {
    // Expand registry if needed
    if (__PS_type_registry.count >= __PS_type_registry.capacity) {
        //this should not happen as the number of types should known at compile/link time
        // add a small smount of memory just in case
        size_t new_capacity = __PS_type_registry.capacity + 100;
        __PS_TypeInfo** new_types = realloc(__PS_type_registry.types, 
                                          sizeof(__PS_TypeInfo*) * new_capacity);
        if (!new_types) {
            fprintf(stderr, "Failed to expand type registry\n");
            exit(1);
        }
        __PS_type_registry.types = new_types;
        __PS_type_registry.capacity = new_capacity;
    }

    // Create new type info
    __PS_TypeInfo* type = __PS_malloc(sizeof(__PS_TypeInfo));
    type->id = __PS_type_registry.count;
    type->size = size;
    type->num_pointers = num_pointers;
    type->type_name = type_name;

    // Add to registry
    __PS_type_registry.types[__PS_type_registry.count] = type;
    return __PS_type_registry.count++;
}

void* __PS_AllocateArray(size_t size, size_t type_id){
    // Calculate total size needed including header
    size_t aligned_size = (sizeof(__PS_ObjectHeader) + size + sizeof(void*)) & ~(sizeof(void*)-1);

    __PS_ObjectHeader* allocated_mem = (__PS_ObjectHeader*) __PS_malloc(aligned_size);
    //Zero out memory
    memset(allocated_mem, 0, aligned_size);
    allocated_mem->size = aligned_size;
    allocated_mem->type = __PS_type_registry.types[type_id];

    // return pointer to data in mem after the header
    void* data = (void*)((char*)allocated_mem + sizeof(__PS_ObjectHeader));

    //add object to linked list onf all allocated objects 
    allocated_mem->next_object = __PS_first_obj_header;
    __PS_first_obj_header = allocated_mem;

    //used as heuristic to count when to GC
    __PS_partial_alloc_count++;
    return data;
}

inline void* __PS_AllocateValueArray(size_t size){
    return __PS_AllocateArray(size, VALUE_ARRAY_TYPE_ID);
}

inline void* __PS_AllocateRefArray(size_t size){
    return __PS_AllocateArray(size, REFERENCE_ARRAY_TYPE_ID);
}

// Get type info by ID
__PS_TypeInfo* __PS_GetTypeInfo(size_t type_id) {
    if (type_id >= __PS_type_registry.count) return NULL;
    return __PS_type_registry.types[type_id];
}

// Should be run at startup to initialize the struct and mutex
void __PS_InitRootTracking(void) {
    __PS_InitScopeStack(1000); //maxdepth of 1000
    pthread_mutex_init(&__PS_scope_stack.lock, NULL);
}

// Allocate memory
// This is the method that should be used when allocating memory for an object
void* __PS_AllocateObject(size_t type_id) {
    __PS_TypeInfo* type = __PS_GetTypeInfo(type_id);
    if (!type) {
        fprintf(stderr, "Invalid type ID: %zu\n", type_id);
        return NULL;
    }

    // Calculate total size needed including header
    size_t aligned_size = (sizeof(__PS_ObjectHeader) + type->size + sizeof(void*)) & ~(sizeof(void*)-1);

    __PS_ObjectHeader* allocated_mem = (__PS_ObjectHeader*) __PS_malloc(aligned_size);
    //Zero out memory
    memset(allocated_mem, 0, aligned_size);
    allocated_mem->size = aligned_size;
    // allocated_mem->marked = 0; // useless bc already zeroed mem
    allocated_mem->type = type;

    // return pointer to data in mem after the header
    void* data = (void*)((char*)allocated_mem + sizeof(__PS_ObjectHeader));

    //add object to linked list onf all allocated objects 
    allocated_mem->next_object = __PS_first_obj_header;
    __PS_first_obj_header = allocated_mem;

    //used as heuristic to count when to GC
    __PS_partial_alloc_count++;
    return data;
}

// Mark an object and recursively mark all objects it references
static void __PS_MarkObject(void* obj) {
    if (!obj) return;

    __PS_ObjectHeader* header = (__PS_ObjectHeader*)((char*)obj - sizeof(__PS_ObjectHeader));
    if (header->marked) return;

    header->marked = true;
    if (!header->type)
        return;
    
    if (header->type->id == REFERENCE_ARRAY_TYPE_ID){
        for (size_t i = 0; i < header->size; i += 8)
            __PS_MarkObject(obj+i);//mark object in array
    }

    // If this object has pointer fields, traverse them
    else if (header->type->num_pointers > 0) {
        // All pointers are at the start of the object data
        void** ptr_fields = (void**)obj;
        for (size_t i = 0; i < header->type->num_pointers; i++) {
            if (ptr_fields[i]) {
                __PS_MarkObject(ptr_fields[i]);
            }
        }
    }
}

// Sweep phase of garbage collection
static void __PS_Sweep(void) {
    __PS_ObjectHeader* current = __PS_first_obj_header;
    __PS_ObjectHeader* first_non_freed_obj = NULL;
    __PS_ObjectHeader* prev_not_freed_obj = NULL;
    __PS_ObjectHeader* next = NULL;
    
    // OPTIMISATION; split into 2 loops to avoid checking many times uselessly if first_non_freed_obj is null
    // First loop where it is null (then break)
    while (current){
        next = current->next_object;
        if (!current->marked){
            // free objects if they're not marked
            __PS_free(current);
        }
        else{
            break;
        }
        current = next;
    }

    //Setup non-freed
    //reset linked list start to the first non-GCed object
    first_non_freed_obj = current;
    prev_not_freed_obj = current;
    current = next;

    // second loop where first_non_freed_obj isn't NULL
    while (current){
        next = current->next_object;
        if (!current->marked){
            // free objects if they're not marked
            __PS_free(current);
        }
        else{
            //remove freed items from linked list: only keep non-freed items
            // this keeps the linked list in the same order
            prev_not_freed_obj->next_object = current;
            prev_not_freed_obj = current;
        }
        current = next;
    }


    // ensure last element doesn't have a free'ed item at the end of the linked list
    if (prev_not_freed_obj)
        prev_not_freed_obj->next_object = NULL;
    // replace list start
    __PS_first_obj_header = first_non_freed_obj;
}

// Main garbage collection function
void __PS_CollectGarbage(void) {
    //reset partial count
    __PS_partial_alloc_count = 0;
    // Reset marks
    __PS_ObjectHeader* current = __PS_first_obj_header;
    while (current) {
        current->marked = false;
        current = current->next_object;
    }

    // Mark from roots
    pthread_mutex_lock(&__PS_scope_stack.lock);
    //TODO find way to traverse stack efficiently
    for (size_t scope_num = 0; scope_num < __PS_scope_stack.count; ++scope_num){
        __PS_Scope* scope = &__PS_scope_stack.scopes[scope_num];
        for (size_t root_num = 0; root_num < scope->num_roots; ++root_num){
            void* obj = *scope->roots[root_num].address;
            __PS_MarkObject(obj);
        }
    }
    
    pthread_mutex_unlock(&__PS_scope_stack.lock);

    // Sweep phase
    __PS_Sweep();
}

// Cleanup everything on program exit
void __PS_Cleanup(void) {
    __PS_CleanupScopeStack();
    // Free all remaining objects
    __PS_ObjectHeader* next = NULL;
    __PS_ObjectHeader* obj = __PS_first_obj_header;
    while (obj){
        // Use next var to avoid use after free (even if right after)
        next = obj->next_object;
        __PS_free(obj);
        obj = next;
    }

    // Free type registry
    for (size_t i = 0; i < __PS_type_registry.count; i++) {
        __PS_free(__PS_type_registry.types[i]);
    }
    __PS_free(__PS_type_registry.types);
    __PS_type_registry.types = NULL;
    __PS_type_registry.capacity = 0;
    __PS_type_registry.count = 0;

    // Cleanup root tracking
    pthread_mutex_destroy(&__PS_scope_stack.lock);
}

// Debug function to print heap statistics
void __PS_PrintHeapStats(void) {
    size_t total_objects = 0;
    size_t total_mem = 0;
    size_t root_count = 0;
    __PS_ObjectHeader* current = __PS_first_obj_header;

    while (current){
        ++total_objects;
        total_mem += current->size;
        current = current->next_object;
    }
    //traverse root set to count vars
    for (size_t i = 0; i < __PS_scope_stack.count; ++i)
        root_count += (&__PS_scope_stack.scopes[i])->num_roots;

    printf("\nHeap Statistics:\n");
    printf("Number of Objects allocated: %zu\n", total_objects);
    printf("Total memory allocated (bytes): %zu\n", total_mem);
    printf("Number of roots (variables): %zu\n", root_count);
    printf("Number of registered types: %zu\n", __PS_type_registry.count);
}