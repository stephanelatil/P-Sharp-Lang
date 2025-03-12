# Hacky way of enabling opaque pointers
# later versions of llvmlite will make this mandatory
import os
os.environ['LLVMLITE_ENABLE_OPAQUE_POINTERS'] = "1"
import llvmlite
llvmlite.ir_layer_typed_pointers_enabled = False
llvmlite.opaque_pointers_enabled = True

from typer import Typer, TypeClass, TypingError
from parser import (PClass,PFunction,PProgram, Typ, ArrayTyp,
                    PStatement, PVariableDeclaration,
                    PLiteral)
from typing import TextIO, List, Dict, Optional, Union
from utils import CodeGenContext, Scopes, CompilerError, CompilerWarning
from llvmlite import ir
from warnings import warn
from constants import *
from llvmlite.binding import (initialize, initialize_native_target, 
                              initialize_native_asmprinter, PipelineTuningOptions,
                              PassBuilder, Target, parse_assembly, parse_bitcode,
                              ModuleRef)


class CodeGen:
    _GC_LIB='../garbage_collector/libps_gc.bc'
    BUILTINS_TYPE_MAP: Dict[str, Union[ir.IntType,
                                       ir.HalfType,
                                       ir.FloatType,
                                       ir.DoubleType,
                                       ir.VoidType]] = {
            'void': ir.VoidType(),
            'char': ir.IntType(8),
            'i8': ir.IntType(8),
            'i16': ir.IntType(16),
            'i32': ir.IntType(32),
            'i64': ir.IntType(64),
            'u8': ir.IntType(8),
            'u16': ir.IntType(16),
            'u32': ir.IntType(32),
            'u64': ir.IntType(64),
            'f16': ir.HalfType(),
            'f32': ir.FloatType(),
            'f64': ir.DoubleType(),
            'bool': ir.IntType(1)
        }
    
    def __init__(self, speed_opt:int=0, size_opt:int=0, use_warnings:bool=False) -> None:
        
        #required for code generation (no cross-compile yet, needs initialize_all* for that)
        initialize()
        initialize_native_target()
        initialize_native_asmprinter()
        
        self.use_warnings = use_warnings
        self.typer = Typer.default
        self.module = ir.Module(name='')
        self.module.triple = Target.from_default_triple().triple
        self.target = Target.from_triple(self.module.triple)\
                                .create_target_machine(
            codemodel='jitdefault',
            jit=False,
        )
        self.optimizer_pass = PassBuilder(self.target, PipelineTuningOptions(speed_opt, size_opt))
    
    
    def compile_module(self, filename:str, file:TextIO, is_library:bool=False):
        # Initializes module & typer
        self.module = ir.Module(name=filename+".o")
        self.module.triple = Target.from_default_triple().triple
        self.typer = Typer(filename, file)
        # Lex, Parse and Type code
        typed_abstract_syntax_tree = self.typer.type_program(self.use_warnings)
        #Init type list map. Initially all reference type fields are just pointers. On subsequent passes they are converter to _TypedPointers
        type_map:Dict[Typ, Union[ir.IntType,ir.HalfType,ir.FloatType,ir.DoubleType,ir.VoidType,ir.LiteralStructType]] = {
            typ:self.get_llvm_struct(typ, None)
            for typ in self.typer.known_types.values()
        }
        # Create CodeGenContext
        context = CodeGenContext(target_data=self.target.target_data,
                                 module=self.module, scopes=Scopes(),
                                 type_map=type_map)
        # Extra passes to types to convert all simple pointers to pointer to specific reference types
        for i in range(3):
            context.type_map = {
                typ:self.get_llvm_struct(typ, context)
                for typ in self.typer.known_types.values()
            }
        #Enter global scope
        context.scopes.enter_scope()
        #initialize builtin function prototypes
        self._init_builtin_functions_prototypes(context)
        
        # Compile all symbol declarations (classes & methods, functions and globals)
        # Note: no operations are run only code is generated, so globals are declared and defined with constant or default values. They will be defined with additional custom/calculated values in the main function
            # (functions/methods bodies are defined though)
        self._compile_top_level_declarations(typed_abstract_syntax_tree, context)
        
        # Here should check if we're building a library.
        self._setup_exit_code_global(context, is_library=is_library)
        if not is_library:
            # generate code for main function
            self._generate_main_function(typed_abstract_syntax_tree, context)
            # static-link the GC (very small so it's fine)
            module_ref = parse_assembly(str(context.module))
            with open(self._GC_LIB, "rb") as f:
                gc_module = parse_bitcode(f.read())
                module_ref.link_in(gc_module)

        # If building a library, add a globals initializer function. and ignore all other statement
        else:
            # TODO set the globals/methods/classes to export and which to keep internally private
            
            # For all generated code library or not
            # Get ModuleRef
            module_ref = parse_assembly(str(context.module))

        # Run verifier
        module_ref.verify()
        # Run optimization passes
        pass_manager = self.optimizer_pass.getModulePassManager()
        pass_manager.add_instruction_combine_pass()
        pass_manager.add_jump_threading_pass()
        pass_manager.add_simplify_cfg_pass()
        pass_manager.add_loop_rotate_pass()
        pass_manager.add_loop_unroll_pass()
        pass_manager.add_refprune_pass()
        pass_manager.add_aa_eval_pass()
        pass_manager.add_verifier()
        pass_manager.run(module_ref, self.optimizer_pass)
        # Return ModuleRef object
        return module_ref
    
    def _setup_exit_code_global(self, context:CodeGenContext, is_library:bool=False):
        """Sets the default main return value to the given value
        Here it's set to a variable value so that each "return" instruction from the main function
        actually sets this value and jumps to the GC Cleanup

        Args:
            context (CodeGenContext): The CodeGenContext used for this module
            default_value (int, optional): Th default return code of the program. Defaults to 0.
        """
        default_value:int = 0
        global_var = ir.GlobalVariable(module=context.module, typ=ir.IntType(32),
                                       name=EXIT_CODE_GLOBAL_VAR_NAME)
        context.scopes.declare_var(EXIT_CODE_GLOBAL_VAR_NAME, global_var.value_type, global_var)
        if not is_library:
            global_var.initializer = ir.Constant(global_var.value_type, default_value)
        
    def _generate_main_function(self, ast:PProgram, context:CodeGenContext):
        """Generates the main function context in the current module.
        It adds the P# garbage collector, calls hook functions if they are defined and adds user code to the main function.

        Args:
            ast (PProgram): The typed AST
            context (CodeGenContext): The context containing the module
        """
        # declare main function
        func_type = ir.FunctionType(ir.IntType(32),[])
        main_func = ir.Function(context.module, func_type, ENTRYPOINT_FUNCTION_NAME)
        # Add primary main function blocks
        # Entry
        context.builder.position_at_end(main_func.append_basic_block('__main_entrypoint'))
        # Exit
        context.global_exit_block = main_func.append_basic_block('__main_exit_cleanup')
        
        # Initialize GC and run hooks if there are any
        self._generate_gc_init(context)
        user_main_func_code_block = context.builder.append_basic_block(MAIN_FUNCTION_USER_CODE_BLOCK)
        context.builder.branch(user_main_func_code_block)
        context.builder.position_at_end(user_main_func_code_block)
        
        # Generate the user code in the main function
        self._generate_user_main_code(ast, context)
        
        # Branch to exit if no explicit return is added
        #make sure use code block is terminated
        assert isinstance(context.builder.block, ir.Block)
        if not context.builder.block.is_terminated:
            context.builder.branch(context.global_exit_block)
        
        # Write in exit block
        context.builder.position_at_end(context.global_exit_block)
        # Generate code for the exit/cleanup block
        self._generate_gc_cleanup(context)
        
        # out of main function
        context.global_exit_block = None

    def _generate_gc_init(self, context:CodeGenContext):
        """Generates function calls to initialize the garbage collector and adds init hook calls

        Args:
            context (CodeGenContext): The code gen context with the current module
        """
        # Run pre-GC-init hook if one is defined
        if context.scopes.has_symbol(FUNC_HOOK_PRE_GC_INIT):
            hook = context.scopes.get_symbol(FUNC_HOOK_PRE_GC_INIT).func_ptr
            assert hook is not None
            context.builder.call(hook, [])

        # Initialize type registry with correct size
        size_t_type = ir.IntType(ir.PointerType().get_abi_size(context.target_data)*8)
        # void __PS_InitTypeRegistry(size_t initial_capacity)
        init_type_registry_func = context.scopes.get_symbol(FUNC_GC_INITIALIZE_TYPE_REGISTRY).func_ptr
        # TODO: len(self.typer.known_types) includes value types and many arrays but having a bit extra space can be optimized later
        context.builder.call(init_type_registry_func,
                             [ir.Constant(size_t_type,
                                          len(self.typer.known_types))])
        
        # Populate type registry
        register_type_func = context.scopes.get_symbol(FUNC_GC_REGISTER_TYPE).func_ptr
        assert register_type_func is not None
        type_id_idx_offset = 2 # 0 and 1 are taken up by ref-arrays and value-arrays
        #size_t __PS_RegisterType(size_t size, size_t num_pointers, const char* type_name)
        for i, (typ, ir_type) in enumerate(context.type_map.items()):
            assert isinstance(typ, Typ)
            if not isinstance(ir_type, ir.LiteralStructType):
                continue
            if not typ.is_reference_type or isinstance(typ, ArrayTyp) or typ.name in ['void','null']:
                continue
            size = ir.Constant(size_t_type,
                               ir_type.get_abi_size(target_data=context.target_data))
            name_c_str = context.get_char_ptr_from_string(typ.name)
            num_ref_types = ir.Constant(size_t_type,
                                        sum([field.is_pointer for field in ir_type.elements]))
            context.builder.call(register_type_func,[
                                     size,
                                     num_ref_types,
                                     name_c_str])
            context.type_ids[typ.name] = type_id_idx_offset + i
        
        #init root tracking (tracking reference type vars)
        # void __PS_InitRootTracking(void)
        init_root_tracking_func = context.scopes.get_symbol(FUNC_GC_INITIALIZE_ROOT_VARIABLE_TRACKING).func_ptr
        assert init_root_tracking_func is not None
        context.builder.call(init_root_tracking_func, [])

        # Run post-GC-init hook if one is defined
        if context.scopes.has_symbol(FUNC_HOOK_POST_GC_INIT):
            hook = context.scopes.get_symbol(FUNC_HOOK_POST_GC_INIT).func_ptr
            assert hook is not None
            context.builder.call(hook, [])
        
    def _generate_gc_cleanup(self, context:CodeGenContext):
        """Generates function calls to cleanup/destroy the garbage collector and adds cleanup hook calls

        Args:
            context (CodeGenContext): The code gen context with the current module
        """
        
        # Run pre-GC-cleanup hook if one is defined
        if context.scopes.has_symbol(FUNC_HOOK_PRE_GC_INIT):
            hook = context.scopes.get_symbol(FUNC_HOOK_PRE_GC_INIT).func_ptr
            assert hook is not None
            context.builder.call(hook, [])
        
        
        # void __PS_InitTypeRegistry(size_t initial_capacity)
        init_type_registry_func = context.scopes.get_symbol(FUNC_GC_CLEANUP_BEFORE_PROGRAM_SHUTDOWN).func_ptr
        assert init_type_registry_func is not None
        # void __PS_CollectGarbage(void)
        context.builder.call(init_type_registry_func,[])

        # Run post-GC-cleanup hook if one is defined
        if context.scopes.has_symbol(FUNC_HOOK_POST_GC_CLEANUP):
            hook = context.scopes.get_symbol(FUNC_HOOK_POST_GC_CLEANUP).func_ptr
            assert hook is not None
            context.builder.call(hook, [])
            
        exit_code = context.scopes.get_symbol(EXIT_CODE_GLOBAL_VAR_NAME)

        assert exit_code.alloca is not None
        context.builder.ret(context.builder.load(exit_code.alloca, typ=exit_code.type_))
        
        
    def _declare_module_functions(self, ast:PProgram, context:CodeGenContext):
        # TODO here we should also add the imports
        for statement in ast.statements:
            if not isinstance(statement, PFunction):
                continue
            if statement.name == ENTRYPOINT_FUNCTION_NAME:
                continue #ignore main: will be added later
            return_type = statement.return_typ_typed.get_llvm_value_type(context)
            assert return_type is not None
            arg_types = [
                arg.typer_pass_var_type.get_llvm_value_type(context)
                for arg in statement.function_args
            ]
            func_type = ir.FunctionType(return_type, arg_types)
            func_ptr = ir.Function(context.module, func_type, statement.name)
            context.scopes.declare_func(statement.name, return_type, func_ptr)
        
    def _declare_module_class_methods(self, ast:PProgram, context:CodeGenContext):
        # TODO here we should also add the imports
        for statement in ast.statements:
            if not isinstance(statement, PClass):
                continue
            for method in statement.methods:
                # TODO: use vtable instead of defining as a global symbol
                method_name = context.get_method_symbol_name(statement.class_typ.name, method.name)
                return_type = method.return_typ_typed.get_llvm_value_type(context)
                assert return_type is not None
                #set "this" as first argument
                arg_types = [statement.class_typ.get_llvm_value_type(context)]
                for arg in method.function_args:
                    arg_types.append(arg.typer_pass_var_type.get_llvm_value_type(context))
                func_type = ir.FunctionType(return_type, arg_types)
                func_ptr = ir.Function(context.module, func_type, method_name)
                context.scopes.declare_func(method_name, return_type, func_ptr)
        
    def _declare_module_globals(self, ast:PProgram, context:CodeGenContext):
        """Declares global variables.
        If the value is defined as a constant (direct constant, not cast/calculation or similar) its initializer will be set to the constant.
        Otherwise a default value will be set and the value will be calculated in the main function 
        (should an init function be made to be called by the `main` or importing modules?)
        """
        # TODO here we should also add the imports
        for statement in ast.statements:
            if not isinstance(statement, PVariableDeclaration):
                continue
            var_type = statement.typer_pass_var_type.get_llvm_value_type(context)
            global_var = ir.GlobalVariable(context.module, var_type,statement.name)
            if isinstance(statement.initial_value, PLiteral):
                global_var.initializer = statement.initial_value.generate_llvm(context)
            else:
                global_var.initializer = statement.typer_pass_var_type.default_llvm_value(context)
            context.scopes.declare_var(global_var.name, var_type, global_var)
        
    def _compile_module_functions(self, ast:PProgram, context:CodeGenContext):
        for statement in ast.statements:
            if not isinstance(statement, PFunction):
                continue
            if statement.name == ENTRYPOINT_FUNCTION_NAME:
                # Don't compile main function. It will be added later
                continue
            function = context.scopes.get_symbol(statement.name).func_ptr
            assert function is not None
            context.builder = ir.IRBuilder(function.append_basic_block(f"{statement.name}_{statement.position.index}_entrypoint"))
            context.scopes.enter_func_scope()
            #add params to the scope (and name them for easy retrieval)
            for ir_arg, p_arg in zip(function.args, statement.function_args):
                # Make sure we have a pointer to the argument location. That way the arg can be overwritten
                # This will be optimized out anyway with the mem2reg pass
                arg_alloca = context.builder.alloca(ir_arg.type)
                context.builder.store(ir_arg, arg_alloca)
                context.scopes.declare_var(p_arg.name, ir_arg.type, arg_alloca)
            #compile function body
            statement.body.generate_llvm(context, build_basic_block=False)
            context.scopes.leave_func_scope()
        
    def _compile_module_class_methods(self, ast:PProgram, context:CodeGenContext):
        for statement in ast.statements:
            if not isinstance(statement, PClass):
                continue
            for method in statement.methods:
                function = context.scopes.get_symbol(method.name).func_ptr
                assert function is not None
                context.builder = ir.IRBuilder(function.append_basic_block(f"{method.name}_{method.position.index}_entrypoint"))
                context.scopes.enter_func_scope()
                #add params to the scope (and name them for easy retrieval)
                for ir_arg, p_arg in zip(function.args, method.function_args):
                    context.scopes.declare_var(p_arg.name, ir_arg.type, ir_arg)
                #compile function body
                method.body.generate_llvm(context)
                context.scopes.leave_func_scope()
    
    def _compile_top_level_declarations(self, ast:PProgram, context:CodeGenContext):
        """This declares then compiles (in multiple passes) the functions, classes and global vars defined in the module
        It will later also include the imported symbols from other modules

        Args:
            ast (PProgram): The module's typed abstract syntax tree
        """
        
        # First pass declares prototypes for the module's functions
        self._declare_module_functions(ast, context)
        # Second pass does the same for the class methods
        self._declare_module_class_methods(ast, context)
        
        # Third pass creates global variables 
        self._declare_module_globals(ast, context)
        
        # Fourth pass compiles the functions
            # needed in 2 passes to ensure cyclic function calls work
            # If f1() uses f2() and f2() uses f1(), we need to know the prototypes of both functions
        self._compile_module_functions(ast, context)
        
        # Fifth Pass compiles all class methods
        self._compile_module_class_methods(ast, context)

    def _generate_user_main_code(self, ast:PProgram, context:CodeGenContext):
        """Generates user code in the main function"""
        for statement in ast.statements:
            if isinstance(statement, PVariableDeclaration) and statement.initial_value is not None:
                # It's a global definition and initialize value
                global_var = context.scopes.get_symbol(statement.name).alloca
                assert global_var is not None
                context.builder.store(statement.initial_value.generate_llvm(context),
                                      global_var)
                continue
        for statement in ast.statements:
            #ignore already defined functions
            if isinstance(statement, PFunction):
                if statement.name == ENTRYPOINT_FUNCTION_NAME:
                    # generate user code in main function
                    # basic block already constructed so we don't need an extra
                    statement.body.generate_llvm(context, build_basic_block=False)
                    #all code generated just return
                    return
                continue
            elif isinstance(statement, (PClass, PVariableDeclaration)):
                #skip classes or globals: Already done
                continue
            else:
                # not a function/class or global
                # currently not supported
                raise CompilerError(f'Unexpected statement at location {statement.position}\n'+\
                                    'Cannot have statements (other than class, function or global definitions) in the global scope\n'+\
                                    'Please write your code inside the i32 main() function')

    def _init_builtin_functions_prototypes(self, context:CodeGenContext):
        """Adds builtin functions to the global scope"""
        size_t_type = ir.IntType(ir.PointerType().get_abi_size(context.target_data)*8)
        char_ptr = ir.PointerType()
        void_ptr = ir.PointerType()
        void = ir.VoidType()
        
        for name, func_type in [
                            (FUNC_GC_INITIALIZE_ROOT_VARIABLE_TRACKING, ir.FunctionType(void,[])),
                            (FUNC_GC_ENTER_SCOPE, ir.FunctionType(void,[size_t_type])),
                            (FUNC_GC_LEAVE_SCOPE, ir.FunctionType(void,[])),
                            (FUNC_GC_PRINT_HEAP_STATS, ir.FunctionType(void,[])),
                            (FUNC_GC_RUN_GARBAGE_COLLECTOR, ir.FunctionType(void,[])),
                            (FUNC_GC_CLEANUP_BEFORE_PROGRAM_SHUTDOWN, ir.FunctionType(void,[])),
                            (FUNC_GC_ALLOCATE_OBJECT, ir.FunctionType(void_ptr,[size_t_type])),
                            (FUNC_GC_ALLOCATE_VALUE_ARRAY, ir.FunctionType(void_ptr,[size_t_type,size_t_type])),
                            (FUNC_GC_ALLOCATE_REFERENCE_OBJ_ARRAY, ir.FunctionType(void_ptr,[size_t_type])),
                            (FUNC_GC_REGISTER_TYPE, ir.FunctionType(size_t_type,[size_t_type, size_t_type, char_ptr])),
                            (FUNC_GC_INITIALIZE_TYPE_REGISTRY, ir.FunctionType(void,[size_t_type])),
                            (FUNC_GC_REGISTER_ROOT_VARIABLE_IN_CURRENT_SCOPE, ir.FunctionType(void,[void_ptr, size_t_type, char_ptr])),
                                ]:
            func = ir.Function(context.module, func_type, name)
            context.scopes.declare_func(name, func_type.return_type, func)
            
        fprintf = ir.Function(context.module, ir.FunctionType(ir.IntType(32),[ir.IntType(32), ir.PointerType()], True), "fprintf")
        exit_func = ir.Function(context.module, ir.FunctionType(ir.VoidType(),[ir.IntType(32)]), "exit")
        context.scopes.declare_func("fprintf", ir.IntType(32), fprintf)
        context.scopes.declare_func("exit", ir.VoidType(), exit_func)

    def get_llvm_struct(self, typ: Typ, context:Optional[CodeGenContext]) -> Union[ir.IntType,
                                                   ir.HalfType,
                                                   ir.FloatType,
                                                   ir.DoubleType,
                                                   ir.VoidType,
                                                   ir.LiteralStructType]:
        """Returns the LLVM struct representing this type.
        All Value types (int/floats) and void will return their direct llvm value types.
        Classes and reference types will return the struct representing it

        Args:
            type_ (Typ): The type to return an array from

        Raises:
            TypingError: If the

        Returns:
            Union[ir.IntType, ir.HalfType, ir.FloatType, ir.DoubleType, ir.VoidType, ir.LiteralStructType]: The IR struct or value type of this Typ
        """
        if typ.name in self.BUILTINS_TYPE_MAP:
            return self.BUILTINS_TYPE_MAP[typ.name]
        if not typ.is_reference_type:
            raise TypingError(f'Unable to get IR Type for value type {typ}')
        
        type_info = self.typer.get_type_info(typ)
        
        if type_info.type_class == TypeClass.CLASS:
            field_types = [
                prop.typer_pass_var_type.get_llvm_value_type(context)
                for prop in typ.fields
            ]
            return ir.LiteralStructType(field_types)
            
        
        if type_info.type_class == TypeClass.ARRAY:
            assert isinstance(typ, ArrayTyp)
            #return a generic array struct (contains an int and a pointer to the array)
            return ir.LiteralStructType([
                ir.IntType(64), #the array length
                ir.ArrayType(
                    # The value type struct of an array element
                    # Direct value type or a pointer if it's a reference type
                    typ.element_typ.get_llvm_value_type(context),
                    0) #arbitrary size
            ])

        if type_info.type_class == TypeClass.STRING:
            return ir.LiteralStructType([
                ir.IntType(64), #the string length
                ir.ArrayType(
                    ir.IntType(8), #a char (strings are basically just char arrays)
                    0) #arbitrary size
            ])
        
        raise TypingError(f"Unsupported type: {typ.name}")