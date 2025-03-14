from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Optional, List, Dict, Tuple, Union
from llvmlite import ir, binding

class Position:
    default:'Position'
    
    def __init__(self, line:int = 1, column:int = 1, index:int = 0, filename:str='??'):
        self.line = line
        self.column = column
        self.index = index
        self.filename = filename

    def advance(self, char:str):
        if char == '\n':
            self.line += 1
            self.column = 1
        else:
            self.column += 1
        self.index += 1

    def copy(self) -> 'Position':
        return Position(self.line, self.column, self.index, self.filename)

    def __add__(self, num_chars:int):
        return Position(self.line, self.column+num_chars, self.index+num_chars, self.filename)
    
    def __str__(self):
        return f'File "{self.filename}", line {self.line}, column {self.column}'
    
Position.default = Position()

@dataclass
class CompilerWarning(Warning):
    message:str
    position:Position = field(default_factory=Position)
    
    def __str__(self):
        return self.message + f" at location {self.position}"

class TypingError(Exception):
    def __init__(self, msg) -> None:
        super().__init__(msg)

class TypeClass(Enum):
    """Classification of types for conversion rules"""
    VOID = auto()
    BOOLEAN = auto()
    INTEGER = auto()
    FLOAT = auto()
    STRING = auto()
    ARRAY = auto()
    CLASS = auto()

@dataclass
class TypeInfo:
    """Information about a type including its class and size"""
    type_class: TypeClass
    bit_width: int = 0  # For numeric types
    is_signed: bool = True  # For integer types
    is_builtin: bool = True

# Mapping of type names to their TypeInfo
TYPE_INFO: Dict[str, TypeInfo] = {
    "void": TypeInfo(TypeClass.VOID),
    "bool": TypeInfo(TypeClass.BOOLEAN, 1, False),
    "string": TypeInfo(TypeClass.STRING),
    "char": TypeInfo(TypeClass.INTEGER, 8, False),

    # Signed integers
    "i8": TypeInfo(TypeClass.INTEGER, 8, True),
    "i16": TypeInfo(TypeClass.INTEGER, 16, True),
    "i32": TypeInfo(TypeClass.INTEGER, 32, True),
    "i64": TypeInfo(TypeClass.INTEGER, 64, True),

    # Unsigned integers
    "u8": TypeInfo(TypeClass.INTEGER, 8, False),
    "u16": TypeInfo(TypeClass.INTEGER, 16, False),
    "u32": TypeInfo(TypeClass.INTEGER, 32, False),
    "u64": TypeInfo(TypeClass.INTEGER, 64, False),

    # Floating point
    "f16": TypeInfo(TypeClass.FLOAT, 16),
    "f32": TypeInfo(TypeClass.FLOAT, 32),
    "f64": TypeInfo(TypeClass.FLOAT, 64),
}


@dataclass
class VarInfo:
    name:str
    type_:ir.Type
    alloca:Optional[ir.NamedValue]=None
    """This is useful to know if the var needs to be explicitly dereferenced! A global var is a pointer to the given type"""
    is_global:bool=False
    func_ptr:Optional[ir.Function]=None
    
    @property
    def is_function(self) -> bool:
        return self.func_ptr is not None

class ScopeVars:
    def __init__(self):
        self.scope_vars = {}
        
    def declare_func(self, name:str, return_type:ir.Type, function_ptr:ir.Function):
        if name in self.scope_vars:
            raise CompilerError(f"Variable already exists!")
        self.scope_vars[name] = VarInfo(name, return_type, func_ptr=function_ptr)
        
    def declare_var(self, name:str, type_:ir.Type, alloca:ir.NamedValue, is_global:bool=False):
        if name in self.scope_vars:
            raise CompilerError(f"Variable already exists!")
        self.scope_vars[name] = VarInfo(name, type_, alloca=alloca, is_global=is_global)
        
    def get_symbol(self, name:str) -> Optional[VarInfo]:
        return self.scope_vars.get(name, None)

class Scopes:
    def __init__(self):
        self.scopes:List[ScopeVars] = []
        self.tmp_func_stack = []

    def enter_scope(self):
        self.scopes.append(ScopeVars())

    def leave_scope(self):
        self.scopes.pop()

    def declare_var(self, name:str, type_:ir.Type, alloca:ir.NamedValue, is_global:bool=False):
        self.scopes[-1].declare_var(name, type_, alloca, is_global)
        
    def declare_func(self, name:str, return_type:ir.Type, function_ptr:ir.Function):
        self.scopes[-1].declare_func(name, return_type, function_ptr)
        
    def enter_func_scope(self):
        self.tmp_func_stack.append(self.scopes[1:].copy())
        self.scopes = [self.scopes[0]]
        self.enter_scope()
        
    def leave_func_scope(self):
        self.leave_scope()
        self.scopes = [self.scopes[0], *self.tmp_func_stack.pop()]
        
    def has_symbol(self, name:str) -> bool:
        """Checks if a given symbol is known

        Args:
            name (str): _description_

        Returns:
            bool: _description_
        """
        for scope in self.scopes[::-1]:
            var_info = scope.get_symbol(name)
            if var_info is not None:
                return True
        return False

    def get_symbol(self, name:str) -> VarInfo:
        for scope in self.scopes[::-1]:
            var_info = scope.get_symbol(name)
            if var_info is not None:
                return var_info
        
        raise CompilerError(f"Unable to find variable {name}")
    
    def get_global_scope(self):
        return self.scopes[0]

class CompilerError(Exception):
    def __init__(self, msg):
        super().__init__(msg)
        self.msg = msg
        
    def __str__(self):
        return f"Compiler Error: {self.msg}"

@dataclass
class CodeGenContext:
    """Context needed by various node when generating IR in the codegen pass"""
    module:ir.Module
    scopes:Scopes
    target_data:binding.TargetData
    # """A function that take a Typ and returns a ir.Type associated (int, float ot struct types or pointers for all other types)"""
    # get_llvm_type: Callable[['Typ'],ir.Type]
    """A dict containing all Types known to the typer and it's corresponding ir.Type"""
    type_map:Dict['Typ', Union[ir.IntType,ir.HalfType,ir.FloatType,ir.DoubleType,ir.VoidType,ir.LiteralStructType]]
    """A stack of tuples pointing to (condition block of loop: for continues, end of loop for break)"""
    loopinfo:List[Tuple[ir.Block, ir.Block]] = field(default_factory=list)
    builder:ir.IRBuilder = ir.IRBuilder()
    global_exit_block:Optional[ir.Block]=None
    type_ids:Dict[str, int] = field(default_factory=dict)
    """A Dict where for every given string there is an associated constant string PS object. constant because strings are immutable"""
    _global_string_objs:Dict[str, ir.GlobalValue] = field(default_factory=dict)
    
    def get_string_const(self, string:str):
        if string in self._global_string_objs:
            return self._global_string_objs[string]
        # ensure string is null terminated to be a proper c_str
        if not string.endswith('\x00'):
            null_terminated_string = string + '\x00'
        else:
            null_terminated_string = string
            
        #Build c string
        string_bytes = null_terminated_string.encode('utf-8')
        string_typ = ir.LiteralStructType([
            ir.IntType(64),
            ir.ArrayType(ir.IntType(8), len(string_bytes))
        ])
        #store constant value globally
        string_obj = ir.GlobalVariable(module=self.module,
                                       typ=string_typ,
                                       name=f".__str_obj_{len(self._global_string_objs)}")
        string_obj.initializer = ir.Constant(string_typ, [len(null_terminated_string), bytearray(string_bytes)])
        #cache value to avoid saturating executable
        self._global_string_objs[string] = string_obj
        return string_obj
    
    def get_char_ptr_from_string(self, string:str):
        """Adds a Global string with the given value (if none already exists) and returns a GEP pointer to the first character (char* c string style)

        Args:
            string (str): The python string to convert to a llvm c-style string

        Returns:
            GEPInstr: a GEP instruction pointer value to the c-string
        """
        # if not string.endswith('\x00'):
        #     string += '\x00'
        # if string not in self._global_c_strings:
        #     string_bytes = string.encode('utf-8')
        #     c_string_type = ir.ArrayType(ir.IntType(8), len(string_bytes))
        #     c_str = ir.GlobalVariable(self.module, c_string_type, name=f".__str_{len(self._global_c_strings)}")
        #     c_str.initializer = ir.Constant(c_string_type, bytearray(string_bytes))
        #     c_str.global_constant = True
        #     self._global_c_strings[string] = c_str
        # else:
        #     c_str = self._global_c_strings[string]
        #     assert isinstance(c_str.type, ir.types._TypedPointerType)
        #     c_string_type = c_str.type.pointee
        string_obj = self.get_string_const(string)
        assert isinstance(string_obj.type, ir.types._TypedPointerType)
        string_typ = string_obj.type.pointee
        zero = ir.Constant(ir.IntType(32), 0)
        one = ir.Constant(ir.IntType(32), 1)
        return self.builder.gep(string_obj, [zero, one, zero], inbounds=True, source_etype=string_typ)
    
    def get_method_symbol_name(self, class_name:str, method_identifier:str):
        return f"__{class_name}.__{method_identifier}"