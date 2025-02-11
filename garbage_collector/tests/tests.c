#include <assert.h>
#include "../gc.h" // Replace with actual header filename

// Test structures
typedef struct TestSimpleObject {
    int data;
} TestSimpleObject;

typedef struct TestObjectWithPointer {
    struct TestObjectWithPointer* next;
    int data;
} TestObjectWithPointer;

typedef struct TestComplexObject {
    struct TestComplexObject* left;
    struct TestComplexObject* right;
    struct TestSimpleObject* simple;
    int data;
} TestComplexObject;

// Global variables for type IDs
static size_t simple_type_id;
static size_t pointer_type_id;
static size_t complex_type_id;

// Helper function to her the object's GC header from the object pointer
static __PS_ObjectHeader* _get_header(void* obj){
    return (__PS_ObjectHeader*) (obj - sizeof(__PS_ObjectHeader));
}

// Helper functions
static void setup_test_types(void) {
    __PS_InitTypeRegistry(10);
    
    // Register test types
    simple_type_id = __PS_RegisterType(
        sizeof(TestSimpleObject),
        0,  // No pointers
        "TestSimpleObject"
    );
    
    pointer_type_id = __PS_RegisterType(
        sizeof(TestObjectWithPointer),
        1,  // One pointer at start
        "TestObjectWithPointer"
    );
    
    complex_type_id = __PS_RegisterType(
        sizeof(TestComplexObject),
        3,  // Three pointers at start
        "TestComplexObject"
    );
}

// Test cases

static void test_type_registry(void) {
    printf("Testing type registry...\n");
    
    // Test type registration
    // Make sure they are allocated properly
    assert(simple_type_id == 0);
    assert(pointer_type_id == 1);
    assert(complex_type_id == 2);
    
    // Test type info retrieval
    __PS_TypeInfo* simple_info = __PS_GetTypeInfo(simple_type_id);
    assert(simple_info != NULL);
    assert(simple_info->size == sizeof(TestSimpleObject));
    assert(simple_info->num_pointers == 0);
    assert(strcmp(simple_info->type_name, "TestSimpleObject") == 0);
    
    __PS_TypeInfo* complex_info = __PS_GetTypeInfo(complex_type_id);
    assert(complex_info != NULL);
    assert(complex_info->size == sizeof(TestComplexObject));
    assert(complex_info->num_pointers == 3);
    
    printf("Type registry tests passed\n");
}

static void test_basic_allocation(void) {
    printf("Testing basic allocation...\n");
    
    // Allocate simple object
    TestSimpleObject* simple = __PS_AllocateObject(simple_type_id);
    assert(simple != NULL);
    simple->data = 42;
    void** var_mem_location = (void**)&simple;
    // Register as root and verify
    __PS_RegisterRoot(var_mem_location, __PS_GetTypeInfo(simple_type_id), "simple");
    
    // Trigger GC
    __PS_CollectGarbage();
    
    // Verify object survived
    __PS_ObjectHeader* header = _get_header(simple);
    assert (header->marked); //ensure it was marked and thus not GC-ed
    assert(simple != NULL);
    assert(simple->data == 42);
    
    // Cleanup
    __PS_UnregisterRoot(var_mem_location);
    __PS_CollectGarbage(); //and collect garbage

    assert (!header->marked); //ensure it was not! marked and thus GC-ed
    
    printf("Basic allocation tests passed\n");
}

static void test_linked_list(void) {
    printf("Testing linked list allocation...\n");
    
    // Create a linked list
    TestObjectWithPointer* head = NULL;
    TestObjectWithPointer* current = NULL;
    
    // Create list of 5 nodes
    for (int i = 0; i < 5; i++) {
        TestObjectWithPointer* node = __PS_AllocateObject(pointer_type_id);
        assert(node != NULL);
        node->data = i;
        node->next = NULL;
        
        if (head == NULL) {
            head = node;
            current = node;
        } else {
            current->next = node;
            current = node;
        }
    }
    
    void** head_var_mem_location = (void**)&head;

    // Register only the head as root
    __PS_RegisterRoot(head_var_mem_location, __PS_GetTypeInfo(pointer_type_id), "head");
    
    // Trigger GC
    __PS_CollectGarbage();
    
    // Verify all nodes survived
    current = head;
    for (int i = 0; i < 5; i++) {
        __PS_ObjectHeader* header = _get_header(current);
        assert (header->marked); //ensure it was marked and thus not GC-ed
        assert(current != NULL);
        assert(current->data == i);
        current = current->next;
    }
    
    // Cleanup
    __PS_UnregisterRoot(head_var_mem_location);
    // Trigger GC
    __PS_CollectGarbage();
    
    // Verify no nodes survived
    current = head;
    for (int i = 0; i < 5; i++) {
        __PS_ObjectHeader* header = _get_header(current);
        assert (!header->marked); //ensure it was not marked and thus GC-ed
        current = current->next;
    }
    
    printf("Linked list tests passed\n");
}

static void test_cyclic_references(void) {
    printf("Testing cyclic references...\n");
    
    // Create a cycle of three objects
    TestObjectWithPointer* obj1 = __PS_AllocateObject(pointer_type_id);
    TestObjectWithPointer* obj2 = __PS_AllocateObject(pointer_type_id);
    TestObjectWithPointer* obj3 = __PS_AllocateObject(pointer_type_id);
    
    obj1->next = obj2;
    obj2->next = obj3;
    obj3->next = obj1;
    
    obj1->data = 1;
    obj2->data = 2;
    obj3->data = 3;
    
    void** obj1_var_mem_location = (void**) &obj1;

    // Register only obj1 as root
    __PS_RegisterRoot(obj1_var_mem_location, __PS_GetTypeInfo(pointer_type_id), "obj1");
    
    // Trigger GC
    __PS_CollectGarbage();
    
    // Verify cycle survived
    assert(obj1->next->data == 2);
    assert(obj1->next->next->data == 3);
    assert(obj1->next->next->next == obj1);

    //ensure it was marked and thus not GC-ed
    assert (_get_header(obj1)->marked);
    assert (_get_header(obj2)->marked);
    assert (_get_header(obj3)->marked);
    
    // Cleanup
    __PS_UnregisterRoot(obj1_var_mem_location);
    __PS_CollectGarbage();

    //ensure it was not marked and thus GC-ed
    assert (!_get_header(obj1)->marked);
    assert (!_get_header(obj2)->marked);
    assert (!_get_header(obj3)->marked);
    
    printf("Cyclic references tests passed\n");
}

static void test_complex_object_tree(void) {
    printf("Testing complex object tree...\n");
    
    // Create a binary tree-like structure
    TestComplexObject* root = __PS_AllocateObject(complex_type_id);
    root->data = 1;
    root->simple = __PS_AllocateObject(simple_type_id);
    root->simple->data = 100;
    
    root->left = __PS_AllocateObject(complex_type_id);
    root->left->data = 2;
    root->left->simple = __PS_AllocateObject(simple_type_id);
    root->left->simple->data = 200;
    
    root->right = __PS_AllocateObject(complex_type_id);
    root->right->data = 3;
    root->right->simple = __PS_AllocateObject(simple_type_id);
    root->right->simple->data = 300;
    
    void** root_var_mem_location = (void**) &root;

    // Register only the root
    __PS_RegisterRoot(root_var_mem_location, __PS_GetTypeInfo(complex_type_id), "root");
    
    // Trigger GC
    __PS_CollectGarbage();
    
    // Verify entire tree survived
    assert(root->data == 1);
    assert(root->simple->data == 100);
    assert(root->left->data == 2);
    assert(root->left->simple->data == 200);
    assert(root->right->data == 3);
    assert(root->right->simple->data == 300);

    //ensure it was marked and thus not GC-ed
    assert (_get_header(root)->marked);
    assert (_get_header(root->simple)->marked);
    assert (_get_header(root->right)->marked);
    assert (_get_header(root->right->simple)->marked);
    assert (_get_header(root->left)->marked);
    assert (_get_header(root->left->simple)->marked);
    
    // Cleanup
    __PS_UnregisterRoot(root_var_mem_location);
    __PS_CollectGarbage();
    
    printf("Complex object tree tests passed\n");
}

static void test_objects_pointed_to_by_multiple_roots(void){
    printf("Testing objects pointed to by multiple roots...\n");

    // Create objects
    TestComplexObject* root = __PS_AllocateObject(complex_type_id);
    root->left = __PS_AllocateObject(complex_type_id);
    root->right = __PS_AllocateObject(complex_type_id);
    
    void** root_var_mem_location = (void**)&root;
    void** left_var_mem_location = (void**)&root->left;

    // Register roots
    __PS_RegisterRoot(left_var_mem_location, __PS_GetTypeInfo(complex_type_id), "left");
    __PS_RegisterRoot(root_var_mem_location, __PS_GetTypeInfo(complex_type_id), "root");

    // Check no GC when all items reachable
    __PS_CollectGarbage();
    assert (_get_header(root)->marked);
    assert (_get_header(root->left)->marked);
    assert (_get_header(root->right)->marked);

    //Unregister root (make root var "out of scope")
    __PS_UnregisterRoot(root_var_mem_location);

    // Check GC is correct: only "left" should be reachable
    __PS_CollectGarbage();
    assert (_get_header(root->left)->marked);

    //there should not be marked (and thus GC-ed)
    assert (! _get_header(root)->marked);
    assert (! _get_header(root->right)->marked);

    //cleanup
    __PS_UnregisterRoot(left_var_mem_location);
    __PS_CollectGarbage();
}

static void test_unreachable_objects(void) {
    printf("Testing unreachable object collection...\n");
    
    // Create objects
    TestComplexObject* root = __PS_AllocateObject(complex_type_id);
    root->left = __PS_AllocateObject(complex_type_id);
    root->right = __PS_AllocateObject(complex_type_id);
    

    void** root_var_mem_location = (void**)&root;

    // Register root
    __PS_RegisterRoot(root_var_mem_location, __PS_GetTypeInfo(complex_type_id), "root");
    
    // Create unreachable objects
    TestComplexObject* unreachable = __PS_AllocateObject(complex_type_id);
    unreachable->left = __PS_AllocateObject(complex_type_id);
    unreachable->right = __PS_AllocateObject(complex_type_id);
    
    // Get heap stats before GC
    __PS_PrintHeapStats();
    
    // Trigger GC
    __PS_CollectGarbage();
    assert (! _get_header(unreachable)->marked);
    assert (! _get_header(unreachable->right)->marked);
    assert (! _get_header(unreachable->left)->marked);
    
    // Get heap stats after GC
    __PS_PrintHeapStats();
    
    // Cleanup
    __PS_UnregisterRoot(root_var_mem_location);
    __PS_CollectGarbage();
    
    printf("Unreachable object collection tests passed\n");
}

// Main test runner
int main(void) {
    // Initialize GC
    __PS_InitRootTracking();
    setup_test_types();
    
    // Run tests
    test_type_registry();
    test_basic_allocation();
    test_linked_list();
    test_cyclic_references();
    test_complex_object_tree();
    test_unreachable_objects();
    test_objects_pointed_to_by_multiple_roots();
    
    // Cleanup
    __PS_Cleanup();
    
    printf("All tests passed successfully!\n");
    return 0;
}