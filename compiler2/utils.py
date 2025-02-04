from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Optional, List, Dict, Callable, Any
from llvmlite import ir

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
    alloca:Optional[ir.AllocaInstr]=None
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
        self.scope_vars["name"] = VarInfo(name, return_type, func_ptr=function_ptr)
        
    def declare_var(self, name:str, type_:ir.Type, alloca:ir.AllocaInstr):
        if name in self.scope_vars:
            raise CompilerError(f"Variable already exists!")
        self.scope_vars["name"] = VarInfo(name, type_, alloca=alloca)
        
    def get_var(self, name:str) -> Optional[VarInfo]:
        return self.scope_vars.get(name, None)


class Scopes:
    def __init__(self):
        self.scopes:List[ScopeVars] = []
        self.tmp_func_stack = []

    def enter_scope(self):
        self.scopes.append(ScopeVars())

    def leave_scope(self):
        self.scopes.pop()

    def declare_var(self, name:str, type_:ir.Type, alloca:ir.AllocaInstr):
        self.scopes[-1].declare_var(name, type_, alloca)
        
    def declare_func(self, name:str, return_type:ir.Type, function_ptr:ir.Function):
        self.declare_func(name, return_type, function_ptr)
        
    def enter_func_scope(self):
        self.tmp_func_stack.append(self.scopes[1:].copy())
        self.scopes = [self.scopes[0]]
        self.enter_scope()
        
    def leave_func_scope(self):
        self.leave_scope()
        self.scopes = [self.scopes[0], *self.tmp_func_stack.pop()]

    def get_var(self, name:str):
        for scope in self.scopes[::-1]:
            var_info = scope.get_var(name)
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
    builder:ir.IRBuilder
    scopes:Scopes
    """A function that take a Typ and returns a ir.Type associated (int, float ot struct types or pointers for all other types)"""
    get_llvm_type: Callable[['Typ'],ir.Type]