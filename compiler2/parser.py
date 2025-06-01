from typing import List, Optional, Dict, Any, Union, Generator, ClassVar
from collections import deque
from dataclasses import dataclass, field
from enum import Enum, auto
from lexer import Lexer, LexemeType, Lexeme, Position
from operations import BinaryOperation, UnaryOperation, TernaryOperator
from llvmlite import ir, binding
from llvmlite.ir._utils import _HasMetadata
from pathlib import Path
from constants import *
from warnings import warn
from objs import CompilationOptions

class ParserWarning(Warning):
    pass

class LexemeStream:
    def __init__(self, lexemes:Generator[Lexeme, None, None], filename:str):
        self.lexeme_gen = lexemes
        self.buffer = deque()
        self.pos = Position(filename=filename)
        self._saved_pos = [0]
        
    def _advance_buffer(self, to_read:int=128):
        """Read ahead N tokens to refill buffer. Stops if reaches EOF"""
        for i in range(to_read):
            lexeme = next(self.lexeme_gen, None)
            if not lexeme:
                raise EOFError()
            self.buffer.append(lexeme)
        
    @property
    def _index(self):
        return sum(self._saved_pos)
    
    def _purge_buffer_of_non_saved_tokens(self):
        if len(self._saved_pos) == 1:
            #no saved position, purge deque of read lexemes
            for i in range(self._saved_pos[0]):
                self.buffer.popleft()
            self._saved_pos[0] = 0
    
    def save_position(self):
        self._saved_pos.append(0)
    
    def drop_saved_position(self):
        assert len(self._saved_pos) > 1
        curr_offset = self._saved_pos.pop()
        #ran on 2 lines to make sure that the index we want to write to is not popped
        self._saved_pos[-1] += curr_offset
        self._purge_buffer_of_non_saved_tokens()
    
    def pop_saved_position(self):
        assert len(self._saved_pos) > 1
        self._saved_pos.pop()
        self._purge_buffer_of_non_saved_tokens()

    def peek(self, amount=0) -> Lexeme:
        try:
            while len(self.buffer) <= amount + self._index:
                self._advance_buffer()
        except EOFError:
            if len(self.buffer) <= amount + self._index:
                return Lexeme.default

        return self.buffer[self._index + amount]

    def advance(self) -> Lexeme:
        lexeme = self.peek()
        if lexeme is not None:
            if len(self._saved_pos) > 1:
                self._saved_pos[-1] += 1
            else:
                self.buffer.popleft()
            self.pos = lexeme.pos
        if lexeme is None:
            raise EOFError()
        return lexeme

    def position(self) -> Position:
        return self.pos.copy()

class TypeClass(Enum):
    """Classification of types for conversion rules"""
    VOID = auto()
    BOOLEAN = auto()
    INTEGER = auto()
    FLOAT = auto()
    STRING = auto()
    ARRAY = auto()
    CLASS = auto()
    FUNCTION = auto()

@dataclass
class TypeInfo:
    """Information about a type including its class and size"""
    type_class: TypeClass
    bit_width: int = 0  # For numeric types
    is_signed: bool = True  # For integer types
    is_builtin: bool = True

@dataclass
class UseCheckMixin:
    """Mixin used to check whether a symbol or field/method or similar has been written to or read"""
    is_assigned: bool
    """Flag for whether the symbol is assigned (Automatically True if it's a global or imported value)"""
    is_read: bool 
    """Flag for whether the symbol is read (Should be after assignment)"""
    def __init__(self, *args, is_assigned=False, is_read=False, **kwargs):
        super().__init__(*args, **kwargs)
        self.is_assigned = is_assigned
        self.is_read = is_read

@dataclass
class Symbol(UseCheckMixin):
    name:str
    declaration_position:Position
    ir_alloca:Optional[ir.NamedValue]=None
    ir_func:Optional[ir.Function]=None
    _typ:Optional[Union['BaseTyp', 'TypeTyp']] = None
    arguments:Optional[List['PVariableDeclaration']] = None # only used if it's a callable
    ambiguous_other_declarations:List['Symbol'] = field(default_factory=list)
    
    def __init__(self, name:str, declaration_position:Position,
                 ir_alloca:Optional[ir.NamedValue]=None, ir_func:Optional[ir.Function]=None,
                 _typ:Optional['BaseTyp'] = None,
                 arguments:Optional[List['PVariableDeclaration']] = None,
                 is_assigned:bool = False, is_read:bool = False):
        self.name = name
        self.declaration_position = declaration_position
        self.ir_alloca = ir_alloca
        self.ir_func = ir_func
        self._typ = _typ
        self.arguments = arguments
        self.is_assigned = is_assigned
        self.is_read = is_read
        
    @property
    def is_ambiguous(self) -> bool:
        return len(self.ambiguous_other_declarations) > 0
    
    @property
    def typ(self) -> Union['BaseTyp', 'TypeTyp']:
        if self._typ is None:
            raise TypingError('Symbol not typed yet')
        return self._typ
    
    @typ.setter
    def typ(self, value:Union['BaseTyp', 'TypeTyp']):
        assert isinstance(value, (BaseTyp, TypeTyp))
        self._typ = value
        
    @property
    def is_function(self):
        return isinstance(self.typ, FunctionTyp)
    
    @property
    def is_namespace(self):
        return isinstance(self.typ, NamespaceTyp)
    
    @property
    def is_variable(self):
        return isinstance(self.typ, (ReferenceTyp, ValueTyp))
    
    def __hash__(self) -> int:
        return (hash(self.name) << 13) + hash(self.declaration_position)

    def __eq__(self, value: object) -> bool:
        if not isinstance(value, Symbol):
            return False
        return (self.name == value.name
                and self._typ == value._typ
                and self.is_namespace == value.is_namespace
                and self.is_function == value.is_function
                and self.is_variable == value.is_variable)

class TypContainer:
    @property
    def typ_element(self) -> 'BaseTyp':
        if isinstance(self, TypeTyp):
            return self.pointed_type
        assert isinstance(self, BaseTyp)
        return self

@dataclass
class BaseTyp(TypContainer):
    """Represents a type in the P# language with its methods and fields"""
    name:str
    parent_namespace:Optional['NamespaceTyp']
    symbol:'Symbol'
    
    def __init__(self, name:str,
                 parent_namespace:Optional['NamespaceTyp']=None,
                 declaration_position:Position=Position.default):
        self.name = name
        self.parent_namespace = parent_namespace
        self.symbol = Symbol(self.name,
                             declaration_position=declaration_position)
        self.symbol.typ = TypeTyp(self)
        self.symbol.is_assigned = True
    
    def __hash__(self) -> int:
        return hash(self.name)
    
    def __eq__(self, value: object) -> bool:
        if not isinstance(value, BaseTyp):
            return False
        return self.name == value.name

    def __str__(self):
        return self.name
    
    @property
    def is_reference_type(self) -> bool:
        return isinstance(self, ReferenceTyp)
    
    @property
    def full_name(self) -> str:
        """Returns the type's full name with parent namespaces and without aliases"""
        if self.parent_namespace is None:
            return self.name
        return f"{self.parent_namespace.full_name}.{self.name}"

@dataclass
class IRCompatibleTyp(BaseTyp):
    fields: Dict[str, 'PClassField'] = field(default_factory=dict)
    #TODO place methods in "fields" because a method is a valid field and it's typed
    methods: Dict[str, 'PMethod'] = field(default_factory=dict)
    default:ClassVar['IRCompatibleTyp'] = None #type: ignore # this is just a placeholder it will be populated after the class definition
    _cached_di_type:Optional[ir.DIValue] = None
    type_info:TypeInfo = field(default_factory=lambda : TypeInfo(TypeClass.CLASS, is_builtin=False))
    
    def __init__(self,name: str,
                 parent_namespace: Optional['NamespaceTyp']=None,
                 declaration_position:Position=Position.default,
                 fields:Optional[Dict[str, 'PClassField']]=None,
                 methods:Optional[Dict[str, 'PMethod']]=None,
                 type_info:Optional[TypeInfo]=None):
        super().__init__(name=name,
                         parent_namespace=parent_namespace,
                         declaration_position=declaration_position)
        self.fields = fields or {}
        self.methods = methods or {}
        self._cached_di_type = None
        self.type_info = type_info or TypeInfo(TypeClass.CLASS, is_builtin=False)
    
    def __eq__(self, value: object) -> bool:
        return super().__eq__(value)
    
    def __hash__(self) -> int:
        return super().__hash__()
    
    def di_type(self, context:'CodeGenContext') -> Optional[ir.DIValue]:
        raise NotImplementedError()
    
    def default_llvm_value(self, context:'CodeGenContext') -> ir.Constant:
        raise NotImplementedError()
    
    def get_llvm_value_type(self, context:'CodeGenContext') -> ir.Type:
        """Returns the llvm value-Type corresponding to the IRCompatibleTyp. All reference types will return an ir.PointerType

        Returns:
            ir.Type: The value type of this type. It's either a PointerType, VoidType, IntType or some FloatType (depending on bit-width)
        """
        raise NotImplementedError()

@dataclass
class ValueTyp(IRCompatibleTyp):
    def __init__(self,name: str,
                 parent_namespace: Optional['NamespaceTyp']=None,
                 declaration_position:Position=Position.default,
                 fields:Optional[Dict[str, 'PClassField']]=None,
                 methods:Optional[Dict[str, 'PMethod']]=None,
                 type_info:Optional[TypeInfo]=None):
        super().__init__(name=name,
                         parent_namespace=parent_namespace,
                         declaration_position=declaration_position,
                         fields=fields,
                         methods=methods,
                         type_info=type_info)
    
    def __eq__(self, value: object) -> bool:
        return super().__eq__(value)
    
    def __hash__(self) -> int:
        return super().__hash__()

    def di_type(self, context:'CodeGenContext') -> Optional[ir.DIValue]:
        if self._cached_di_type is not None:
            return self._cached_di_type
        ditype = None
        tinfo = self.type_info
        if self.name == 'char':
            ditype = context.module.add_debug_info("DIBasicType",
                                                    {
                                                    "name":self.name,
                                                    "size":tinfo.bit_width,
                                                    "encoding": ir.DIToken("DW_ATE_signed_char") if tinfo.is_signed else ir.DIToken("DW_ATE_unsigned_char")
                                                    })
        elif tinfo.type_class == TypeClass.INTEGER:
            ditype = context.module.add_debug_info("DIBasicType",
                                                    {
                                                    "name":self.name,
                                                    "size":tinfo.bit_width,
                                                    "encoding": ir.DIToken("DW_ATE_signed") if tinfo.is_signed else ir.DIToken("DW_ATE_unsigned")
                                                    })
        elif tinfo.type_class == TypeClass.BOOLEAN:
            ditype = context.module.add_debug_info("DIBasicType",
                                                    {
                                                    "name":self.name,
                                                    "size":tinfo.bit_width,
                                                    "encoding": ir.DIToken("DW_ATE_boolean")
                                                    })
        elif tinfo.type_class == TypeClass.FLOAT:
            ditype = context.module.add_debug_info("DIBasicType",
                                                    {
                                                    "name":self.name,
                                                    "size":tinfo.bit_width,
                                                    "encoding": 4#"DW_ATE_float"
                                                    })
        elif tinfo.type_class == TypeClass.VOID:
            return None
        #set in cache
        self._cached_di_type = ditype
        return ditype
    
    def get_llvm_value_type(self, context:'CodeGenContext') -> ir.Type:
        """Returns the llvm value-Type corresponding to the IRCompatibleTyp. All reference types will return an ir.PointerType

        Returns:
            ir.Type: The value type of this type. It's either a PointerType, VoidType, IntType or some FloatType (depending on bit-width)
        """
        type_map = {
            'void': ir.VoidType(),
            'f16': ir.HalfType(),
            'f32': ir.FloatType(),
            'f64': ir.DoubleType(),
            #TODO string should be in std?
            'string': ir.PointerType(ir.LiteralStructType([
                ir.IntType(ir.PointerType().get_abi_size(context.target_data)),
                ir.ArrayType(ir.IntType(8), 0)])),
            'null': ir.PointerType() # null is a point type (points to nothing but still a pointer technically)
        }
        
        if self.name in type_map:
            return type_map[self.name]
        elif self.type_info.type_class in [TypeClass.INTEGER, TypeClass.BOOLEAN]:
            return ir.IntType(self.type_info.bit_width)
        raise TypingError(f"Unknown value type {self.name}")
    
    def default_llvm_value(self, context:'CodeGenContext'):
        # return ir.Constant(context.type_map[self], None)
        return ir.Constant(self.get_llvm_value_type(context), None)

@dataclass
class ReferenceTyp(IRCompatibleTyp):
    def __init__(self,name: str,
                 parent_namespace: Optional['NamespaceTyp']=None,
                 declaration_position:Position=Position.default,
                 fields:Optional[Dict[str, 'PClassField']]=None,
                 methods:Optional[Dict[str, 'PMethod']]=None,
                 type_info:Optional[TypeInfo]=None):
        super().__init__(name=name,
                         parent_namespace=parent_namespace,
                         declaration_position=declaration_position,
                         fields=fields,
                         methods=methods,
                         type_info=type_info)

    def __eq__(self, value: object) -> bool:
        return super().__eq__(value)
    
    def __hash__(self) -> int:
        return super().__hash__()
   
    def get_llvm_value_type(self, context: 'CodeGenContext') -> ir.Type:
        if context is None:
            return ir.PointerType()
        else:
            return ir.PointerType(context.type_map[self])
        
    def di_type(self, context:'CodeGenContext') -> Optional[ir.DIValue]:
        if self._cached_di_type is not None:
            return self._cached_di_type
        
        ditype = None
        if self.name == 'string':
            string_length_bitlength = ir.IntType(64).get_abi_size(context.target_data)*8
            string_length = context.module.add_debug_info("DIDerivedType",
                                            {   # string size (excluding null ptr)
                                                "tag":ir.DIToken("DW_TAG_member"),
                                                "name": "Length",
                                                "baseType": context.type_by_name("i64").di_type(context),
                                                "size": string_length_bitlength,
                                            })
            ditype = context.module.add_debug_info("DICompositeType",
                            {
                                "tag" : ir.DIToken("DW_TAG_structure_type"),
                                "name": "string",
                                "elements":[
                                    string_length, 
                                    # string of chars
                                    context.module.add_debug_info("DIDerivedType",{
                                        "tag":ir.DIToken("DW_TAG_member"),
                                        "name": "c-string",
                                        "offset":string_length_bitlength,
                                        "baseType":context.module.add_debug_info("DIStringType",{
                                            "name":"string_value",
                                            "stringLength": string_length
                                        })
                                    })
                                ]
                            })
            #pointer to string
            ditype = context.module.add_debug_info("DIDerivedType",
                                {
                                    "tag":ir.DIToken("DW_TAG_pointer_type"),
                                    "name":f"__{self.name}_reference",
                                    "baseType": ditype,
                                    "size":ir.PointerType().get_abi_size(context.target_data)*8
                                })
        else: # A user defined class
            offset = 0
            elements = list()
            #type field list 
            for field in self.fields:
                assert isinstance(field, PClassField)
                elements.append(context.module.add_debug_info("DIDerivedType",
                                        {
                                            "tag":ir.DIToken("DW_TAG_member"),
                                            "name": field.name,
                                            "offset": offset,
                                            "baseType": field.typer_pass_var_type.di_type(context)
                                        }))
                corresponding_ir_type = field.typer_pass_var_type.get_llvm_value_type(context)
                offset += 8*corresponding_ir_type.get_abi_size(context.target_data)
                
            ditype = context.module.add_debug_info("DICompositeType",
                            {
                                "tag" : ir.DIToken("DW_TAG_structure_type"),
                                "name": self.name,
                                "elements": elements
                            })
            #pointer to ref type
            ditype = context.module.add_debug_info("DIDerivedType",
                                {
                                    "tag":ir.DIToken("DW_TAG_pointer_type"),
                                    "name":f"ptr to {self.name}",
                                    "baseType": ditype,
                                    "size":ir.PointerType().get_abi_size(context.target_data)*8
                                })
        return ditype
    
    def default_llvm_value(self, context: 'CodeGenContext') -> ir.Constant:
        return ir.Constant(ir.PointerType(), ir.PointerType.null)

@dataclass
class ArrayTyp(ReferenceTyp):
    def __init__(self, element_type:IRCompatibleTyp):
        self.element_typ:IRCompatibleTyp = element_type        
        methods:Dict[str, PMethod] = {}
        fields:Dict[str, PClassField] = {"Length":PClassField("Length",
                                                            #TODO make global Const somewhere to define if array length is a i64 or i32
                                                            PType('i64', Lexeme.default),
                                                            field_index=0,
                                                            lexeme=Lexeme.default,
                                                            is_public=True,
                                                            is_builtin=True,
                                                            default_value=None)
                                    }
        
        super().__init__(f'{element_type.name}[]',
                         methods=methods,
                         fields=fields, #type: ignore
                         parent_namespace=NamespaceTyp.builtin)
        self.type_info.type_class = TypeClass.ARRAY
        self.type_info.is_builtin = True
    
    def __eq__(self, value: object) -> bool:
        return super().__eq__(value)
    
    def __hash__(self) -> int:
        return super().__hash__()
    
    def di_type(self, context: 'CodeGenContext'):
        if self._cached_di_type is not None:
            return self._cached_di_type
        
        assert len(self.fields) == 1 and "Length" in self.fields
        assert isinstance(self.fields["Length"], PClassField)
        length_field_type:IRCompatibleTyp = self.fields["Length"].typer_pass_var_type
        length_field_size = (length_field_type.get_llvm_value_type(context)
                                              .get_abi_size(context.target_data)*8)
        
        element_array_type = context.module.add_debug_info("DICompositeType",
                                                {
                                                    "tag":ir.DIToken('DW_TAG_array_type'),
                                                    "baseType": self.element_typ.di_type(context),
                                                    "size": 0
                                                })
        
        ditype = context.module.add_debug_info("DICompositeType",
                        {
                            "tag" : ir.DIToken("DW_TAG_structure_type"),
                            "name": self.name,
                            "elements":[
                                context.module.add_debug_info("DIDerivedType",
                                        {   #array_size
                                            "tag":ir.DIToken("DW_TAG_member"),
                                            "name": "Length",
                                            "baseType": length_field_type.di_type(context),
                                            "size": length_field_size,
                                            "offset":0
                                        }), 
                                # array elements
                                context.module.add_debug_info("DIDerivedType",{
                                        "tag":ir.DIToken("DW_TAG_member"),
                                        "name":"elements",
                                        "baseType": element_array_type,
                                        "offset": length_field_size,
                                    })
                            ]
                        })
        self._cached_di_type = ditype
        return ditype

@dataclass
class FunctionTyp(IRCompatibleTyp):
    return_type:IRCompatibleTyp = IRCompatibleTyp.default
    arguments:List[IRCompatibleTyp] = field(default_factory=list)
    is_method:bool = False
    
    def __init__(self,
                 decl_position:Position,
                 return_type:IRCompatibleTyp = IRCompatibleTyp.default,
                 arguments:Optional[List[IRCompatibleTyp]] = None,
                 is_method:bool = False,
                 parent_namespace:Optional['NamespaceTyp']=None):
        self.return_type = return_type
        self.arguments = arguments or list()
        #TODO for future use with delegate/function types in the code
        func_symbol = Symbol("fn<>",
                            declaration_position=decl_position)
        func_symbol.typ = self        
        super().__init__(f"fn<{','.join(str(arg) for arg in self.arguments)}=>{self.return_type}",
                         parent_namespace=parent_namespace)
        self.is_method = is_method
        self.type_info.type_class = TypeClass.FUNCTION

    def __eq__(self, value: object) -> bool:
        return super().__eq__(value)
    
    def __hash__(self) -> int:
        return super().__hash__()
    
    def di_type(self, context:'CodeGenContext') -> Optional[ir.DIValue]:
        if self._cached_di_type is not None:
            return self._cached_di_type
        ditype = context.module.add_debug_info("DISubroutineType",
                                    {
                                        "types": [self.return_type.di_type(context)]+\
                                                    [arg.di_type(context) for arg in self.arguments]
                                    })
        self._cached_di_type = ditype
        return ditype
    
    def default_llvm_value(self, context:'CodeGenContext') -> ir.Constant:
        raise NotImplementedError()
    
    def get_llvm_value_type(self, context:'CodeGenContext') -> ir.Type:
        """Returns the llvm value-Type corresponding to the IRCompatibleTyp. All reference types will return an ir.PointerType

        Returns:
            ir.Type: The value type of this type. It's either a PointerType, VoidType, IntType or some FloatType (depending on bit-width)
        """
        raise NotImplementedError()

## TODO in unsafe context
# @dataclass    
# class PointerTyp(IRCompatibleTyp):
#     pass

# ????
# @dataclass
# class FunctionPointerTyp(PointerType):
#     pass

# ????
# @dataclass
# The type for 
# class ClassTyp(BaseType):
#     pass

@dataclass
class TypeTyp(TypContainer):
    pointed_type:BaseTyp

@dataclass
class NamespaceTyp(BaseTyp):
    fields: Dict[str, Union['PClass', 'PFunction', 'PVariableDeclaration', 'PIdentifier']] = field(default_factory=dict)
    builtin:ClassVar['NamespaceTyp'] = None #type: ignore # this is just a placeholder it will be populated after the class definition
    
    def __init__(self, name:str, fields:Optional[Dict[str, Union['PClass', 'PFunction', 'PVariableDeclaration', 'PIdentifier']]]=None,
                 parent_namespace:Optional['NamespaceTyp']=None):
        """Creates a new namespace type. The fields is used to defined what is available to import from this namespace

        Args:
            name (str): The name of this namespace
            fields (List[PIdentifier]): The list of global vars functions and types that are usable when imported from this namespace
        """
        
        super().__init__(name, parent_namespace=parent_namespace)
        self.fields = fields or dict()
    
    def __eq__(self, value: object) -> bool:
        return isinstance(value, NamespaceTyp) and value.full_name == self.full_name
        
    def di_type(self, context: 'CodeGenContext') -> Optional[ir.DIValue]:
        raise NotImplementedError('A namespace does not have a type')

    def get_llvm_value_type(self, context: Optional['CodeGenContext']):
        raise NotImplementedError('A namespace does not have a type')
    
NamespaceTyp.builtin = NamespaceTyp(BUILTIN_NAMESPACE)
IRCompatibleTyp.default = ValueTyp("void", parent_namespace=NamespaceTyp.builtin,
                                   type_info=TypeInfo(TypeClass.VOID))

class ParserError(Exception):
    """Custom exception for parser-specific errors"""
    def __init__(self, message: str, lexeme: Lexeme):
        self.message = message
        self.lexeme = lexeme
        super().__init__(f"{message} at {lexeme.pos} with lexeme: {lexeme}")

class TypingError(Exception):
    def __init__(self, msg) -> None:
        super().__init__(msg)

class SymbolAmbiguousException(Exception):
    """Raise when the compiler cannot decide what symbol it's supposed to consider
    (i.e. if multiple imported namespaces define the same symbol and the parent namespace is not defined explicitly)"""
    def __init__(self, symbol:Symbol):
        assert symbol.is_ambiguous
        super().__init__(f"Compiler has an ambiguous reference between and cannot decide between declarations from"
                         f"{symbol.typ.full_name} in {symbol.declaration_position}, "
                         ','.join(f"{sym.typ.full_name} in {sym.declaration_position}"
                                  for sym in symbol.ambiguous_other_declarations))

class SymbolRedefinitionError(Exception):
    """Raised when attempting to redefine a symbol in the same scope"""
    def __init__(self, name: str, original_position: Position, new_declaration_position: Position):
        self.name = name
        self.original = original_position
        self.new_declaration = new_declaration_position
        super().__init__(
            f"Symbol '{name}' already defined at {original_position.line}:"
            f"{original_position.column}, cannot redefine at "
            f"{new_declaration_position.line}:{new_declaration_position.column}"
        )

class SymbolNotFoundError(Exception):
    """Raised when a referenced symbol cannot be found in any accessible scope"""
    def __init__(self, name: str, position: Position):
        self.name = name
        self.position = position
        super().__init__(
            f"Symbol '{name}' not found (referenced at {position.line}:{position.column})")

class ScopeType(Enum):
    GlobalScope = auto()
    ClassScope = auto()
    LoopScope = auto()
    FunctionScope = auto()
    BlockScope = auto()

@dataclass    
class LocalScope:
    """The current scope of the block. It lists known symbols"""
    scope_type:ScopeType = ScopeType.BlockScope
    """The type of scope"""
    parent:Optional['LocalScope'] = None
    """The parent scope to this one (None if it's a global scope)"""
    symbols:Dict[str, Symbol] = field(default_factory=dict)
    """The symbol map containing the known scopes. Can be variables or functions (and classes or namespaces for global scopes)"""
    
    def __init__(self,
                 scope_type:ScopeType,
                 parent:Optional['LocalScope']=None,
                 symbols:Optional[Dict[str, Symbol]]=None):
        self.scope_type = scope_type
        self.parent = parent
        self.symbols = symbols or dict()
    
    def has_local_or_global_symbol(self, name:str) -> bool:
        if isinstance(self, LocalScope):
            for symbol_name in self.symbols.keys():
                if symbol_name == name:
                    return True
        if self.parent is not None:
            return self.parent.has_local_or_global_symbol(name)
        return False
    
    def has_class_symbol(self, name:str) -> bool:
        if isinstance(self, ClassScope):
            for symbol_name in self.symbols.keys():
                if symbol_name == name:
                    return True
            return False
        if self.parent is not None:
            return self.parent.has_class_symbol(name)
        return False
    
    def has_imported_symbol(self, name):
        if isinstance(self, GlobalScope):
            for symbol in self.imported_symbols:
                pass
            return False
        if self.parent is not None:
            return self.parent.has_imported_symbol(name)
        return False
    
    def get_symbol(self, name:str, position:Position=Position.default) -> Symbol:
        """Fetches the symbol with the specified name from local/global symbols.
        If none is found, check the class methods/fields
        If none is found, check the imports
        Similar search to c# symbols

        Args:
            name (str): The symbol to look for
            position (Position): Where the symbol is searched for

        Returns:
            Symbol: the found symbols
            
        Raises:
            SymbolNotFoundError of no symbol with this name is found
        """
        #todo optimize search to have only one pass
        try:
            return self.get_local_or_global_symbol(name, position)
        except:
            pass
        try:
            return self.get_class_symbol(name, position)
        except:
            pass
        return self.get_imported_symbol(name, position)
    
    def get_local_or_global_symbol(self, name:str, symbol_query_pos:Position) -> Symbol:
        if isinstance(self, LocalScope):
            if name in self.symbols:
                return self.symbols[name]
        if self.parent is not None:
            return self.parent.get_local_or_global_symbol(name, symbol_query_pos)
        raise SymbolNotFoundError(name, symbol_query_pos)
    
    def get_class_symbol(self, name:str, symbol_query_pos:Position) -> Symbol:
        if isinstance(self, ClassScope):
            if name in self.symbols:
                return self.symbols[name]
        if self.parent is not None:
            return self.parent.get_class_symbol(name, symbol_query_pos)
        raise SymbolNotFoundError(name, symbol_query_pos)
    
    def get_imported_symbol(self, name:str, symbol_query_pos:Position) -> Symbol:
        if isinstance(self, GlobalScope):
            if name in self.imported_symbols:
                return self.imported_symbols[name]
        if self.parent is not None:
            return self.parent.get_imported_symbol(name, symbol_query_pos)
        raise SymbolNotFoundError(name, symbol_query_pos)
    
    def declare_local(self, symbol:Symbol) -> None:
        if self.has_local_or_global_symbol(symbol.name):
            raise SymbolRedefinitionError(symbol.name,
                                          self.get_symbol(symbol.name, Position.default).declaration_position,
                                          symbol.declaration_position)
        self.symbols[symbol.name] = symbol
        
    def has_symbol(self, name:str, position:Position=Position.default):
        """Checks if the given symbol exists
        If none is found, check the class methods/fields
        If none is found, check the imports
        Similar search to c# symbols

        Args:
            name (str): The symbol to look for
            position (Position): Where the symbol is searched for

        Returns:
            bool: if the symbol exists
        """
        try:
            return self.get_symbol(name, position) is not None
        except:
            return False
    
    @property
    def num_ref_vars_declared_in_scope(self) -> int:
        return sum((isinstance(symbol.typ, ReferenceTyp) for symbol in self.symbols.values()))
    
    @property
    def gc_scope_should_be_defined(self) -> bool:
        """Whether this scope should be notified to the GC as a scope.
        For now it's just a bool check if there are reference variables defined"""
        return self.num_ref_vars_declared_in_scope > 0

    def generate_gc_scope_entry(self, context:'CodeGenContext'):
        """Generates LLVM-ir for garbage collection on scope entry. Notes the number of ref vars in the local scope no declare"""
        if not self.gc_scope_should_be_defined:
            #noop if no reference type root-vars are declared in this scope
            return
        size_t_type = ir.IntType(ir.PointerType().get_abi_size(context.target_data)*8)
        enter_scope_func = self.get_symbol(FUNC_GC_ENTER_SCOPE, Position.default).ir_func
        assert enter_scope_func is not None
        context.builder.call(enter_scope_func, [ir.Constant(size_t_type, self.num_ref_vars_declared_in_scope)])

    def generate_gc_scope_leave(self, context:'CodeGenContext', num_user_scopes_to_leave:int=1):
        """Generates LLVM-ir ot notify to the garbage collector to leave N scopes.
        Also keeps in mind skipped scopes where the GC was not notified (in case no Ref vars were declared)"""
        size_t_type = ir.IntType(ir.PointerType().get_abi_size(context.target_data)*8)
        leave_scope_func = self.get_symbol(FUNC_GC_LEAVE_SCOPE, Position.default).ir_func
        assert leave_scope_func is not None
        
        #calculate number of GC scopes to leave
        curr_scope, num_gc_scopes_to_leave  = self,0
        while num_user_scopes_to_leave > 0:
            num_gc_scopes_to_leave += curr_scope.gc_scope_should_be_defined
            num_user_scopes_to_leave -= 1
            if num_user_scopes_to_leave > 0:
                assert curr_scope.parent is not None, 'Cannot leave a scope that has not been declared to the GC previously'
                curr_scope = curr_scope.parent
        if num_gc_scopes_to_leave <= 0:
            return
        context.builder.call(leave_scope_func, 
                             [ir.Constant(size_t_type, num_gc_scopes_to_leave)])

    def add_root_to_gc(self, context:'CodeGenContext', var_name:str, pos:Position=Position.default):
        """Adds variable root location to GC"""
        symbol:Symbol = self.get_symbol(var_name, pos)
        type_ = symbol.typ
        assert isinstance(type_, ReferenceTyp)
        assert symbol.ir_alloca is not None
        if type_.is_reference_type:
            if isinstance(type_, ArrayTyp):
                if type_.element_typ.is_reference_type:
                    type_id = REFERENCE_ARRAY_TYPE_ID
                else:
                    type_id = VALUE_ARRAY_TYPE_ID
            else:
                type_id = context.type_ids[type_.name]
            
            size_t_type = ir.IntType(ir.PointerType().get_abi_size(context.target_data) * 8)
            register_root_func = self.get_symbol(FUNC_GC_REGISTER_ROOT_VARIABLE_IN_CURRENT_SCOPE, pos).ir_func
            assert register_root_func is not None
            context.builder.call(register_root_func,
                                 [symbol.ir_alloca, #location of root in memory. (ptr to the held ref vars)
                                  ir.Constant(size_t_type, type_id), #type id
                                  context.get_char_ptr_from_string(var_name) #variable name TODO: remove this. It should be in the debug symbols!
                                  ])

class NullScope(LocalScope):
    """Similar to a local scope but won't actually be compiled to a GC scope. it's a passthrough to the parent"""
    def get_symbol(self, name: str, position: Position = Position.default) -> Symbol:
        assert self.parent is not None
        return self.parent.get_symbol(name=name,
                                      position=position)
    
    def declare_local(self, symbol:Symbol) -> None:
        assert self.parent is not None
        self.parent.declare_local(symbol)
        
    def has_symbol(self, name:str, position:Position=Position.default) -> bool:
        """Checks if the given symbol exists
        If none is found, check the class methods/fields
        If none is found, check the imports
        Similar search to c# symbols

        Args:
            name (str): The symbol to look for
            position (Position): Where the symbol is searched for

        Returns:
            bool: if the symbol exists
        """
        assert self.parent is not None
        return self.parent.has_symbol(name=name,
                                      position=position)
    
    @property
    def num_ref_vars_declared_in_scope(self) -> int:
        return 0
    
    @property
    def gc_scope_should_be_defined(self) -> bool:
        """Whether this scope should be notified to the GC as a scope.
        For now it's just a bool check if there are reference variables defined"""
        return False

@dataclass
class GlobalScope(LocalScope):
    """The symbols imported from another namespace. Can be global vars, classes or functions"""
    imported_symbols:Dict[str, Symbol] = field(default_factory=dict)
    
    def __init__(self, module_symbols:Optional[Dict[str, Symbol]] = None,
                       imported_symbols:Optional[Dict[str, Symbol]] = None):
        super().__init__(ScopeType.GlobalScope,
                         None,
                         module_symbols or None)
        self.imported_symbols = imported_symbols or dict()

    def declare_import(self, symbol:Symbol):
        """Adds the imported symbol to the list. Makes symbol ambiguous if already defined"""
        if symbol.name in self.imported_symbols:
            self.imported_symbols[symbol.name].ambiguous_other_declarations.append(symbol)
        else:
            self.imported_symbols[symbol.name] = symbol

@dataclass
class ClassScope(LocalScope):
    class_ptype:'PType' = field(default_factory=lambda:PType('', Position.default))
    _class_typ:Optional['ReferenceTyp'] = None
    
    def __init__(self, parent:LocalScope, class_ptype:'PType'):
        super().__init__(scope_type=ScopeType.ClassScope,
                         parent=parent)
        self.class_ptype = class_ptype
        
    def declare_field_or_function(self, symbol:Symbol):
        return self.declare_local(symbol)
    
    @property
    def class_typ(self) -> ReferenceTyp:
        if self._class_typ is None:
            raise TypingError('Untyped Class scope error')
        return self._class_typ
    
    @class_typ.setter
    def class_typ(self, value:ReferenceTyp):
        assert isinstance(value, ReferenceTyp)
        self._class_typ = value

class CompilerError(Exception):
    def __init__(self, msg):
        super().__init__(msg)
        self.msg = msg
        
    def __str__(self):
        return f"Compiler Error: {self.msg}"

@dataclass
class LoopContext:
    continue_loop_block:ir.Block
    end_of_loop_block:ir.Block
    is_for_loop:bool
    current_loop_scope_depth:int = 0
    
@dataclass
class DebugInfo:
    di_file:ir.DIValue
    di_compile_unit:ir.DIValue
    dbg_declare_func:ir.Function
    dbg_value_func:ir.Function
    dbg_assign_func:ir.Function
    di_scope:List[ir.DIValue] = field(default_factory=list)

@dataclass
class CodeGenContext:
    """Context needed by various node when generating IR in the codegen pass"""
    module:ir.Module
    target_data:binding.TargetData
    """A dict containing all Types known to the typer and it's corresponding ir.Type"""
    type_map:Dict[IRCompatibleTyp, Union[ir.IntType,ir.HalfType,ir.FloatType,ir.DoubleType,ir.VoidType,ir.LiteralStructType]]
    #the debug information. ignored if -g flag not set
    debug_info:Optional[DebugInfo]
    global_scope:GlobalScope
    complete_namespace:str
    """A stack of tuples pointing to (condition block of loop: for continues, end of loop for break)"""
    loopinfo:List[LoopContext] = field(default_factory=list)
    builder:ir.IRBuilder = ir.IRBuilder()
    global_exit_block:Optional[ir.Block]=None
    type_ids:Dict[str, int] = field(default_factory=dict)
    """A Dict where for every given string there is an associated constant string PS object. constant because strings are immutable"""
    _global_string_objs:Dict[str, ir.GlobalValue] = field(default_factory=dict)
    compilation_opts:CompilationOptions = field(default_factory=CompilationOptions)
    
    def get_string_const(self, string:str):
        if string in self._global_string_objs:
            return self._global_string_objs[string]
        #take length before null termination to properly handle manual strings which may contain null chars (\x00)
        string_length = len(string)
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
        string_obj.initializer = ir.Constant(string_typ, [string_length, bytearray(string_bytes)]) #type: ignore Trying to set to None
        #cache value to avoid saturating executable
        self._global_string_objs[string] = string_obj
        return string_obj
    
    def type_by_name(self, name:str) -> IRCompatibleTyp:
        for typ in self.type_map.keys():
            if typ.name == name:
                return typ
        raise NameError("No type with name is known", name)
    
    def get_char_ptr_from_string(self, string:str):
        """Adds a Global string with the given value (if none already exists) and returns a GEP pointer to the first character (char* c string style)

        Args:
            string (str): The python string to convert to a llvm c-style string

        Returns:
            GEPInstr: a GEP instruction pointer value to the c-string
        """
        string_obj = self.get_string_const(string)
        assert isinstance(string_obj.type, ir.types._TypedPointerType)
        string_typ = string_obj.type.pointee
        zero = ir.Constant(ir.IntType(32), 0)
        one = ir.Constant(ir.IntType(32), 1)
        return self.builder.gep(string_obj, [zero, one, zero], inbounds=True, source_etype=string_typ)

class NodeType(Enum):
    """Enumeration of all possible node types in the parser tree"""
    EMPTY = auto()
    PROGRAM = auto()
    NAMESPACE = auto()
    FUNCTION = auto()
    TYPE = auto()
    CLASS = auto()
    BLOCK = auto()
    VARIABLE_DECLARATION = auto()
    ASSIGNMENT = auto()
    DISCARD = auto()
    BINARY_OPERATION = auto()
    UNARY_OPERATION = auto()
    IF_STATEMENT = auto()
    WHILE_STATEMENT = auto()
    FOR_STATEMENT = auto()
    RETURN_STATEMENT = auto()
    FUNCTION_CALL = auto()
    IDENTIFIER = auto()
    LITERAL = auto()
    OBJECT_INSTANTIATION = auto()
    ARRAY_INSTANTIATION = auto()
    CAST = auto()
    ATTRIBUTE = auto()
    IMPORT = auto()
    CLASS_PROPERTY = auto()
    METHOD_CALL = auto()
    BREAK_STATEMENT = auto()
    CONTINUE_STATEMENT = auto()
    ASSERT_STATEMENT = auto()
    TERNARY_OPERATION = auto()
    ARRAY_ACCESS = auto()

@dataclass
class BlockProperties:
    """The properties of the current block to be passed to statements and lower blocks"""

    is_class:bool = False
    """Whether the block is contained in a class"""
    is_top_level:bool = True
    """Whether this block is the top level block of the module"""
    is_loop:bool = False
    """Whether this block is contained in a loop (Note that this keeps the value True if nested multiple loops deep and is False only if it's not within a loop)"""
    in_function:bool = False
    """Whether this block is contained inside a function block"""
    current_scope:LocalScope = field(default_factory=GlobalScope)
    """The current scope containing the known variables"""

    def copy_with(self, is_loop:bool=False,
                  is_class:bool=False,
                  in_function:bool=False,
                  is_top_level:bool=False,
                  scope:Optional[LocalScope]=None):
        return BlockProperties(
            is_loop=self.is_loop or is_loop,
            is_class= self.is_class or is_class,
            is_top_level= self.is_top_level and is_top_level,
            in_function=in_function or self.in_function,
            current_scope=scope or self.current_scope)

@dataclass
class PStatement:
    """Base class for all AST nodes"""
    node_type: NodeType
    position: Position
    
    def __post_init__(self):
        #add field to progress backwards though the tree
        self._parent: Optional["PStatement"] = None
        
    @property
    def children(self) -> Generator["PStatement", None, None]:
        if False:
            yield
        return

    @property
    def parent(self) -> "PStatement":
        """The parent element in the tree. Used to calculate the element's depth/scope depth"""
        if self._parent is None:
            assert isinstance(self, PProgram) #only PProgram does not have a parent
            raise CompilerError("The top level PProgram node does not have a parent!")
        return self._parent
    
    @property
    def depth_from_next_loop(self) -> int:
        """How many scopes deep this statement is from the above loop
        a loop has a depth of 0. Any statement inside has a depth of 1 (or more if scoped within)
        This is used to count how many scopes to leave when breaking/continuing from a loop"""
        depth = 1
        scope = self.parent_scope
        while scope.scope_type != ScopeType.LoopScope:
            depth += 1
            scope = scope.parent
            assert scope is not None
        return depth
    
    @property
    def depth_from_next_function(self) -> int:
        """How many scopes deep this statement is within a function
        A statement in a function's top scope has a depth of 1 including its params
        This is used to calculate how many scopes to leave when returning from a function"""
        depth = 1
        scope = self.parent_scope
        while scope.scope_type != ScopeType.FunctionScope:
            depth += 1
            scope = scope.parent
            assert scope is not None
        return depth
    
    @property
    def count_ref_vars_declared_in_scope(self) -> int:
        """Counts the number of reference Variables are defined in the scope"""
        return 0
    
    def _setup_parents(self):
        if self._parent is not None:
            return #speedup and prevents cycles
        for child in self.children:
            child._setup_parents()
            child._parent = self

    def generate_llvm(self, context:CodeGenContext) -> Optional[ir.Value]:
        raise NotImplementedError(f"Code generation for {type(self)} is not yet implemented")
    
    @property
    def parent_scope(self) -> LocalScope:
        return self.parent.parent_scope
    
    def exit_with_error(self, context:CodeGenContext, error_code:int=1, error_message:str="Error "):
        printf = self.parent_scope.get_symbol("printf", Position.default).ir_func
        exit_func = self.parent_scope.get_symbol("exit", Position.default).ir_func
        assert printf is not None
        assert exit_func is not None
        error_message += f" in file %s at line %d:%d\n"
        error_message_c_str_with_format = context.get_char_ptr_from_string(error_message)
        context.builder.call(printf, [
            error_message_c_str_with_format,
            context.get_char_ptr_from_string(self.position.filename), # filename
            ir.Constant(ir.IntType(32), self.position.line), # line number
            ir.Constant(ir.IntType(32), self.position.column), # Column number
        ])
        context.builder.call(exit_func, [ir.Constant(ir.IntType(32), error_code)])
        context.builder.unreachable()

    def di_location(self, context:CodeGenContext, includeFile=True):
        """returns the kay-value pairs for the location of the debug info"""
        assert context.debug_info is not None
        loc:Dict['str', Any] = {
                "line": self.position.line
            }
        if (len(context.debug_info.di_scope) > 0 and 
                context.debug_info.di_scope[-1].kind in ("DISubprogram", "DILexicalBlock")):
            loc["scope"] = context.debug_info.di_scope[-1]
        if includeFile:
            loc["file"] = context.debug_info.di_file
        return loc
    
    def add_di_location_metadata(self, context:CodeGenContext) ->ir.DIValue:
        return context.module.add_debug_info("DILocation",
                                             self.di_location(context, includeFile=False))

    def add_debug_info(self, context:CodeGenContext) -> Optional[ir.DIValue]:
        """returns a DIExpression dor debug into to the expression"""
        if not context.compilation_opts.add_debug_symbols:
            return
        assert context.debug_info is not None
        
        return self.add_di_location_metadata(context)

@dataclass
class PScopeStatement(PStatement):
    scope:LocalScope
    
    @property
    def parent_scope(self) -> LocalScope:
        if self.scope is not None:
            return self.scope
        return super().parent_scope
    
    def _setup_parents(self):
        return super()._setup_parents()

    @property
    def count_ref_vars_declared_in_scope(self) -> int:
        """Returns the number of reference variables defined in the scope defined by this block"""
        return self.parent_scope.num_ref_vars_declared_in_scope

@dataclass
class PExpression(PStatement):
    """Base class for all expression nodes - nodes that produce a value"""
    
    def __post_init__(self):
        super().__post_init__()
        self.expr_type:Optional[BaseTyp] = None  # Will be set during typing pass
        self.is_lvalue = getattr(self, "is_lvalue", False)

    def generate_llvm(self, context:CodeGenContext, get_ptr_to_expression=False) -> ir.Value:
        raise NotImplementedError(f"Code generation for {type(self)} is not yet implemented")

@dataclass
class PNoop(PExpression):
    def __init__(self, lexeme:Lexeme):
        super().__init__(NodeType.EMPTY, lexeme.pos)
    
    def generate_llvm(self, context:CodeGenContext, get_ptr_to_expression=False) -> ir.Value:
        assert not get_ptr_to_expression, "Cannot get pointer to a NoOp"
        return ir.Constant(ir.IntType(1), True)

@dataclass
class PProgram(PScopeStatement):
    """Root node of the program"""
    statements: List[PStatement]
    namespace_name: List[str]
    imports:List['PImport']
        
    @property
    def children(self) -> Generator["PStatement", None, None]:
        for stmt in self.statements:
            yield stmt
        return

    def __init__(self, statements: List[PStatement], lexeme: Lexeme,
                 scope:GlobalScope, namespace:Optional[List[str]]=None,
                 imports:Optional[List['PImport']]=None):
        super().__init__(NodeType.PROGRAM, lexeme.pos, scope)
        self.namespace_name =  namespace or ["Default"]
        self.statements = statements
        self.imports = imports or list()
        
        namespace_symbol = Symbol(self.namespace_name[0],
                                  Position.default)
        self.scope.declare_local(namespace_symbol)
        
    def generate_header(self) -> str:
        classes:List[PClass] = []
        functions:List[PFunction] = []
        global_vars:List[PVariableDeclaration] = []
        
        for stmnt in self.statements:
            if isinstance(stmnt, PClass):
                classes.append(stmnt)
            elif isinstance(stmnt, PFunction):
                functions.append(stmnt)
            elif isinstance(stmnt, PVariableDeclaration):
                global_vars.append(stmnt)
        
        header = f"{LexemeType.KEYWORD_CONTROL_NAMESPACE.get_keyword()} {self.namespace_name};\n\n"
        header += "\n".join((g.generate_header() for g in global_vars)) + "\n\n"
        header += "\n".join((c.generate_header() for c in classes)) + "\n\n"
        header += "\n".join((f.generate_header() for f in functions)) + "\n\n"
        return header

    def _setup_parents(self):
        super()._setup_parents()
        for import_stmt in self.imports:
            import_stmt._parent = self
            import_stmt._setup_parents()

@dataclass
class PFunction(PScopeStatement):
    """Function definition node"""
    name: str
    return_type: 'PType'
    function_args: List['PVariableDeclaration']  # List of (type, name) tuples
    symbol:Symbol
    body: Optional['PBlock']
    is_called: bool = False
    is_builtin:bool=False
        
    @property
    def children(self) -> Generator["PStatement", None, None]:
        for stmt in (self.return_type, 
                     *self.function_args):
            yield stmt
        if self.body is not None:
            yield self.body
        return
    
    def __hash__(self) -> int:
        return hash(self.name) + hash(self.return_type) + sum([hash(func) for func in self.function_args])

    @staticmethod
    def get_linkable_name(function_name:str,
                          namespace:Union[str, List[str]],
                          class_name:Optional[str]=None):
        if isinstance(namespace, list):
            namespace = '.'.join(namespace)
        if class_name is None:
            return f"{namespace}.$${function_name}"
        else:
            return f"{namespace}.${class_name}.$${function_name}"
    
    @property
    def header_is_typed(self) -> bool:
        return isinstance(self.symbol._typ, IRCompatibleTyp)
    
    @property
    def return_typ_typed(self) -> IRCompatibleTyp:
        if not isinstance(self.symbol.typ, FunctionTyp):
            raise TypingError(f"Function has not been typed yet")
        return self.symbol.typ.return_type

    @property
    def explicit_arguments(self):
        return self.function_args

    def __init__(self, name: str, return_type: 'PType', parameters: List['PVariableDeclaration'],
                 body: Optional['PBlock'], lexeme: Lexeme, scope:LocalScope, is_builtin:bool=False):
        super().__init__(NodeType.FUNCTION, lexeme.pos, scope)
        self.name = name
        self.return_type = return_type
        self.function_args = parameters
        self.body = body
        self.is_builtin = is_builtin
        self.symbol= Symbol(
            name,
            lexeme.pos,
            arguments=parameters,
            is_assigned=self.body is not None
        )

    @property
    def is_only_declaration(self):
        return self.body is None

    @property
    def function_typ(self) -> FunctionTyp:
        assert isinstance(self.symbol.typ, FunctionTyp)
        return self.symbol.typ

    @function_typ.setter
    def function_typ(self, value:FunctionTyp):
        assert isinstance(value, FunctionTyp)
        self.symbol.typ = value
    
    def generate_header(self) -> str:
        """Generates the function's declarations, to be used as imports"""
        return (f"{self.return_typ_typed.full_name} {self.name}(" +
                ",".join((f"{arg.typer_pass_var_type.full_name} {arg.name}"
                          for arg in self.explicit_arguments))
                +");")
    
    def generate_llvm(self, context: CodeGenContext) -> None:
        func = self.symbol.ir_func
        assert func is not None
        
        if self.is_only_declaration:
            return
        assert self.body is not None

        context.builder.position_at_start(func.append_basic_block(f'__{self.name}_entrypoint_{self.position.index}'))

        self.parent_scope.generate_gc_scope_entry(context)
        
        if context.compilation_opts.add_debug_symbols and isinstance(func, _HasMetadata):
            func.set_metadata("dbg", self.add_debug_info(context))
        
        # defined args in scoper:
        assert len(self.function_args) == len(func.args)
        arg_num = 0
        for param, arg_value in zip(self.function_args, func.args):
            arg_num += 1
            # build alloca to a function argument
            # In llvm function arguments are just NamedValues and don't have a mem address.
            # We define a location on the stack for them so they can be written to.
            # This will be optimized out by the mem2reg pass
                # NB: written to just means that an argument x can be written to.
                # The caller will not have the value changed from his point of view, he just passed a value not a reference!
            arg_alloca = context.builder.alloca(arg_value.type)
            param.symbol.ir_alloca = arg_alloca
            debug_info:Optional[ir.DIValue] = None
            if context.compilation_opts.add_debug_symbols and isinstance(arg_alloca, _HasMetadata):
                assert context.debug_info is not None
                debug_info = param.add_di_location_metadata(context)
                arg_alloca.set_metadata("dbg", debug_info)
                
                di_local_var = context.module.add_debug_info("DILocalVariable",
                                            {
                                                "name": param.name,
                                                **param.di_location(context),
                                                "type": param.typer_pass_var_type.di_type(context),
                                                "arg":arg_num
                                            })
                
                call = context.builder.call(context.debug_info.dbg_declare_func,
                                    [arg_alloca, #alloca Metadata
                                    di_local_var,# metadata associated with local var info
                                    context.module.add_debug_info("DIExpression", {})]) # expression metadata
                call.set_metadata('dbg', self.add_di_location_metadata(context))
                
            context.builder.store(arg_value, arg_alloca)
            
            if param.is_root_to_declare_to_gc:
                self.parent_scope.add_root_to_gc(context, param.name, param.position)
        # run body statements
        self.body.generate_llvm(context)
        
        #ensure all block are properly terminated
        for block in list(func.basic_blocks):
            assert isinstance(block, ir.Block)
            if not block.is_terminated:
                with context.builder.goto_block(block):
                    # add default return to ensure branch is terminated
                    # will be optimized out if unreachable
                    if func.function_type.return_type == ir.VoidType():
                        context.builder.ret_void()
                    else:
                        context.builder.ret(self.return_typ_typed.default_llvm_value(context))

        # GC scope leaving handled by the return instruction (implicit for void methods)
        
    def di_type(self, context:CodeGenContext):
        return [self.return_typ_typed.di_type(context)] + [
                arg.typer_pass_var_type.di_type(context) for arg in self.function_args]
        
    def add_debug_info(self, context: CodeGenContext) -> Optional[ir.DIValue]:
        if not context.compilation_opts.add_debug_symbols:
            return
        assert context.debug_info is not None
        subroutine_type = context.module.add_debug_info("DISubroutineType",
                                    {
                                        "types": [self.return_typ_typed.di_type(context)]+\
                                                    [arg.typer_pass_var_type.di_type(context) for arg in self.function_args]
                                    })
        di_subprogram = context.module.add_debug_info("DISubprogram",
                {
                    "name": self.name,
                    "linkageName": self.get_linkable_name(self.name,
                                                          context.complete_namespace,
                                                          self.class_type.name if isinstance(self, PMethod) else ''),
                    **self.di_location(context),
                    "type": subroutine_type,
                    "isDefinition": True,
                    "unit":context.debug_info.di_compile_unit,
                    "spFlags":ir.DIToken('DISPFlagDefinition'),
                    "retainedNodes":[]
                }, is_distinct=True)
        context.debug_info.di_scope.append(di_subprogram)
        return di_subprogram

@dataclass    
class PMethod(PFunction):
    _class_type:Optional[IRCompatibleTyp]=None
        
    @staticmethod
    def fromPFunction(pfunc:PFunction, class_type:'PType'):
        """Converts a PFunction to a PMethod, updating it's symbol in the scope tree as well and adding the implicit "this" argument"""
        
        # Add implicit "this" argument
        # TODO: Do not include for static methods!
        this = PVariableDeclaration(PThis.NAME, class_type,
                                    None, class_type.position)
        pfunc.function_args.insert(0, this)
        #update symbol 
        pfunc.symbol.arguments = pfunc.function_args
        #declare symbol in scope
        pfunc.parent_scope.declare_local(this.symbol)
        #ignore warnings for implicit symbol
        this.symbol.is_assigned = True
        this.symbol.is_read = True
        
        return PMethod(node_type= pfunc.node_type,
                       position=pfunc.position,
                       scope=pfunc.scope,
                       name=pfunc.name,
                       return_type=pfunc.return_type,
                       function_args=pfunc.function_args,
                       symbol=pfunc.symbol,
                       body=pfunc.body)

    @property
    def explicit_arguments(self):
        return self.function_args[1:]

    @property
    def linkable_name(self):
        namespace = ''
        parent = self.parent
        while not isinstance(parent, PProgram):
            if parent is None:
                raise RuntimeError('Unable to fetch current namespace')
            parent=parent.parent
        return PMethod.get_linkable_name(self.name,
                                         parent.namespace_name,
                                         self.class_type.name)
    
    @property
    def class_type(self):
        if self._class_type is None:
            raise TypingError(f"Function has not been typed yet")
        return self._class_type
    
    def __hash__(self) -> int:
        return super().__hash__()
    
    def __eq__(self, value: object) -> bool:
        if not isinstance(value, PMethod):
            return False
        return super().__eq__(value)

@dataclass
class PClass(PScopeStatement, UseCheckMixin):
    """Class definition node"""
    name: str
    fields: Dict[str, 'PClassField']
    methods: List[PMethod]
    symbol:Symbol
    _is_value_type=False
    
    @property
    def full_name(self) -> str:
        return self.class_typ.pointed_type.full_name
    
    @property
    def class_typ(self) -> TypeTyp:
        if self.symbol._typ is None:
            raise TypingError('Class has not been typed yet')
        assert isinstance(self.symbol.typ, TypeTyp)
        return self.symbol.typ
        
    @class_typ.setter
    def class_typ(self, value:TypeTyp):
        assert isinstance(value, TypeTyp)
        self.symbol._typ = value
        
    @property
    def children(self) -> Generator["PStatement", None, None]:
        for stmt in (*self.fields.values(), 
                     *self.methods):
            yield stmt
        return

    def __init__(self, name: str, fields: Dict[str, 'PClassField'],
                 methods: List[PMethod], lexeme: Lexeme, type_symbol:Symbol,
                 scope:ClassScope):
        
        super().__init__(node_type=NodeType.CLASS,
                         position=lexeme.pos,
                         scope=scope)
        self.name = name
        self.fields = fields
        self.methods = methods
        self.symbol = type_symbol

    def generate_header(self) -> str:
        """Generates the function's declarations, to be used as imports"""
        return (f"class {self.name}\n{{\n"
                +"\n".join((f"\t{field.typer_pass_var_type.full_name} {field.name};"
                            for field in sorted(self.fields.values(), key=lambda f:f.field_index)))
                +"\n\n"
                + "\n".join((meth.generate_header() for meth in self.methods))
                +"\n}\n")

@dataclass
class PClassField(PStatement):
    """Class field definition node"""
    name: str
    var_type: 'PType'
    field_index:int
    is_public: bool
    default_value: Optional[PExpression]
    _typer_pass_var_type: Optional[IRCompatibleTyp] = None
    is_assigned: bool = False
    is_read: bool = False
    is_builtin: bool = False
    
    @property
    def typer_pass_var_type(self) -> IRCompatibleTyp:
        if self._typer_pass_var_type is None:
            raise TypingError("Typer has not typed this node yet!")
        return self._typer_pass_var_type
        
    @property
    def children(self) -> Generator["PStatement", None, None]:
        yield self.var_type
        if self.default_value is not None:
            yield self.default_value
        return

    def __init__(self, name: str, type: 'PType', is_public: bool, field_index:int,
                 lexeme: Lexeme, default_value:Optional[PExpression],
                 is_builtin:bool = False):
        super().__init__(NodeType.CLASS_PROPERTY, lexeme.pos)
        self.name = name
        self.var_type = type
        self.is_public = is_public
        self.default_value = default_value
        self.is_builtin = is_builtin
        self.field_index = field_index
        
    def __hash__(self) -> int:
        return hash(self.name) + hash(self.var_type)
    
    def __eq__(self, value: object) -> bool:
        if not isinstance(value, PClassField):
            return False
        return self.name == value.name and self.var_type == value.var_type

@dataclass
class PBlock(PScopeStatement):
    """Block of statements"""
    statements: List[PStatement]
    block_properties:BlockProperties

    def __init__(self, statements: List[PStatement], lexeme: Lexeme,
                 block_properties:BlockProperties):
        super().__init__(NodeType.BLOCK, lexeme.pos, block_properties.current_scope)
        self.statements = statements
        self.block_properties = block_properties
        
    @property
    def children(self) -> Generator["PStatement", None, None]:
        for stmt in self.statements:
            yield stmt
        return
    
    def generate_llvm(self, context: CodeGenContext) -> None:
        """Generates the llvm IR code for this PBlock

        Args:
            context (CodeGenContext): The context containing the current module
            build_basic_block (bool, optional): Whether to generate a new basic block for this PBlock.
            Also terminates the  current basic block and creates a new one to continue after this one. Defaults to True.
        """
        assert isinstance(context.builder.block, ir.Block)
        if context.compilation_opts.add_debug_symbols:
            assert context.debug_info is not None
            context.debug_info.di_scope.append(self.add_debug_info(context))
        if not isinstance(self.scope, NullScope):
            self.scope.generate_gc_scope_entry(context)
        for stmt in self.statements:
            stmt.generate_llvm(context)
            assert isinstance(context.builder.block, ir.Block)
            if context.builder.block.is_terminated:
                #TODO: add warning here if it still has statements in terminated block
                break
        else:
            #otherwise leave the current scope for the block if the block has not been terminated by a return, break or continue
            if not isinstance(self.scope, NullScope):
                self.scope.generate_gc_scope_leave(context)
            
        if context.compilation_opts.add_debug_symbols:
            assert context.debug_info is not None
            context.debug_info.di_scope.pop()
            
    def add_debug_info(self, context: CodeGenContext):
        assert isinstance(context.builder.block, ir.Block)
        assert context.debug_info is not None
        return context.module.add_debug_info("DILexicalBlock", self.di_location(context))
    
@dataclass
class PImport(PStatement):
    namespace_parts:List[str]
    namespace_symbol:Symbol
    headers:List[Union['PVariableDeclaration', PFunction, PClass]]
    alias:Optional[str] = None

    @property
    def children(self) -> Generator["PStatement", None, None]:
        for declaration in self.headers:
            yield declaration
        return
    
    @property
    def namespace_typ(self) -> NamespaceTyp:
        assert isinstance(self.namespace_symbol.typ, NamespaceTyp)
        return self.namespace_symbol.typ
    
    def _setup_parents(self):
        assert self._parent is not None
        for child in self.children:
            child._setup_parents()
            child._parent = self.parent
    
    @namespace_typ.setter
    def namespace_typ(self, value:NamespaceTyp):
        assert isinstance(value, NamespaceTyp)
        self.namespace_symbol.typ = value
    
    def __init__(self, namespace_parts:List['PIdentifier'], lexeme_pos:Union[Lexeme, Position],
                 alias:Optional[str]=None):
        super().__init__(node_type=NodeType.IMPORT,
                         position=lexeme_pos.pos if isinstance(lexeme_pos, Lexeme) else lexeme_pos)
        assert len(namespace_parts) > 0
        self.namespace_parts = [part.name for part in namespace_parts]
        self.alias = alias
        part = namespace_parts.pop()
        ptype = PNamespaceType(base_type=part.name,
                                lexeme_pos=part.position)
        
        
        self.namespace_symbol = Symbol(
            name=self.namespace_parts[0],
            declaration_position=self.position,
            is_assigned=True,
            is_read=True
        )
        if alias is not None:
            self.namespace_symbol.name = alias
        self.headers = self.fetch_declarations()
    
    def fetch_declarations(self) -> List[Union['PVariableDeclaration', PFunction, PClass]]:
        """Adds declarations to the symbol and propagates them up to the global namespace as an import-declaration.
        If multiple declarations have the same name, only the first one will be added to the import declarations"""
        
        def find_header(name) -> Path:
            """Finds the header file in the compiler's std_lib or in the current project"""
            cwd = Path()
            header_files = cwd.rglob(f'./{name}', case_sensitive=True)
            header = next(header_files, None)
            if header is None:
                raise FileNotFoundError(f'Unable to find header in current project directory')
            return header
        
        def set_assigned_and_read(node:Union[PVariableDeclaration, PFunction, PClass]):
            node.symbol.is_assigned=True
            node.symbol.is_read=True
            if isinstance(node, PFunction):
                for arg in node.function_args:
                    set_assigned_and_read(arg)
                node.is_called = True
            elif isinstance(node, PClass):
                for func in node.methods:
                    set_assigned_and_read(func)
                
        # TODO find better way to define where to look for the headers
        # Maybe add flags to the compiler to direct where to search like -I for gcc
        # and search first the current 'lib' and 'out' folder of the projects
        
        header_name = ".".join(self.namespace_parts)+'.psh'
        header_file_path = Path(__file__).parent.joinpath("std_lib", header_name)
        if not header_file_path.exists():
            header_file_path = find_header(header_name)

        assert header_file_path.exists() and header_file_path.is_file()
        with open(header_file_path, 'rt') as header_reader:
            header_parser = Parser(Lexer(header_file_path.name, header_reader))
            headers = header_parser.parse_header()
            for header in headers:
                set_assigned_and_read(header)
            return headers

@dataclass
class PVariableDeclaration(PStatement):
    """Variable declaration node"""
    name: str
    var_type: 'PType'
    initial_value: Optional[PExpression]
    symbol:Symbol
    
    @property
    def typer_pass_var_type(self) -> IRCompatibleTyp:
        if not isinstance(self.symbol.typ, IRCompatibleTyp):
            raise CompilerError('PVarDecl fas not been typed')
        return self.symbol.typ
    
    @typer_pass_var_type.setter
    def typer_pass_var_type(self, value):
        assert isinstance(value, IRCompatibleTyp)
        self.symbol.typ = value
        
    @property
    def children(self) -> Generator["PStatement", None, None]:
        yield self.var_type
        if self.initial_value is not None:
            yield self.initial_value
        return
    
    @property
    def is_root_to_declare_to_gc(self) -> bool:
        """Flag which says whether this variable declaration should be declared to the GC to track its objects"""
        return self.typer_pass_var_type.is_reference_type

    def __init__(self, name: str, var_type: 'PType', initial_value: Optional[PExpression], lexeme_pos: Union[Lexeme, Position]):
        super().__init__(NodeType.VARIABLE_DECLARATION, lexeme_pos.pos if isinstance(lexeme_pos, Lexeme) else lexeme_pos)
        self.name = name
        self.var_type = var_type
        self.initial_value = initial_value
        
        self.symbol = Symbol(self.name,
                             self.position,
                             is_assigned=self.initial_value is not None)
    
    def __hash__(self) -> int:
        return hash(self.name) + hash(self.var_type)
    
    def __eq__(self, value: object) -> bool:
        if not isinstance(value, PVariableDeclaration):
            return False
        return self.name == value.name and self.var_type == value.var_type
    
    def generate_llvm(self, context: CodeGenContext) -> None:        
        type_ = self.typer_pass_var_type.get_llvm_value_type(context)
        alloca = context.builder.alloca(type_,name=self.name)
        symbol = self.parent_scope.get_symbol(self.name, self.position)
        symbol.ir_alloca = alloca
        
        if self.is_root_to_declare_to_gc:
            self.parent_scope.add_root_to_gc(context, self.name, self.position)

        if context.compilation_opts.add_debug_symbols:
            self.add_debug_info(context)

        if self.initial_value is None:
            init = self.typer_pass_var_type.default_llvm_value(context)
        else:
            init = self.initial_value.generate_llvm(context, False)
        
        instr = context.builder.store(init, alloca)
        if self.initial_value is not None and context.compilation_opts.add_debug_symbols and isinstance(instr, _HasMetadata):
            instr.set_metadata('dbg', self.add_di_location_metadata(context))
                
        
    def add_debug_info(self, context: CodeGenContext) -> Optional[ir.DIValue]:
        if not context.compilation_opts.add_debug_symbols:
            return
        assert context.debug_info is not None
        di_local_var = context.module.add_debug_info("DILocalVariable",
                                            {
                                                "name": self.name,
                                                **self.di_location(context),
                                                "type": self.typer_pass_var_type.di_type(context)
                                            })
        alloca = self.parent_scope.get_symbol(self.name, self.position).ir_alloca
        assert alloca is not None
        call = context.builder.call(context.debug_info.dbg_declare_func,
                             [alloca, #alloca Metadata
                              di_local_var,# metadata associated with local var info
                              context.module.add_debug_info("DIExpression", {})]) # expression metadata
        call.set_metadata('dbg', self.add_di_location_metadata(context))
        return
    
    def generate_header(self):
        return f"{self.typer_pass_var_type.full_name} {self.name};"

@dataclass
class PAssignment(PExpression):
    """Assignment operation node"""
    target: Union['PIdentifier', 'PDotAttribute', 'PArrayIndexing']
    value: PExpression

    def __init__(self, target: Union['PIdentifier', 'PDotAttribute', 'PArrayIndexing'], value: PExpression, lexeme: Lexeme):
        super().__init__(NodeType.ASSIGNMENT, lexeme.pos)
        self.target = target
        self.target.is_lvalue = True
        self.value = value
        
    @property
    def children(self) -> Generator["PStatement", None, None]:
        yield self.target
        yield self.value
        return
        
    def generate_llvm(self, context:CodeGenContext, get_ptr_to_expression=False) -> ir.Value:
        assert not get_ptr_to_expression, "Cannot get pointer to an assignment value"
        # get ptr to assign to
        if isinstance(self.target, PIdentifier):
            target = self.parent_scope.get_symbol(self.target.name, self.position).ir_alloca
        elif isinstance(self.target, (PDotAttribute, PArrayIndexing)):
            #should return GEP ptr value
            target = self.target.generate_llvm(context, get_ptr_to_expression=True)
        else:
            raise NotImplementedError()
        
        assert target is not None
        #get value to assign
        value = self.value.generate_llvm(context)
        #assign to target
        instr = context.builder.store(value, target)
        if context.compilation_opts.add_debug_symbols:
            assert context.debug_info is not None
            di_loc = self.add_di_location_metadata(context)
            instr.set_metadata("dbg", di_loc)
            
            #TODO add debug info here
            # dbg_assign = context.builder.call(context.debug_info.dbg_assign_func,
            #                                   [
            #                                     value,
            #                                     context.module.add_debug_info("DIExpression",{}),
            #                                     context.module.add_debug_info("DILocalVariable",
            #                                             {
            #                                                 "name": target,
            #                                                 **target.di_location(context),
            #                                                 "type": target.expr_type.di_type(context)
            #                                             }),#DILocalVariable,
            #                                     context.module.add_debug_info("DIAssignID", {}, is_distinct=True),
            #                                     target, # should be the original memory address of the base variable
            #                                         # aka. the array if getting a field like class.field, this points to the class
            #                                         # or if adding to an array: this should point to the original array
                                                    
            #                                     context.module.add_debug_info("DIExpression", {}),
            #                                         #DIExpression showing how to run the pointer arithmetic
            #                                         # like for class.field DIExpression(DW_OP_plus_uconst, $OffsetInBytes (or bits?))
            #                                     di_loc #location
            #                                     ])
            # dbg_assign.set_metadata("dbg", di_loc)
        #return the value
        return value

class PDiscard(PStatement):
    """Discard an expression result"""
    expression:PExpression
        
    @property
    def children(self) -> Generator["PStatement", None, None]:
        yield self.expression
        return
    
    def __init__(self, expression:PExpression, lexeme: Lexeme):
        super().__init__(NodeType.DISCARD, lexeme.pos)
        self.expression = expression
    
    def generate_llvm(self, context: CodeGenContext) -> None:
        self.expression.generate_llvm(context)
        #discard result

@dataclass
class PBinaryOperation(PExpression):
    """Binary operation node"""
    operation: BinaryOperation
    left: PExpression
    right: PExpression

    def __init__(self, operation: BinaryOperation, left: PExpression, right: PExpression, lexeme: Lexeme):
        super().__init__(NodeType.BINARY_OPERATION, lexeme.pos)
        self.operation = operation
        self.left = left
        self.right = right
        
    @property
    def children(self) -> Generator["PStatement", None, None]:
        yield self.left
        yield self.right
        return
        
    def generate_and_short_circuit(self, left:ir.Value, context:CodeGenContext):
        # Create basic blocks for different paths
        curr_block = context.builder.block
        true_block = context.builder.append_basic_block(f'and_true_{self.position.index}')
        end_block = context.builder.append_basic_block(f'and_end_{self.position.index}')
        
        # Conditional branch based on left side
        context.builder.cbranch(left, true_block, end_block)

        # True block: evaluate right side
        context.builder.position_at_end(true_block)
        right = self.right.generate_llvm(context)
        
        if context.compilation_opts.add_debug_symbols and isinstance(right, _HasMetadata):
                right.set_metadata("dbg", self.right.add_debug_info(context))
        context.builder.branch(end_block)

        # Merge block: PHI node to combine results
        context.builder.position_at_end(end_block)
        phi = context.builder.phi(ir.IntType(1))
        phi.add_incoming(right, true_block)
        phi.add_incoming(ir.Constant(ir.IntType(1), 0), curr_block)

        return phi
        
    def generate_or_short_circuit(self, left:ir.Value, context:CodeGenContext):
        # Create basic blocks for different paths
        curr_block = context.builder.block
        false_block = context.builder.append_basic_block(f'or_false_{self.position.index}')
        end_block = context.builder.append_basic_block(f'or_end_{self.position.index}')
        
        # Conditional branch based on left side
        context.builder.cbranch(left, end_block, false_block)

        # False block: evaluate right side
        context.builder.position_at_end(false_block)
        right = self.right.generate_llvm(context)
        
        if context.compilation_opts.add_debug_symbols and isinstance(right, _HasMetadata):
                right.set_metadata("dbg", self.right.add_debug_info(context))
        context.builder.branch(end_block)

        # Merge block: PHI node to combine results
        context.builder.position_at_end(end_block)
        phi = context.builder.phi(ir.IntType(1))
        phi.add_incoming(right, false_block)
        phi.add_incoming(ir.Constant(ir.IntType(1), 1), curr_block)

        return phi

    def generate_llvm(self, context:CodeGenContext, get_ptr_to_expression=False) -> ir.Value:
        assert not get_ptr_to_expression, "Cannot get pointer to an operation result"
        left = self.left.generate_llvm(context)
        if self.expr_type is None:
            raise CompilerError(f"AST Node has not been typed at location {self.position}")
        if self.expr_type.is_reference_type:
            raise NotImplementedError() #here should call the builtin's Equals() function
        assert isinstance(self.expr_type, IRCompatibleTyp)
        type_info = self.expr_type.type_info
        
        ret_val = None
        if self.operation == BinaryOperation.LOGIC_AND:
            ret_val = context.builder.and_(left, self.right.generate_llvm(context))
        elif self.operation == BinaryOperation.LOGIC_OR:
            ret_val = context.builder.or_(left, self.right.generate_llvm(context))
        elif self.operation == BinaryOperation.BOOL_AND:
            ret_val = self.generate_and_short_circuit(left, context)
        elif self.operation == BinaryOperation.BOOL_OR:
            ret_val = self.generate_or_short_circuit(left, context)
        elif self.operation in (BinaryOperation.BOOL_EQ,
                                BinaryOperation.BOOL_GEQ,
                                BinaryOperation.BOOL_GT,
                                BinaryOperation.BOOL_LEQ,
                                BinaryOperation.BOOL_LT,
                                BinaryOperation.BOOL_NEQ):
            if type_info.type_class == TypeClass.FLOAT:
                ret_val = context.builder.fcmp_ordered(self.operation.value, left, self.right.generate_llvm(context))
            elif type_info.type_class in (TypeClass.INTEGER,TypeClass.BOOLEAN):
                if type_info.is_signed:
                    ret_val = context.builder.icmp_signed(self.operation.value, left, self.right.generate_llvm(context))
                else:
                    ret_val = context.builder.icmp_unsigned(self.operation.value, left, self.right.generate_llvm(context))
        elif self.operation == BinaryOperation.DIVIDE:
            if type_info.type_class == TypeClass.FLOAT:
                ret_val = context.builder.fdiv(left, self.right.generate_llvm(context))
            elif type_info.type_class == TypeClass.INTEGER:
                ret_val = context.builder.sdiv(left, self.right.generate_llvm(context)) if type_info.is_signed else context.builder.udiv(left, self.right.generate_llvm(context))
            else:
                raise NotImplementedError()
        elif self.operation == BinaryOperation.MINUS:
            if type_info.type_class == TypeClass.FLOAT:
                ret_val = context.builder.fsub(left, self.right.generate_llvm(context))
            elif type_info.type_class == TypeClass.INTEGER:
                ret_val = context.builder.sub(left, self.right.generate_llvm(context))
            else:
                raise NotImplementedError()
        elif self.operation == BinaryOperation.PLUS:
            if type_info.type_class == TypeClass.FLOAT:
                ret_val = context.builder.fadd(left, self.right.generate_llvm(context))
            elif type_info.type_class == TypeClass.INTEGER:
                ret_val = context.builder.add(left, self.right.generate_llvm(context))
            else:
                raise NotImplementedError()
        elif self.operation == BinaryOperation.MOD:
            if type_info.type_class == TypeClass.FLOAT:
                ret_val = context.builder.frem(left, self.right.generate_llvm(context))
            elif type_info.type_class == TypeClass.INTEGER:
                ret_val = context.builder.srem(left, self.right.generate_llvm(context)) if type_info.is_signed else context.builder.urem(left, self.right.generate_llvm(context))
            else:
                raise NotImplementedError()
        elif self.operation == BinaryOperation.SHIFT_LEFT:
            if type_info.type_class == TypeClass.INTEGER:
                ret_val = context.builder.shl(left, self.right.generate_llvm(context))
            else:
                raise NotImplementedError()
        elif self.operation == BinaryOperation.SHIFT_RIGHT:
            if type_info.type_class == TypeClass.INTEGER:
                ret_val = context.builder.ashr(left, self.right.generate_llvm(context)) if type_info.is_signed else context.builder.lshr(left, self.right.generate_llvm(context))
            else:
                raise NotImplementedError()
        elif self.operation == BinaryOperation.TIMES:
            if type_info.type_class == TypeClass.FLOAT:
                ret_val = context.builder.fmul(left, self.right.generate_llvm(context))
            elif type_info.type_class == TypeClass.INTEGER:
                ret_val = context.builder.mul(left, self.right.generate_llvm(context))
            else:
                raise NotImplementedError()
        elif self.operation == BinaryOperation.XOR:
            if type_info.type_class in (TypeClass.INTEGER, TypeClass.BOOLEAN):
                ret_val = context.builder.xor(left, self.right.generate_llvm(context))
            else:
                raise NotImplementedError()
        else:
            raise NotImplementedError()
        
        if context.compilation_opts.add_debug_symbols:
            if isinstance(ret_val, ir.Instruction):
                ret_val.set_metadata("dbg", self.add_debug_info(context))
        assert isinstance(ret_val, ir.NamedValue)
        return ret_val

@dataclass
class PUnaryOperation(PExpression):
    """Unary operation node"""
    operation: UnaryOperation
    operand: PExpression

    def __init__(self, operation: UnaryOperation, operand: PExpression, lexeme: Lexeme):
        super().__init__(NodeType.UNARY_OPERATION, lexeme.pos)
        self.operation = operation
        self.operand = operand
        # TODO: This should always be false no?
        self.operand.is_lvalue = False
        
    @property
    def children(self) -> Generator["PStatement", None, None]:
        yield self.operand
        return

    def generate_llvm(self, context:CodeGenContext, get_ptr_to_expression=False) -> ir.Value:
        assert not get_ptr_to_expression, "Cannot get pointer to an operation result"
        
        operand = self.operand.generate_llvm(context, 
                                             get_ptr_to_expression=self.operation in (
                                                 UnaryOperation.POST_DECREMENT, UnaryOperation.POST_INCREMENT,
                                                 UnaryOperation.PRE_DECREMENT, UnaryOperation.PRE_INCREMENT))
        assert isinstance(self.operand.expr_type, IRCompatibleTyp)
        assert isinstance(self.expr_type, IRCompatibleTyp)
        
        ret_val = None
        typeinfo = self.operand.expr_type.type_info
        if self.operation in (UnaryOperation.BOOL_NOT, UnaryOperation.LOGIC_NOT, UnaryOperation.MINUS):
            if self.operation == UnaryOperation.BOOL_NOT:
                if typeinfo.type_class == TypeClass.FLOAT:
                    ret_val = context.builder.fcmp_ordered('==', operand, self.operand.expr_type.default_llvm_value(context))
                elif typeinfo.type_class == TypeClass.BOOLEAN:
                    ret_val = context.builder.not_(operand)
                else:
                    ret_val = context.builder.icmp_unsigned('==', operand, self.operand.expr_type.default_llvm_value(context))
            elif self.operation == UnaryOperation.LOGIC_NOT:
                if typeinfo.type_class in [TypeClass.FLOAT, TypeClass.BOOLEAN, TypeClass.INTEGER]:
                    ret_val = context.builder.not_(operand)
                else:
                    raise NotImplementedError()
            elif self.operation == UnaryOperation.MINUS:
                if typeinfo.type_class == TypeClass.FLOAT:
                    ret_val = context.builder.fneg(operand)
                else:
                    ret_val = context.builder.neg(operand)
        elif self.operation in (UnaryOperation.POST_DECREMENT, UnaryOperation.POST_INCREMENT,
                                UnaryOperation.PRE_DECREMENT, UnaryOperation.PRE_INCREMENT):
            operand_ptr = operand
            operand = context.builder.load(operand_ptr,
                                           typ=self.operand.expr_type.get_llvm_value_type(context))
            if self.operation == UnaryOperation.PRE_INCREMENT:
                ret_val = context.builder.add(operand, ir.Constant(self.expr_type.get_llvm_value_type(context),1))
                # self.operand is a ptr (or NamedValue)
                assert isinstance(self.operand, (PIdentifier, PArrayIndexing, PThis, PDotAttribute))
                context.builder.store(ret_val, operand_ptr)
            elif self.operation == UnaryOperation.PRE_DECREMENT:
                ret_val = context.builder.sub(operand, ir.Constant(self.expr_type.get_llvm_value_type(context),1))
                assert isinstance(self.operand, (PIdentifier, PArrayIndexing, PThis, PDotAttribute))
                context.builder.store(ret_val, operand_ptr)
            elif self.operation == UnaryOperation.POST_INCREMENT:
                ret_val = operand
                after_op_val = context.builder.add(operand, ir.Constant(self.expr_type.get_llvm_value_type(context),1))
                assert isinstance(self.operand, (PIdentifier, PArrayIndexing, PThis, PDotAttribute))
                context.builder.store(after_op_val, operand_ptr)
            elif self.operation == UnaryOperation.POST_DECREMENT:
                ret_val = operand
                after_op_val = context.builder.sub(operand, ir.Constant(self.expr_type.get_llvm_value_type(context),1))
                assert isinstance(self.operand, (PIdentifier, PArrayIndexing, PThis, PDotAttribute))
                context.builder.store(after_op_val, operand_ptr)
        else:
            raise NotImplementedError()
        if context.compilation_opts.add_debug_symbols and isinstance(ret_val, _HasMetadata):
                ret_val.set_metadata("dbg", self.add_debug_info(context))
        assert isinstance(ret_val, ir.NamedValue)
        return ret_val

@dataclass
class PIfStatement(PStatement):
    """If statement node"""
    condition: PExpression
    then_block: PBlock
    else_block: Optional[PBlock]

    def __init__(self, condition: PExpression, then_block: PBlock,
                 else_block: Optional[PBlock], lexeme: Lexeme):
        super().__init__(NodeType.IF_STATEMENT, lexeme.pos)
        self.condition = condition
        self.then_block = then_block
        self.else_block = else_block
        
    @property
    def children(self) -> Generator["PStatement", None, None]:
        yield self.condition 
        yield self.then_block
        if self.else_block is not None:
            yield self.else_block
        return
    
    def generate_llvm(self, context: CodeGenContext) -> None:
        cond = self.condition.generate_llvm(context)
        if context.compilation_opts.add_debug_symbols and isinstance(cond, _HasMetadata):
            cond.set_metadata('dbg', self.condition.add_di_location_metadata(context))

        if self.else_block is not None:
            with context.builder.if_else(cond) as (then, otherwise):
                with then:
                    self.then_block.generate_llvm(context)
                with otherwise:
                    self.else_block.generate_llvm(context)
        else:
            with context.builder.if_then(cond):
                self.then_block.generate_llvm(context)
                

@dataclass
class PWhileStatement(PStatement):
    """While loop node"""
    condition: PExpression
    body: PBlock

    def __init__(self, condition: PExpression, body: PBlock, lexeme: Lexeme):
        super().__init__(NodeType.WHILE_STATEMENT, lexeme.pos)
        self.condition = condition
        self.body = body
        
    @property
    def children(self) -> Generator["PStatement", None, None]:
        yield self.condition
        yield self.body
        return
        
    def generate_llvm(self, context: CodeGenContext) -> None:
        # Create basic blocks for loop structure
        cond_block = context.builder.append_basic_block(f"w_cond_{self.condition.position.index}")
        body_block = context.builder.append_basic_block(f"w_body_{self.body.position.index}")
        after_block = context.builder.append_basic_block(f"w_after_{self.body.position.index}")
        #add info pointing to condition and end of loop for continue/break
        context.loopinfo.append(LoopContext(cond_block,after_block, is_for_loop=False, current_loop_scope_depth=0))

        context.builder.branch(cond_block)
        # Generate condition in condition block
        context.builder.position_at_end(cond_block)
        cond_value = self.condition.generate_llvm(context)
        if context.compilation_opts.add_debug_symbols and isinstance(cond_value, _HasMetadata):
            cond_value.set_metadata('dbg', self.condition.add_di_location_metadata(context))

        context.builder.cbranch(cond_value, body_block, after_block)

        # Generate loop body in body block
        context.builder.position_at_end(body_block)
        self.body.generate_llvm(context)
        
        # make sure end of body is reachable:
        assert isinstance(context.builder.block, ir.Block)
        if context.builder.block.is_terminated:
            context.loopinfo.pop()
            return
        # Branch back to condition block after body execution
        context.builder.branch(cond_block)

        # Set insertion point to after block for subsequent code
        context.builder.position_at_end(after_block)
        #pop loop info, we're leaving block
        context.loopinfo.pop()

@dataclass
class PForStatement(PScopeStatement):
    """For loop node"""
    initializer: Union[PVariableDeclaration, PAssignment, PNoop]
    condition: Union[PExpression, PNoop]
    increment: Union[PStatement, PNoop]
    body: PBlock

    def __init__(self, initializer: Union[PVariableDeclaration, PAssignment, PNoop], condition: Union[PExpression, PNoop],
                 increment: Union[PStatement, PNoop], body: PBlock, lexeme: Lexeme, scope:LocalScope):
        super().__init__(NodeType.FOR_STATEMENT, lexeme.pos, scope)
        self.initializer = initializer
        self.condition = condition
        self.increment = increment
        self.body = body
        
    @property
    def children(self) -> Generator["PStatement", None, None]:
        yield self.initializer
        yield self.condition
        yield self.increment
        yield self.body
        return
        
    def generate_llvm(self, context: CodeGenContext) -> None:
        for_initializer_ref_vars = 0
        if isinstance(self.initializer, PVariableDeclaration):
            for_initializer_ref_vars = int(self.initializer.typer_pass_var_type.is_reference_type)
        
        self.parent_scope.generate_gc_scope_entry(context)
        
        init = self.initializer.generate_llvm(context)
        if context.compilation_opts.add_debug_symbols and isinstance(init, _HasMetadata):
            init.set_metadata('dbg', self.initializer.add_di_location_metadata(context))
        # Create basic blocks for loop structure
        increment_block:ir.Block = context.builder.append_basic_block(f"for_inc_{self.condition.position.index}")
        cond_block:ir.Block = context.builder.append_basic_block(f"for_cond_{self.condition.position.index}")
        body_block:ir.Block = context.builder.append_basic_block(f"for_body_{self.body.position.index}")
        after_block:ir.Block = context.builder.append_basic_block(f"for_after_{self.body.position.index}")
        #add info pointing to condition and end of loop for continue/break
        context.loopinfo.append(LoopContext(increment_block,after_block,
                                            is_for_loop=True, current_loop_scope_depth=1))
        
        context.builder.branch(cond_block)
        # Generate condition in condition block
        context.builder.position_at_end(cond_block)
        cond_value = self.condition.generate_llvm(context)
        if context.compilation_opts.add_debug_symbols and isinstance(cond_value, _HasMetadata):
            cond_value.set_metadata('dbg', self.condition.add_di_location_metadata(context))
        context.builder.cbranch(cond_value, body_block, after_block)

        # Generate loop body in body block
        context.builder.position_at_end(body_block)
        self.body.generate_llvm(context)
        assert isinstance(context.builder.block, ir.Block)
        if not context.builder.block.is_terminated:
            context.builder.branch(increment_block)
        # at the end of the for loop run the increment statement
        context.builder.position_at_end(increment_block)
        increment = self.increment.generate_llvm(context)
        if context.compilation_opts.add_debug_symbols and isinstance(increment, _HasMetadata):
            increment.set_metadata('dbg', self.increment.add_di_location_metadata(context))
        # Branch back to condition block after body execution
        context.builder.branch(cond_block)

        # Set insertion point to after block for subsequent code
        context.builder.position_at_end(after_block)
        #pop loop info, we're leaving block
        context.loopinfo.pop()
        #remove initializer scope
        self.parent_scope.generate_gc_scope_leave(context)

@dataclass
class PReturnStatement(PStatement):
    """Return statement node"""
    value: PExpression

    def __init__(self, value: Optional[PExpression], lexeme: Lexeme):
        super().__init__(NodeType.RETURN_STATEMENT, lexeme.pos)
        self.value = value or PVoid(lexeme)
        
    @property
    def children(self) -> Generator["PStatement", None, None]:
        if self.value is not None:
            yield self.value
        return
        
    def generate_llvm(self, context: CodeGenContext) -> None:
        # if we are within the module's main function
        if context.global_exit_block is not None:
            #make sure the main function returns the correct return type
            assert isinstance(self.value.expr_type, IRCompatibleTyp)
            assert self.value.expr_type.get_llvm_value_type(context) == ir.IntType(32)
            exit_code = self.parent_scope.get_symbol(EXIT_CODE_GLOBAL_VAR_NAME, self.position).ir_alloca
            assert exit_code is not None
            instr = context.builder.store(self.value.generate_llvm(context), exit_code)
            # leave all scopes not needed as GC cleanup will handle destroying all scopes
            # go to exit
            context.builder.branch(context.global_exit_block)
            
        elif isinstance(self.value, PVoid):
            self.parent_scope.generate_gc_scope_leave(context, self.depth_from_next_function)
            instr = context.builder.ret_void()
        else:
            ret_val = self.value.generate_llvm(context)
            self.parent_scope.generate_gc_scope_leave(context, self.depth_from_next_function)
            instr = context.builder.ret(ret_val)

        if context.compilation_opts.add_debug_symbols:
            instr.set_metadata("dbg", self.add_di_location_metadata(context))
            
    
    @staticmethod
    def implicit_return(position:Position, parent:PScopeStatement):
        ret = PReturnStatement(None, Lexeme.default)
        ret._parent = parent
        ret.position = position
        return ret

@dataclass
class PCall(PExpression):
    """Function call node"""
    function: Union["PIdentifier", "PDotAttribute"]
    arguments: List[PExpression]

    def __init__(self, function: Union["PIdentifier","PDotAttribute"], arguments: List[PExpression], lexeme: Lexeme):
        super().__init__(NodeType.FUNCTION_CALL, lexeme.pos)
        self.function = function
        self.arguments = arguments
        
        if isinstance(function, PIdentifier) and function.name == 'main':
            raise CompilerError(f"Cannot call main function directly")
        
    @property
    def children(self) -> Generator["PStatement", None, None]:
        for stmt in (self.function, 
                     *self.arguments):
            yield stmt
        return
    
    def generate_llvm(self, context:CodeGenContext, get_ptr_to_expression=False) -> ir.Value:
        assert not get_ptr_to_expression, "Cannot get pointer to a function result"
        # get function pointer
        assert isinstance(self.function.expr_type, FunctionTyp)
        args = []
        if self.function.expr_type.is_method:
            if isinstance(self.function, PIdentifier):
                # if it's just a identifier referencing a method within a class
                this_symbol = self.parent_scope.get_symbol(PThis.NAME)
                assert this_symbol.ir_alloca is not None
                args.append(this_symbol.ir_alloca)
            else:
                # assert isinstance(self.function, PDotAttribute)
                this = self.function.left.generate_llvm(context, False)
                args.append(this)
        fun = self.function.generate_llvm(context)
        assert isinstance(fun, ir.Function)
        # get ptrs to all arguments
        for arg in self.arguments:
            args.append(arg.generate_llvm(context))
        for i, expected_arg in enumerate(fun.args):
            args[i] = context.builder.bitcast(args[i], expected_arg.type)
        #call function
        ret_val = context.builder.call(fun, args)
        if context.compilation_opts.add_debug_symbols:
            ret_val.set_metadata('dbg', self.add_di_location_metadata(context)) 
        return ret_val

# @dataclass
# class PMethodCall(PExpression):
#     """Method call node"""
#     object: PExpression
#     method_name: "PIdentifier"
#     arguments: List[PExpression]

#     def __init__(self, object: PExpression, method: "PIdentifier", arguments: List[PExpression], lexeme: Lexeme):
#         super().__init__(NodeType.METHOD_CALL, lexeme.pos)
#         self.object = object
#         self.method_name = method
#         self.arguments = arguments
        
#     @property
#     def children(self) -> Generator["PStatement", None, None]:
#         for stmt in (self.object,
#                      self.method_name, 
#                      *self.arguments):
#             yield stmt
#         return
    
#     def generate_llvm(self, context:CodeGenContext, get_ptr_to_expression=False) -> ir.Value:
#         assert not get_ptr_to_expression, "Cannot get pointer to a function return value"
#         assert self.object.expr_type is not None
#         # TODO: get method function pointer from a v-table
#         this = self.object.generate_llvm(context, False)
#         # null_check on "this" ONLY if it's a reference type
#         if self.object.expr_type.is_reference_type:
#             null_check_func = self.parent_scope.get_symbol(FUNC_NULL_REF_CHECK,
#                                                                            self.position).ir_func
#             assert null_check_func is not None
#             context.builder.call(null_check_func, [this, context.get_char_ptr_from_string(self.position.filename),
#                                                 ir.Constant(ir.IntType(32), self.position.line),
#                                                 ir.Constant(ir.IntType(32), self.position.column)])

#         fun = self.object.expr_type.methods[self.method_name.name].symbol.ir_func
#         assert isinstance(fun, ir.Function)
#         #setup arguments
#         args = [this] + [a.generate_llvm(context) for a in self.arguments]
#         args = [context.builder.bitcast(arg,expected_arg.type) 
#                 for arg, expected_arg in zip(args, fun.args)]
#         assert isinstance(fun, ir.Function)
#         ret_val = context.builder.call(fun, args)
#         if context.compilation_opts.add_debug_symbols:
#             ret_val.set_metadata('dbg', self.add_di_location_metadata(context)) 
#         return ret_val

@dataclass
class PIdentifier(PExpression):
    """Identifier node"""
    name: str

    def __init__(self, name: str, lexeme_pos: Union[Lexeme, Position]):
        super().__init__(NodeType.IDENTIFIER, 
                         lexeme_pos.pos if isinstance(lexeme_pos, Lexeme) else lexeme_pos)
        self.name = name
    
    def generate_llvm(self, context: CodeGenContext, get_ptr_to_expression=False) -> Union[ir.Value, ir.Function]:
        variable = self.parent_scope.get_symbol(self.name, self.position)
        
        if variable.is_function:
            assert variable.ir_func is not None
            return variable.ir_func
        assert variable.ir_alloca is not None
        if get_ptr_to_expression:
            return variable.ir_alloca
        else:
            assert isinstance(self.expr_type, IRCompatibleTyp)
            var_type = self.expr_type.get_llvm_value_type(context)
            return context.builder.load(variable.ir_alloca, typ=var_type)

@dataclass
class PThis(PExpression):
    """This node: reference to the current instance"""
    
    """string representation of 'this'. Used to avoid magic values"""
    NAME:ClassVar[str] = "this"
    
    def __init__(self, lexeme:Lexeme):
        super().__init__(NodeType.IDENTIFIER, lexeme.pos)
    
    def generate_llvm(self, context: CodeGenContext, get_ptr_to_expression=False) -> ir.Value:
        this = self.parent_scope.get_symbol(self.NAME, self.position).ir_alloca
        assert this is not None
        assert isinstance(self.expr_type, IRCompatibleTyp)
        var_type = self.expr_type.get_llvm_value_type(context)
        if get_ptr_to_expression:
            return this
        else:
            return context.builder.load(this, typ=var_type)
    
@dataclass
class PVoid(PExpression):
    """Node used for empty return statement"""
    def __init__(self, lexeme:Lexeme):
        super().__init__(NodeType.EMPTY, lexeme.pos)

@dataclass
class PLiteral(PExpression):
    """Literal value node"""
    value: Any
    literal_type: str  # "int", "float", "string", "char", "bool" or "null"

    def __init__(self, value: Any, literal_type: str, lexeme: Lexeme):
        super().__init__(NodeType.LITERAL, lexeme.pos)
        self.value = value
        self.literal_type = literal_type
        
    def generate_llvm(self, context:CodeGenContext, get_ptr_to_expression=False) -> ir.Constant:
        assert not get_ptr_to_expression, "Cannot get pointer to a literal value"
        assert isinstance(self.expr_type, IRCompatibleTyp)
        const_typ = self.expr_type.get_llvm_value_type(context)
        if self.literal_type == "string":
            string_obj = context.get_string_const(self.value)
            # Bitcast from anon-type to actual string type
            string_obj = context.builder.bitcast(string_obj, const_typ)
            assert isinstance(string_obj, ir.CastInstr)
            return string_obj
        return ir.Constant(const_typ, self.value)

@dataclass
class PCast(PExpression):
    """Type cast expression node"""
    target_type: 'PType'  # The type to cast to
    expression: PExpression  # The expression being cast

    def __init__(self, target_type:'PType', expression:PExpression):
        super().__init__(NodeType.CAST, target_type.position)
        self.target_type = target_type
        self.expression = expression
        
    @property
    def children(self) -> Generator["PStatement", None, None]:
        yield self.target_type
        yield self.expression
        return
    
    def generate_llvm(self, context:CodeGenContext, get_ptr_to_expression=False) -> ir.Value:
        assert not get_ptr_to_expression, "Cannot get pointer to a casted value"
        expr = self.expression.generate_llvm(context)
        original_type = self.expression.expr_type
        target_type = self.expr_type
        assert isinstance(original_type, IRCompatibleTyp)
        assert isinstance(target_type, IRCompatibleTyp)

        
        original_type_info = original_type.type_info
        target_type_info = target_type.type_info
        
        ret_val = expr
        if target_type == original_type:
            pass #nothing to do
        elif original_type_info.type_class == TypeClass.BOOLEAN:
            ret_val = context.builder.select(
                    cond=expr,
                    lhs=ir.Constant(target_type.get_llvm_value_type(context), 1),
                    rhs=ir.Constant(target_type.get_llvm_value_type(context), 0)
                )
        elif (target_type.is_reference_type or original_type.is_reference_type):
            if target_type.name == "null":
                #cast to void ptr
                result = context.builder.bitcast(expr, ir.PointerType())
                assert isinstance(result, ir.Value)
                ret_val = result
            raise CompilerError("Cannot cast reference types yet")
        elif target_type_info.type_class == TypeClass.FLOAT:
            #convert to float
            if original_type_info.type_class in [TypeClass.INTEGER]:
                if original_type_info.is_signed:
                    val = context.builder.sitofp(expr, target_type.get_llvm_value_type(context))
                    assert isinstance(val, ir.Value)
                    ret_val = val
                else:
                    val = context.builder.uitofp(expr, target_type.get_llvm_value_type(context))
                    assert isinstance(val, ir.Value)
                    ret_val = val
            elif original_type_info.type_class == TypeClass.FLOAT:
                if original_type_info.bit_width > target_type_info.bit_width:
                    #truncate
                    val = context.builder.fptrunc(expr, target_type.get_llvm_value_type(context))
                    assert isinstance(val, ir.Value)
                    ret_val = val
                else: #increase size of FP
                    val = context.builder.fpext(expr, target_type.get_llvm_value_type(context))
                    assert isinstance(val, ir.Value)
                    ret_val = val
            else:
                raise TypingError(f"Cannot Cast from {original_type} to {target_type}")
        elif target_type_info.type_class == TypeClass.INTEGER:
            #convert to int
            if original_type_info.type_class in [TypeClass.INTEGER]:
                if original_type_info.bit_width < target_type_info.bit_width: #cast to larger int
                    if original_type_info.is_signed:
                        val = context.builder.sext(expr, target_type.get_llvm_value_type(context))
                        assert isinstance(val, ir.Value)
                        ret_val = val
                    else:
                        val = context.builder.zext(expr, target_type.get_llvm_value_type(context))
                        assert isinstance(val, ir.Value)
                        ret_val = val
                elif original_type_info.bit_width > target_type_info.bit_width:
                    val = context.builder.trunc(expr, target_type.get_llvm_value_type(context))
                    assert isinstance(val, ir.Value)
                    ret_val = val
                else:
                    #sign to unsigned or vice versa
                    val = context.builder.bitcast(expr, target_type.get_llvm_value_type(context))
                    assert isinstance(val, ir.Value)
                    ret_val = val
            elif original_type_info.type_class == TypeClass.FLOAT:
                #float to int
                if target_type_info.is_signed:
                    val = context.builder.fptosi(expr, target_type.get_llvm_value_type(context))
                    assert isinstance(val, ir.Value)
                    ret_val = val
                else:
                    val = context.builder.fptoui(expr, target_type.get_llvm_value_type(context))
                    assert isinstance(val, ir.Value)
                    ret_val = val
        elif target_type_info.type_class == TypeClass.BOOLEAN:
            #do zero check
            if original_type_info.type_class == TypeClass.INTEGER:
                ret_val = context.builder.select(
                    cond=context.builder.icmp_unsigned('!=', expr, ir.Constant(ir.IntType(1), 0)),
                    lhs=ir.Constant(ir.IntType(1), True),
                    rhs=ir.Constant(ir.IntType(1), False)
                )
            elif original_type_info.type_class == TypeClass.FLOAT:
                ret_val = context.builder.select(
                    cond=context.builder.fcmp_ordered('!=', expr, ir.Constant(original_type.get_llvm_value_type(context), 0)),
                    lhs=ir.Constant(ir.IntType(1), True),
                    rhs=ir.Constant(ir.IntType(1), False)
                )
            else:
                ret_val = context.builder.select(
                    cond=context.builder.icmp_unsigned('!=', expr, ir.Constant(ir.PointerType(), ir.PointerType.null)),
                    lhs=ir.Constant(ir.IntType(1), True),
                    rhs=ir.Constant(ir.IntType(1), False)
                )
        else:
            raise TypingError(f"Cannot Cast from {original_type} to {target_type}")
        if context.compilation_opts.add_debug_symbols and isinstance(ret_val, _HasMetadata):
            ret_val.set_metadata('dbg', self.add_di_location_metadata(context))
        return ret_val

@dataclass
class PBreakStatement(PStatement):
    """Break statement node"""

    def __init__(self, lexeme: Lexeme):
        super().__init__(NodeType.BREAK_STATEMENT, lexeme.pos)
        
    def generate_llvm(self, context: CodeGenContext) -> None:
        end_of_loop_block = context.loopinfo[-1].end_of_loop_block
        self.parent_scope.generate_gc_scope_leave(context, self.depth_from_next_loop)
        instr = context.builder.branch(end_of_loop_block)
        if context.compilation_opts.add_debug_symbols:
            instr.set_metadata("dbg", self.add_di_location_metadata(context))

@dataclass
class PContinueStatement(PStatement):
    """Continue statement node"""

    def __init__(self, lexeme: Lexeme):
        super().__init__(NodeType.CONTINUE_STATEMENT, lexeme.pos)
        
    def generate_llvm(self, context: CodeGenContext) -> None:
        continue_loop_block = context.loopinfo[-1].continue_loop_block
        self.parent_scope.generate_gc_scope_leave(context, 
                                                  self.depth_from_next_loop-1) # -1 to stay within the loop scope
        instr = context.builder.branch(continue_loop_block)
        if context.compilation_opts.add_debug_symbols:
            instr.set_metadata("dbg", self.add_di_location_metadata(context))

@dataclass
class PAssertStatement(PStatement):
    """Assert statement node"""
    condition: PExpression
    message: Optional[PLiteral]

    def __init__(self, condition: PExpression, message: Optional[PLiteral], lexeme: Lexeme):
        super().__init__(NodeType.ASSERT_STATEMENT, lexeme.pos)
        self.condition = condition
        self.message = message
        
    @property
    def children(self) -> Generator["PStatement", None, None]:
        yield self.condition
        if self.message is not None:
            yield self.message
        return
    
    def generate_llvm(self, context: CodeGenContext) -> None:
        condition_is_false = context.builder.not_(self.condition.generate_llvm(context))
        if context.compilation_opts.add_debug_symbols and isinstance(condition_is_false, _HasMetadata):
            condition_is_false.set_metadata("dbg", self.add_di_location_metadata(context))
        with context.builder.if_then(condition_is_false, False):
            if self.message is not None:
                self.exit_with_error(context, error_code=125, error_message="Assertion Failed: " + str(self.message.value))
            else:
                self.exit_with_error(context, error_code=125, error_message="Assertion Failed:")
            
@dataclass
class PDotAttribute(PExpression):
    left:PExpression
    right:PIdentifier
    ir_value_left:Optional[ir.Value] #Used to avoid dubplicate calculations of the left side when calling methods

    def __init__(self, left: PExpression, right:PIdentifier):
        super().__init__(NodeType.ATTRIBUTE, left.position)
        self.left = left
        self.right = right
        
    @property
    def children(self) -> Generator["PStatement", None, None]:
        yield self.left
        yield self.right
        return
    
    def generate_llvm(self, context: CodeGenContext, get_ptr_to_expression=False) -> Union[ir.Value, ir.Function]:
        # It's an actual variable we're trying to access
        # TODO fix for mew method calling 
        if isinstance(self.left.expr_type, IRCompatibleTyp):
            # left**
            left_mem_loc = self.ir_value_left or self.left.generate_llvm(context, get_ptr_to_expression=True)
            self.ir_value_left = left_mem_loc
            assert isinstance(left_mem_loc, ir.NamedValue)
            assert self.left.expr_type is not None
            left_type = self.left.expr_type.get_llvm_value_type(context)
            assert isinstance(left_type, ir.types._TypedPointerType)
            # left* (a pointer to the object on the heap/stack)
            left_ptr = context.builder.load(left_mem_loc, typ=left_type)
            #Do null check here
            null_check_func = self.parent_scope.get_symbol(FUNC_NULL_REF_CHECK, self.position).ir_func
            assert null_check_func is not None
            context.builder.call(null_check_func, [left_ptr, context.get_char_ptr_from_string(self.position.filename),
                                                ir.Constant(ir.IntType(32), self.position.line),
                                                ir.Constant(ir.IntType(32), self.position.column)])
            
            assert isinstance(left_ptr.type, ir.PointerType)
            for i, field in enumerate(sorted(self.left.expr_type.fields.values(),
                                             key=lambda f:f.field_index)):
                if field.name == self.right.name:
                    assert isinstance(field, PClassField)
                    # found the correct field
                    field_ptr = context.builder.gep(left_ptr, [ir.Constant(ir.IntType(32), 0), # *left
                                                            ir.Constant(ir.IntType(32), i) #(*left).ith element
                                                            ],
                                                    source_etype=left_type.pointee)
                    #fix typing of the element gotten
                    field_ptr_type = ir.PointerType(field.typer_pass_var_type.get_llvm_value_type(context))
                    field_ptr = context.builder.bitcast(field_ptr, field_ptr_type)
                    assert isinstance(field_ptr, (ir.CastInstr, ir.GEPInstr))
                    if context.compilation_opts.add_debug_symbols:
                        field_ptr.set_metadata("dbg", self.add_di_location_metadata(context))
                    
                    if get_ptr_to_expression:
                        return field_ptr
                    else:
                        return context.builder.load(field_ptr,
                                                    typ=field.typer_pass_var_type.get_llvm_value_type(context))
            raise TypingError(f"Cannot find field {self.right.name} in type {self.left.expr_type}")
        else: 
            # Here for static Class access
            raise NotImplementedError()

@dataclass
class PTernaryOperation(PExpression):
    """Ternary operation node"""
    condition: PExpression
    true_value: PExpression
    false_value: PExpression

    def __init__(self, condition: PExpression, true_value: PExpression, false_value: PExpression, lexeme: Lexeme):
        super().__init__(NodeType.TERNARY_OPERATION, lexeme.pos)
        self.condition = condition
        self.true_value = true_value
        self.false_value = false_value
        
    @property
    def children(self) -> Generator["PStatement", None, None]:
        yield self.condition
        yield self.true_value
        yield self.false_value
        return
    
    def generate_llvm(self, context:CodeGenContext, get_ptr_to_expression=False) -> ir.Value:
        cond = self.condition.generate_llvm(context)
        if context.compilation_opts.add_debug_symbols and isinstance(cond, _HasMetadata):
            cond.set_metadata("dbg", self.condition.add_di_location_metadata(context))
        true_block = context.builder.append_basic_block(f'ternary_true_{self.position.index}')
        false_block = context.builder.append_basic_block(f'ternary_false_{self.position.index}')
        end_block = context.builder.append_basic_block(f'after_ternary{self.position.index}')
        
        # Conditional branch based on left side
        context.builder.cbranch(cond, true_block, false_block)

        # True block: evaluate of condition is true
        context.builder.position_at_end(true_block)
        true_val = self.true_value.generate_llvm(context, get_ptr_to_expression)
        if context.compilation_opts.add_debug_symbols and isinstance(true_val, _HasMetadata):
            true_val.set_metadata("dbg", self.true_value.add_di_location_metadata(context))
        #set block for phi node (in case blocks are edited for true_val, a nested ternry for example)
        true_block_end = context.builder.block
        assert isinstance(true_block_end, ir.Block)
        context.builder.branch(end_block)
        
        context.builder.position_at_end(false_block)
        false_val = self.false_value.generate_llvm(context, get_ptr_to_expression)
        if context.compilation_opts.add_debug_symbols and isinstance(false_block, _HasMetadata):
            false_block.set_metadata("dbg", self.false_value.add_di_location_metadata(context))
        #set block for phi node (in case blocks are edited for false_val, a nested ternry for example)
        false_block_end = context.builder.block
        assert isinstance(false_block_end, ir.Block)
        context.builder.branch(end_block)

        # Merge block: PHI node to combine results
        context.builder.position_at_end(end_block)
        assert isinstance(self.expr_type, IRCompatibleTyp)
        phi = context.builder.phi(self.expr_type.get_llvm_value_type(context))
        phi.add_incoming(true_val, true_block_end)
        phi.add_incoming(false_val, false_block_end)

        return phi

@dataclass
class PObjectInstantiation(PExpression):
    """Represents a class instantiation expression """
    class_type: 'PType'  # The type of class being instantiated

    def __init__(self, class_type: 'PType', lexeme):
        """
        Initialize object instantiation node

        Args:
            class_type: The type/name of the class being instantiated
            lexeme: The lexeme containing position information (the 'new' keyword)
        """
        super().__init__(NodeType.OBJECT_INSTANTIATION, lexeme.pos)
        self.class_type = class_type
        
    @property
    def children(self) -> Generator["PStatement", None, None]:
        yield self.class_type
        return
    
    def generate_llvm(self, context:CodeGenContext, get_ptr_to_expression=False) -> ir.Value:
        size_t_type = ir.IntType(ir.PointerType().get_abi_size(context.target_data)*8)
        
        assert not get_ptr_to_expression, "Cannot get ptr to Object reference"
        alloc_func = self.parent_scope.get_symbol(FUNC_GC_ALLOCATE_OBJECT, self.position).ir_func
        assert alloc_func is not None
        assert self.expr_type is not None
        allocated_ptr = context.builder.call(alloc_func,
            [ir.Constant(size_t_type, context.type_ids[self.expr_type.name])])
        assert isinstance(self.expr_type, IRCompatibleTyp)
        class_ref_type = self.expr_type.get_llvm_value_type(context)
        assert isinstance(class_ref_type, ir.types._TypedPointerType)
        allocated_ptr = context.builder.bitcast(allocated_ptr, class_ref_type)
        assert isinstance(allocated_ptr, ir.NamedValue)

        if context.compilation_opts.add_debug_symbols and isinstance(allocated_ptr, _HasMetadata):
            allocated_ptr.set_metadata("dbg", self.add_di_location_metadata(context))
        
        # Implicit constructor
        # Element is allocated
        # Now we need to allocate all of its fields
        for field_num, field in enumerate(self.expr_type.fields.values()):
            assert isinstance(field, PClassField)
            if field.default_value is None:
                continue #not set it's a null_ptr (zero-ed out field for value types)
            field_ptr = context.builder.gep(allocated_ptr, 
                                            [
                                                ir.Constant(ir.IntType(32), 0),
                                                ir.Constant(ir.IntType(32), field_num)
                                            ],
                                            source_etype=class_ref_type.pointee)
            context.builder.comment(f"Initializes default value for {self.class_type.type_string}.{field.name}")
            context.builder.store(field.default_value.generate_llvm(context, get_ptr_to_expression=False),
                                  field_ptr)
        
        return allocated_ptr

@dataclass
class PArrayInstantiation(PExpression):
    """Represents array instantiation like new int[10]"""
    element_type: 'PType'  # The base type of array elements
    size: PExpression  # The size expression for the array
    _element_type_typ:Optional[IRCompatibleTyp] = None
    
    @property
    def element_type_typ(self):
        if self._element_type_typ is None:
            raise TypingError(f"Element type has not been typed yet")
        return self._element_type_typ

    def __init__(self, element_type: 'PType', size: PExpression, lexeme):
        """
        Initialize array instantiation node

        Args:
            element_type: The type of elements in the array
            size: Expression defining the array size
            lexeme: The lexeme containing position information (the 'new' keyword)
        """
        super().__init__(NodeType.ARRAY_INSTANTIATION, lexeme.pos)
        self.element_type = element_type
        self.size = size
        
    @property
    def children(self) -> Generator["PStatement", None, None]:
        yield self.size
        yield self.element_type
        return
    
    def generate_llvm(self, context: CodeGenContext, get_ptr_to_expression=False) -> ir.Value:
        assert not get_ptr_to_expression, "Cannot get ptr to array reference"
        n_elements = self.size.generate_llvm(context)
        
        if self.element_type_typ.is_reference_type:
            # Each element is a reference type
            alloc_func = self.parent_scope.get_symbol(FUNC_GC_ALLOCATE_REFERENCE_OBJ_ARRAY, self.position).ir_func
            assert alloc_func is not None
            # void* __PS_AllocateRefArray(size_t num_elements)
            ptr_to_array = context.builder.call(alloc_func, [n_elements])
        else:
            # Each element is a value type
            element_size = self.element_type_typ.get_llvm_value_type(context).get_abi_size(
                                                                context.target_data,
                                                                context.module.context)
            assert element_size in [1,2,4,8]
            element_size = ir.Constant(ir.IntType(8), element_size)
            alloc_func = self.parent_scope.get_symbol(FUNC_GC_ALLOCATE_VALUE_ARRAY, self.position).ir_func
            assert alloc_func is not None
            # void* __PS_AllocateValueArray(size_t element_size, size_t num_elements)
            ptr_to_array = context.builder.call(alloc_func, [element_size, n_elements])
        

        if context.compilation_opts.add_debug_symbols and isinstance(ptr_to_array, _HasMetadata):
            ptr_to_array.set_metadata("dbg", self.add_di_location_metadata(context))

        return ptr_to_array

@dataclass
class PType(PStatement):
    type_string:str
    expr_type:Optional[BaseTyp]
    parent_namespace:Optional['PNamespaceType']
    """Should onty be set if the type is accessed by referencing the Namespace (e.g. Namespace.SubSpace.SomeType)"""

    def __init__(self, base_type:str, lexeme_pos:Union[Lexeme,Position],
                 parent_namespace:Optional['PNamespaceType'] = None):
        super().__init__(NodeType.TYPE, lexeme_pos if isinstance(lexeme_pos, Position) else lexeme_pos.pos)
        self.type_string = base_type
        self.expr_type = None
        self.parent_namespace = parent_namespace

    def __str__(self):
        if self.parent_namespace is not None:
            return f"{self.parent_namespace}.{self.type_string}"
        return self.type_string
    
    def __hash__(self) -> int:
        return hash(str(self))
    
    def __eq__(self, value: object) -> bool:
        if not isinstance(value, PType):
            return False
        return str(self) == str(value)
    
    @property
    def children(self) -> Generator["PStatement", None, None]:
        if self.parent_namespace is not None:
            yield self.parent_namespace
        return
    
@dataclass
class PNamespaceType(PType):
    builtin:ClassVar['PNamespaceType']
    
    def __init__(self, base_type:str, lexeme_pos:Union[Lexeme,Position],
                 parent_namespace:Optional['PNamespaceType'] = None):
        super().__init__(base_type, lexeme_pos,
                         parent_namespace=parent_namespace)
        
    @staticmethod
    def fromPtype(ptype:PType) -> 'PNamespaceType':
        assert type(ptype) is PType
        return PNamespaceType(base_type=ptype.type_string,
                              lexeme_pos=ptype.position,
                              parent_namespace=ptype.parent_namespace)
        
PNamespaceType.builtin = PNamespaceType(base_type=BUILTIN_NAMESPACE,
                                        lexeme_pos=Position.default)

@dataclass
class PFunctionType(PType):
    argument_ptypes:List[PType]
    return_ptype:PType
    
    @staticmethod
    def string_representation(return_ptype:PType, argument_ptypes:List[PType]):
        return (f"({','.join([t.type_string for t in argument_ptypes])})" +
                f"->{return_ptype}")
    
    def __init__(self, return_ptype:PType, lexeme_pos:Union[Lexeme,Position],
                 argument_ptypes:Optional[List[PType]]=None,
                 parent_namespace:Optional['PNamespaceType']=None):
        self.argument_ptypes = argument_ptypes or []
        self.return_ptype = return_ptype
        super().__init__(self.string_representation(self.return_ptype,
                                                    self.argument_ptypes),
                         lexeme_pos=lexeme_pos,
                         parent_namespace=parent_namespace)
    
    @property
    def children(self) -> Generator["PStatement", None, None]:
        yield self.return_ptype
        if self.parent_namespace is not None:
            yield self.parent_namespace
        for arg_ptype in self.argument_ptypes:
            yield arg_ptype
        return
        
    def __hash__(self) -> int:
        return super().__hash__()
    
    def __eq__(self, value: object) -> bool:
        return super().__eq__(value)
    
    def __str__(self):
        return super().__str__()

@dataclass
class PArrayType(PType):
    """
    Represents an array type in the AST.
    For example: int[] or MyClass[][]
    """
    element_type: Union['PArrayType',PType]

    def __init__(self, base_type:Union['PArrayType',PType],
                 lexeme_pos:Union[Lexeme, Position]):
        self.element_type = base_type
        super().__init__(str(self), lexeme_pos)
        self.parent_namespace = None

    def __str__(self) -> str:
        """Convert array type to string representation"""
        return f"{str(self.element_type)}[]"
    
    def __hash__(self) -> int:
        return hash(str(self))
    
    def __eq__(self, value: object) -> bool:
        if not isinstance(value, PArrayType):
            return False
        return str(self) == str(value)
    
    @property
    def children(self) -> Generator["PStatement", None, None]:
        yield self.element_type
        if self.parent_namespace is not None:
            yield self.parent_namespace
        return
    
    @property
    def dimensions(self):
        dim = 1
        base_type = self.element_type
        while isinstance(base_type, PArrayType):
            base_type = base_type.element_type
            dim += 1
        return dim
    
    @property
    def base_type(self):
        base_type = self.element_type
        while isinstance(base_type, PArrayType):
            base_type = base_type.element_type
        return base_type

@dataclass
class PArrayIndexing(PExpression):
    """
    Represents an array access expression in the AST.
    For example: arr[0] or arr[i][j]
    """
    array: PExpression # The array being accessed
    index: PExpression  # The index expression

    def __init__(self, array: PExpression, index: PExpression, lexeme):
        """Initialize array access node with position from lexeme"""
        super().__init__(NodeType.ARRAY_ACCESS, lexeme.pos)
        self.array = array
        self.index = index
        
    @property
    def children(self) -> Generator["PStatement", None, None]:
        yield self.array
        yield self.index
        return
    
    def generate_llvm(self, context: CodeGenContext, get_ptr_to_expression=False) -> ir.Value:
        #get type of array
        assert isinstance(self.array.expr_type, ArrayTyp)
        assert isinstance(self.expr_type, IRCompatibleTyp)
        array_struct_type = self.array.expr_type.get_llvm_value_type(context)
        assert isinstance(array_struct_type, ir.types._TypedPointerType)
        array_element_type = self.expr_type.get_llvm_value_type(context)
        
        array_obj = self.array.generate_llvm(context, False)
        array_element_size_in_bytes = array_element_type.get_abi_size(context.target_data)
        assert array_element_size_in_bytes in [1,2,4,8], f"Array element should be 1,2,4 or 8 bytes long not {array_element_size_in_bytes}"
        array_element_size_in_bytes = ir.Constant(ir.IntType(8), array_element_size_in_bytes)
        index = self.index.generate_llvm(context, False)
        
        element_fetch_function = self.parent_scope.get_symbol(FUNC_GET_ARRAY_ELEMENT_PTR, self.position).ir_func
        assert element_fetch_function is not None
        array_element_ptr = context.builder.call(element_fetch_function,
                                                 [
                                                     array_obj, #the array ref
                                                     array_element_size_in_bytes, #the element size (should be 1,2,4 or 8)
                                                     index, # the array index to fetch (negative values are accepted)
                                                     context.get_char_ptr_from_string(self.position.filename),
                                                     ir.Constant(ir.IntType(32), self.position.line),
                                                     ir.Constant(ir.IntType(32), self.position.column)
                                                 ])
        #make sure it's the correct type because the fetcg function returns a void*
        array_element_ptr = context.builder.bitcast(array_element_ptr, ir.PointerType(array_element_type))
        assert isinstance(array_element_ptr, ir.NamedValue)
        if get_ptr_to_expression:
            return array_element_ptr
        else:
            return context.builder.load(array_element_ptr, typ=array_element_type)
    
    def _bounds_check(self, index_ptr:ir.Value, arr_length:ir.Value, context:CodeGenContext):
        """Check the index is within the bounds. Crashes otherwise"""
        out_of_bounds = context.builder.or_(
            context.builder.icmp_unsigned('>=', index_ptr, arr_length),
            context.builder.icmp_unsigned('<', index_ptr, ir.Constant(ir.IntType(64),0))
        )
        with context.builder.if_then(out_of_bounds, False):
            self.exit_with_error(context, 1, f"Cannot access outside of the bounds of the array")

class Parser:
    """Parser for P# language that builds an AST from lexemes"""

    def __init__(self, lexer: Lexer):
        self.lexer = lexer
        self.lexeme_stream = LexemeStream(lexer.lex(), lexer.filename)

        # Define operator precedence
        self.precedence: Dict[Union[BinaryOperation, UnaryOperation, TernaryOperator], int] = {
            BinaryOperation.ASSIGN:0,
            BinaryOperation.COPY:0,
            TernaryOperator.QUESTIONMARK:2,
            BinaryOperation.BOOL_OR: 4,
            BinaryOperation.BOOL_AND: 6,
            BinaryOperation.BOOL_EQ: 8,
            BinaryOperation.BOOL_NEQ: 8,
            BinaryOperation.BOOL_GT: 8,
            BinaryOperation.BOOL_LT: 8,
            BinaryOperation.BOOL_GEQ: 8,
            BinaryOperation.BOOL_LEQ: 8,
            BinaryOperation.LOGIC_OR: 10,
            BinaryOperation.LOGIC_AND: 12,
            BinaryOperation.XOR: 14,
            BinaryOperation.PLUS: 16,
            BinaryOperation.MINUS: 16,
            BinaryOperation.SHIFT_LEFT: 18,
            BinaryOperation.SHIFT_RIGHT: 18,
            BinaryOperation.TIMES: 20,
            BinaryOperation.DIVIDE: 20,
            BinaryOperation.MOD: 20,
            UnaryOperation.BOOL_NOT:22,
            UnaryOperation.LOGIC_NOT:22,
            UnaryOperation.MINUS:22,
            UnaryOperation.POST_INCREMENT:24,
            UnaryOperation.POST_DECREMENT:24,
            UnaryOperation.PRE_INCREMENT:26,
            UnaryOperation.PRE_DECREMENT:26
        }

        self.unary_binary_ops: Dict[LexemeType, Union[BinaryOperation,UnaryOperation, TernaryOperator]] = {
            LexemeType.OPERATOR_BINARY_PLUS: BinaryOperation.PLUS,
            LexemeType.OPERATOR_BINARY_MINUS: BinaryOperation.MINUS,
            LexemeType.OPERATOR_BINARY_TIMES: BinaryOperation.TIMES,
            LexemeType.OPERATOR_BINARY_DIV: BinaryOperation.DIVIDE,
            LexemeType.OPERATOR_BINARY_MOD: BinaryOperation.MOD,
            LexemeType.OPERATOR_BINARY_BOOL_EQ: BinaryOperation.BOOL_EQ,
            LexemeType.OPERATOR_BINARY_BOOL_NEQ: BinaryOperation.BOOL_NEQ,
            LexemeType.OPERATOR_BINARY_BOOL_GT: BinaryOperation.BOOL_GT,
            LexemeType.OPERATOR_BINARY_BOOL_LT: BinaryOperation.BOOL_LT,
            LexemeType.OPERATOR_BINARY_BOOL_GEQ: BinaryOperation.BOOL_GEQ,
            LexemeType.OPERATOR_BINARY_BOOL_LEQ: BinaryOperation.BOOL_LEQ,
            LexemeType.OPERATOR_BINARY_BOOL_AND: BinaryOperation.BOOL_AND,
            LexemeType.OPERATOR_BINARY_BOOL_OR: BinaryOperation.BOOL_OR,
            LexemeType.OPERATOR_BINARY_AND: BinaryOperation.LOGIC_AND,
            LexemeType.OPERATOR_BINARY_OR: BinaryOperation.LOGIC_OR,
            LexemeType.OPERATOR_BINARY_XOR: BinaryOperation.XOR,
            LexemeType.OPERATOR_BINARY_SHL: BinaryOperation.SHIFT_LEFT,
            LexemeType.OPERATOR_BINARY_SHR: BinaryOperation.SHIFT_RIGHT,

            LexemeType.OPERATOR_UNARY_INCREMENT:UnaryOperation.POST_INCREMENT,
            LexemeType.OPERATOR_UNARY_DECREMENT:UnaryOperation.POST_DECREMENT,
            LexemeType.OPERATOR_UNARY_BOOL_NOT:UnaryOperation.BOOL_NOT,
            LexemeType.OPERATOR_UNARY_LOGIC_NOT:UnaryOperation.LOGIC_NOT,

            LexemeType.PUNCTUATION_TERNARYCONDITIONAL_QUESTIONMARK:TernaryOperator.QUESTIONMARK,
        }
        # Set of type keywords
        self.type_keywords: set[LexemeType] = {
            LexemeType.KEYWORD_TYPE_VOID,
            LexemeType.KEYWORD_TYPE_INT8,
            LexemeType.KEYWORD_TYPE_INT16,
            LexemeType.KEYWORD_TYPE_INT32,
            LexemeType.KEYWORD_TYPE_INT64,
            LexemeType.KEYWORD_TYPE_CHAR,
            LexemeType.KEYWORD_TYPE_UINT8,
            LexemeType.KEYWORD_TYPE_UINT16,
            LexemeType.KEYWORD_TYPE_UINT32,
            LexemeType.KEYWORD_TYPE_UINT64,
            LexemeType.KEYWORD_TYPE_STRING,
            LexemeType.KEYWORD_TYPE_FLOAT16,
            LexemeType.KEYWORD_TYPE_FLOAT32,
            LexemeType.KEYWORD_TYPE_FLOAT64,
            LexemeType.KEYWORD_TYPE_CHAR,
            LexemeType.KEYWORD_TYPE_BOOLEAN
        }

    @property
    def current_lexeme(self):
        return self.lexeme_stream.peek()

    def _expect(self, *lexeme_types: LexemeType) -> Lexeme:
        """Verify current lexeme is of expected type and advance"""
        if self.current_lexeme is Lexeme.default:
            raise ParserError(f"Got Empty Lexeme instead of {' or '.join(lt.name for lt in lexeme_types)}",
                              Lexeme.default)
        if self.current_lexeme.type not in lexeme_types:
            raise ParserError(
                f"Expected one of ({','.join(lt.name for lt in lexeme_types)}), got {self.current_lexeme.type.name if self.current_lexeme else 'EOF'}",
                self.current_lexeme)
        return self.lexeme_stream.advance()

    def _match(self, *lexeme_types: LexemeType) -> bool:
        """Check if current lexeme matches any of the given types"""
        return self._peek_matches(0, *lexeme_types)

    def _peek_matches(self, offset, *lexeme_types: LexemeType) -> bool:
        """Check if next lexeme matches any of the given types at index offset without advancing"""
        assert offset >= 0, "Cannot peek into the past (offset < 0)"
        lexeme = self.lexeme_stream.peek(offset)
        return lexeme is not None and lexeme.type in lexeme_types
    
    def parse_header(self, namespace_parts:Optional[List[str]]=None) -> List[Union['PVariableDeclaration', PFunction, PClass]]:
        """Parses the file as a header file containing only declarations

        Args:
            namespace_parts (List[str], optional): If set verifies that the headerwe are parsing is the correct namespace

        Returns:
            List[Union['PVariableDeclaration', PFunction, PClass]]: _description_
        """
        parsed_header = self.parse(add_std_lib=False)
        header_elements:List[Union['PVariableDeclaration', PFunction, PClass]] = []
        
        for statement in parsed_header.statements:
            if isinstance(statement, PVariableDeclaration):
                header_elements.append(statement)
            elif isinstance(statement, PFunction):
                statement.body = None #this is unused
                header_elements.append(statement)
            elif isinstance(statement, PClass):
                for field in statement.fields.values():
                    field.default_value = None #clear ununsed
                for method in statement.methods:
                    method.body = None #clear unused and makes sure it's just a header
                header_elements.append(statement)
        return header_elements
        

    def parse(self, add_std_lib:bool=True) -> PProgram:
        """Parse the entire program"""
        statements:List[PStatement] = list()
        imports:List[PImport] = []
        if add_std_lib:
            # Adds default Std namespace to the project (only the used functions will be included in the final executable so no prob for size)
            imports.append(PImport([PIdentifier(BUILTIN_NAMESPACE,
                                                Lexeme.default)],
                                    Position.default))
        start_lexeme = self.current_lexeme
        namespace_parts = None
        
        if self._match(LexemeType.KEYWORD_CONTROL_NAMESPACE):
            #handle namespace decleration
            namespace_parts = self._parse_namespace_name()
        block_properties = BlockProperties()

        while self.current_lexeme and self.current_lexeme.type != LexemeType.EOF:
            stmt = self._parse_statement(block_properties)
            if isinstance(stmt, PImport):
                imports.append(stmt)
            else:
                statements.append(stmt)

        assert isinstance(block_properties.current_scope, GlobalScope)
        pprogram = PProgram(statements, start_lexeme,
                            scope=block_properties.current_scope,
                            namespace=namespace_parts,
                            imports=imports)
        return pprogram

    def _parse_object_instantiation(self) -> Union[PObjectInstantiation,PArrayInstantiation]:
        """Parse a class instantiation expression."""
        # Consume 'new' keyword
        new_lexeme = self._expect(LexemeType.KEYWORD_OBJECT_NEW)

        # Parse class name
        if self._match(LexemeType.IDENTIFIER, *self.type_keywords):
            class_name_lexeme = self.current_lexeme
            object_type = self._parse_type()
        else:
            raise ParserError("Expected class name or type after 'new' keyword", self.current_lexeme)

        # Parse parentheses (required, but empty since constructors aren't supported yet)
        if self._match(LexemeType.PUNCTUATION_OPENPAREN):
            self._expect(LexemeType.PUNCTUATION_OPENPAREN)
            self._expect(LexemeType.PUNCTUATION_CLOSEPAREN)

            return PObjectInstantiation(object_type, new_lexeme)
        
        elif self._match(LexemeType.PUNCTUATION_OPENBRACKET):
            if isinstance(object_type, PArrayType):
                raise ParserError(f"Cannot create sub-array before creating parent array.", self.current_lexeme)
            self._expect(LexemeType.PUNCTUATION_OPENBRACKET)
            size = self._parse_expression()
            self._expect(LexemeType.PUNCTUATION_CLOSEBRACKET)
            
            while self._match(LexemeType.PUNCTUATION_OPENBRACKET) and self._peek_matches(1, LexemeType.PUNCTUATION_CLOSEBRACKET):
                self._expect(LexemeType.PUNCTUATION_OPENBRACKET)
                self._expect(LexemeType.PUNCTUATION_CLOSEBRACKET)
                object_type = PArrayType(object_type, object_type.position)
            return PArrayInstantiation(object_type, size, class_name_lexeme)
        else:
            raise ParserError("Invalid Lexeme: Expected opening bracket or opening parenthesis", self.current_lexeme)

    def _parse_namespace_name(self) -> List[str]:
        parts:List[str] = []
        self._expect(LexemeType.KEYWORD_CONTROL_NAMESPACE)
        #handle top level of namspace
        ident = self._expect(LexemeType.IDENTIFIER)
        parts.append(ident.value)
        
        #handle namspace sub-levels
        while self._match(LexemeType.OPERATOR_DOT):
            self._expect(LexemeType.OPERATOR_DOT)
            ident = self._expect(LexemeType.IDENTIFIER)
            parts.append(ident.value)
        #ensure properly terminated
        self._expect(LexemeType.PUNCTUATION_SEMICOLON)
        
        return parts
        
    def _parse_statement(self, block_properties:BlockProperties) -> PStatement:
        """Parse a single statement"""
        if self.current_lexeme is Lexeme.default:
            raise ParserError("Unexpected end of file", self.current_lexeme)

        # Match statement type
        if self._check_declaration(block_properties):
            decl = self._parse_declaration(block_properties)
            block_properties.current_scope.declare_local(decl.symbol)
            return decl
        elif (self._match(LexemeType.IDENTIFIER)
              and (self._peek_matches(1, LexemeType.IDENTIFIER) \
                   or (self._peek_matches(1, LexemeType.PUNCTUATION_OPENBRACKET)
                       and self._peek_matches(2, LexemeType.PUNCTUATION_CLOSEBRACKET)))):
            #starts with a type 
            decl = self._parse_declaration(block_properties)
            block_properties.current_scope.declare_local(decl.symbol)
            return decl
        elif self._match(LexemeType.KEYWORD_CONTROL_IF):
            return self._parse_if_statement(block_properties.copy_with(is_top_level=False))
        elif self._match(LexemeType.KEYWORD_CONTROL_WHILE):
            return self._parse_while_statement(block_properties.copy_with(is_top_level=False))
        elif self._match(LexemeType.KEYWORD_CONTROL_FOR):
            return self._parse_for_statement(block_properties.copy_with(is_top_level=False))
        elif self._match(LexemeType.KEYWORD_CONTROL_RETURN):
            if not block_properties.in_function:
                raise ParserError("Cannot have a return statement outside of a function", self.current_lexeme)
            return self._parse_return_statement()
        elif self._match(LexemeType.KEYWORD_CONTROL_BREAK):
            if not block_properties.is_loop:
                raise ParserError("Cannot have a break statement outside of a loop block", self.current_lexeme)
            return self._parse_break_statement()
        elif self._match(LexemeType.KEYWORD_CONTROL_CONTINUE):
            if not block_properties.is_loop:
                raise ParserError("Cannot have a continue statement outside of a loop block", self.current_lexeme)
            return self._parse_continue_statement()
        elif self._match(LexemeType.KEYWORD_CONTROL_ASSERT):
            return self._parse_assert_statement()
        elif self._match(LexemeType.KEYWORD_CONTROL_IMPORT):
            return self._parse_import(block_properties)
        elif self._match(LexemeType.DISCARD):
            return self._parse_discard()
        elif self._match(LexemeType.KEYWORD_OBJECT_CLASS):
            if not block_properties.is_top_level:
                raise ParserError("Cannot have a break statement outside of a loop block", self.current_lexeme)
            return self._parse_class_definition(block_properties.copy_with(is_class=True,
                                                                           is_top_level=False))
        elif self._match(LexemeType.PUNCTUATION_OPENBRACE):
            block_scope = LocalScope(ScopeType.BlockScope,
                                     block_properties.current_scope)
            return self._parse_block(block_properties.copy_with(is_top_level=False,
                                                                scope=block_scope))

        # Expression statement (assignment, function call, etc.)
        expr = self._parse_expression()
        self._expect(LexemeType.PUNCTUATION_SEMICOLON)
        return expr
    
    def _parse_import(self, block_properties:BlockProperties) -> PImport:
        #TODO change to make closer to C# style
        if not block_properties.is_top_level:
            raise ParserError("All imports must be at the top level of the progam", self.current_lexeme)
        self._expect(LexemeType.KEYWORD_CONTROL_IMPORT)
        namespace_id = self._expect(LexemeType.IDENTIFIER)
        first_lexeme = namespace_id
        parts = [PIdentifier(namespace_id.value,
                                namespace_id)]
        while self._match(LexemeType.OPERATOR_DOT):
            self._expect(LexemeType.OPERATOR_DOT)
            namespace_id = self._expect(LexemeType.IDENTIFIER)
            parts.append(PIdentifier(namespace_id.value,
                                     namespace_id))

        if self._match(LexemeType.KEYWORD_CONTROL_AS):
            self._expect(LexemeType.KEYWORD_CONTROL_AS)
            namespace_alias = self._expect(LexemeType.IDENTIFIER)
        
            self._expect(LexemeType.PUNCTUATION_SEMICOLON)
                
            return PImport(parts,
                           namespace_alias,
                           alias=namespace_alias.value)
        
        self._expect(LexemeType.PUNCTUATION_SEMICOLON)
        return PImport(parts, first_lexeme)
    
    def _check_declaration(self, block_properties:BlockProperties) -> bool:
        """Checks whether the folowing lexemes start a valid declaration (variable or function)

        Returns:
            bool: True if it's a valid declaration (or starts like one), False otherwise
        """
        
        self.lexeme_stream.save_position()
        try:
            if not self._match(*self.type_keywords, LexemeType.IDENTIFIER):
                return False
            self._parse_type()
            self._expect(LexemeType.IDENTIFIER)
            # check if var decl
            return self._match(LexemeType.PUNCTUATION_SEMICOLON, 
                               LexemeType.PUNCTUATION_OPENPAREN,
                               LexemeType.OPERATOR_BINARY_ASSIGN)
        except:
            #failed
            return False
        finally:
            self.lexeme_stream.pop_saved_position()

    def _parse_declaration(self, block_properties:BlockProperties) -> Union[PVariableDeclaration, PFunction]:
        """Parse a variable or function declaration"""
        type_lexeme = self.current_lexeme
        var_type = self._parse_type()

        name_lexeme = self._expect(LexemeType.IDENTIFIER)
        name = name_lexeme.value

        # Function declaration
        if self._match(LexemeType.PUNCTUATION_OPENPAREN):
            if not block_properties.is_top_level:
                raise ParserError("Functions cannot be defined in a scope. They must be defined at the top level.", self.current_lexeme)
            if block_properties.in_function:
                raise ParserError("Functions cannot be defined inside another function. They must be defined at the top level.", self.current_lexeme)
            return self._parse_function_declaration(name, var_type, type_lexeme,
                                                    block_properties.copy_with(
                                                        is_top_level=False,
                                                        in_function=True,
                                                        scope=LocalScope(parent=block_properties.current_scope,
                                                                         scope_type=ScopeType.FunctionScope)))

        # Variable declaration
        initial_value = None
        if self._match(LexemeType.OPERATOR_BINARY_ASSIGN):
            self.lexeme_stream.advance()
            initial_value = self._parse_expression()

        elif self._match(LexemeType.OPERATOR_BINARY_COPY):
            raise NotImplementedError("Copy operation is not implemented yet")

        self._expect(LexemeType.PUNCTUATION_SEMICOLON)
        return PVariableDeclaration(name, var_type, initial_value, type_lexeme)

    def _parse_function_declaration(self, name: str, return_type: PType, start_lexeme: Lexeme,
                                    block_properties:BlockProperties) -> PFunction:
        """Parse a function declaration"""
        self._expect(LexemeType.PUNCTUATION_OPENPAREN)
        parameters:List[PVariableDeclaration] = []
        function_scope = block_properties.current_scope

        # Parse parameters
        if not self._match(LexemeType.PUNCTUATION_CLOSEPAREN):
            while True:
                if not self._match(*self.type_keywords, LexemeType.IDENTIFIER):
                    raise ParserError("Expected type in function parameters", self.current_lexeme)
                param_type = self._parse_type()

                param_name_lexeme = self._expect(LexemeType.IDENTIFIER)
                param = PVariableDeclaration(name=param_name_lexeme.value,
                                             var_type=param_type,
                                             initial_value=None,
                                             lexeme_pos=param_name_lexeme)
                parameters.append(param)
                function_scope.declare_local(param.symbol)

                if not self._match(LexemeType.PUNCTUATION_COMMA):
                    break # Arrived at the end of the params
                # Has more parameters: consume comma
                self._expect(LexemeType.PUNCTUATION_COMMA)

        self._expect(LexemeType.PUNCTUATION_CLOSEPAREN)
        if self._match(LexemeType.PUNCTUATION_SEMICOLON):
            self._expect(LexemeType.PUNCTUATION_SEMICOLON)
            body = None
        else:
            body = self._parse_block(block_properties.copy_with(
                                     scope=NullScope(scope_type=ScopeType.BlockScope,
                                                    parent=function_scope)))

        return PFunction(name, return_type, parameters, body,
                         start_lexeme, scope=function_scope)

    def _parse_block(self, block_properties:BlockProperties) -> PBlock:
        """Parse a block of statements"""
        start_lexeme = self._expect(LexemeType.PUNCTUATION_OPENBRACE)
        statements = []

        while not self._match(LexemeType.PUNCTUATION_CLOSEBRACE):
            if not self.current_lexeme:
                raise ParserError("Unterminated block", start_lexeme)
            statements.append(self._parse_statement(block_properties))

        self._expect(LexemeType.PUNCTUATION_CLOSEBRACE)
        return PBlock(statements, start_lexeme, 
                      block_properties=block_properties)

    def _parse_type(self) -> PType:
        """
        Parse a type declaration, which can be either a simple type or an array type.
        Examples:
            - int
            - MyClass
            - int[]
            - MyClass[][]
            - Namespace.MyClass
            

        Returns:
            Union[str, PArrayType]: The parsed type (either a string for simple types
                                or PArrayType for array types)
        """
        # Parse base type first
        type_lexeme = self._expect(*self.type_keywords, LexemeType.IDENTIFIER)
        base_type = PType(type_lexeme.value, type_lexeme)
        while self._match(LexemeType.OPERATOR_DOT):
            self._expect(LexemeType.OPERATOR_DOT)
            lexeme = self._expect(LexemeType.IDENTIFIER, *self.type_keywords)
            base_type = PType(base_type=lexeme.value,
                              lexeme_pos=lexeme,
                              parent_namespace=PNamespaceType.fromPtype(base_type))

        # Check for array brackets
        while self._match(LexemeType.PUNCTUATION_OPENBRACKET) and self._peek_matches(1, LexemeType.PUNCTUATION_CLOSEBRACKET):
            self._expect(LexemeType.PUNCTUATION_OPENBRACKET)
            self._expect(LexemeType.PUNCTUATION_CLOSEBRACKET)
            base_type = PArrayType(base_type, type_lexeme)

        return base_type

    def _parse_array_indexing(self, array: PExpression) -> PArrayIndexing:
        """
        Parse an array access expression (e.g., arr[index]).
        Called after seeing an opening bracket during expression parsing.

        Args:
            array (PExpression): The array expression being accessed

        Returns:
            PArrayAccess: Node representing the array access

        Raises:
            ParserError: If array access syntax is invalid
        """
        if not isinstance(array, PExpression):
            raise ParserError("Cannot index any other than an expression", self.current_lexeme)
        open_bracket = self._expect(LexemeType.PUNCTUATION_OPENBRACKET)
        index = self._parse_expression()
        self._expect(LexemeType.PUNCTUATION_CLOSEBRACKET)

        return PArrayIndexing(array, index, open_bracket)

    def _parse_expression(self, min_precedence: int = 0, is_lvalue=True) -> PExpression:
        """Parse an expression using precedence climbing"""
        left = self._parse_primary(is_lvalue)
        
        # Continue processing any chained operations (method calls, indexing, dot access)
        left = self._process_chained_operations(left, is_lvalue)
        
        # Binary operations and operators with precedence
        while (not self.current_lexeme is Lexeme.default and
            self.current_lexeme.type in self.unary_binary_ops and
            (self.precedence[self.unary_binary_ops[self.current_lexeme.type]] >= min_precedence)):
            is_lvalue = False
            op_lexeme = self.current_lexeme
            op = self.unary_binary_ops[op_lexeme.type]

            if isinstance(op, TernaryOperator):
                left = self._parse_ternary_operation(left)
                continue

            # consume op
            self.lexeme_stream.advance()

            if isinstance(op, UnaryOperation):
                if not isinstance(left, (PArrayIndexing, PIdentifier, PDotAttribute, PThis)):
                    raise ParserError("Cannot increment or decrement something other than a variable or array index", op_lexeme)
                if op_lexeme.type == LexemeType.OPERATOR_UNARY_INCREMENT:
                    left = PUnaryOperation(UnaryOperation.POST_INCREMENT,
                                        left, op_lexeme)
                elif op_lexeme.type == LexemeType.OPERATOR_UNARY_DECREMENT:
                    left = PUnaryOperation(UnaryOperation.POST_DECREMENT,
                                        left, op_lexeme)
                else:
                    raise ParserError("Cannot have a Unary Operator other than ++ or -- after an identifier",
                                    op_lexeme)
                continue

            current_precedence = self.precedence[op]

            right = self._parse_expression(current_precedence + 1, is_lvalue=False)
            left = PBinaryOperation(op, left, right, op_lexeme)
            
            # Process any chained operations on the resultant binary operation
            left = self._process_chained_operations(left, False)

        # Parse assignments 
        if is_lvalue and not (self.current_lexeme is Lexeme.default):
            if self._match(LexemeType.OPERATOR_BINARY_ASSIGN):
                if not isinstance(left, (PDotAttribute, PIdentifier, PArrayIndexing)):
                    raise ParserError("Cannot assign to anything else than a variable, array or field",
                                    self.current_lexeme)
                self._expect(LexemeType.OPERATOR_BINARY_ASSIGN)
                assign_lexeme = self.current_lexeme
                left = PAssignment(left, self._parse_expression(is_lvalue=False), assign_lexeme)
            elif self._match(LexemeType.OPERATOR_BINARY_COPY):
                raise NotImplementedError("Copy Operator is not yet supported")
                if not isinstance(left, (PDotAttribute, PIdentifier)):
                    raise ParserError("Cannot assign to anything else than a variable or property", self.current_lexeme)
            else:
                # Handle +=, -=, *= ... and other binop assignments
                for lexeme_type, op in ((LexemeType.OPERATOR_BINARY_PLUSEQ, BinaryOperation.PLUS),
                                        (LexemeType.OPERATOR_BINARY_MINUSEQ, BinaryOperation.MINUS),
                                        (LexemeType.OPERATOR_BINARY_TIMESEQ, BinaryOperation.TIMES),
                                        (LexemeType.OPERATOR_BINARY_DIVEQ, BinaryOperation.DIVIDE),
                                        (LexemeType.OPERATOR_BINARY_ANDEQ, BinaryOperation.LOGIC_AND),
                                        (LexemeType.OPERATOR_BINARY_OREQ, BinaryOperation.LOGIC_OR),
                                        (LexemeType.OPERATOR_BINARY_XOREQ, BinaryOperation.XOR),
                                        (LexemeType.OPERATOR_BINARY_SHLEQ, BinaryOperation.SHIFT_LEFT),
                                        (LexemeType.OPERATOR_BINARY_SHREQ, BinaryOperation.SHIFT_RIGHT)):
                    if self._match(lexeme_type):
                        curr_lexeme = self.current_lexeme
                        self._expect(lexeme_type)
                        assert isinstance(left, (PIdentifier, PDotAttribute, PArrayIndexing))
                        left = PAssignment(left,
                                        # do binop
                                        PBinaryOperation(op,
                                                            left,
                                                            self._parse_expression(is_lvalue=False),
                                                            self.current_lexeme),
                                        curr_lexeme)
                        break
        return left

    def _parse_discard(self) -> PDiscard:
        """Parse an expression and discard the value"""
        discard_lexeme = self._expect(LexemeType.DISCARD)
        
        self._expect(LexemeType.OPERATOR_BINARY_ASSIGN)
        expression = self._parse_expression(is_lvalue=False)
        self._expect(LexemeType.PUNCTUATION_SEMICOLON)
        
        return PDiscard(expression, discard_lexeme)

    def _parse_cast(self) -> PCast:
        """Parse a C-style cast expression: (type)expr"""
        cast_lexeme = self._expect(LexemeType.PUNCTUATION_OPENPAREN)

        # Parse the target type - can be primitive type or custom class name
        if not (self._match(*self.type_keywords, LexemeType.IDENTIFIER)):
            raise ParserError("Expected type name in cast expression", self.current_lexeme)

        target_type = self._parse_type()

        self._expect(LexemeType.PUNCTUATION_CLOSEPAREN)

        # Parse the expression being cast (with high precedence to bind tightly)
        # max precedence because a cast applies only directly to the expressions after it
        expression = self._parse_expression(min_precedence=max(self.precedence.values()))

        return PCast(target_type, expression)

    def _parse_primary(self, is_lvalue=True) -> PExpression:
        """Parse a primary expression 
        (identifier, literal, parenthesized expr, cast, chained dot access, calls, etc.)"""
        if self.current_lexeme is Lexeme.default:
            raise ParserError("Unexpected end of file", self.current_lexeme)

        # Handle opening parenthesis - could be cast or grouped expression
        if self._match(LexemeType.PUNCTUATION_OPENPAREN):
            open_paren_lexeme = self._expect(LexemeType.PUNCTUATION_OPENPAREN)  # consume opening paren
            
            # Check if this might be a cast by looking for a type
            
            if self._match(*self.type_keywords, LexemeType.IDENTIFIER):
                # Remember current position to backtrack if needed
                self.lexeme_stream.save_position()
                
                # Try to parse as a type
                try:
                    potential_type = self._parse_type()
                    
                    # If we find a closing paren after the type, it's likely a cast
                    if self._match(LexemeType.PUNCTUATION_CLOSEPAREN):
                        self._expect(LexemeType.PUNCTUATION_CLOSEPAREN)
                        # Parse expression being cast (with high precedence)
                        # expression = self._parse_expression(min_precedence=max(self.precedence.values()))
                        expression = self._parse_primary(is_lvalue=False)
                        self.lexeme_stream.drop_saved_position()
                        return PCast(potential_type, expression)
                    
                    else:
                        # Not a cast, restore position and continue as grouped expression
                        self.lexeme_stream.pop_saved_position()
                except ParserError:
                    # Not a valid type, restore position
                    self.lexeme_stream.pop_saved_position()
            
            # Parse as a normal parenthesized expression
            expr = self._parse_expression(is_lvalue=False)
            self._expect(LexemeType.PUNCTUATION_CLOSEPAREN)
            return expr

        # Handle literals
        elif self._match(LexemeType.NUMBER_INT, LexemeType.NUMBER_FLOAT,
                        LexemeType.STRING_LITERAL, LexemeType.NUMBER_CHAR):
            return self._parse_literal()

        # Handle identifiers and calls
        elif self._match(LexemeType.IDENTIFIER, LexemeType.KEYWORD_OBJECT_THIS):
            return self._parse_identifier_or_call_or_array_indexing()

        # Handle unary operators
        elif self._match(LexemeType.OPERATOR_BINARY_MINUS,
                        LexemeType.OPERATOR_UNARY_BOOL_NOT,
                        LexemeType.OPERATOR_UNARY_LOGIC_NOT,
                        LexemeType.OPERATOR_UNARY_INCREMENT,
                        LexemeType.OPERATOR_UNARY_DECREMENT):
            op_map = {
                LexemeType.OPERATOR_BINARY_MINUS: UnaryOperation.MINUS,
                LexemeType.OPERATOR_UNARY_BOOL_NOT: UnaryOperation.BOOL_NOT,
                LexemeType.OPERATOR_UNARY_INCREMENT: UnaryOperation.PRE_INCREMENT,
                LexemeType.OPERATOR_UNARY_DECREMENT: UnaryOperation.PRE_DECREMENT,
                LexemeType.OPERATOR_UNARY_LOGIC_NOT: UnaryOperation.LOGIC_NOT
            }

            op_lexeme = self.lexeme_stream.advance()
            op = op_map[op_lexeme.type]
            # Parse the expression with appropriate precedence
            operand = self._parse_primary()  # Use primary to handle unary op precedence correctly

            if (op in (UnaryOperation.PRE_DECREMENT, UnaryOperation.PRE_INCREMENT)
                and not isinstance(operand, (PArrayIndexing, PIdentifier, PDotAttribute, PThis))):
                raise ParserError("Cannot increment or decrement something other than a variable", op_lexeme)

            return PUnaryOperation(op, operand, op_lexeme)

        # Handle boolean literals
        elif self._match(LexemeType.KEYWORD_OBJECT_TRUE, LexemeType.KEYWORD_OBJECT_FALSE):
            value = self.current_lexeme.type == LexemeType.KEYWORD_OBJECT_TRUE
            lexeme = self.lexeme_stream.advance()
            return PLiteral(value, "bool", lexeme)

        # Handle null literal
        elif self._match(LexemeType.KEYWORD_OBJECT_NULL):
            lexeme = self.lexeme_stream.advance()
            return PLiteral(None, "null", lexeme)

        elif self._match(LexemeType.KEYWORD_OBJECT_NEW):
            return self._parse_object_instantiation()

        raise ParserError("Unexpected token in expression", self.current_lexeme)

    def _process_chained_operations(self, expr: PExpression, is_lvalue=True) -> PExpression:
        """Process any chained operations like method calls, array indexing, or dot access"""
        while True:
            # Process any potential chaining
            if self._match(LexemeType.OPERATOR_DOT):
                # Handle dot access
                expr = self._parse_member_access(expr)
            elif self._match(LexemeType.PUNCTUATION_OPENBRACKET):
                # Handle array indexing
                expr = self._parse_array_indexing(expr)
            elif self._match(LexemeType.PUNCTUATION_OPENPAREN):
                # Handle method/function calls
                if not isinstance(expr, (PIdentifier, PDotAttribute)):
                    raise ParserError(f"Cannot call a {type(expr)}. Only an identifier or property can be called",
                                    self.current_lexeme)
                expr = self._parse_call_and_arguments(expr)
            else:
                # No more chaining
                break
        return expr

    def _parse_literal(self) -> PLiteral:
        """Parse a literal value"""
        lexeme = self.lexeme_stream.advance()

        #TODO implement integer and float suffixing to change default literal bit_size (default is i32 or f32)
        if lexeme.type == LexemeType.NUMBER_INT:
            return PLiteral(int(lexeme.value), "int", lexeme)
        elif lexeme.type == LexemeType.NUMBER_FLOAT:
            return PLiteral(float(lexeme.value), "float", lexeme)
        elif lexeme.type == LexemeType.STRING_LITERAL:
            # Remove quotes from string literal
            return PLiteral(lexeme.value[1:-1], "string", lexeme)
        elif lexeme.type == LexemeType.NUMBER_CHAR:
            # Handle char literal
            return PLiteral(ord(lexeme.value[1:-1]), "char", lexeme)

        raise ParserError("Invalid literal", lexeme)

    def _parse_identifier_or_call_or_array_indexing(self) -> Union[PThis, PCall, PIdentifier, PDotAttribute, PArrayIndexing]:
        """Parse an identifier and any subsequent field accesses, method calls, or function calls.

        This method handles the following patterns:
        - Simple identifier: myVar
        - Function call: myFunction()
        - Property access: myObject.field
        - Method call: myObject.method()
        - Chained access: myObject.field.subField.method()
        - Array Indexing: some_array[index] 

        Returns:
            Union[PExpression, PIdentifier, PArrayIndexing, PDotAttribute]: The parsed expression

        Raises:
            ParserError: If there's an invalid token in the expression
        """
        # Parse the initial identifier
        if self._match(LexemeType.KEYWORD_OBJECT_THIS):
            expr = PThis(self._expect(LexemeType.KEYWORD_OBJECT_THIS))
        else:
            id_lexeme = self._expect(LexemeType.IDENTIFIER)
            expr = PIdentifier(id_lexeme.value, id_lexeme)

        while True:
            # Check for field access or method call
            if self._match(LexemeType.OPERATOR_DOT):
                expr = self._parse_member_access(expr)

            # Handle indexing identifier
            elif self._match(LexemeType.PUNCTUATION_OPENBRACKET):
                expr = self._parse_array_indexing(expr)
            elif self._match(LexemeType.PUNCTUATION_OPENPAREN):
                if not isinstance(expr, (PIdentifier, PDotAttribute)):
                    raise ParserError(f"Cannot call a {type(expr)}. Only an identifier can be called",
                                    self.current_lexeme)
                expr = self._parse_call_and_arguments(expr)

            # No more chaining
            else:
                break

        return expr

    def _parse_call_and_arguments(self, function: Union[PIdentifier,PDotAttribute]) -> PCall:
        """Parse function call arguments.

        Args:
            function (PIdentifier|PDotAttribute): The function expression to be called

        Returns:
            PFunctionCall: The parsed function call

        Raises:
            ParserError: If there's a syntax error in the argument list
        """
        open_paren_lexeme = self._expect(LexemeType.PUNCTUATION_OPENPAREN)
        arguments = []

        # Parse arguments if any
        if not self._match(LexemeType.PUNCTUATION_CLOSEPAREN):
            while True:
                arguments.append(self._parse_expression())
                if not self._match(LexemeType.PUNCTUATION_COMMA):
                    break
                self._expect(LexemeType.PUNCTUATION_COMMA)

        self._expect(LexemeType.PUNCTUATION_CLOSEPAREN)
        return PCall(function, arguments, open_paren_lexeme)

    def _parse_member_access(self, left: PExpression) -> PDotAttribute:
        """Parse a member access expression, a field access.

        Args:
            left (PExpression): The expression before the dot operator

        Returns:
            PDotAttribute: The parsed member access

        Raises:
            ParserError: If there's a syntax error in the member access
        """
        # Consume the dot
        self._expect(LexemeType.OPERATOR_DOT)

        # Get identifier after dot
        member_lexeme = self._expect(LexemeType.IDENTIFIER)
        member_identifier = PIdentifier(member_lexeme.value, member_lexeme)

        # Generate PDot for the field/method access
        return PDotAttribute(left, member_identifier)

    def _parse_if_statement(self, block_properties:BlockProperties) -> PIfStatement:
        """Parse an if statement"""
        if_lexeme = self._expect(LexemeType.KEYWORD_CONTROL_IF)
        self._expect(LexemeType.PUNCTUATION_OPENPAREN)
        condition = self._parse_expression()
        self._expect(LexemeType.PUNCTUATION_CLOSEPAREN)

        # Then block can be a single statement or be a {braced block}
        then_block_scope = LocalScope(ScopeType.BlockScope,
                                        parent=block_properties.current_scope)
        then_block_props = block_properties.copy_with(scope=then_block_scope)
        if self._match(LexemeType.PUNCTUATION_OPENBRACE):
            then_block = self._parse_block(then_block_props)
        else:
            start_lexeme = self.current_lexeme
            then_block = self._parse_statement(then_block_props)
            then_block = PBlock([then_block], start_lexeme,
                                block_properties=then_block_props)

        else_block = None

        if self._match(LexemeType.KEYWORD_CONTROL_ELSE):
            self.lexeme_stream.advance()
            else_block_scope = LocalScope(ScopeType.BlockScope,
                                        parent=block_properties.current_scope)
            else_block_props = block_properties.copy_with(scope=else_block_scope)
            # Then block can be a single statement or be a {braced block}
            if self._match(LexemeType.PUNCTUATION_OPENBRACE):
                else_block = self._parse_block(else_block_props)
            else:
                start_lexeme = self.current_lexeme
                else_block = self._parse_statement(else_block_props)
                else_block = PBlock([else_block], start_lexeme,
                                    block_properties=else_block_props)

        return PIfStatement(condition, then_block, else_block, if_lexeme)

    def _parse_while_statement(self, block_properties:BlockProperties) -> PWhileStatement:
        """Parse a while loop statement"""
        while_lexeme = self._expect(LexemeType.KEYWORD_CONTROL_WHILE)
        self._expect(LexemeType.PUNCTUATION_OPENPAREN)
        condition = self._parse_expression()
        self._expect(LexemeType.PUNCTUATION_CLOSEPAREN)

        block_properties = block_properties.copy_with(is_loop=True,
                                                      scope=LocalScope(scope_type=ScopeType.LoopScope,
                                                                       parent=block_properties.current_scope))

        if self._match(LexemeType.PUNCTUATION_OPENBRACE):
            body = self._parse_block(block_properties)
        else:
            start_lexeme = self.current_lexeme
            body = PBlock([self._parse_statement(block_properties)],
                          start_lexeme,
                          block_properties=block_properties)
        return PWhileStatement(condition, body, while_lexeme)

    def _parse_for_statement(self, block_properties:BlockProperties) -> PForStatement:
        """Parse a for loop statement"""
        for_lexeme = self._expect(LexemeType.KEYWORD_CONTROL_FOR)
        self._expect(LexemeType.PUNCTUATION_OPENPAREN)
        
        for_scope = LocalScope(ScopeType.LoopScope,
                               parent=block_properties.current_scope)
        block_properties = block_properties.copy_with(is_loop=True,
                                                      scope=NullScope(ScopeType.BlockScope,
                                                                      parent=for_scope))

        # Initialize statement (optional)
        if self._match(LexemeType.PUNCTUATION_SEMICOLON):
            initializer = PNoop(self.current_lexeme)
            self._expect(LexemeType.PUNCTUATION_SEMICOLON)
        else:
            initializer = self._parse_statement(block_properties)
            assert isinstance(initializer, (PAssignment, PVariableDeclaration))

        # Condition (optional)
        if self._match(LexemeType.PUNCTUATION_SEMICOLON):
            condition = PNoop(self.current_lexeme)
        else:
            condition = self._parse_expression()
        self._expect(LexemeType.PUNCTUATION_SEMICOLON)

        # Increment statement (optional)
        if self._match(LexemeType.PUNCTUATION_CLOSEPAREN):
            increment = PNoop(self.current_lexeme)
        else:
            increment = self._parse_expression()

        self._expect(LexemeType.PUNCTUATION_CLOSEPAREN)

        if self._match(LexemeType.PUNCTUATION_OPENBRACE):
            body = self._parse_block(block_properties)
        else:
            start_lexeme = self.current_lexeme
            body = PBlock([self._parse_statement(block_properties)],
                          start_lexeme,
                          block_properties=block_properties)

        return PForStatement(initializer, condition, increment, body,
                             for_lexeme, scope=for_scope)

    def _parse_return_statement(self) -> PReturnStatement:
        """Parse a return statement"""
        return_lexeme = self._expect(LexemeType.KEYWORD_CONTROL_RETURN)
        value = None

        if not self._match(LexemeType.PUNCTUATION_SEMICOLON):
            value = self._parse_expression()

        self._expect(LexemeType.PUNCTUATION_SEMICOLON)
        return PReturnStatement(value, return_lexeme)

    def _parse_break_statement(self) -> PBreakStatement:
        """Parse a break statement"""
        break_lexeme = self._expect(LexemeType.KEYWORD_CONTROL_BREAK)
        self._expect(LexemeType.PUNCTUATION_SEMICOLON)
        return PBreakStatement(break_lexeme)

    def _parse_continue_statement(self) -> PContinueStatement:
        """Parse a continue statement"""
        continue_lexeme = self._expect(LexemeType.KEYWORD_CONTROL_CONTINUE)
        self._expect(LexemeType.PUNCTUATION_SEMICOLON)
        return PContinueStatement(continue_lexeme)

    def _parse_assert_statement(self) -> PAssertStatement:
        """Parse an assert statement"""
        assert_lexeme = self._expect(LexemeType.KEYWORD_CONTROL_ASSERT)
        # self._expect(LexemeType.PUNCTUATION_OPENPAREN)
        condition = self._parse_expression()

        message = None
        if self._match(LexemeType.PUNCTUATION_COMMA):
            self.lexeme_stream.advance()
            message = self._parse_expression()
            assert isinstance(message, PLiteral)

        # self._expect(LexemeType.PUNCTUATION_CLOSEPAREN)
        self._expect(LexemeType.PUNCTUATION_SEMICOLON)
        return PAssertStatement(condition, message, assert_lexeme)

    def _parse_class_definition(self, block_properties:BlockProperties) -> PClass:
        """Parse a class definition"""
        class_lexeme = self._expect(LexemeType.KEYWORD_OBJECT_CLASS)
        class_name_lexeme = self._expect(LexemeType.IDENTIFIER)

        self._expect(LexemeType.PUNCTUATION_OPENBRACE)
        fields: List[PClassField] = []
        methods: List[PMethod] = []
        
        class_ptype = PType(class_name_lexeme.value, class_name_lexeme)
        class_symbol = Symbol(
            class_name_lexeme.value,
            class_name_lexeme.pos,
            class_ptype
        )
        block_properties.current_scope.declare_local(class_symbol)
        
        class_scope = ClassScope(block_properties.current_scope,
                                 class_ptype)
        
        block_properties = block_properties.copy_with(is_class=True,
                                                      scope=class_scope)
        while not self._match(LexemeType.PUNCTUATION_CLOSEBRACE):
            if self._match(*self.type_keywords, LexemeType.IDENTIFIER):
                # Parse field or method type
                type_lexeme = self.current_lexeme
                type_name = self._parse_type()

                name_lexeme = self._expect(LexemeType.IDENTIFIER)
                member_name = name_lexeme.value

                if self._match(LexemeType.PUNCTUATION_OPENPAREN):
                    # Method
                    method = self._parse_function_declaration(member_name, type_name, type_lexeme,
                                                              block_properties.copy_with(in_function=True,
                                                                                         scope=LocalScope(parent=block_properties.current_scope,
                                                                                                          scope_type=ScopeType.FunctionScope)))
                    methods.append(PMethod.fromPFunction(method, class_ptype))
                else:
                    # Property
                    is_public = True  # TODO: Handle visibility modifiers
                    default_value = None
                    if self._match(LexemeType.OPERATOR_BINARY_ASSIGN):
                        self._expect(LexemeType.OPERATOR_BINARY_ASSIGN)
                        default_value = self._parse_expression(is_lvalue=False)
                    self._expect(LexemeType.PUNCTUATION_SEMICOLON)
                    fields.append(PClassField(name=member_name, 
                                              type=type_name,
                                              is_public=is_public,
                                              lexeme=type_lexeme,
                                              default_value=default_value,
                                              field_index=0))
            else:
                raise ParserError("Expected class member definition", self.current_lexeme)

        self._expect(LexemeType.PUNCTUATION_CLOSEBRACE)
        #sort fields to place all pointers (reference types) at the begining of the struct
        #it ise useful for the GC to tarverse the object's fields that are reference types
        fields.sort(key= lambda p:
                    int(p.var_type.type_string in ['bool', 'char', 'i8', 'u8', 'i16', 'u16', 'f16', 
                                                    'i32', 'u32', 'f32', 'i64', 'u64', 'f64', 'ul'])
            )
        class_fields:Dict[str, PClassField] = {}
        for i, field in enumerate(fields):
            field.field_index = i
            class_fields[field.name] = field
        return PClass(class_name_lexeme.value, class_fields, methods,
                      class_lexeme, type_symbol=class_symbol,
                      scope=class_scope)

    def _parse_ternary_operation(self, condition) -> PTernaryOperation:
        """Parse a ternary operation (condition ? true_value : false_value)"""

        self._expect(LexemeType.PUNCTUATION_TERNARYCONDITIONAL_QUESTIONMARK)
        true_value = self._parse_expression()

        self._expect(LexemeType.PUNCTUATION_TERNARYSEPARATOR_COLON)
        false_value = self._parse_expression()

        return PTernaryOperation(condition, true_value, false_value, self.current_lexeme)