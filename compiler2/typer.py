from typing import Dict, List, Optional, Union, TextIO
from dataclasses import dataclass, field
from io import StringIO
from copy import deepcopy
from pathlib import Path
from lexer import Lexeme, Lexer, Position
from operations import BinaryOperation, UnaryOperation
from parser import (TypeClass, TypeInfo, TypingError,
                    Parser, PFunction, PClassField, PProgram, PType,
                    PIdentifier, PArrayIndexing, PArrayInstantiation,
                    PBlock, PArrayType, PAssertStatement, PAssignment,
                    PBinaryOperation, PBreakStatement, PCast, PClass,
                    PContinueStatement, PDotAttribute, PExpression,
                    PForStatement, PUnaryOperation, PNoop,
                    PIfStatement, PLiteral, PMethod, PCall,
                    PObjectInstantiation, PReturnStatement, PStatement,
                    PTernaryOperation, PThis,PVariableDeclaration, 
                    PWhileStatement, PDiscard, PVoid, ArrayTyp,
                    PNamespaceType, IRCompatibleTyp, ValueTyp,
                    ReferenceTyp, NamespaceTyp, NodeType, Symbol,
                    PFunctionType, LocalScope, ScopeType, GlobalScope,
                    FunctionTyp, BaseTyp, PImport, TypeTyp)
from constants import BUILTIN_NAMESPACE


#TODO where to find the headers are located
LIB_HEADER_LOC = Path(__file__).parent.joinpath('lib', 'header')


@dataclass
class CompilerWarning(Warning):
    message:str
    position:Position = field(default_factory=Position)
    
    def __str__(self):
        return self.message + f" at location {self.position}"

def create_property(name: str, type_str: str, index:int) -> PClassField:
    """Helper function to create a class property"""
    field = PClassField(
        name=name,
        type=PType(type_str, Lexeme.default),
        is_public=True,
        field_index=index,
        lexeme=Lexeme.default,
        default_value=None,
    )
    # set assigned & read for builtins
    field.is_assigned = True
    field.is_read = True
    return field

def create_method(name: str, return_type: str, class_type_string:str, params: List[tuple[str, str]], builtin:bool=True) -> PMethod:
    """Helper function to create a method"""
    def typestring_to_ptype(typestring:str) -> PType:
        if typestring.endswith('[]'):
            return PArrayType(typestring_to_ptype(typestring[:-2]), Lexeme.default)
        return PType(typestring, Lexeme.default)
    
    
    arguments = [PVariableDeclaration(n, typestring_to_ptype(t), None, Lexeme.default) for t, n in params]
    function_scope = LocalScope(ScopeType.FunctionScope,
                                symbols={
                                    arg.name:Symbol(arg.name, arg.position)
                                    for arg in arguments
                                })
    function_symbol = Symbol(name=PMethod.get_linkable_name(name, BUILTIN_NAMESPACE, class_type_string),
                             declaration_position=Position.default,
                             arguments=arguments
                             )
    return PMethod(
        node_type=NodeType.FUNCTION,
        position=Position.default,
        name=name,
        return_type=typestring_to_ptype(return_type),
        function_args=arguments,
        body=None,
        is_builtin=builtin,
        scope=function_scope,
        symbol=function_symbol
    )

# Define the built-in types with their methods and properties
_builtin_types: Dict[str, IRCompatibleTyp] = {
    # Numeric types
    "i8": ValueTyp(
        name="i8",
        methods={
            "ToString":create_method("ToString", "string", "i8", []),
            "Parse":create_method("Parse", "i8", "i8", [("string", "s")])
        },
        parent_namespace=NamespaceTyp.builtin,
        type_info=TypeInfo(TypeClass.INTEGER, 8, is_signed=True)
    ),
    "i16": ValueTyp(
        name="i16",
        methods={
            "ToString":create_method("ToString", "i16", "string", []),
            "Parse":create_method("Parse", "i16", "i16", [("string", "s")])
        },
        parent_namespace=NamespaceTyp.builtin,
        type_info=TypeInfo(TypeClass.INTEGER, 16, is_signed=True)
    ),
    "i32": ValueTyp(
        name="i32",
        methods={
            "ToString":create_method("ToString", "string", "i32", []),
            "Parse":create_method("Parse", "i32", "i32", [("string", "s")])
        },
        parent_namespace=NamespaceTyp.builtin,
        type_info=TypeInfo(TypeClass.INTEGER, 32, is_signed=True)
    ),
    "i64": ValueTyp(
        name="i64",
        methods={
            "ToString":create_method("ToString", "string", "i64", []),
            "Parse":create_method("Parse", "i64", "i64", [("string", "s")])
        },
        parent_namespace=NamespaceTyp.builtin,
        type_info=TypeInfo(TypeClass.INTEGER, 64, is_signed=True)
    ),
    "u8": ValueTyp(
        name="u8",
        methods={
            "ToString":create_method("ToString", "string", "u8", []),
            "Parse":create_method("Parse", "u8", "u8", [("string", "s")])
        },
        parent_namespace=NamespaceTyp.builtin,
        type_info=TypeInfo(TypeClass.INTEGER, 8, is_signed=False)
    ),
    "u16": ValueTyp(
        name="u16",
        methods={
            "ToString":create_method("ToString", "string", "u16", []),
            "Parse":create_method("Parse", "u16", "u16", [("string", "s")])
        },
        parent_namespace=NamespaceTyp.builtin,
        type_info=TypeInfo(TypeClass.INTEGER, 16, is_signed=False)
    ),
    "u32": ValueTyp(
        name="u32",
        methods={
            "ToString":create_method("ToString", "string", "u32", []),
            "Parse":create_method("Parse", "u32", "u32", [("string", "s")])
        },
        parent_namespace=NamespaceTyp.builtin,
        type_info=TypeInfo(TypeClass.INTEGER, 32, is_signed=False)
    ),
    "u64": ValueTyp(
        name="u64",
        methods={
            "ToString":create_method("ToString", "string", "u64", []),
            "Parse":create_method("Parse", "u64", "u64", [("string", "s")])
        },
        parent_namespace=NamespaceTyp.builtin,
        type_info=TypeInfo(TypeClass.INTEGER, 64, is_signed=False)
    ),
    "ul": ValueTyp(
        name="ul",
        methods={
            "ToString":create_method("ToString", "string", "ul", []),
            "Parse":create_method("Parse", "ul", "ul", [("string", "s")])
        },
        parent_namespace=NamespaceTyp.builtin,
        type_info=TypeInfo(TypeClass.INTEGER, 64, is_signed=False)
    ),
    "f16": ValueTyp(
        name="f16",
        methods={
            "ToString":create_method("ToString", "string", "f16", []),
            "Parse":create_method("Parse", "f16", "f16", [("string", "s")]),
            "Round":create_method("Round", "f16", "f16", []),
            "Floor":create_method("Floor", "f16", "f16", []),
            "Ceiling":create_method("Ceiling", "f16", "f16", [])
        },
        parent_namespace=NamespaceTyp.builtin,
        type_info=TypeInfo(TypeClass.FLOAT, 16)
    ),
    "f32": ValueTyp(
        name="f32",
        methods={
            "ToString":create_method("ToString", "string", "f32", []),
            "Parse":create_method("Parse", "f32", "f32", [("string", "s")]),
            "Round":create_method("Round", "f32", "f32", []),
            "Floor":create_method("Floor", "f32", "f32", []),
            "Ceiling":create_method("Ceiling", "f32", "f32", [])
        },
        parent_namespace=NamespaceTyp.builtin,
        type_info=TypeInfo(TypeClass.FLOAT, 32)
    ),
    "f64": ValueTyp(
        name="f64",
        methods={
            "ToString":create_method("ToString", "string", "f64", []),
            "Parse":create_method("Parse", "f64", "f64", [("string", "s")]),
            "Round":create_method("Round", "f64", "f64", []),
            "Floor":create_method("Floor", "f64", "f64", []),
            "Ceiling":create_method("Ceiling", "f64", "f64", [])
        },
        parent_namespace=NamespaceTyp.builtin,
        type_info=TypeInfo(TypeClass.FLOAT, 64)
    ),

    # String type
    "string": ReferenceTyp(
        name="string",
        methods={
            "ToString":create_method("ToString", "string", "string", []),
            "Substring":create_method("Substring", "string", "string", [("i32", "start"), ("i32", "length")]),
            "ToUpper":create_method("ToUpper", "string", "string", []),
            "ToLower":create_method("ToLower", "string", "string", []),
            "Trim":create_method("Trim", "string", "string", []),
            "Replace":create_method("Replace", "string", "string", [("string", "old"), ("string", "new")]),
            "Split":create_method("Split", "string[]", "string", [("string", "separator")]),
            "Contains":create_method("Contains", "bool", "string", [("string", "value")]),
            "StartsWith":create_method("StartsWith", "bool", "string", [("string", "value")]),
            "EndsWith":create_method("EndsWith", "bool", "string", [("string", "value")])
        },
        fields={
            "Length": create_property("Length", "u64", index=0),
            #TODO replace "__null" type with ptr type to signify unknown pointer (void* type). Will be useful in unsafe context
            "__c_string": create_property("__c_string", "__null", index=1) # a pointer to the start of the c_string
        },
        parent_namespace=NamespaceTyp.builtin,
        type_info=TypeInfo(TypeClass.STRING)
    ),

    # Boolean type
    "bool": ValueTyp(
        name="bool",
        methods={
            "ToString":create_method("ToString", "string", "bool", []),
            "Parse":create_method("Parse", "bool", "bool", [("string", "s")])
        },
        parent_namespace=NamespaceTyp.builtin,
        type_info=TypeInfo(TypeClass.BOOLEAN, 1, is_signed=False)
    ),

    # Character type
    "char": ValueTyp(
        name="char",
        methods={
            "ToString":create_method("ToString", "string", "char", []),
            "IsDigit":create_method("IsDigit", "bool", "char", []),
            "IsLetter":create_method("IsLetter", "bool", "char", []),
            "IsWhitespace":create_method("IsWhitespace", "bool", "char", []),
            "ToUpper":create_method("ToUpper", "char", "char", []),
            "ToLower":create_method("ToLower", "char", "char", [])
        },
        parent_namespace=NamespaceTyp.builtin,
        type_info=TypeInfo(TypeClass.INTEGER, 8, is_signed=False)
    ),
    'void': IRCompatibleTyp.default,
    '__null': ReferenceTyp('null', parent_namespace=NamespaceTyp.builtin)
}

# @dataclass
# class Symbol:
#     """Represents a symbol (variable or function) in the scope"""
#     name: str
#     type: PType
#     declaration: PStatement
#     is_function: bool = False
#     parameters: Optional[List[PVariableDeclaration]] = None
#     #checks symbol use
#     is_assigned: bool = False # Checks if a function is assigned before use (can be bypassed if global used in function)
#     is_read: bool = False # checks if a variable is read (must be after assignment)
    
#     def __post_init__(self):
#         if self.name == "this":
#             # "this" is always valid in all methods
#             # Should be removed later to act as flag to send warning to make method static if "this" is not used 
#             self.is_assigned = True
#             self.is_read = True

# @dataclass
# class Scope:
#     """Represents a single scope level with its symbols"""
#     parent: Optional['Scope'] = None
#     symbols: Dict[str, Symbol] = field(default_factory=dict)

#     def define(self, name: str, type_: PType, declaration: PStatement,
#                is_function: bool = False,
#                parameters: Optional[List[PVariableDeclaration]] = None) -> Symbol:
#         """Define a new symbol in the current scope"""

#         #ensure one does not yet exist
#         if (symbol:=self.lookup(name)) is not None:
#             raise SymbolRedefinitionError(name,  symbol, declaration)
#         self.symbols[name] = Symbol(name, type_, declaration, is_function, parameters)
#         return self.symbols[name]

#     def lookup(self, name: str) -> Optional[Symbol]:
#         """Look up a symbol in this scope or any parent scope"""
#         current = self
#         while current is not None:
#             if name in current.symbols:
#                 return current.symbols[name]
#             current = current.parent
#         return None

# @dataclass
# class ScopeManager:
#     """Manages the hierarchy of scopes during type checking"""
#     current_scope: Scope = field(default_factory=Scope)
#     _function_scope_stack:List = field(default_factory=list)
    
#     def enter_function_scope(self):
#         self._function_scope_stack.append(self.current_scope)
#         global_scope = self.current_scope
#         while global_scope.parent is not None:
#             global_scope = global_scope.parent
#         self.current_scope = Scope(parent=global_scope)

#     def enter_scope(self) -> None:
#         """Enter a new scope"""
#         new_scope = Scope(parent=self.current_scope)
#         self.current_scope = new_scope
        
#     def exit_function_scope(self):
#         self.current_scope = self._function_scope_stack.pop()

#     def exit_scope(self) -> None:
#         """Exit the current scope"""
#         if self.current_scope.parent is None:
#             raise RuntimeError("Cannot exit global scope")
#         self.current_scope = self.current_scope.parent

#     def define_variable(self, var_decl: PVariableDeclaration) -> Symbol:
#         """Define a variable in the current scope"""
#         return self.current_scope.define(var_decl.name, var_decl.var_type, var_decl)

#     def define_function(self, function: PFunction) -> Symbol:
#         """Define a function in the current scope"""
#         return self.current_scope.define(
#             function.name,
#             function.return_type,
#             function,
#             is_function=True,
#             parameters=function.function_args
#         )

#     def lookup(self, name: str, statement:PStatement) -> Symbol:
#         """Look up a symbol in the current scope hierarchy"""
#         symbol = self.current_scope.lookup(name)
#         if symbol is None:
#             raise SymbolNotFoundError(name, statement)
#         return symbol

class UnknownTypeError(Exception):
    def __init__(self, type_:PType) -> None:
        self.unknown_type = type_
        super().__init__(
            f"Use of unknown type {type_} at {type_.position.line}:{type_.position.column}"
        )

class TypingConversionError(Exception):
    """Raised when an invalid type conversion is attempted"""
    def __init__(self, from_type: IRCompatibleTyp, to_type: IRCompatibleTyp, node: PStatement):
        self.from_type = from_type
        self.to_type = to_type
        self.node = node
        super().__init__(
            f"Cannot convert from {from_type} to {to_type} at {node.position}"
        )

class Typer:
    default:'Typer'
    
    def _error_if_not_ir_type(self, typ:BaseTyp, position:Position) -> None:
        if not isinstance(typ, IRCompatibleTyp):
            raise TypingError(f"Type {typ} is not valid at {position}\nDid you mean to reference a sub-type in the {typ} namespace?")
    
    """Handles type checking and returns a Typed AST"""
    def __init__(self, filename:str, file:TextIO, ptr_size:int=64):
        self.parser = Parser(Lexer(filename, file))
        self.known_types = deepcopy(_builtin_types)
        self.known_types['ul'].type_info.bit_width = ptr_size
        self._in_class:Optional[IRCompatibleTyp] = None
        self.expected_return_type:Optional[IRCompatibleTyp] = None
        self.is_assignment = False #set to true when typing an identifier to be assigned
        self.warnings: List[CompilerWarning] = []
        self._ast: Optional[PProgram] = None
        self.current_namespace:NamespaceTyp = NamespaceTyp('')
        
        self.all_symbols: set[Symbol] = set()  # Track all symbols
        self.all_functions: set[PFunction] = set()  # Track all functions
        self.all_class_properties: set[PClassField] = set()  # Track class properties
        self.all_class_methods: set[PFunction] = set()  # Track class methods

        self._node_function_map = {
            # Array operations
            PArrayIndexing: self._type_array_indexing,
            PArrayInstantiation: self._type_array_instantiation,

            # Basic expressions
            PIdentifier: self._type_identifier,
            PLiteral: self._type_literal,
            PBinaryOperation: self._type_binary_operation,
            PUnaryOperation: self._type_unary_operation,
            PTernaryOperation: self._type_ternary_operation,

            # Functions and calls
            PCall: self._type_call,
            # PMethodCall: self._type_method_call,

            # Control flow
            PIfStatement: self._type_if_statement,
            PWhileStatement: self._type_while_statement,
            PForStatement: self._type_for_statement,
            PReturnStatement: self._type_return_statement,
            PBreakStatement: self._type_break_statement,
            PContinueStatement: self._type_continue_statement,
            PAssertStatement: self._type_assert_statement,

            # Variable operations
            PVariableDeclaration: self._type_variable_declaration,
            PDiscard: self._type_discard,
            PAssignment: self._type_assignment,
            PNoop:self._type_noop,
            PVoid:self._type_void,

            # Class related
            PClass: self._type_class,
            PClassField: self._type_class_field,
            PDotAttribute: self._type_dot_attribute,
            PObjectInstantiation: self._type_object_instantiation,

            # Type operations
            PCast: self._type_cast,
            PType: self._type_ptype,
            PArrayType: self._type_ptype,
            PFunctionType: self._type_ptype,
            PNamespaceType: self._type_ptype,

            # Program structure
            PBlock: self._type_block,
            PFunction: self._type_function,
            PMethod: self._type_function,

            # Special cases
            PThis: self._type_this
        }
        
    def _print_warnings(self):
        for warning in self.warnings:
            print(str(warning))
            
    def _setup_namespace(self):
        assert self._ast is not None
        symbol = self._ast.scope.get_symbol(self._ast.namespace_name[0])
        #the current namespace is the end of the namespace chain: in the A.B.C namespace, current_namespace is C
        self.current_namespace = NamespaceTyp(self._ast.namespace_name[0])
        symbol.typ = self.current_namespace
        for part in self._ast.namespace_name[1:]:
            # Also add sub-namespace field to all intermediate
            # i.e. in A.B.C, A has a B namespace field and B has C namespace field
            next_one_down = NamespaceTyp(part,
                                         parent_namespace=self.current_namespace)
            pnode = PIdentifier(part, Lexeme.default)
            self.current_namespace.fields[part] = pnode
            pnode.expr_type = next_one_down
            self.current_namespace = next_one_down

    def type_program(self, warnings:bool = False) -> PProgram:
        """Type check the entire source code and return the typed AST"""
        if self._ast is not None:
            if warnings:
                self._print_warnings()
            return self._ast
        self._ast = self.parser.parse()
        self._setup_namespace()
        # make tree traversable in both directions
        self._ast._setup_parents()

        #type builtin methods and add symbols to the global namespace
        for typ in list(self.known_types.values()):
            self._ast.scope.declare_local(typ.symbol)
            if typ.name in ['void', 'null']:
                continue
            #make sure to say the class we're in
            self._in_class = typ
            for elem in [*typ.fields.values(), *typ.methods.values()]:
                self._type_statement(elem)
                    
        self._in_class = None
        
        # type the imports
        for import_stmt in self._ast.imports:
            self._type_import(import_stmt)
        
        # First pass (quick) to build type list with user defined classes
        for statement in self._ast.statements:
            if isinstance(statement, PClass):
                statement.class_typ = TypeTyp(ReferenceTyp(statement.name, 
                                                       methods={m.name:m for m in statement.methods},
                                                       fields=statement.fields))
                self.current_namespace.fields[statement.name] = statement
                assert isinstance(statement.class_typ.pointed_type, ReferenceTyp)
                self.known_types[statement.full_name] = statement.class_typ.pointed_type
            elif isinstance(statement, PFunction):
                self.current_namespace.fields[statement.name] = statement
            elif isinstance(statement, PVariableDeclaration):
                self.current_namespace.fields[statement.name] = statement
            continue

        # Full tree traversal pass
        for statement in self._ast.statements:
            self._type_statement(statement)
        
        self._check_unused_symbols()

        if warnings:
            self._print_warnings()
        self._cfg_check(self._ast)
        return self._ast

    def _check_unused_symbols(self):
        # Check variables
        for symbol in self.all_symbols:
            if not symbol.is_read and not symbol.is_function:
                self.warnings.append(CompilerWarning(
                    f"Variable '{symbol.name}' is declared but never read",
                    symbol.declaration_position
                ))
        # Check functions
        for func in self.all_functions:
            if func.is_builtin:
                continue #ignore builtin or imported functions
            if not func.is_called and func.name != 'main':  # Exclude main if present
                self.warnings.append(CompilerWarning(
                    f"Function '{func.name}' is declared but never called",
                    func.position
                ))
        # Check class properties and methods
        for prop in self.all_class_properties:
            if prop.is_builtin:
                continue
            if not prop.is_assigned:
                self.warnings.append(CompilerWarning(
                    f"Class property '{prop.name}' is never assigned",
                    prop.position
                ))
            elif not prop.is_public and not prop.is_read:
                self.warnings.append(CompilerWarning(
                    f"Private class property '{prop.name}' is never read",
                    prop.position
                ))
        for method in self.all_class_methods:
            if method.is_builtin:
                continue #ignore unused builtins
            if not method.is_called:
                self.warnings.append(CompilerWarning(
                    f"Method '{method.name}' is declared but never called",
                    method.position
                ))

    def _ptype_from_typ(self, typ:IRCompatibleTyp, pos:Optional[Position]=None) -> PType|PArrayType:
        if pos is None:
            pos = Position.default
        if not isinstance(typ, ArrayTyp):
            return PType(typ.name, pos)
        #typ is array
        return PArrayType(self._ptype_from_typ(typ.element_typ), pos)

    def is_numeric_type(self, type_: Union[IRCompatibleTyp, TypeInfo]) -> bool:
        """Check if type is numeric (integer or float)"""
        info = type_ if isinstance(type_, TypeInfo) else type_.type_info
        return info.type_class in (TypeClass.INTEGER, TypeClass.FLOAT, TypeClass.BOOLEAN)

    def check_types_match(self, expected: IRCompatibleTyp, actual: IRCompatibleTyp) -> bool:
        """
        Check if two types are compatible, considering implicit conversions.
        Returns True if types match or actual can be implicitly converted to expected.
        """
        if str(expected) == str(actual):
            return True

        # Handle numeric conversions
        if self.is_numeric_type(expected) and self.is_numeric_type(actual):
            return self.can_convert_numeric(actual, expected)
        
        # Can always set a reference type to null
        if expected.is_reference_type and actual == self.known_types["__null"]:
            return True
        
        if actual.is_reference_type and expected.name == 'null':
            # null type is a shortcut to signify ANY reference type. Will be fixed when polymorphism is implemented
            # TODO Fix when adding polymorphism
            return True

        expected_info = expected.type_info
        actual_info = actual.type_info

        # Handle array types
        if expected_info.type_class == TypeClass.ARRAY and actual_info.type_class == TypeClass.ARRAY:
            # Array types must match exactly
            return str(expected) == str(actual)

        # Handle string conversions - anything can convert to string
        return False

    def can_convert_numeric(self, from_type: IRCompatibleTyp, to_type: IRCompatibleTyp) -> bool:
        """Determine if numeric conversion is allowed between types"""
        from_info = from_type.type_info
        to_info = to_type.type_info

        # Only handle numeric types
        if not (self.is_numeric_type(from_info) and self.is_numeric_type(to_info)):
            return False
        
        if from_type == to_type:
            return True
        
        if to_info.type_class == TypeClass.BOOLEAN:
            return False #cannot implicitly convert to bool
        
        if from_info.type_class == TypeClass.BOOLEAN:
            return True

        # Convert to float is always allowed for numeric types
        if to_info.type_class == TypeClass.FLOAT:
            # Can only convert to wider float types to avoid precision loss
            if from_info.type_class == TypeClass.FLOAT:
                return to_info.bit_width >= from_info.bit_width
            # Integers can convert to any float except f16 if too wide
            if from_info.type_class == TypeClass.INTEGER and to_info.bit_width == 16:
                # Only small integers can safely convert to f16
                return from_info.bit_width <= 8
            return True

        # Integer conversions
        if from_info.type_class == TypeClass.INTEGER and to_info.type_class == TypeClass.INTEGER:
            # Unsigned to signed requires extra bit
            if not from_info.is_signed and to_info.is_signed:
                return to_info.bit_width > from_info.bit_width

            # Same signedness - just compare widths
            if from_info.is_signed == to_info.is_signed:
                return to_info.bit_width >= from_info.bit_width

            # Signed to unsigned requires knowing value at runtime
            return False

        # Float to integer requires explicit cast
        return False

    def get_common_type(self, type1: IRCompatibleTyp, type2: IRCompatibleTyp) -> Optional[IRCompatibleTyp]:
        """
        Find the common type that both types can be converted to.
        Used for determining result type of binary operations.
        """
        
        if str(type1) == str(type2):
            return type1
        
        # If either is non-numeric, no common type
        if not (self.is_numeric_type(type1) and self.is_numeric_type(type2)):
            return None

        info1 = type1.type_info
        info2 = type2.type_info

        # If either is float, result is the widest float
        if TypeClass.FLOAT in (info1.type_class, info2.type_class):
            if info1.type_class == TypeClass.FLOAT and info2.type_class == TypeClass.FLOAT:
                return type1 if info1.bit_width > info2.bit_width else type2

            # When mixing integer and float:
            # - If integer is small enough (<=8 bits), can use f16
            # - Otherwise need at least f32
            float_type = type1 if info1.type_class == TypeClass.FLOAT else type2
            int_info = info2 if info1.type_class == TypeClass.FLOAT else info1

            if int_info.bit_width <= 8:
                # Can use f16 or wider if the float type is wider
                float_width = float_type.type_info.bit_width
                if float_width <= 16:
                    return self.known_types["f16"]
                if float_width <= 32:
                    return self.known_types["f32"]
                return self.known_types["f64"]
            else:
                # Need at least f32
                float_width = float_type.type_info.bit_width
                if float_width <= 32:
                    return self.known_types["f32"]
                return self.known_types["f64"]
            
        if info2.type_class == TypeClass.BOOLEAN:
            # type1 is an int (bigger than bool so it's fine)
            return type1
        if info1.type_class == TypeClass.BOOLEAN:
            # type2 is an int (bigger than bool so it's fine)
            return type2

        # Both are integers
        if info1.is_signed or info2.is_signed:
            # If either is signed, use signed type with enough bits
            max_width = max(info1.bit_width, info2.bit_width) \
                            + info1.is_signed ^ info2.is_signed #if one is unsigned, common type must be of greater width
            #only return i8 if both are. no explicit check needed
            if max_width <= 16:
                return self.known_types["i16"]
            if max_width <= 32:
                return self.known_types["i32"]
            return self.known_types["i64"]

        # Both unsigned - use widest type
        max_width = max(info1.bit_width, info2.bit_width)
        #only return u8 if both are. no explicit check needed
        if max_width <= 16:
            return self.known_types["u16"]
        if max_width <= 32:
            return self.known_types["u32"]
        return self.known_types["u64"]
    
    def can_do_operation_on_type(self, operation: Union[BinaryOperation, UnaryOperation], type_: IRCompatibleTyp) -> bool:
        """Check if the given operation can be performed on the given type."""
        # Always allow Bool negation (a `not 0` or `not ""` will return True, and false otherwise)
        if operation == UnaryOperation.BOOL_NOT:
            return True
        
        type_info = type_.type_info
        
        # Handle numeric operations first (most common case)
        if type_info.type_class in (TypeClass.INTEGER, TypeClass.FLOAT):
            if isinstance(operation, BinaryOperation):
                # All arithmetic operations are valid for numeric types
                if operation in (BinaryOperation.PLUS, BinaryOperation.MINUS, 
                            BinaryOperation.TIMES, BinaryOperation.DIVIDE):
                    return True
                    
                # Modulo only works with integers
                if operation == BinaryOperation.MOD:
                    return type_info.type_class == TypeClass.INTEGER
                    
                # Bitwise operations only work with integers
                if operation in (BinaryOperation.LOGIC_AND, BinaryOperation.LOGIC_OR,
                            BinaryOperation.XOR, BinaryOperation.SHIFT_LEFT,
                            BinaryOperation.SHIFT_RIGHT):
                    return type_info.type_class == TypeClass.INTEGER
                    
                # Comparison operations work with all numeric types
                if operation in (BinaryOperation.BOOL_EQ, BinaryOperation.BOOL_NEQ,
                            BinaryOperation.BOOL_GT, BinaryOperation.BOOL_LT,
                            BinaryOperation.BOOL_GEQ, BinaryOperation.BOOL_LEQ):
                    return True
                    
            elif isinstance(operation, UnaryOperation):
                # Numeric negation is valid for all numeric types
                if operation == UnaryOperation.MINUS:
                    return True
                    
                # Increment/decrement only valid for integers
                if operation in (UnaryOperation.POST_INCREMENT, UnaryOperation.POST_DECREMENT,
                            UnaryOperation.PRE_INCREMENT, UnaryOperation.PRE_DECREMENT):
                    return type_info.type_class == TypeClass.INTEGER
        
        # Handle boolean type
        elif type_info.type_class == TypeClass.BOOLEAN:
            if isinstance(operation, BinaryOperation):
                # Boolean operations
                if operation in (BinaryOperation.BOOL_AND, BinaryOperation.BOOL_OR,
                            BinaryOperation.BOOL_EQ, BinaryOperation.BOOL_NEQ):
                    return True
                    
            elif isinstance(operation, UnaryOperation):
                # Logic negation is also valid
                if operation == UnaryOperation.LOGIC_NOT:
                    return True
        
        # Handle string type
        elif type_info.type_class == TypeClass.STRING:
            if isinstance(operation, BinaryOperation):
                # String concatenation
                if operation == BinaryOperation.PLUS:
                    return True
                # String comparison will compare char per char 
                if operation in (BinaryOperation.BOOL_EQ, BinaryOperation.BOOL_NEQ,
                            BinaryOperation.BOOL_GT, BinaryOperation.BOOL_LT,
                            BinaryOperation.BOOL_GEQ, BinaryOperation.BOOL_LEQ):
                    return True
        
        # Handle array type
        elif type_info.type_class == TypeClass.ARRAY:
            if isinstance(operation, BinaryOperation):
                # Arrays can be compared for equality/inequality
                if operation in (BinaryOperation.BOOL_EQ, BinaryOperation.BOOL_NEQ):
                    return True
                
        return False

    def _type_statement(self, statement: PStatement) -> Optional[BaseTyp]:
        """Type checks a statement (or expression) and returns its type"""
        if isinstance(statement, PExpression):
            return self._type_expression(statement)
        assert isinstance(statement, (PArrayIndexing, PArrayInstantiation,
                                          PIdentifier, PLiteral, PBinaryOperation,
                                          PUnaryOperation, PTernaryOperation,
                                          PIfStatement, PWhileStatement,
                                          PForStatement, PReturnStatement,
                                          PBreakStatement, PContinueStatement,
                                          PAssertStatement, PVariableDeclaration,
                                          PClassField, PDotAttribute, PDiscard,
                                          PObjectInstantiation, PCast, PType,
                                          PCall, PClass, PArrayType, PBlock,
                                          PFunction, PThis))
        typer_func = self._node_function_map.get(type(statement), None)
        assert typer_func is not None
        return typer_func(statement)

    def _type_expression(self, expression: PExpression) -> Union[IRCompatibleTyp, NamespaceTyp]:
        """Type checks an expression definition and returns its type"""
        assert isinstance(expression, (PArrayIndexing, PArrayInstantiation,
                                          PIdentifier, PLiteral, PBinaryOperation,
                                          PUnaryOperation, PTernaryOperation,
                                          PCall, PThis, PDotAttribute,
                                          PObjectInstantiation, PCast,
                                          PNoop, PVoid, PAssignment))
        typer_func = self._node_function_map.get(type(expression), None)
        assert typer_func is not None
        return typer_func(expression)
    
    def _type_noop(self, noop:PNoop):
        """Type check a Noop (optional entry) Always valid type checks to true"""
        noop.expr_type = self.known_types['bool']
        return noop.expr_type
    
    def _type_void(self, void:PVoid):
        """Type check a Noop (optional entry) Always valid type checks to true"""
        void.expr_type = self.known_types['void']
        return void.expr_type

    def _type_class(self, class_def: PClass) -> BaseTyp:
        """Type checks a class definition and returns its type"""
        class_typ = self.known_types[class_def.full_name]
        self._in_class = class_typ
        assert isinstance(class_typ, ReferenceTyp)
        
        for prop in class_def.fields.values():
            self._type_class_field(prop)
        
        for method in class_def.methods:
            self.all_class_methods.add(method)
            self._type_function(method)
        self._in_class = None
        return class_typ
        
    def _type_import(self, pimport:PImport):
        """Here it populates the alias and namespace types and everything within the namespace, symbols etc."""
        #first add namespace to symbols and sub-namespaces if there are any
        global_scope = pimport.parent_scope
        assert isinstance(global_scope, GlobalScope)
        imported_namespace:Optional[NamespaceTyp] = None
        if global_scope.has_symbol(pimport.namespace_parts[0]):
            namespace_typ = global_scope.get_symbol(pimport.namespace_parts[0]).typ
            assert isinstance(namespace_typ, NamespaceTyp)
            imported_namespace = namespace_typ
        else:
            imported_namespace = NamespaceTyp(pimport.namespace_parts[0])
            global_scope.declare_local(imported_namespace.symbol)
        
        for part in pimport.namespace_parts[1:]:
            next_one_down = NamespaceTyp(part,
                                         parent_namespace=imported_namespace)
            pnode = PIdentifier(part, pimport.position)
            pnode.expr_type = next_one_down
            imported_namespace.fields[part] = pnode
            imported_namespace = next_one_down
        assert imported_namespace is not None
        pimport.namespace_typ = imported_namespace
        
        #first pass to add types to namespace and to also add to scope
        for statement in pimport.headers:
            if isinstance(statement, PClass):
                statement.class_typ = TypeTyp(ReferenceTyp(statement.name, 
                                                    methods={m.name:m for m in statement.methods},
                                                    fields=statement.fields,
                                                    parent_namespace=imported_namespace))
                imported_namespace.fields[statement.name] = statement
                assert isinstance(statement.class_typ.pointed_type, ReferenceTyp)
                self.known_types[statement.full_name] = statement.class_typ.pointed_type
                global_scope.declare_import(statement.class_typ.pointed_type.symbol)
            elif isinstance(statement, PFunction):
                imported_namespace.fields[statement.name] = statement
            elif isinstance(statement, PVariableDeclaration):
                imported_namespace.fields[statement.name] = statement
            global_scope.declare_import
        #pass to add all 
        for statement in pimport.headers:
            self._type_statement(statement)

    def _type_ptype(self, ptype:PType) -> IRCompatibleTyp:
        """Type checks a class definition and returns its type"""
        if isinstance(ptype, PFunctionType):
            return FunctionTyp(decl_position=ptype.position,
                               return_type=self._type_ptype(ptype.return_ptype),
                               arguments=[self._type_ptype(arg) for arg in ptype.argument_ptypes],
                               is_method=False)
        elif str(ptype) in self.known_types:
            return self.known_types[str(ptype)]
        elif ptype.parent_namespace is not None:
            type_stack = []
            parent = ptype
            while parent is not None:
                type_stack.append(parent.type_string)
                parent = parent.parent_namespace
            symbol = ptype.parent_scope.get_symbol(type_stack.pop())
            typ = symbol.typ
            while len(type_stack) > 0:
                assert isinstance(typ, NamespaceTyp)
                typ = typ.fields[type_stack.pop()]
            assert isinstance(typ, IRCompatibleTyp)
            self.known_types[str(ptype)] = typ
            return typ
        elif isinstance(ptype, PArrayType):
            element_typ = self._type_ptype(ptype.element_type)
            arrTyp = ArrayTyp(element_type=element_typ)
            self.known_types[ptype.type_string] = arrTyp
            #store tmp class location fo type builtins (TODO: should be done another way, typing it somewhere else)
            tmp_class = self._in_class
            self._in_class = arrTyp
            for field in arrTyp.fields.values():
                assert isinstance(field, PClassField)
                self._type_class_field(field)
            for method in arrTyp.methods.values():
                self._type_function(method)
            #return to prev state
            self._in_class = tmp_class
            return arrTyp
        elif ptype.parent_scope.has_symbol(ptype.type_string): # here ptype.parent_namespace is None
            typ_symbol = ptype.parent_scope.get_symbol(ptype.type_string, ptype.position)
            assert isinstance(typ_symbol.typ, TypeTyp)
            if not isinstance(typ_symbol.typ.pointed_type, IRCompatibleTyp):
                raise TypingError(f"{ptype.type_string} is not a valid type")
            return typ_symbol.typ.pointed_type
        raise UnknownTypeError(ptype)
    
    def _type_function_header(self, func: PFunction|PMethod) -> FunctionTyp:
        """Type checks a function definition"""
        if isinstance(func, PMethod):
            assert self._in_class is not None #if method: ensure we're in a class!
            class_typ = self._in_class
            assert isinstance(class_typ, IRCompatibleTyp)
            func._class_type = class_typ
        else: # function not a method
            if not func.is_builtin:
                #ignore checks on builtins
                self.all_functions.add(func)
        
        for arg in func.function_args:
            self._type_variable_declaration(arg)
            symbol = arg.symbol
            # Function args are always assigned
            symbol.is_assigned = True
            if func.is_builtin:
                # ignore checks on builtins
                # TODO: Do the same on imported, maybe consider builtin = imported?
                symbol.is_read = True
                func.symbol.is_read = True
                func.symbol.is_assigned = True
        
        return_typ = self._type_ptype(func.return_type)
        func.function_typ = FunctionTyp(decl_position=func.position,
                                        return_type=return_typ,
                                        arguments=[arg.typer_pass_var_type for arg in func.function_args],
                                        is_method=isinstance(func, PMethod))
        return func.function_typ

    def _type_function(self, func: PFunction|PMethod) -> FunctionTyp:
        if not func.header_is_typed: 
            #not yet typed
            self._type_function_header(func)
            
        if not func.is_only_declaration:
            assert func.body is not None
            #ignore None body it's just a declarations
            self.expected_return_type = func.return_typ_typed
            self._type_block(func.body)

            #add implicit return at the end of a void function if there isn't one already
            if self.expected_return_type.type_info.type_class == TypeClass.VOID:
                if len(func.body.statements) == 0:
                    func.body.statements.append(
                        PReturnStatement.implicit_return(func.body.position, func.body))
                if not isinstance(func.body.statements[-1], PReturnStatement):
                    func.body.statements.append(
                        PReturnStatement.implicit_return(
                            func.body.statements[-1].position,
                            func.body))
            self.expected_return_type = None
        return func.function_typ

    def _type_block(self, block: PBlock) -> None:
        """Type checks a block of statements, optionally verifying return type"""
        for statement in block.statements:
            self._type_statement(statement)

    def _type_variable_declaration(self, var_decl: PVariableDeclaration) -> BaseTyp:
        """Type checks a variable declaration"""
        if var_decl.symbol._typ is None:
            self.all_symbols.add(var_decl.symbol)
            var_decl.typer_pass_var_type = self._type_ptype(var_decl.var_type)

        if var_decl.initial_value is None:
            return var_decl.typer_pass_var_type
        
        var_decl.symbol.is_assigned = True
        var_type = var_decl.symbol.typ
        assert isinstance(var_type, IRCompatibleTyp)
        expr_type = self._type_expression(var_decl.initial_value)
        assert isinstance(expr_type, IRCompatibleTyp)
        #TODO if check fails here add to errors and suppose it's fine, continue
        if not self.check_types_match(var_type, expr_type):
            raise TypingConversionError(expr_type, var_type, var_decl)
        if expr_type != var_type:
            var_decl.initial_value = self._add_implicit_cast(
                                            var_decl.initial_value, var_type)
        return var_decl.typer_pass_var_type

    def _type_discard(self, discard:PDiscard) -> None:
        self._type_expression(discard.expression)

    def _type_class_field(self, prop:PClassField) -> None:
        """Type checks a class field"""
        var_type = self._type_ptype(prop.var_type)
        self._error_if_not_ir_type(var_type, prop.var_type.position)
        prop._typer_pass_var_type = var_type
        self.all_class_properties.add(prop)

        if prop.default_value is None:
            return
        prop.is_assigned = True
        expr_type = self._type_expression(prop.default_value)
        assert isinstance(expr_type, IRCompatibleTyp)     
               
        if not self.check_types_match(var_type, expr_type):
            raise TypingConversionError(var_type, expr_type, prop)

    def _type_assignment(self, assignment: PAssignment) -> IRCompatibleTyp:
        """Type checks an assignment and returns the assigned type"""
        self.is_assignment = True
        ident_type = self._type_expression(assignment.target)
        self.is_assignment = False
        assignment.expr_type = ident_type
        expression_type = self._type_expression(assignment.value)
        assert isinstance(ident_type, IRCompatibleTyp)
        assert isinstance(expression_type, IRCompatibleTyp)
        
        if not self.check_types_match(ident_type, expression_type):
            raise TypingConversionError(expression_type, ident_type, assignment)
        if ident_type != expression_type:
            #implicit cast
            assignment.value = self._add_implicit_cast(assignment.value, ident_type)
        return ident_type

    def _type_binary_operation(self, binop: PBinaryOperation) -> IRCompatibleTyp:
        """Type checks a binary operation and returns its result type"""
        left_type = self._type_expression(binop.left)
        right_type = self._type_expression(binop.right)
        assert isinstance(left_type, IRCompatibleTyp)
        assert isinstance(right_type, IRCompatibleTyp)
        common = self.get_common_type(left_type, right_type)
        if common is None:
            raise TypingError(f"Type {left_type} and {right_type} are not compatible")
        # force cast if not same type
        if left_type != common:
            binop.left = self._add_implicit_cast(binop.left, common)
        if right_type != common:
            binop.right = self._add_implicit_cast(binop.right, common)
        if binop.operation.name.startswith('BOOL_'):
            #comparators and boolean operators return bool
            binop.expr_type = self.known_types['bool']
        else:
            binop.expr_type = common
        
        if not self.can_do_operation_on_type(binop.operation, common):
            raise TypingError("Cannot do binary operation {binop.operation.name} between types {left_type} and {right_type}")
        
        return binop.expr_type

    def _type_unary_operation(self, unop: PUnaryOperation) -> IRCompatibleTyp:
        """Type checks a unary operation and returns its result type"""
        operand_type = self._type_expression(unop.operand)
        assert isinstance(operand_type, IRCompatibleTyp)
        if not self.can_do_operation_on_type(unop.operation, operand_type):
            raise TypingError(f"Cannot perform Unary Operation {unop.operation.name} on type {operand_type}")
        
        if unop.operation == UnaryOperation.BOOL_NOT:
            unop.expr_type = self.known_types['bool']
        else:
            unop.expr_type = operand_type
        return unop.expr_type

    def _type_if_statement(self, if_stmt: PIfStatement) -> None:
        """Type checks an if statement"""
        condition_type = self._type_expression(if_stmt.condition)
        assert isinstance(condition_type, IRCompatibleTyp)
        if not condition_type.type_info.type_class == TypeClass.BOOLEAN:
            raise TypingConversionError(condition_type, self.known_types['bool'], if_stmt.condition)
        self._type_block(if_stmt.then_block)
        if if_stmt.else_block is not None:
            self._type_block(if_stmt.else_block)

    def _type_while_statement(self, while_stmt: PWhileStatement) -> None:
        """Type checks a while loop"""
        condition_type = self._type_expression(while_stmt.condition)
        assert isinstance(condition_type, IRCompatibleTyp)
        if not condition_type.type_info.type_class == TypeClass.BOOLEAN:
            raise TypingConversionError(condition_type, self.known_types['bool'], while_stmt.condition)
        self._type_block(while_stmt.body)

    def _type_for_statement(self, for_stmt: PForStatement) -> None:
        """Type checks a for loop"""
        self._type_statement(for_stmt.initializer)
        
        if not isinstance(for_stmt.condition, PNoop):
            condition_type = self._type_expression(for_stmt.condition)
            assert isinstance(condition_type, IRCompatibleTyp)
            if not condition_type.type_info.type_class == TypeClass.BOOLEAN:
                raise TypingConversionError(condition_type, self.known_types['bool'], for_stmt.condition)
        else:
            for_stmt.condition.expr_type = self.known_types['bool']
            
        self._type_statement(for_stmt.increment)
        
        self._type_block(for_stmt.body)

    def _type_return_statement(self, return_stmt: PReturnStatement) -> None:
        """Type checks a return statement against expected return type"""
        assert self.expected_return_type is not None
        expression_type = self._type_expression(return_stmt.value)
        assert isinstance(expression_type, IRCompatibleTyp)
        if not self.check_types_match(self.expected_return_type, expression_type):
            raise TypingConversionError(expression_type, self.expected_return_type, return_stmt)
        
        if self.expected_return_type != return_stmt.value.expr_type:
            return_stmt.value = self._add_implicit_cast(
                                        return_stmt.value,
                                        self.expected_return_type)

    def _type_call(self, func_call: PCall) -> IRCompatibleTyp:
        """Type checks a function call and returns its return type"""
        func_ident = func_call.function
        
        func_typ = self._type_expression(func_ident)
        if not isinstance(func_typ, FunctionTyp):
            raise TypingError(f"The type {func_typ} is not callable at {func_ident.position}")
        if isinstance(func_ident, PDotAttribute) and not isinstance(func_ident.left.expr_type, NamespaceTyp):
            func_typ.is_method = True
        
        expected_arguments = func_typ.arguments.copy()
        if func_typ.is_method and len(expected_arguments) > 0:
            expected_arguments.pop(0)
        
        if len(expected_arguments) != len(func_call.arguments):
            raise TypingError(f"The function expects {len(func_call.arguments)} arguments but got {len(expected_arguments)}"+\
                              f" at location {func_call.position}")
        
        for i, (expected_type, actual) in enumerate(zip(expected_arguments, func_call.arguments)):
            actual_type = self._type_expression(actual)
            assert isinstance(actual_type, IRCompatibleTyp)
            if not self.check_types_match(expected_type, actual_type):
                raise TypingConversionError(actual_type, expected_type, actual)
            if expected_type != actual_type:
                func_call.arguments[i] = self._add_implicit_cast(actual, expected_type)
        
        func_call.expr_type = func_typ.return_type
        return func_call.expr_type

    # def _type_method_call(self, method_call: PMethodCall) -> IRCompatibleTyp:
    #     """Type checks a method call and returns its return type"""
    #     obj_type = self._type_expression(method_call.object)
    #     if isinstance(obj_type, NamespaceTyp):
    #         assert method_call.method_name.name in obj_type.fields
    #         func = obj_type.fields[method_call.method_name.name]
    #         assert isinstance(func.expr_type, FunctionTyp)

    #         for expected_type, actual in zip(func.expr_type.arguments, method_call.arguments):
    #             actual_type = self._type_expression(actual)
    #             assert isinstance(actual_type, IRCompatibleTyp)
    #             if not self.check_types_match(expected_type, actual_type):
    #                 raise TypingConversionError(actual_type, expected_type, actual)
    #         method_call.expr_type = func.expr_type.return_type
    #     else:
    #         if not method_call.method_name.name in obj_type.methods:
    #             raise TypingError(f"Method {method_call.method_name.name} of type {obj_type} if unknown at location {method_call.position}")
    #         method = obj_type.methods[method_call.method_name.name]
    #         method.is_called = True
    #         if len(method.explicit_arguments) != len(method_call.arguments):
    #             raise TypingError(f"The function expects {len(method.function_args)} arguments but got {len(method_call.arguments)}"+\
    #                             f" at location {method_call.position}")

    #         for expected_param, actual in zip(method.explicit_arguments, method_call.arguments):
    #             expected_type = self._type_ptype(expected_param.var_type)
    #             actual_type = self._type_expression(actual)
    #             assert isinstance(actual_type, IRCompatibleTyp)
    #             if not self.check_types_match(expected_type, actual_type):
    #                 raise TypingConversionError(actual_type, expected_type, actual)
            
    #         method_call.expr_type = self._type_ptype(method.return_type)

    #     return method_call.expr_type

    def _type_identifier(self, identifier: PIdentifier) -> IRCompatibleTyp:
        """Type checks an identifier and returns its type"""
        symbol = identifier.parent_scope.get_symbol(identifier.name, identifier.position)
        if not isinstance(symbol.typ, IRCompatibleTyp):
            raise TypingError(f"{symbol.typ} is not a valid type for this identifier")
        identifier.expr_type = symbol.typ
        if self.is_assignment:
            symbol.is_assigned = True
        else:
            if not symbol.is_assigned:
                self.warnings.append(CompilerWarning(
                    f"Symbol '{symbol.name}' is potentially not assigned (it will have it's default value)",
                    identifier.position
                ))
            symbol.is_read = True
        return identifier.expr_type

    def _type_literal(self, literal: PLiteral) -> IRCompatibleTyp:
        """Type checks a literal and returns its type"""
        # choses a default but can be cast if the user needs a bigger number (or suffixed)
        if literal.literal_type == 'int':
            assert isinstance(literal.value, int)
            # Currently number out of range will be truncated and only least significant bits kept 
            literal.expr_type = self.known_types['i32']
        elif literal.literal_type == 'bool':
            assert isinstance(literal.value, bool)
            literal.expr_type = self.known_types['bool']
        elif literal.literal_type == 'char':
            assert isinstance(literal.value, int)
            literal.expr_type = self.known_types['char']
        elif literal.literal_type == 'string':
            assert isinstance(literal.value, str)
            literal.expr_type = self.known_types['string']
        elif literal.literal_type == 'null':
            assert literal.value is None
            literal.expr_type = self.known_types['__null']
        else:
            assert literal.literal_type == 'float'
            assert isinstance(literal.value, float)
            # Currently number out of range will be truncated and cropped to f32 precision
            literal.expr_type = self.known_types['f32']
        return literal.expr_type

    def _type_this(self, this_keyword: PThis) -> IRCompatibleTyp:
        """Type checks a cast expression and returns the target type"""
        if self._in_class is None:
            raise TypingError("'this' is not defined outside of a class")
        this_keyword.expr_type = self._in_class
        return this_keyword.expr_type

    def _type_cast(self, cast: PCast) -> IRCompatibleTyp:
        """Type checks a cast expression and returns the target type"""
        expression_type = self._type_expression(cast.expression)
        target_type = self._type_ptype(cast.target_type)
        target_type_info = target_type.type_info
        
        assert isinstance(expression_type, IRCompatibleTyp)
        
        if expression_type.name == target_type.name:
            self.warnings.append(CompilerWarning(f"Unnecessary Cast", cast.position))
            cast.expr_type = target_type

        elif self.is_numeric_type(expression_type) and self.is_numeric_type(target_type_info):
            cast.expr_type = target_type
        elif target_type_info.type_class == TypeClass.BOOLEAN:
            cast.expr_type = target_type
        elif target_type_info.type_class == TypeClass.STRING:
            raise TypingError(f"Cannot cast to string. Use the .ToString() method instead")
        elif expression_type == self.known_types['__null']:
            if not target_type.is_reference_type:
                raise TypingError(f'Cannot place null into a non-reference type')
            # in case it's a null literal
            cast.expr_type = target_type
        else:
            raise TypingError(f"Unable to cast {expression_type} to {target_type} at location {cast.position}")
            
        return cast.expr_type

    def _type_array_indexing(self, array_index: PArrayIndexing) -> IRCompatibleTyp:
        """Type checks an array indexing expression and returns the element type"""
        index_type = self.known_types['i64'] # not unsigned to allow for negative indexing (-1 is the last element, -2 the second to last etc.)
        array_type = self._type_expression(array_index.array)
        if not isinstance(array_type, ArrayTyp):
            raise TypingError(f"Expected array type but got '{array_type.name}'")    
        
        index = self._type_expression(array_index.index)
        assert isinstance(index, IRCompatibleTyp)
        if index.type_info.type_class != TypeClass.INTEGER:
            raise TypingError(f"The index must be an integer type not '{index}'")
        if array_index.expr_type != index_type:
            #implicit convert array index to i64
            array_index.index = self._add_implicit_cast(array_index.index, index_type)
        
        array_index.expr_type = array_type.element_typ
        return array_type.element_typ

    def _type_object_instantiation(self, obj_init: PObjectInstantiation) -> IRCompatibleTyp:
        """Type checks an object instantiation and returns the object type"""
        obj_init.expr_type = self._type_ptype(obj_init.class_type)
        return obj_init.expr_type

    def _type_array_instantiation(self, array_init: PArrayInstantiation) -> IRCompatibleTyp:
        """Type checks an array instantiation and returns the array type"""
        array_init.expr_type = self._type_ptype(PArrayType(array_init.element_type, array_init.element_type.position))
        array_size_type = self._type_expression(array_init.size)
        assert isinstance(array_size_type, IRCompatibleTyp)
        if array_size_type.type_info.type_class != TypeClass.INTEGER:
            raise TypingError(f"Expected an array size of type Integer but got '{array_size_type}'")
        if array_size_type != self.known_types['u64']:
            array_init.size = self._add_implicit_cast(array_init.size, self.known_types['u64'])
        array_init._element_type_typ = self._type_ptype(array_init.element_type)
        return array_init.expr_type
        

    def _type_dot_attribute(self, dot_attr: PDotAttribute) -> Union[IRCompatibleTyp, NamespaceTyp]:
        """Type checks a dot attribute access and returns its type"""
        tmp_assignment = self.is_assignment
        self.is_assignment = False
        left_type = self._type_expression(dot_attr.left)
        if isinstance(left_type, IRCompatibleTyp):
            if dot_attr.right.name in left_type.fields:
                field = left_type.fields[dot_attr.right.name]
                assert isinstance(field, PClassField)
                if dot_attr.right.expr_type is None:
                    dot_attr.right.expr_type = self._type_ptype(field.var_type)
                dot_attr.expr_type = dot_attr.right.expr_type
                field.is_assigned |= tmp_assignment
            elif dot_attr.right.name in left_type.methods:
                method = left_type.methods[dot_attr.right.name]
                assert isinstance(method, PFunction)
                dot_attr.right.expr_type = method.function_typ
                dot_attr.expr_type = dot_attr.right.expr_type
            else:
                raise TypingError(f"'{dot_attr.right.name}' is not a known property of '{left_type}'")
        elif isinstance(left_type, NamespaceTyp):
            field = left_type.fields.get(dot_attr.right.name, None)
            assert dot_attr.right.expr_type is not None
            dot_attr.expr_type = dot_attr.right.expr_type
        else:
            raise TypingError(f"'Invalid symbol in {dot_attr.left.position}")
        assert isinstance(dot_attr.expr_type, (NamespaceTyp, IRCompatibleTyp))
        return dot_attr.expr_type

    def _type_ternary_operation(self, ternary: PTernaryOperation) -> IRCompatibleTyp:
        """Type checks a ternary operation and returns its result type"""
        condition_type = self._type_expression(ternary.condition)
        assert isinstance(condition_type, IRCompatibleTyp)
        if condition_type.type_info.type_class != TypeClass.BOOLEAN:
            raise TypingError(f"Cannot use a {condition_type} in the condition of a ternary operator. Are you missing a cast? {ternary.condition.position}")
        if_true_value_type = self._type_expression(ternary.true_value)
        if_false_value_type = self._type_expression(ternary.false_value)
        
        assert isinstance(if_true_value_type, IRCompatibleTyp)
        assert isinstance(if_false_value_type, IRCompatibleTyp)
        
        ternary.expr_type = self.get_common_type(if_true_value_type, if_false_value_type)
        
        if ternary.expr_type is None:
            raise TypingError(f"Types of result expressions are incompatible at location {ternary.true_value}")
        
        return ternary.expr_type

    def _type_break_statement(self, break_stmt: PBreakStatement) -> None:
        """Type checks a break statement"""
        return

    def _type_continue_statement(self, continue_stmt: PContinueStatement) -> None:
        """Type checks a continue statement"""
        return

    def _type_assert_statement(self, assert_stmt: PAssertStatement) -> None:
        """Type checks an assert statement"""
        condition_type = self._type_expression(assert_stmt.condition)
        assert isinstance(condition_type, IRCompatibleTyp)
        if condition_type.type_info.type_class != TypeClass.BOOLEAN:
            raise TypingError(f"An assertion expression must be a boolean. Are you missing a cast? {assert_stmt.condition.position}")
        
        if assert_stmt.message is not None:
            message_type = self._type_expression(assert_stmt.message)
            assert isinstance(message_type, IRCompatibleTyp)
            if message_type.type_info.type_class != TypeClass.STRING:
                raise TypingError(f"An assertion message must be a string!")
            
    def _cfg_check(self, program:Union[PProgram,PBlock]) -> None:
        """Check to ensure all functions have a valid return. Raises error if invalid otherwise returns None"""
        #TODO here remove unreachable statements and raise warning
        for statement in program.statements:
            if isinstance(statement, (PFunction, PMethod)):
                if not self._has_return(statement.body):
                    raise TypingError(f"Not all code paths return a value for function {statement.name} at {statement.position}")
            elif isinstance(statement, PClass):
                for method in statement.methods:
                    if method.is_builtin:
                        continue #ignore builtin methods. Just here for linking
                    if not self._has_return(method.body):
                        raise TypingError(f"Not all code paths return a value for function {method.name} at {method.position}")
    
    def _has_return(self, statement:Optional[PStatement]) -> bool:
        if statement is None:
            return False
        
        if isinstance(statement, PReturnStatement):
            return True
        
        if isinstance(statement, PBlock):
            for stmnt in statement.statements:
                if self._has_return(stmnt):
                    return True
            return False
            
        if isinstance(statement, PIfStatement):
            return self._has_return(statement.else_block) and self._has_return(statement.then_block)
        
        if isinstance(statement, (PWhileStatement,PForStatement)):
            return self._has_return(statement.body)
        
        return False
    
    def _add_implicit_cast(self, expression_to_cast:PExpression, target_type:IRCompatibleTyp):
        cast = PCast(self._ptype_from_typ(target_type, expression_to_cast.position), expression_to_cast)
        cast.expr_type = target_type
        return cast

Typer.default = Typer('??', StringIO(''))