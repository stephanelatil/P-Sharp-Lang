from dataclasses import dataclass
from enum import Enum, auto
from typing import Dict

class TypeClass(Enum):
    """Classification of types for conversion rules"""
    VOID = auto()
    BOOLEAN = auto()
    INTEGER = auto()
    FLOAT = auto()
    CHARACTER = auto()
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
    "bool": TypeInfo(TypeClass.BOOLEAN, 8, False),
    "string": TypeInfo(TypeClass.STRING),
    "char": TypeInfo(TypeClass.CHARACTER, 8, False),
    
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
class TypingProperties:
    pointer_size:int=64
    max_int_size:int=64
    max_float_size:int=64
    
    def type_is_supported(self, type_info:TypeInfo) -> bool:
        if type_info.type_class == TypeClass.INTEGER:
            return type_info.bit_width <= self.max_int_size
        
        elif type_info.type_class == TypeClass.FLOAT:
            return type_info.bit_width <= self.max_float_size
        
        raise TypeError("Unknown TypeClass")