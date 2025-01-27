from dataclasses import dataclass, field
from enum import Enum, auto
from typing import Dict


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
