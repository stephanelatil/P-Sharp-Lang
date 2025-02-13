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
    __PS_EnterScope(1);
    
    // Allocate simple object
    TestSimpleObject* simple = __PS_AllocateObject(simple_type_id);
    assert(simple != NULL);
    simple->data = 42;
    void** var_mem_location = (void**)&simple;
    // Register as root and verify
    __PS_RegisterRoot(var_mem_location, simple_type_id, "simple");
    
    // Trigger GC
    __PS_CollectGarbage();
    
    // Verify object survived
    __PS_ObjectHeader* header = _get_header(simple);
    assert (header->marked); //ensure it was marked and thus not GC-ed
    assert(simple != NULL);
    assert(simple->data == 42);
    
    // Cleanup
    __PS_LeaveScope();
    __PS_CollectGarbage(); //and collect garbage

    assert (!header->marked); //ensure it was not! marked and thus GC-ed
    
    printf("Basic allocation tests passed\n");
}

static void test_linked_list(void) {
    printf("Testing linked list allocation...\n");
    __PS_EnterScope(1);
    
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
    __PS_RegisterRoot(head_var_mem_location, pointer_type_id, "head");
    
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
    __PS_LeaveScope();
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
    __PS_EnterScope(1);
    
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
    __PS_RegisterRoot(obj1_var_mem_location, pointer_type_id, "obj1");
    
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
    __PS_LeaveScope();
    __PS_CollectGarbage();

    //ensure it was not marked and thus GC-ed
    assert (!_get_header(obj1)->marked);
    assert (!_get_header(obj2)->marked);
    assert (!_get_header(obj3)->marked);
    
    printf("Cyclic references tests passed\n");
}

static void test_complex_object_tree(void) {
    printf("Testing complex object tree...\n");
    __PS_EnterScope(1);
    
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
    __PS_RegisterRoot(root_var_mem_location, complex_type_id, "root");
    
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
    __PS_LeaveScope();
    __PS_CollectGarbage();
    
    printf("Complex object tree tests passed\n");
}

static void test_unreachable_objects(void) {
    printf("Testing unreachable object collection...\n");
    __PS_EnterScope(1);
    
    // Create objects
    TestComplexObject* root = __PS_AllocateObject(complex_type_id);
    root->left = __PS_AllocateObject(complex_type_id);
    root->right = __PS_AllocateObject(complex_type_id);
    

    void** root_var_mem_location = (void**)&root;

    // Register root
    __PS_RegisterRoot(root_var_mem_location, complex_type_id, "root");
    
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
    __PS_LeaveScope();
    __PS_CollectGarbage();
    
    printf("Unreachable object collection tests passed\n");
}

static void test_objects_pointed_to_by_multiple_roots(void){
    printf("Testing objects pointed to by multiple roots...\n");
    __PS_EnterScope(1);

    // Create objects
    TestComplexObject* root = __PS_AllocateObject(complex_type_id);
    root->left = __PS_AllocateObject(complex_type_id);
    root->right = __PS_AllocateObject(complex_type_id);
    
    void** root_var_mem_location = (void**)&root;
    void** left_var_mem_location = (void**)&root->left;

    // Register roots
    __PS_RegisterRoot(left_var_mem_location, complex_type_id, "left");
    
    __PS_EnterScope(1);
    __PS_RegisterRoot(root_var_mem_location, complex_type_id, "root");

    // Check no GC when all items reachable
    __PS_CollectGarbage();
    assert (_get_header(root)->marked);
    assert (_get_header(root->left)->marked);
    assert (_get_header(root->right)->marked);

    //Unregister root (make root var "out of scope")
    __PS_LeaveScope();

    // Check GC is correct: only "left" should be reachable
    __PS_CollectGarbage();
    assert (_get_header(root->left)->marked);

    //there should not be marked (and thus GC-ed)
    assert (! _get_header(root)->marked);
    assert (! _get_header(root->right)->marked);

    //cleanup
    __PS_LeaveScope();
    __PS_CollectGarbage();
}

// Test scope management
static void test_basic_scope_management(void) {
    printf("Testing basic scope management...\n");
    
    // Test basic scope enter/leave
    __PS_EnterScope(1);
    TestSimpleObject* obj = __PS_AllocateObject(simple_type_id);
    obj->data = 42;
    void** obj_loc = (void**)&obj;
    __PS_RegisterRoot(obj_loc, simple_type_id, "obj");
    
    // Verify object is in scope
    __PS_CollectGarbage();
    assert(_get_header(obj)->marked);
    
    __PS_LeaveScope();
    __PS_CollectGarbage();
    // Object should be collected after scope exit
    assert(!_get_header(obj)->marked);
    
    printf("Basic scope management tests passed\n");
}

static void test_nested_scopes(void) {
    printf("Testing nested scopes...\n");
    
    // Create outer scope with object
    __PS_EnterScope(1);
    TestSimpleObject* outer_obj = __PS_AllocateObject(simple_type_id);
    outer_obj->data = 1;
    void** outer_loc = (void**)&outer_obj;
    __PS_RegisterRoot(outer_loc, simple_type_id, "outer_obj");
    
    // Create inner scope with different object
    __PS_EnterScope(1);
    TestSimpleObject* inner_obj = __PS_AllocateObject(simple_type_id);
    inner_obj->data = 2;
    void** inner_loc = (void**)&inner_obj;
    __PS_RegisterRoot(inner_loc, simple_type_id, "inner_obj");
    
    // Verify both objects survive GC
    __PS_CollectGarbage();
    assert(_get_header(outer_obj)->marked);
    assert(_get_header(inner_obj)->marked);
    
    // Leave inner scope
    __PS_LeaveScope();
    __PS_CollectGarbage();
    
    // Inner object should be collected, outer survives
    assert(!_get_header(inner_obj)->marked);
    assert(_get_header(outer_obj)->marked);
    
    // Leave outer scope
    __PS_LeaveScope();
    __PS_CollectGarbage();
    
    // Both objects should be collected
    assert(!_get_header(outer_obj)->marked);
    
    printf("Nested scopes tests passed\n");
}

static void test_scope_capacity(void) {
    printf("Testing scope capacity handling...\n");
    
    // Test scope with exact capacity
    __PS_EnterScope(2);
    TestSimpleObject* obj1 = __PS_AllocateObject(simple_type_id);
    TestSimpleObject* obj2 = __PS_AllocateObject(simple_type_id);
    void** obj1_loc = (void**)&obj1;
    void** obj2_loc = (void**)&obj2;
    
    // These should succeed
    __PS_RegisterRoot(obj1_loc, simple_type_id, "obj1");
    __PS_RegisterRoot(obj2_loc, simple_type_id, "obj2");
    
    // Verify objects are tracked
    __PS_CollectGarbage();
    assert(_get_header(obj1)->marked);
    assert(_get_header(obj2)->marked);
    
    __PS_LeaveScope();
    // Cleanup
    __PS_CollectGarbage();
    
    printf("Scope capacity tests passed\n");
}

static void test_scope_interactions(void) {
    printf("Testing scope interactions...\n");
    
    // Create outer scope with shared object
    __PS_EnterScope(1);
    TestComplexObject* shared = __PS_AllocateObject(complex_type_id);
    shared->data = 42;
    void** shared_loc = (void**)&shared;
    __PS_RegisterRoot(shared_loc, complex_type_id, "shared");
    
    // Create inner scope that references shared object
    __PS_EnterScope(1);
    TestComplexObject* inner = __PS_AllocateObject(complex_type_id);
    inner->left = shared;  // Reference to outer scope object
    void** inner_loc = (void**)&inner;
    __PS_RegisterRoot(inner_loc, complex_type_id, "inner");
    
    // Verify all objects survive
    __PS_CollectGarbage();
    assert(_get_header(shared)->marked);
    assert(_get_header(inner)->marked);
    
    // Leave inner scope
    __PS_LeaveScope();
    __PS_CollectGarbage();
    
    // Inner object should be collected, shared survives
    assert(!_get_header(inner)->marked);
    assert(_get_header(shared)->marked);
    
    // Leave outer scope
    __PS_LeaveScope();
    
    printf("Scope interactions tests passed\n");
}

static void test_scope_edge_cases(void) {
    printf("Testing scope edge cases...\n");
    
    // Test entering scope with zero capacity
    __PS_EnterScope(0);
    __PS_LeaveScope();
    
    // Test multiple nested scopes
    for (int i = 0; i < 10; i++) {
        __PS_EnterScope(1);
        TestSimpleObject* obj = __PS_AllocateObject(simple_type_id);
        void** obj_loc = (void**)&obj;
        __PS_RegisterRoot(obj_loc, simple_type_id, "obj");
    }
    
    // Leave all scopes
    for (int i = 0; i < 10; i++) {
        __PS_LeaveScope();
    }
    
    // Test scope with multiple references to same object
    __PS_EnterScope(2);
    TestComplexObject* obj = __PS_AllocateObject(complex_type_id);
    void** obj_loc1 = (void**)&obj;
    void** obj_loc2 = (void**)&obj;
    
    __PS_RegisterRoot(obj_loc1, complex_type_id, "obj1");
    __PS_RegisterRoot(obj_loc2, complex_type_id, "obj2");
    
    __PS_CollectGarbage();
    assert(_get_header(obj)->marked);
    
    __PS_LeaveScope();
    
    printf("Scope edge cases tests passed\n");
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

    test_basic_scope_management();
    test_nested_scopes();
    test_scope_capacity();
    test_scope_interactions();
    test_scope_edge_cases();
    
    // Cleanup
    __PS_Cleanup();
    
    printf("All tests passed successfully!\n");
    return 0;
}