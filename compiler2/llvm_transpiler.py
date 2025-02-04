from typer import Typer, ArchProperties, Typ, TypeClass, TypingError
from parser import (PClass,PFunction,PProgram,
                    PStatement, PVariableDeclaration)
from typing import TextIO, List, Dict
from utils import CodeGenContext, Scopes
from llvmlite import ir
import ctypes
from llvmlite.binding import (initialize, initialize_native_target, 
                              initialize_native_asmprinter, PipelineTuningOptions,
                              PassBuilder, Target)

class CodeGen:
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
        arch_size = ctypes.sizeof(ctypes.c_void_p)*8
        # used for pointer size (useful for size calcs and the GC probably?)
        self.typer = Typer(filename, file, ArchProperties(arch_size,
                                                    # set max float & int size to 64bit
                                                    # (llvm will take care if we're not on a 64 bit arch probably)
                                                   max_int_size=64,
                                                   max_float_size=64))
        self.module = ir.Module(name=filename+".o")
        self.builder: ir.IRBuilder = ir.IRBuilder()
        target = Target.from_default_triple().create_target_machine(
            codemodel='jitdefault',
            jit=False,
        )
        self.optimizer_pass = PassBuilder(target, PipelineTuningOptions(speed_opt, size_opt)
                                          ).getModulePassManager()
        self.current_function = None
        self.named_values = Scopes()

    def get_llvm_type(self, type_: Typ) -> ir.Type:
        if type_.name in self.type_map:
            return self.type_map[type_.name]
        
        type_info = self.typer.get_type_info(type_)
        
        if type_info.type_class == TypeClass.ARRAY:
            element_type_name = type_.name[:-2]
            element_typ = self.typer.known_types.get(element_type_name)
            if not element_typ:
                raise ValueError(f"Element type {element_type_name} not found")
            element_llvm_type = self.get_llvm_type(element_typ)
            array_struct = ir.LiteralStructType([
                ir.IntType(32),  # length field
                ir.PointerType(element_llvm_type)  # data pointer
            ])
            self.type_map[type_.name] = array_struct
            return array_struct
        elif type_info.type_class == TypeClass.CLASS:
            field_types = []
            for prop in type_.properties:
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

    def compile_file_to_ir(self, warnings:bool=False):        
        self.ast = self.typer.type_program(warnings)
        
        context = CodeGenContext(module=self.module, builder=self.builder,
                                 scopes=self.named_values, get_llvm_type=self.get_llvm_type)
        self._compile_program(self.ast, context)
        return self.module

    def _compile_program(self, program: PProgram, context:CodeGenContext):
        self.named_values.enter_scope() #for global vars
        main_stmts = []
        classes:List[PClass] = []
        for stmt in program.statements:
            if isinstance(stmt, PClass):
                classes.append(stmt)
                self.register_class_type(stmt, context)
            elif isinstance(stmt, PFunction):
                stmt.generate_llvm(context)
            elif isinstance(stmt, PVariableDeclaration):
                self._compile_declare_global_variable(stmt, context)
            else:
                main_stmts.append(stmt)
        # TODO: here use classes var to define class methods
        
        self._compile_implicit_main_function(main_stmts, context)
        context.scopes.leave_scope()
        #NB: here scopes should be empty
        
    def _compile_implicit_main_function(self, statements:List[PStatement], context:CodeGenContext):
        
        #TODO make implicit __main function here
        # add __main to module
        for stmt in statements:
        # and compile inner
            if isinstance(stmt, PVariableDeclaration):
                self._compile_define_global_variable(stmt, context)
            else:
                stmt.generate_llvm(context)

    def register_class_type(self, cls: PClass, context:CodeGenContext):
        """Register class type and methods"""
        if cls.name in self.type_map:
            return
        class_typ:Typ = self.typer.known_types[cls.name]
        properties:List[Typ] = []
        for prop in class_typ.properties:
            if prop.typer_pass_var_type is None:
                raise TypingError(f"Property {prop.name} of type {cls.name} is not typed!")
            properties.append(prop.typer_pass_var_type)
        self.type_map[cls.name] = ir.LiteralStructType(properties)

    def _compile_declare_global_variable(self, var_decl: PVariableDeclaration, context:CodeGenContext):
        """Declare variable and associate ptr address"""
        var_type = self.get_llvm_type(var_decl.typer_pass_var_type)
        alloca = self.builder.alloca(var_type, name=var_decl.name)
        self.named_values.declare_var(var_decl.name, context.get_llvm_type(var_decl.typer_pass_var_type), alloca)

    def _compile_define_global_variable(self, var_decl: PVariableDeclaration, context:CodeGenContext):
        """Assign value (explicit or default) to variable"""
        global_var = self.named_values.get_var(var_decl.name)
        if var_decl.initial_value is None:
            #no value defined: get default value for type
            init_value = var_decl.typer_pass_var_type.default_llvm_value
        else:
            init_value = var_decl.initial_value.generate_llvm(context)
        self.builder.store(init_value, global_var.alloca)
