# Hacky way of enabling opaque pointers
# later versions of llvmlite will make this mandatory
import os
os.environ['LLVMLITE_ENABLE_OPAQUE_POINTERS'] = "1"

from typer import Typer, TypeClass, TypingError
from parser import (PClass,PFunction,PProgram, Typ, ArrayTyp,
                    PStatement, PVariableDeclaration)
from typing import TextIO, List, Dict, Optional, Union
from utils import CodeGenContext, Scopes, CompilerError, CompilerWarning
from llvmlite import ir
from warnings import warn
from llvmlite.binding import (initialize, initialize_native_target, 
                              initialize_native_asmprinter, PipelineTuningOptions,
                              PassBuilder, Target, parse_assembly, parse_bitcode,
                              ModuleRef)


class CodeGen:
    _GC_LIB='../garbage_collector/libps_gc.bc'
    
    def __init__(self, filename:str, file:TextIO, speed_opt:int=0, size_opt:int=0) -> None:
        
        #required for code generation (no cross-compile yet, needs initialize_all* for that)
        initialize()
        initialize_native_target()
        initialize_native_asmprinter()
        
        self.type_map: Dict[str, ir.Type] = {
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
            'bool': ir.IntType(1),
            'null': ir.PointerType() # null is a point type (points to nothing but still a pointer technically)
        }
        self.typer = Typer(filename, file)
        self.module = ir.Module(name=filename+".o")
        self.target = Target.from_default_triple().create_target_machine(
            codemodel='jitdefault',
            jit=False,
        )
        self.optimizer_pass = PassBuilder(self.target, PipelineTuningOptions(speed_opt, size_opt)
                                          ).getModulePassManager()
        
    def _init_builtin_functions_prototypes(self, context:CodeGenContext):
        """Adds builtin functions to the global scope"""
        size_t_type = ir.IntType(ir.PointerType().get_abi_size(context.target_data)*8)
        char_ptr = ir.PointerType()
        void_ptr = ir.PointerType()
        void = ir.VoidType()
        
        for name, func_type in [
                            ("__PS_InitRootTracking", ir.FunctionType(void,[])),
                            ("__PS_EnterScope", ir.FunctionType(void,[size_t_type])),
                            ("__PS_LeaveScope", ir.FunctionType(void,[])),
                            ("__PS_CollectGarbage", ir.FunctionType(void,[])),
                            ("__PS_PrintHeapStats", ir.FunctionType(void,[])),
                            ("__PS_Cleanup", ir.FunctionType(void,[])),
                            ("__PS_AllocateObject", ir.FunctionType(void_ptr,[size_t_type])),
                            ("__PS_AllocateValueArray", ir.FunctionType(void_ptr,[size_t_type,size_t_type])),
                            ("__PS_AllocateRefArray", ir.FunctionType(void_ptr,[size_t_type])),
                            ("__PS_RegisterType", ir.FunctionType(size_t_type,[size_t_type, size_t_type, char_ptr])),
                            ("__PS_InitTypeRegistry", ir.FunctionType(void,[size_t_type])),
                            ("__PS_RegisterRoot", ir.FunctionType(void,[void_ptr, size_t_type, char_ptr])),
                                ]:
            func = ir.Function(context.module, func_type, name)
            context.builtin_functions[name] = func
            
    def _get_size(self, context:CodeGenContext, typ:Typ):
        """Returns the size of the type (struct) in bytes"""
        size = 0
        for field in typ.fields:
            field_typ = field.typer_pass_var_type
            if field_typ.is_reference_type:
                size += ir.PointerType().get_abi_size(context.target_data)
            else:
                typeinfo = self.typer.get_type_info(field_typ)
                size += typeinfo.bit_width
                
        return size
        
    def _register_types_to_gc(self, context:CodeGenContext):
        size_t_type = ir.IntType(ir.PointerType().get_abi_size(context.target_data)*8)
        types_list = self.typer.known_types
        for known_type in types_list.values():
            for field in known_type.fields:
                self.typer._type_class_property(field)
        
        i = 2 #first index of a type (0 and 1 are taken up by array types!)
        for typ in types_list.values():
            if not typ.is_reference_type or typ.name in ['void','__null', '__array']:
                continue
            size = ir.Constant(size_t_type, self._get_size(context, typ))
            num_ref_types = ir.Constant(size_t_type, sum([t.typer_pass_var_type.is_reference_type for t in typ.fields]))
            
            #size_t __PS_RegisterType(size_t size, size_t num_pointers, const char* type_name)
            name_c_str = context.get_char_ptr_from_string(typ.name)
            context.builder.call(context.builtin_functions["__PS_RegisterType"],[
                                     size,
                                     num_ref_types,
                                     #convert string to bytes array
                                     name_c_str])
            context.type_ids[typ.name] = i
            i += 1
        
    def _initialize_gc_on_start(self, context:CodeGenContext):
        context.builder.call(context.builtin_functions["__PS_InitRootTracking"],[])
        self._register_types_to_gc(context)
        
    def _cleanup_gc_and_exit(self, context:CodeGenContext):
        context.builder = ir.IRBuilder(context.global_exit_block)
        
        context.builder.call(context.builtin_functions["__PS_Cleanup"],[])
        #exit with given return code
        ret_val = context.scopes.get_var(context._RETURN_CODE_VAR_NAME).alloca
        ret_val = context.builder.load(ret_val)
        context.builder.ret(ret_val)

    def get_llvm_type(self, type_: Typ) -> ir.Type:
        if type_.name in self.type_map:
            return self.type_map[type_.name]
        
        type_info = self.typer.get_type_info(type_)
        
        if type_info.type_class == TypeClass.ARRAY:
            #return a generic array struct (contains an int and a pointer to the array)
            return ir.PointerType()
        elif type_info.type_class == TypeClass.CLASS:
            field_types = []
            for prop in type_.fields:
                prop_typ = self.typer._type_ptype(prop.var_type)
                field_types.append(self.get_llvm_type(prop_typ))
            class_struct = ir.LiteralStructType(field_types)
            self.type_map[type_.name] = class_struct
            return class_struct
        elif type_info.type_class == TypeClass.STRING:
            string_struct = ir.LiteralStructType([
                ir.IntType(32),
                ir.PointerType(ir.IntType(8))
            ])
            self.type_map['string'] = string_struct
            return string_struct
        else:
            raise TypingError(f"Unsupported type: {type_.name}")

    def compile_file_to_ir(self, warnings:bool=False) -> ModuleRef:
        with open(self._GC_LIB, "rb") as f:
            gc_module = parse_bitcode(f.read())
        
        self.ast = self.typer.type_program(warnings)
        
        context = CodeGenContext(target_data=self.target.target_data,
                                 module=self.module, scopes=Scopes(),
                                 get_llvm_type=self.get_llvm_type)
        self._init_builtin_functions_prototypes(context)
        
        self._compile_program(self.ast, context)
        program_module = parse_assembly(str(context.module))
        program_module.link_in(gc_module)
        return program_module
    
    def __init_type_registry(self, context:CodeGenContext):
        """Initialize type registry with correct size"""
        size_t_type = ir.IntType(ir.PointerType().get_abi_size(context.target_data)*8)
        # void __PS_InitTypeRegistry(size_t initial_capacity)
        context.builder.call(context.builtin_functions['__PS_InitTypeRegistry'],
                             [ir.Constant(size_t_type,len(self.typer.known_types))])
        # len(self.typer.known_types) includes value types but having a bit extra space can be optimized later
        # it's fine for now

    def _compile_program(self, program: PProgram, context:CodeGenContext):
        context.scopes.enter_scope() #for global vars
        main_stmts = []
        main_func:Optional[PFunction] = None
        classes:List[PClass] = []
        for stmt in program.statements:
            if isinstance(stmt, PClass):
                classes.append(stmt)
                self.register_class_type(stmt, context)
            elif isinstance(stmt, PFunction):
                if stmt.name == "main":
                    if main_func is not None:
                        raise CompilerError(f"Cannot have multiple 'main' functions in the program!")
                    main_func = stmt
                else:
                    stmt.generate_llvm(context)
            else:
                main_stmts.append(stmt)

        if main_func is not None and len(main_stmts) > 0:
            warn(f"'main' function is defined at {main_func.position}\n instructions outside of functions will not be run!", CompilerWarning)
        self._compile_entrypoint_function(main_stmts, main_func, context=context)
        context.scopes.leave_scope()

    def _compile_entrypoint_function(self, statements:List[PStatement], main_func:Optional[PFunction], context:CodeGenContext):
        """ Generates IR for the entrypoint
            It first runs all freestanding statements then runs the inside of the main function if one is present"""
        func_type = ir.FunctionType(self.type_map['i32'],[])

        # Create function in module
        func = ir.Function(self.module, func_type, name="main")
        context.builder = ir.IRBuilder(func.append_basic_block('__implicit_main_entrypoint'))
        context.global_exit_block = func.append_basic_block('___main_exit_cleanup')
        self._setup_return_code_global(context)
        self.__init_type_registry(context)
        self._initialize_gc_on_start(context)
        
        for stmt in statements:
            if isinstance(stmt, PVariableDeclaration):
                self._compile_declare_global_variable(stmt, context)
            else:
                stmt.generate_llvm(context)
        if main_func is not None:
            for stmt in main_func.body.statements:
                stmt.generate_llvm(context)
        context.builder.branch(context.global_exit_block)
        self._cleanup_gc_and_exit(context)

    def register_class_type(self, cls: PClass, context:CodeGenContext):
        """Register class type and methods"""
        if cls.name in self.type_map:
            return
        class_typ:Typ = self.typer.known_types[cls.name]
        properties:List[Typ] = []
        for prop in class_typ.fields:
            if prop.typer_pass_var_type is None:
                raise TypingError(f"Property {prop.name} of type {cls.name} is not typed!")
            properties.append(prop.typer_pass_var_type)
        self.type_map[cls.name] = ir.LiteralStructType(properties)

    def _compile_declare_global_variable(self, var_decl: PVariableDeclaration, context:CodeGenContext):
        """Declare variable and associate ptr address"""
        var_type = self.get_llvm_type(var_decl.typer_pass_var_type)
        # alloca = self.builder.alloca(var_type, name=var_decl.name)
        alloca = ir.GlobalVariable(context.module, var_type, var_decl.name)
        context.scopes.declare_var(var_decl.name, context.get_llvm_type(var_decl.typer_pass_var_type), alloca)
        # Assign value (explicit or default) to variable
        if var_decl.initial_value is None:
            #no value defined: get default value for type
            init_value = var_decl.typer_pass_var_type.default_llvm_value
        else:
            init_value = var_decl.initial_value.generate_llvm(context)
        context.builder.store(init_value, alloca)
        
    def _setup_return_code_global(self, context:CodeGenContext, default_value:int=0):
        """Sets the default main return value to the given value
        Here it's set to a variable value so that each "return" instruction from the main function
        actually sets this value and jumps to the GC Cleanup

        Args:
            context (CodeGenContext): The CodeGenContext used for this module
            default_value (int, optional): Th default return code of the program. Defaults to 0.
        """
        global_var = ir.GlobalVariable(context.module, ir.IntType(32),
                                       name=context._RETURN_CODE_VAR_NAME)
        context.scopes.declare_var(context._RETURN_CODE_VAR_NAME, global_var.value_type, global_var)
        context.builder.store(ir.Constant(global_var.value_type, default_value), global_var)
