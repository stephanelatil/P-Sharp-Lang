# Hacky way of enabling opaque pointers
# later versions of llvmlite will make this mandatory
import os
os.environ['LLVMLITE_ENABLE_OPAQUE_POINTERS'] = "1"
import llvmlite
llvmlite.ir_layer_typed_pointers_enabled = False
llvmlite.opaque_pointers_enabled = True

from typer import Typer, TypeClass, TypingError, CompilerWarning
from parser import (PClass,PFunction,PProgram, IRCompatibleTyp,
                    ArrayTyp, PClassField,
                    PReturnStatement, PVariableDeclaration,
                    PLiteral, CodeGenContext, Scopes,
                    CompilerError, DebugInfo, ReferenceTyp)
from subprocess import Popen, PIPE
from tempfile import TemporaryDirectory
from typing import TextIO, Dict, Optional, Union
from llvmlite import ir
from warnings import warn
from constants import *
from objs import OutputFormat, LLVM_Version, CompilationOptions
from llvmlite.binding import (initialize, initialize_native_target, 
                              initialize_native_asmprinter, Target,
                              parse_bitcode, TypeRef, TypeKind)
from pathlib import Path

class CodeGen:
    _COMPILER_VERSION = "0.1"
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
    
    def __init__(self, use_warnings:bool=False) -> None:
        
        #required for code generation (no cross-compile yet, needs initialize_all* for that)
        initialize()
        initialize_native_target()
        initialize_native_asmprinter()
        
        self._RUNTIME_LIB=Path(__file__).parent.parent.joinpath('garbage_collector', 'ps_re.bc')
        self.use_warnings = use_warnings
        self.typer = Typer.default
        self.module = ir.Module(name='')
        self.module.triple = Target.from_default_triple().triple
        self.target = Target.from_triple(self.module.triple)\
                                .create_target_machine(
            codemodel='jitdefault',
            jit=False,
        )
    
    
    def compile_module(self, filepath:Path,
                       file:TextIO,
                       output_file:str,
                       emit_format:OutputFormat,
                       llvm_version:LLVM_Version=LLVM_Version.v15,
                       clang_flags:Optional[list]=None,
                       compiler_opts:CompilationOptions=CompilationOptions()) -> Path:
        """Compiles the module to the requested output and linked with the runtime environment if it's not a library

        Args:
            filepath (Path): The input file path
            file (TextIO): The readable buffer to the file contents
            output_file (str): The file where to place the compiled and linked output
            emit (OutputFormat): The format of the output
            is_library (bool, optional): Whether to compile the module as a library. Defaults to False.
            llvm_version (LLVM_Version, optional): The LLVM version to use. Defaults to version 15.

        Returns:
            Path: The filepath to the compiled and linked module of the requested format
        """        
        clang_flags = clang_flags or list()
        # Initializes module & typer
        filename = filepath.name
        self.typer = Typer(filename, file)
        # Lex, Parse and Type code
        typed_abstract_syntax_tree = self.typer.type_program(self.use_warnings)
        self.module = ir.Module(name=typed_abstract_syntax_tree.namespace_name+'-'+
                                filepath.stem)
        self.module.triple = Target.from_default_triple().triple
        #Init type list map. Initially all reference type fields are just pointers. On subsequent passes they are converter to _TypedPointers
        type_map:Dict[IRCompatibleTyp, Union[ir.IntType,ir.HalfType,ir.FloatType,ir.DoubleType,ir.VoidType,ir.LiteralStructType]] = {
            typ:self.get_llvm_struct(typ, None)
            for typ in self.typer.known_types.values()
        }
        if compiler_opts.add_debug_symbols:
            dbg_declare = ir.Function(self.module, 
                                      ir.FunctionType(ir.VoidType(), [ir.MetaDataType()] * 3),
                                      'llvm.dbg.declare')
            dbg_assign = ir.Function(self.module, 
                                      ir.FunctionType(ir.VoidType(), [ir.MetaDataType()] * 3),
                                      'llvm.dbg.assign')
            dbg_value = ir.Function(self.module, 
                                      ir.FunctionType(ir.VoidType(), [ir.MetaDataType()] * 3),
                                      'llvm.dbg.value')
            di_file = self.module.add_debug_info("DIFile", 
                                                {"filename": filename,
                                                "directory": str(filepath.parent.resolve())})
            di_compile_unit = self.module.add_debug_info("DICompileUnit", 
                                                    {
                                                        "language": ir.DIToken('DW_LANG_C99'),
                                                        "producer": f"pscc {self._COMPILER_VERSION}/llvmlite {llvmlite._version.version_version}",
                                                        "runtimeVersion": 1,
                                                        "isOptimized":False,
                                                        "emissionKind": ir.DIToken('FullDebug'),
                                                        "nameTableKind": ir.DIToken('None'),
                                                        "splitDebugInlining": False,
                                                        "file": di_file
                                                    },
                                                    is_distinct=True)
            # add Metadata for debugging
            self.module.add_named_metadata('llvm.dbg.cu', di_compile_unit)
            self.module.add_named_metadata('llvm.module.flags', [ir.Constant(ir.IntType(32),7), "Dwarf Version", ir.Constant(ir.IntType(32),5)])
            self.module.add_named_metadata('llvm.module.flags', [ir.Constant(ir.IntType(32),2), "Debug Info Version", ir.Constant(ir.IntType(32),3)])
            self.module.add_named_metadata('llvm.module.flags', [ir.Constant(ir.IntType(32),1), "wchar_size", ir.Constant(ir.IntType(32),4)])
            self.module.add_named_metadata('llvm.module.flags', [ir.Constant(ir.IntType(32),7), "PIC Level", ir.Constant(ir.IntType(32),2)])
            self.module.add_named_metadata('llvm.module.flags', [ir.Constant(ir.IntType(32),7), "PIE Level", ir.Constant(ir.IntType(32),2)])
            self.module.add_named_metadata('llvm.module.flags', [ir.Constant(ir.IntType(32),7), "uwtable", ir.Constant(ir.IntType(32),2)])
            self.module.add_named_metadata('llvm.module.flags', [ir.Constant(ir.IntType(32),7), "frame-pointer", ir.Constant(ir.IntType(32),2)])
            # Create CodeGenContext
            debug_info = DebugInfo(di_file=di_file,
                                    di_compile_unit=di_compile_unit,
                                    dbg_declare_func=dbg_declare,
                                    dbg_assign_func=dbg_assign,
                                    dbg_value_func=dbg_value,
                                    di_scope=[
                                        self.module.add_debug_info("DINamespace",
                                                                   {
                                                                       "scope":di_compile_unit,
                                                                       "name":typed_abstract_syntax_tree.namespace_name
                                                                   })
                                    ])
        else:
            debug_info = None
        self.module.add_named_metadata("llvm.ident", [f"pscc {self._COMPILER_VERSION}/llvmlite {llvmlite._version.version_version}"])
        context = CodeGenContext(module=self.module, scopes=Scopes(),
                                target_data=self.target.target_data,
                                type_map=type_map,
                                debug_info=debug_info,
                                compilation_opts=compiler_opts,
                                namespace=typed_abstract_syntax_tree.namespace_name)
        # Setup type_ids
        type_id = 2 # 0 and 1 are taken up by ref-arrays and value-arrays
        for typ, ir_type in context.type_map.items():
            assert isinstance(typ, IRCompatibleTyp)
            if not isinstance(ir_type, ir.LiteralStructType):
                continue
            if not typ.is_reference_type or isinstance(typ, ArrayTyp) or typ.name in ['void','null']:
                continue
            context.type_ids[typ.name] = type_id
            type_id += 1

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
        self._declare_top_level_declarations(typed_abstract_syntax_tree, context)
        self._define_top_level_declarations(typed_abstract_syntax_tree, context)
        
        # Generate function to populate globals
        globals_ref_type_count = self._generate_globals_populator(typed_abstract_syntax_tree, context)
        
        if not compiler_opts.is_library:
            self._setup_exit_code_global(context, is_library=compiler_opts.is_library)
            # generate code for main function
            self._generate_main_function(typed_abstract_syntax_tree, context, globals_ref_type_count)
            self._compile_prog(context.module, output_file=output_file,
                                llvm_version=llvm_version, output_format=emit_format,
                                clang_flags=clang_flags)

        # If building a library, add a globals initializer function. and ignore all other statement
        else:
            # TODO set the globals/methods/classes to export and which to keep internally private
            # compile write to file and return path to it
            with TemporaryDirectory() as tmpdir:
                tmp_module_ll = Path(tmpdir, 'generated_ir.ll')
                tmp_module_ll.write_text(str(context.module), encoding='utf_8')
                self._compile_to_output_format(tmp_module_ll,
                                                output_file=output_file,
                                                llvm_version=llvm_version,
                                                output_format=emit_format,
                                                clang_flags=clang_flags)

        return Path(output_file).resolve().absolute()
    
    def _compile_prog(self, module:ir.Module, output_file:str,
                     llvm_version:LLVM_Version, output_format:OutputFormat,
                     clang_flags:list):
        with TemporaryDirectory() as tmpdir:
            tmp_generated_ir_file = Path(tmpdir, 'generated_ir.ll')
            tmp_generated_ir_file.write_text(str(module),
                                     'utf_8')
            link_flags = [str(tmp_generated_ir_file), f'--override={tmp_generated_ir_file}',
                          "--suppress-warnings", str(self._RUNTIME_LIB)]
            if output_format in [OutputFormat.IntermediateRepresentation, OutputFormat.BitCode]:
                if output_format == OutputFormat.IntermediateRepresentation:
                    link_flags += ['-S', '-o', output_file]
                elif output_format == OutputFormat.BitCode:
                    link_flags += ['-o', output_file]
                proc = Popen(['llvm-link'+llvm_version.suffix(), *link_flags])
                proc.communicate()
                # compiled to the requested output format. no additional compilation needed
                return
            
            tmp_linked_bc_file = Path(tmpdir, 'linked_module.bc')
            #needs to use clang to advance
            link_flags += ['-o', str(tmp_linked_bc_file)]
            proc = Popen(['llvm-link'+llvm_version.suffix(), *link_flags])
            proc.wait()
            
            self._compile_to_output_format(module_bc=tmp_linked_bc_file,
                                           output_file=output_file, 
                                           llvm_version=llvm_version,
                                           output_format=output_format,
                                           clang_flags=clang_flags)

    def _compile_to_output_format(self, module_bc:Path, output_file:str,
                     llvm_version:LLVM_Version, output_format:OutputFormat,
                     clang_flags:list):
        clang_flags = ['-x', 'ir', '-Wno-override-module'] + clang_flags
        if output_format == OutputFormat.Assembly:
            clang_flags.append('-S')
        elif output_format == OutputFormat.Object:
            clang_flags.append('-c')
        elif output_format == OutputFormat.Executable:
            pass
        elif output_format == OutputFormat.IntermediateRepresentation:
            clang_flags.append('-emit-llvm')
            clang_flags.append('-S')
        elif output_format == OutputFormat.BitCode:
            clang_flags.append('-emit-llvm')
            clang_flags.append('-c')
        else:
            raise NotImplementedError(f"Unknown output format {output_format}")
        
        proc = Popen(["clang"+llvm_version.suffix(), *clang_flags,
                        "-o", output_file, str(module_bc)], stdin=PIPE)
        proc.wait()
    
    def _define_top_level_declarations(self, ast:PProgram, context:CodeGenContext):
        """Generates the code within all functions and methods"""
        
        # This pass compiles the functions
            # needed in 2 passes to ensure cyclic function calls work
            # If f1() uses f2() and f2() uses f1(), we need to know the prototypes of both functions
        self._compile_module_functions(ast, context)
        
        # Final Pass compiles all class methods
        self._compile_module_class_methods(ast, context)
    
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
            global_var.initializer = ir.Constant(global_var.value_type, default_value) #type: ignore Initializer is always none according to the typer
        
    def _generate_main_function(self, ast:PProgram, context:CodeGenContext, reference_type_globals_count:int=0):
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
        
        #add debug info if requested
        if context.compilation_opts.add_debug_symbols:
            assert context.debug_info is not None
            for statement in ast.statements:
                if isinstance(statement, PFunction):
                    if statement.name == ENTRYPOINT_FUNCTION_NAME:
                        main_func.set_metadata("dbg", statement.add_debug_info(context))
                        break
        # Generate the user code in the main function
        self._generate_user_main_code(ast, context, reference_type_globals_count)
        
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
        
    def _generate_globals_populator(self, ast:PProgram, context:CodeGenContext):
        """Generate function to populate the global variables"""
        globals_ref_type_count = 0
        func_type = ir.FunctionType(ir.VoidType(), [])
        func = ir.Function(context.module, func_type, FUNC_POPULATE_GLOBALS)
        context.scopes.declare_func(FUNC_POPULATE_GLOBALS, ir.VoidType(), func)
        context.builder.position_at_start(func.append_basic_block(FUNC_POPULATE_GLOBALS+'_entry'))
        if context.compilation_opts.add_debug_symbols:
            assert context.debug_info is not None
            subroutine_type = context.module.add_debug_info("DISubroutineType",
                                        {
                                            "types": [None]
                                        })
            di_subprogram = context.module.add_debug_info("DISubprogram",
                    {
                        "name": FUNC_POPULATE_GLOBALS,
                        #TODO edit linkable name with namespace info
                        "linkageName": f"{context.namespace}.{FUNC_POPULATE_GLOBALS}",
                        "line":0,
                        "file":None,
                        "type": subroutine_type,
                        "isDefinition": True,
                        "unit":context.debug_info.di_compile_unit,
                        "spFlags":ir.DIToken('DISPFlagDefinition'),
                        "retainedNodes":[]
                    }, is_distinct=True)
            context.debug_info.di_scope.append(di_subprogram)
        
        for statement in ast.statements:
            if isinstance(statement, PVariableDeclaration) and statement.initial_value is not None:
                # It's a global definition and initialize value
                global_var = context.scopes.get_symbol(statement.name).alloca
                assert global_var is not None
                context.builder.store(statement.initial_value.generate_llvm(context),
                                      global_var)
                assert isinstance(statement.typer_pass_var_type, ReferenceTyp)
                context.add_root_to_gc(global_var,
                                       statement.typer_pass_var_type,
                                       statement.name)
                if statement.typer_pass_var_type.is_reference_type:
                    globals_ref_type_count += 1
        context.builder.ret_void()
        if context.compilation_opts.add_debug_symbols:
            assert context.debug_info is not None
            context.debug_info.di_scope.pop()
        return globals_ref_type_count

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
        context.builder.call(init_type_registry_func,
                             [ir.Constant(size_t_type, max(context.type_ids.values()))])
        
        # Populate type registry
        register_type_func = context.scopes.get_symbol(FUNC_GC_REGISTER_TYPE).func_ptr
        assert register_type_func is not None
        type_id = 2 # 0 and 1 are taken up by ref-arrays and value-arrays
        #size_t __PS_RegisterType(size_t size, size_t num_pointers, const char* type_name)
        for typ, ir_type in context.type_map.items():
            assert isinstance(typ, IRCompatibleTyp)
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
            context.type_ids[typ.name] = type_id
            type_id += 1
        
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
            func_ptr = ir.Function(context.module, func_type, statement.get_linkable_name(context))
            context.scopes.declare_func(statement.get_linkable_name(context), return_type, func_ptr)
        
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
                arg_types = []
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
            if isinstance(statement.initial_value, PLiteral) and statement.initial_value.literal_type != "string":
                global_var.initializer = statement.initial_value.generate_llvm(context) #type: ignore
            else:
                global_var.initializer = statement.typer_pass_var_type.default_llvm_value(context) #type: ignore
            if context.compilation_opts.add_debug_symbols:
                assert context.debug_info is not None
                debug_info = context.module.add_debug_info("DIGlobalVariable",
                                                {
                                                    "name":statement.name,
                                                    "file":context.debug_info.di_file,
                                                    **statement.di_location(context),
                                                    "type": statement.typer_pass_var_type.di_type(context)
                                                })
                debug_info = context.module.add_debug_info("DIGlobalVariableExpression",
                                { 
                                    "var": debug_info,
                                    "expr": context.module.add_debug_info("DIExpression", {})
                                })
                global_var.set_metadata("dbg", debug_info)
            else:
                debug_info = None
            context.scopes.declare_var(global_var.name, var_type, global_var)
        
    def _compile_module_functions(self, ast:PProgram, context:CodeGenContext):
        for statement in ast.statements:
            if not isinstance(statement, PFunction):
                continue
            if statement.name == ENTRYPOINT_FUNCTION_NAME:
                # Don't compile main function. It will be added later
                continue
            statement.generate_llvm(context)
        
    def _compile_module_class_methods(self, ast:PProgram, context:CodeGenContext):
        for statement in ast.statements:
            if not isinstance(statement, PClass):
                continue
            for method in statement.methods:
                if method.is_builtin:
                    continue
                method.generate_llvm(context)
    
    def _declare_top_level_declarations(self, ast:PProgram, context:CodeGenContext):
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

    def _generate_user_main_code(self, ast:PProgram, context:CodeGenContext, global_ref_var_count:int=0):
        """Generates user code in the main function"""
        main_func_stmt = None
        #find main function and ensure only ClassDecl, VarDecl and FuncDecl statements are in the global scope
        for statement in ast.statements:
            if isinstance(statement, PFunction):
                if statement.name == ENTRYPOINT_FUNCTION_NAME:
                    main_func_stmt = statement
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

        if main_func_stmt is not None:
            #count the number of defined reference value variables in this scope
            main_scope_ref_var_count = 0
            for stmt in main_func_stmt.body.statements:
                if isinstance(stmt, PVariableDeclaration) and stmt.typer_pass_var_type.is_reference_type:
                    main_scope_ref_var_count += 1

            #enter main function scope and build
            context.enter_scope(main_scope_ref_var_count + global_ref_var_count)
            # make sure to populate globals first and add them to the GC
            populate_globals_func = context.scopes.get_symbol(FUNC_POPULATE_GLOBALS).func_ptr
            assert populate_globals_func is not None
            context.builder.call(populate_globals_func,[])
            main_function_returned = False
            for stmt in main_func_stmt.body.statements:
                if main_function_returned:
                    warn(f"Statement will be ignored as it is unreachable in {stmt.position}",
                        CompilerWarning)
                    continue
                stmt.generate_llvm(context)
                if isinstance(stmt, PReturnStatement):
                    # return has already left the scope and terminated the current block
                    main_function_returned = True
            if not main_function_returned:
                warn(f"No return defined for main function. Adding implicit return 0 in main function in {main_func_stmt.position}",
                    CompilerWarning)
            # do not need to exit scope here because the main function has explicit returns that handle it
        else:
            warn("No main function",
                 CompilerWarning)

    def _init_builtin_functions_prototypes(self, context:CodeGenContext):
        """Adds builtin functions to the global scope"""
        
        def typeref_to_type(typeref:TypeRef) -> ir.Type:
            assert typeref.type_kind in (TypeKind.integer, TypeKind.float,
                                         TypeKind.half, TypeKind.double,
                                         TypeKind.pointer, TypeKind.void)
            if typeref.type_kind == TypeKind.integer:
                return ir.IntType(typeref.type_width)
            elif typeref.type_kind == TypeKind.void:
                return ir.VoidType()
            elif typeref.type_kind == TypeKind.pointer:
                return ir.PointerType()
            elif typeref.type_kind == TypeKind.float:
                return ir.FloatType()
            elif typeref.type_kind == TypeKind.double:
                return ir.DoubleType()
            elif typeref.type_kind == TypeKind.half:
                return ir.HalfType()
            else:
                raise CompilerError(f"Cannot convert TypeRef kind {typeref.type_kind} to Type")
        
        # Retrieve and declare builtins from the runtime
        with open(self._RUNTIME_LIB, 'rb') as runtime_bc:
            runtime_mod = parse_bitcode(runtime_bc.read())
        for runtime_func in runtime_mod.functions:
            #convert TypeRef to Type
            element_types = [typeref_to_type(typeref) for typeref in runtime_func.global_value_type.elements]
            return_type = element_types.pop(0)
            
            func_type = ir.FunctionType(return_type, element_types)
            
            func = ir.Function(context.module,
                               func_type,
                               runtime_func.name)
            context.scopes.declare_func(name=runtime_func.name,
                                        return_type=func.return_value.type,
                                        function_ptr=func)

    def get_llvm_struct(self, typ: IRCompatibleTyp, context:Optional[CodeGenContext]) -> Union[ir.IntType,
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
        assert type_info.type_class in (TypeClass.CLASS, TypeClass.ARRAY, TypeClass.STRING)
        
        if type_info.type_class == TypeClass.CLASS:
            field_types = [
                prop.typer_pass_var_type.get_llvm_value_type(context)
                for prop in typ.fields if isinstance(prop, PClassField)
            ]
            return ir.LiteralStructType(field_types)
            
        
        elif type_info.type_class == TypeClass.ARRAY:
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

        else:
            assert type_info.type_class == TypeClass.STRING
            return ir.LiteralStructType([
                ir.IntType(64), #the string length
                ir.ArrayType(
                    ir.IntType(8), #a char (strings are basically just char arrays)
                    0) #arbitrary size
            ])