#include <stdio.h>
#include <stdlib.h>
#include <stdbool.h>
#include <stdint.h>
#include <pthread.h>
#include "gc.h"

/// Global type registry
static __PS_TypeRegistry __PS_type_registry = {0}; //initialize to 0

/// The function used to allocate memory on the heap
static void* (*__PS_malloc)(size_t) = malloc;
static void (*__PS_free)(void*) = free;

// Global variables
static __PS_RootSet __PS_root_set = {0}; //initialize to 0
static __PS_ObjectHeader* __PS_first_obj_header = NULL; //TODO add mutex for this element as well?

// Initialize the type registry
void __PS_InitTypeRegistry(size_t initial_capacity) {
    __PS_type_registry.types = malloc(sizeof(__PS_TypeInfo*) * initial_capacity);
    __PS_type_registry.capacity = initial_capacity;
    __PS_type_registry.count = 0;
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
    __PS_TypeInfo* type = malloc(sizeof(__PS_TypeInfo));
    type->id = __PS_type_registry.count;
    type->size = size;
    type->num_pointers = num_pointers;
    type->type_name = type_name;

    // Add to registry
    __PS_type_registry.types[__PS_type_registry.count] = type;
    return __PS_type_registry.count++;
}

// Get type info by ID
__PS_TypeInfo* __PS_GetTypeInfo(size_t type_id) {
    if (type_id >= __PS_type_registry.count) return NULL;
    return __PS_type_registry.types[type_id];
}

// Should be run at startup to initialize the struct and mutex
void __PS_InitRootTracking(void) {
    __PS_root_set.root_count = 0;
    pthread_mutex_init(&__PS_root_set.lock, NULL);
}

// Register a root variable (reference types only!)
// TODO: Ignore variables that host temporary items that can in the future be handled by static memory management.
// Done when entering a scope and registering all reference type variables
void __PS_RegisterRoot(void** address, __PS_TypeInfo* type, const char* name) {
    pthread_mutex_lock(&__PS_root_set.lock);
    if (__PS_root_set.root_count < MAX_ROOTS) {
        __PS_root_set.roots[__PS_root_set.root_count].address = address;
        __PS_root_set.roots[__PS_root_set.root_count].type = type;
        __PS_root_set.roots[__PS_root_set.root_count].name = name;
        __PS_root_set.root_count++;
    }
    else{
        fprintf(stderr, "Maximum number of variables defined supported by the language");
        exit(1);
    }
    pthread_mutex_unlock(&__PS_root_set.lock);
}

// Unregister a root variable
// TODO: Root should be a stack so we just need to unregister N variables
void __PS_UnregisterRoot(void** address) {
    pthread_mutex_lock(&__PS_root_set.lock);
    for (long i = __PS_root_set.root_count-1; i >= 0; --i) {
        if (__PS_root_set.roots[i].address == address) {
            // Move last root to this position to fill the gap
            // Possible issue if we're removing the last variable?
            __PS_root_set.roots[i] = __PS_root_set.roots[__PS_root_set.root_count - 1];
            __PS_root_set.root_count--;
            break;
        }
    }
    pthread_mutex_unlock(&__PS_root_set.lock);
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
    size_t aligned_size = (sizeof(__PS_ObjectHeader) + type->size + 7) & ~7;

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

    return data;
}

// Mark an object and recursively mark all objects it references
static void __PS_MarkObject(void* obj) {
    if (!obj) return;

    __PS_ObjectHeader* header = (__PS_ObjectHeader*)((char*)obj - sizeof(__PS_ObjectHeader));
    if (header->marked) return;

    header->marked = true;

    // If this object has pointer fields, traverse them
    if (header->type && header->type->num_pointers > 0) {
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
    // Reset marks
    __PS_ObjectHeader* current = __PS_first_obj_header;
    while (current) {
        current->marked = false;
        current = current->next_object;
    }

    // Mark from roots
    pthread_mutex_lock(&__PS_root_set.lock);
    for (size_t i = 0; i < __PS_root_set.root_count; i++) {
        void* obj = *__PS_root_set.roots[i].address;
        if (obj) {
            __PS_MarkObject(obj);
        }
    }
    pthread_mutex_unlock(&__PS_root_set.lock);

    // Sweep phase
    __PS_Sweep();
}

// Cleanup everything on program exit
void __PS_Cleanup(void) {
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
        free(__PS_type_registry.types[i]);
    }
    free(__PS_type_registry.types);
    __PS_type_registry.types = NULL;
    __PS_type_registry.capacity = 0;
    __PS_type_registry.count = 0;

    // Cleanup root tracking
    pthread_mutex_destroy(&__PS_root_set.lock);
}

// Debug function to print heap statistics
void __PS_PrintHeapStats(void) {
    size_t total_objects = 0;
    size_t total_mem = 0;
    __PS_ObjectHeader* current = __PS_first_obj_header;

    while (current){
        ++total_objects;
        total_mem += current->size;
        current = current->next_object;
    }

    printf("\nHeap Statistics:\n");
    printf("Number of Objects allocated: %zu\n", total_objects);
    printf("Total memory allocated (bytes): %zu\n", total_mem);
    printf("Number of roots (variables): %zu\n", __PS_root_set.root_count);
    printf("Number of registered types: %zu\n", __PS_type_registry.count);
}