from enum import IntEnum, StrEnum, Enum
from dataclasses import dataclass, field

class LLVM_Version(IntEnum):
    v15=15
    v16=16
    v17=17
    v18=18
    v19=19
    
    def suffix(self):
        return f"-{self.value}"
    
class OutputFormat(StrEnum):
    """The supported output formats for the compiler"""
    """LLVM IR, human readable intermediate representation"""
    IntermediateRepresentation="ir"
    """LLVM BitCode, machine readable intermediate representation"""
    BitCode="bc"
    """Native assembly code for the platform"""
    Assembly="asm"
    """An object file to be compiled and/or linked further to an executable"""
    Object="obj"
    """An executable format (Or library if flag is set)"""
    Executable="exe"
    
class OptimisationLevel(Enum):
    Zero = '0'
    One = '1'
    Two = '2'
    Three = '3'
    Size = 's'

@dataclass
class CompilationOptions:
    optimisation_level:OptimisationLevel = OptimisationLevel.Zero
    add_debug_symbols:bool = False
    is_library:bool = False