REFERENCE_ARRAY_TYPE_ID = 0
VALUE_ARRAY_TYPE_ID = 1

MAIN_FUNCTION_USER_CODE_BLOCK = '__user_main_func_code_block'
ENTRYPOINT_FUNCTION_NAME = 'main'

FUNC_GC_INITIALIZE_ROOT_VARIABLE_TRACKING = "__PS_InitRootTracking"
FUNC_GC_INITIALIZE_TYPE_REGISTRY = "__PS_InitTypeRegistry"
FUNC_GC_REGISTER_TYPE = "__PS_RegisterType"
FUNC_GC_ENTER_SCOPE = "__PS_EnterScope"
FUNC_GC_LEAVE_SCOPE = "__PS_LeaveScope"
FUNC_GC_REGISTER_ROOT_VARIABLE_IN_CURRENT_SCOPE = "__PS_RegisterRoot"
FUNC_GC_RUN_GARBAGE_COLLECTOR = "__PS_CollectGarbage"
FUNC_GC_CLEANUP_BEFORE_PROGRAM_SHUTDOWN = "__PS_Cleanup"
FUNC_GC_ALLOCATE_OBJECT = "__PS_AllocateObject"
FUNC_GC_ALLOCATE_VALUE_ARRAY = "__PS_AllocateValueArray"
FUNC_GC_ALLOCATE_REFERENCE_OBJ_ARRAY = "__PS_AllocateRefArray"
FUNC_GC_PRINT_HEAP_STATS = "__PS_PrintHeapStats"
FUNC_DEFAULT_TOSTRING = "__PS_DefaultToString"

# Special setup hooks called before or after the garbage collector init/cleanups
"""Function called before the GC initializes.
The `new` keyword should not be used here (before the GC initializes), it's undefined behavior and may crash"""
FUNC_HOOK_PRE_GC_INIT = "__PS_PreGcInitHook"
"""Function called after the GC initializes and before any code in the main function. Globals may or may not be properly initialized"""
FUNC_HOOK_POST_GC_INIT = "__PS_PostGcInitHook"
"""Function called after all code in the main function and before the GC cleanup and after a GC pass. Use it to check for memory leaks and GC errors."""
FUNC_HOOK_PRE_GC_CLEANUP = "__PS_PreGcCleanupHook"
"""Function called after the GC runs its cleanup.
ALL reference variables, defined before and in this function are considered cleaned up and accessing them will lead to undefined behavior
The `new` keyword should not be used here"""
FUNC_HOOK_POST_GC_CLEANUP = "__PS_PostGcCleanupHook"

"""The name of the global symbol that holds the program exit code"""
EXIT_CODE_GLOBAL_VAR_NAME = "__PS_ExitCodeValue"