#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdbool.h>
#include <stdint.h>
#include <pthread.h>


#define REFERENCE_ARRAY_TYPE_ID 0
#define VALUE_ARRAY_TYPE_ID 1

// Forward declarations
typedef struct __PS_TypeInfo __PS_TypeInfo;
typedef struct __PS_ObjectHeader __PS_ObjectHeader;

// Type registry for storing all program types
typedef struct {
    __PS_TypeInfo** types;
    size_t capacity;
    size_t count;
} __PS_TypeRegistry;

// Type information structure
// All pointers in objects must be at the start of the object's data
struct __PS_TypeInfo {
    size_t id;                 // Unique type ID
    size_t size;               // Total size of object's data (excluding header) in bytes
    size_t num_pointers;       // Number of pointer fields (all at start of data)
    const char* type_name;     // Name of type (for debugging)
};

// Memory block header
struct __PS_ObjectHeader {
    size_t size;              // Total size including header
    __PS_TypeInfo* type;      // Pointer to type information
    __PS_ObjectHeader* next_object; //Pointer to the next allocated object
    bool marked;              // Mark bit for GC
};

// Root set tracking
// TODO: make dynamically scalable to adjust in case of deep recursive functions that use lots of vars
#define MAX_ROOTS 15000

typedef struct {
    void** address;          // Address of the root pointer
    __PS_TypeInfo* type;     // Type of the pointed-to object
    const char* name;        // Variable name (for debugging)
} __PS_Root;

// Structure to represent a scope's root variables
typedef struct {
    // size_t root_start_index;  // Index in the global root array where this scope's roots begin
    size_t capacity;
    size_t num_roots;         // Number of roots in this scope
    __PS_Root* roots;         // The roots array of the current scope
} __PS_Scope;

// Stack to track active scopes
typedef struct {
    __PS_Scope* scopes;       // Array of scopes
    size_t capacity;          // Maximum number of nested scopes supported
    size_t count;             // Current number of active scopes
    pthread_mutex_t lock;    // For thread safety
} __PS_ScopeStack;

// Initialize the scope stack
void __PS_InitScopeStack(size_t max_scopes);

// Enter a new scope that will contain the specified number of roots
void __PS_EnterScope(size_t num_roots);

// Leave the current scope and unregister all its roots
void __PS_LeaveScope(void);

// Cleanup the scope stack
void __PS_CleanupScopeStack(void);

// Initialize the type registry
void __PS_InitTypeRegistry(size_t initial_capacity);

// Register a new type
// Called during program initialization for each type in the program
size_t __PS_RegisterType(size_t size, size_t num_pointers, const char* type_name);

// Get type info by ID
__PS_TypeInfo* __PS_GetTypeInfo(size_t type_id);

// Should be run at startup to initialize the struct and mutex
void __PS_InitRootTracking(void);

// Register a root variable (reference types only!)
// TODO: Ignore variables that host temporary items that can in the future be handled by static memory management.
// Done when entering a scope and registering all reference type variables
void __PS_RegisterRoot(void** address, size_t type_id, const char* name);

// Allocate memory
// This is the method that should be used when allocating memory for an object
void* __PS_AllocateObject(size_t type_id);

/// @brief Allocate contiguous memory for an array of value types
/// @param size The size in bytes to allocate (includes size (size_t) of the array)
/// @return The pointer to the array_struct
void* __PS_AllocateValueArray(size_t element_size, size_t num_elements);

/// @brief Allocate contiguous memory for an array of reference types
/// @param size The size in bytes to allocate (includes size (size_t) of the array)
/// @return The pointer to the array_struct
void* __PS_AllocateRefArray(size_t num_elements);

// Main garbage collection function
void __PS_CollectGarbage(void);

// Cleanup everything on program exit
void __PS_Cleanup(void);

// Debug function to print heap statistics
void __PS_PrintHeapStats(void);
