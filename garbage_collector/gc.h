#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <stdbool.h>
#include <stdint.h>
#include <pthread.h>

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
    size_t id;                  // Unique type ID
    size_t size;               // Total size of object's data (excluding header)
    size_t num_pointers;       // Number of pointer fields (all at start of data)
    const char* type_name;     // Name of type (for debugging)
};

// Memory block header
struct __PS_ObjectHeader {
    size_t size;              // Total size including header
    bool marked;              // Mark bit for GC
    __PS_TypeInfo* type;      // Pointer to type information
    __PS_ObjectHeader* prev_object; //Pointer to the previous allocated object
    __PS_ObjectHeader* next_object; //Pointer to the next allocated object
};

// Root set tracking
#define MAX_ROOTS 10000

typedef struct {
    void** address;           // Address of the root pointer
    __PS_TypeInfo* type;     // Type of the pointed-to object
    const char* name;        // Variable name (for debugging)
} __PS_Root;

typedef struct {
    //TODO should convert to stack-array!
    __PS_Root roots[MAX_ROOTS];
    size_t root_count;
    pthread_mutex_t lock;    // For thread safety
} __PS_RootSet;

// Initialize the type registry
void __PS_InitTypeRegistry(size_t initial_capacity);

// Register a new type
// Called during program initialization for each type in the program
size_t __PS_RegisterType(size_t size, size_t num_pointers, const char* type_name);

// Get type info by ID
__PS_TypeInfo* __PS_GetTypeInfo(size_t type_id);

// Initialize the heap
void __PS_InitializeHeap(size_t size);

// Initialize root tracking
void __PS_InitRootTracking(void);

// Register a root variable
void __PS_RegisterRoot(void** address, __PS_TypeInfo* type, const char* name);

// Unregister a root variable
void __PS_UnregisterRoot(void** address);

// Allocate memory
void* __PS_Alloc(size_t type_id);

// Mark an object and recursively mark all objects it references
static void __PS_MarkObject(void* obj);

// Sweep phase of garbage collection
static void __PS_Sweep(void);

// Main garbage collection function
void __PS_CollectGarbage(void);

// Cleanup everything
void __PS_Cleanup(void);

// Debug function to print heap statistics
void __PS_PrintHeapStats(void);
