from typing import Dict, List, Optional, Union, TextIO
from dataclasses import dataclass, field
from io import StringIO
from lexer import Lexeme, Lexer
from utils import TypeClass, TypeInfo, TYPE_INFO, CompilerWarning, Position, TypingError
from operations import BinaryOperation, UnaryOperation
from parser import (Parser, PFunction, PClassField, PProgram, PType,
                   PIdentifier, PArrayIndexing, PArrayInstantiation,
                   PBlock, PArrayType, PAssertStatement, PAssignment,
                   PBinaryOperation, PBreakStatement, PCast, PClass,
                   PContinueStatement, PDotAttribute, PExpression,
                   PForStatement, PUnaryOperation, PFunctionCall, PNoop,
                   PIfStatement, PLiteral, PMethodCall, PMethod,
                   PObjectInstantiation, PReturnStatement, PStatement,
                   PTernaryOperation, PThis,PVariableDeclaration, 
                   PWhileStatement, PDiscard, PVoid, Typ)

@dataclass
class ArchProperties:
    pointer_size:int=64
    max_int_size:int=64
    max_float_size:int=64

    def type_is_supported(self, type_info:TypeInfo) -> bool:
        if type_info.type_class == TypeClass.INTEGER:
            return type_info.bit_width <= self.max_int_size

        elif type_info.type_class == TypeClass.FLOAT:
            return type_info.bit_width <= self.max_float_size

        return True #8 bit or lower values are supported and pointers too

def create_property(name: str, type_str: str) -> PClassField:
    """Helper function to create a class property"""
    return PClassField(
        name=name,
        type=PType(type_str, Lexeme.default),
        is_public=True,
        lexeme=Lexeme.default,
        default_value=None
    )

def create_method(name: str, return_type: str, params: List[tuple[str, str]], builtin:bool=True) -> PMethod:
    """Helper function to create a method"""
    return PMethod(
        name=name,
        return_type=PType(return_type, Lexeme.default),
        parameters=[PVariableDeclaration(n, PType(t, Lexeme.default), None, Lexeme.default) for t, n in params],
        body=PBlock([], Lexeme.default),
        lexeme=Lexeme.default
    )

# Define the built-in types with their methods and properties
_builtin_types: Dict[str, Typ] = {
    # Numeric types
    "i8": Typ(
        name="i8",
        methods=[
            create_method("ToString", "string", []),
            create_method("Parse", "i8", [("string", "s")])
        ],
        fields=[],
        is_reference_type=False
    ),
    "i16": Typ(
        name="i16",
        methods=[
            create_method("ToString", "string", []),
            create_method("Parse", "i16", [("string", "s")])
        ],
        fields=[],
        is_reference_type=False
    ),
    "i32": Typ(
        name="i32",
        methods=[
            create_method("ToString", "string", []),
            create_method("Parse", "i32", [("string", "s")])
        ],
        fields=[],
        is_reference_type=False
    ),
    "i64": Typ(
        name="i64",
        methods=[
            create_method("ToString", "string", []),
            create_method("Parse", "i64", [("string", "s")])
        ],
        fields=[],
        is_reference_type=False
    ),
    "u8": Typ(
        name="u8",
        methods=[
            create_method("ToString", "string", []),
            create_method("Parse", "u8", [("string", "s")])
        ],
        fields=[],
        is_reference_type=False
    ),
    "u16": Typ(
        name="u16",
        methods=[
            create_method("ToString", "string", []),
            create_method("Parse", "u16", [("string", "s")])
        ],
        fields=[],
        is_reference_type=False
    ),
    "u32": Typ(
        name="u32",
        methods=[
            create_method("ToString", "string", []),
            create_method("Parse", "u32", [("string", "s")])
        ],
        fields=[],
        is_reference_type=False
    ),
    "u64": Typ(
        name="u64",
        methods=[
            create_method("ToString", "string", []),
            create_method("Parse", "u64", [("string", "s")])
        ],
        fields=[],
        is_reference_type=False
    ),
    "f16": Typ(
        name="f16",
        methods=[
            create_method("ToString", "string", []),
            create_method("Parse", "f16", [("string", "s")]),
            create_method("Round", "f16", []),
            create_method("Floor", "f16", []),
            create_method("Ceiling", "f16", [])
        ],
        fields=[],
        is_reference_type=False
    ),
    "f32": Typ(
        name="f32",
        methods=[
            create_method("ToString", "string", []),
            create_method("Parse", "f32", [("string", "s")]),
            create_method("Round", "f32", []),
            create_method("Floor", "f32", []),
            create_method("Ceiling", "f32", [])
        ],
        fields=[],
        is_reference_type=False
    ),
    "f64": Typ(
        name="f64",
        methods=[
            create_method("ToString", "string", []),
            create_method("Parse", "f64", [("string", "s")]),
            create_method("Round", "f64", []),
            create_method("Floor", "f64", []),
            create_method("Ceiling", "f64", [])
        ],
        fields=[],
        is_reference_type=False
    ),

    # String type
    "string": Typ(
        name="string",
        methods=[
            create_method("ToString", "string", []),
            create_method("Length", "i32", []),
            create_method("Substring", "string", [("i32", "start"), ("i32", "length")]),
            create_method("ToUpper", "string", []),
            create_method("ToLower", "string", []),
            create_method("Trim", "string", []),
            create_method("Replace", "string", [("string", "old"), ("string", "new")]),
            create_method("Split", "string[]", [("string", "separator")]),
            create_method("Contains", "bool", [("string", "value")]),
            create_method("StartsWith", "bool", [("string", "value")]),
            create_method("EndsWith", "bool", [("string", "value")])
        ],
        fields=[
            create_property("Length", "u64")
        ]
    ),

    # Boolean type
    "bool": Typ(
        name="bool",
        methods=[
            create_method("ToString", "string", []),
            create_method("Parse", "bool", [("string", "s")])
        ],
        fields=[],
        is_reference_type=False
    ),

    # Character type
    "char": Typ(
        name="char",
        methods=[
            create_method("ToString", "string", []),
            create_method("IsDigit", "bool", []),
            create_method("IsLetter", "bool", []),
            create_method("IsWhitespace", "bool", []),
            create_method("ToUpper", "char", []),
            create_method("ToLower", "char", [])
        ],
        fields=[],
        is_reference_type=False
    ),

    # Array type (will be used as base for all array types)
    "__array": Typ(
        name="__array",
        methods=[
            create_method("ToString", "string", []),
            create_method("Copy", "void", [("i32", "sourceIndex"),
                                         ("array", "destination"),
                                         ("i32", "destinationIndex"),
                                         ("i32", "length")]),
            create_method("Fill", "void", [("any", "value")]),
            create_method("Clear", "void", []),
            create_method("Contains", "bool", [("any", "value")]),
            create_method("IndexOf", "i32", [("any", "value")]),
            create_method("LastIndexOf", "i32", [("any", "value")]),
            create_method("Reverse", "void", [])
        ],
        fields=[
            create_property("Length", "u64"),
        ],
        is_reference_type=True,
        is_array=True
    ),
    'void': Typ('void', [],[]),
    '__null': Typ('null', [], [], True)
}

@dataclass
class Symbol:
    """Represents a symbol (variable or function) in the scope"""
    name: str
    type: PType
    declaration: PStatement
    is_function: bool = False
    parameters: Optional[List[PVariableDeclaration]] = None
    #checks symbol use
    is_assigned: bool = False # Checks if a function is assigned before use (can be bypassed if global used in function)
    is_read: bool = False # checks if a variable is read (must be after assignment)

@dataclass
class Scope:
    """Represents a single scope level with its symbols"""
    parent: Optional['Scope'] = None
    symbols: Dict[str, Symbol] = field(default_factory=dict)

    def define(self, name: str, type_: PType, declaration: PStatement,
               is_function: bool = False,
               parameters: Optional[List[PVariableDeclaration]] = None) -> Symbol:
        """Define a new symbol in the current scope"""

        #ensure one does not yet exist
        if (symbol:=self.lookup(name)) is not None:
            raise SymbolRedefinitionError(name,  symbol, declaration)
        self.symbols[name] = Symbol(name, type_, declaration, is_function, parameters)
        return self.symbols[name]

    def lookup(self, name: str) -> Optional[Symbol]:
        """Look up a symbol in this scope or any parent scope"""
        current = self
        while current is not None:
            if name in current.symbols:
                return current.symbols[name]
            current = current.parent
        return None

class SymbolRedefinitionError(Exception):
    """Raised when attempting to redefine a symbol in the same scope"""
    def __init__(self, name: str, original: Symbol, new_declaration: PStatement):
        self.name = name
        self.original = original
        self.new_declaration = new_declaration
        super().__init__(
            f"Symbol '{name}' already defined at {original.declaration.position.line}:"
            f"{original.declaration.position.column}, cannot redefine at "
            f"{new_declaration.position.line}:{new_declaration.position.column}"
        )

class SymbolNotFoundError(Exception):
    """Raised when a referenced symbol cannot be found in any accessible scope"""
    def __init__(self, name: str, reference: PStatement):
        self.name = name
        self.reference = reference
        super().__init__(
            f"Symbol '{name}' not found (referenced at {reference.position.line}:"
            f"{reference.position.column})"
        )

@dataclass
class ScopeManager:
    """Manages the hierarchy of scopes during type checking"""
    current_scope: Scope = field(default_factory=Scope)
    _function_scope_stack:List = field(default_factory=list)
    
    def enter_function_scope(self):
        self._function_scope_stack.append(self.current_scope)
        global_scope = self.current_scope
        while global_scope.parent is not None:
            global_scope = global_scope.parent
        self.current_scope = Scope(parent=global_scope)

    def enter_scope(self) -> None:
        """Enter a new scope"""
        new_scope = Scope(parent=self.current_scope)
        self.current_scope = new_scope
        
    def exit_function_scope(self):
        self.current_scope = self._function_scope_stack.pop()

    def exit_scope(self) -> None:
        """Exit the current scope"""
        if self.current_scope.parent is None:
            raise RuntimeError("Cannot exit global scope")
        self.current_scope = self.current_scope.parent

    def define_variable(self, var_decl: PVariableDeclaration) -> Symbol:
        """Define a variable in the current scope"""
        return self.current_scope.define(var_decl.name, var_decl.var_type, var_decl)

    def define_function(self, function: PFunction) -> Symbol:
        """Define a function in the current scope"""
        return self.current_scope.define(
            function.name,
            function.return_type,
            function,
            is_function=True,
            parameters=function.parameters
        )

    def lookup(self, name: str, statement:PStatement) -> Symbol:
        """Look up a symbol in the current scope hierarchy"""
        symbol = self.current_scope.lookup(name)
        if symbol is None:
            raise SymbolNotFoundError(name, statement)
        return symbol

class UnknownTypeError(Exception):
    def __init__(self, type_:PType) -> None:
        self.unknown_type = type_
        super().__init__(
            f"Use of unknown type {type_} at {type_.position.line}:{type_.position.column}"
        )

class TypingConversionError(Exception):
    """Raised when an invalid type conversion is attempted"""
    def __init__(self, from_type: Typ, to_type: Typ, node: PStatement):
        self.from_type = from_type
        self.to_type = to_type
        self.node = node
        super().__init__(
            f"Cannot convert from {from_type} to {to_type} at {node.position.line}:{node.position.column}"
        )

class Typer:
    default:'Typer'
    
    """Handles type checking and returns a Typed AST"""
    def __init__(self, filename:str, file:TextIO, archProps:Optional[ArchProperties]=None):
        self.archProperties = archProps or ArchProperties()
        self.parser = Parser(Lexer(filename, file))
        self.known_types = _builtin_types.copy()
        self._in_class:Optional[PType] = None
        self.expected_return_type:Optional[Typ] = None
        self._scope_manager = ScopeManager()
        self.is_assignment = False #set to true when typing an identifier to be assigned
        self.warnings: List[CompilerWarning] = []
        self._ast: Optional[PProgram] = None
        
        self.all_symbols: List[Symbol] = []  # Track all symbols
        self.all_functions: List[PFunction] = []  # Track all functions
        self.all_class_properties: List[PClassField] = []  # Track class properties
        self.all_class_methods: List[PFunction] = []  # Track class methods

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
            PFunctionCall: self._type_function_call,
            PMethodCall: self._type_method_call,

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
            PClassField: self._type_class_property,
            PDotAttribute: self._type_dot_attribute,
            PObjectInstantiation: self._type_object_instantiation,

            # Type operations
            PCast: self._type_cast,
            PType: self._type_ptype,
            PArrayType: self._type_ptype,

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

    def type_program(self, warnings:bool = False) -> PProgram:
        """Type check the entire source code and return the typed AST"""
        if self._ast is not None:
            self._print_warnings()
            return self._ast
        self._ast = self.parser.parse()

        # First pass (quick) to build type list with user defined classes
        for statement in self._ast.statements:
            if isinstance(statement, PClass):
                self.known_types[statement.name] = Typ(statement.name, statement.methods, statement.fields)
            elif isinstance(statement, PFunction):
                self._scope_manager.define_function(statement)
            continue

        # Full tree traversal pass
        for statement in self._ast.statements:
            self._type_statement(statement)
        
        self._check_unused_symbols()

        self._print_warnings()
        self._cfg_check(self._ast)
        return self._ast

    def _check_unused_symbols(self):
        # Check variables
        for symbol in self.all_symbols:
            if not symbol.is_read and not symbol.is_function:
                self.warnings.append(CompilerWarning(
                    f"Variable '{symbol.name}' is declared but never read",
                    symbol.declaration.position
                ))
        # Check functions
        for func in self.all_functions:
            if func.position is Position.default:
                pass
            if not func.is_called and func.name != 'main':  # Exclude main if present
                self.warnings.append(CompilerWarning(
                    f"Function '{func.name}' is declared but never called",
                    func.position
                ))
        # Check class properties and methods
        for prop in self.all_class_properties:
            if not prop.is_read and not prop.is_assigned:
                self.warnings.append(CompilerWarning(
                    f"Class property '{prop.name}' is never used",
                    prop.position
                ))
        for method in self.all_class_methods:
            if method.position is Position.default:
                continue #ignore unused builtins
            if not method.is_called:
                self.warnings.append(CompilerWarning(
                    f"Method '{method.name}' is declared but never called",
                    method.position
                ))

    def _ptype_from_typ(self, typ:Typ, pos:Optional[Position]=None) -> PType|PArrayType:
        if pos is None:
            pos = Position.default
        if not typ.is_array:
            return PType(typ.name, pos)
        #typ is array
        #gets the base type name then loops over to create a PArrayType of the correct dimension
        base_name = typ.name.replace('[]','')
        ptyp = PType(base_name, pos)
        while len(base_name) < len(typ.name):
            base_name += '[]'
            ptyp = PArrayType(ptyp, pos)
        return ptyp

    def get_type_info(self, type_: Typ) -> TypeInfo:
        """Get TypeInfo for a given type, handling array types"""

        # Handle array types
        if type_.is_array:
            return TypeInfo(TypeClass.ARRAY, is_signed=False)

        type_str = type_.name

        # Look up built-in type
        if type_str in TYPE_INFO:
            return TYPE_INFO[type_str]

        # Must be a custom class
        return TypeInfo(TypeClass.CLASS, is_builtin=False)

    def is_numeric_type(self, type_: Typ) -> bool:
        """Check if type is numeric (integer or float)"""
        info = self.get_type_info(type_)
        return info.type_class in (TypeClass.INTEGER, TypeClass.FLOAT, TypeClass.BOOLEAN)

    def check_types_match(self, expected: Typ, actual: Typ) -> bool:
        """
        Check if two types are compatible, considering implicit conversions.
        Returns True if types match or actual can be implicitly converted to expected.
        """
        if str(expected) == str(actual):
            return True

        expected_info = self.get_type_info(expected)
        actual_info = self.get_type_info(actual)

        # Handle array types
        if expected_info.type_class == TypeClass.ARRAY and actual_info.type_class == TypeClass.ARRAY:
            # Array types must match exactly
            return str(expected) == str(actual)

        # Handle numeric conversions
        if self.is_numeric_type(expected) and self.is_numeric_type(actual):
            return self.can_convert_numeric(actual, expected)

        # Handle string conversions - anything can convert to string
        return False

    def can_convert_numeric(self, from_type: Typ, to_type: Typ) -> bool:
        """Determine if numeric conversion is allowed between types"""
        from_info = self.get_type_info(from_type)
        to_info = self.get_type_info(to_type)

        # Only handle numeric types
        if not (self.is_numeric_type(from_type) and self.is_numeric_type(to_type)):
            return False
        
        if from_type == to_info:
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

    def get_common_type(self, type1: Typ, type2: Typ) -> Optional[Typ]:
        """
        Find the common type that both types can be converted to.
        Used for determining result type of binary operations.
        """
        
        if str(type1) == str(type2):
            return type1
        
        # If either is non-numeric, no common type
        if not (self.is_numeric_type(type1) and self.is_numeric_type(type2)):
            return None

        info1 = self.get_type_info(type1)
        info2 = self.get_type_info(type2)

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
                float_width = self.get_type_info(float_type).bit_width
                if float_width <= 16:
                    return self.known_types["f16"]
                if float_width <= 32:
                    return self.known_types["f32"]
                return self.known_types["f64"]
            else:
                # Need at least f32
                float_width = self.get_type_info(float_type).bit_width
                if float_width <= 32:
                    return self.known_types["f32"]
                return self.known_types["f64"]

        # Both are integers
        if not (info1.is_signed and info2.is_signed):
            # If either is unsigned, use unsigned type with enough bits
            max_width = max(info1.bit_width, info2.bit_width)
            if max_width <= 8:
                return self.known_types["u8"]
            if max_width <= 16:
                return self.known_types["u16"]
            if max_width <= 32:
                return self.known_types["u32"]
            return self.known_types["u64"]

        # Both signed - use widest type
        max_width = max(info1.bit_width, info2.bit_width)
        if max_width <= 8:
            return self.known_types["i8"]
        if max_width <= 16:
            return self.known_types["i16"]
        if max_width <= 32:
            return self.known_types["i32"]
        return self.known_types["i64"]
    
    def can_do_operation_on_type(self, operation: Union[BinaryOperation, UnaryOperation], type_: Typ) -> bool:
        """Check if the given operation can be performed on the given type."""
        # Always allow Bool negation (a `not 0` or `not ""` will return True, and false otherwise)
        if operation == UnaryOperation.BOOL_NOT:
            return True
        
        type_info = self.get_type_info(type_)
        
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
        
        # Assignment and copy operations are handled separately in type checking
        if isinstance(operation, BinaryOperation):
            if operation in (BinaryOperation.ASSIGN, BinaryOperation.COPY):
                return True
                
        return False

    def _type_statement(self, statement: PStatement) -> Optional[Typ]:
        """Type checks a statement (or expression) and returns its type"""
        if isinstance(statement, PExpression):
            return self._type_expression(statement)
        if not isinstance(statement, (PArrayIndexing, PArrayInstantiation,
                                          PIdentifier, PLiteral, PBinaryOperation,
                                          PUnaryOperation, PTernaryOperation,
                                          PFunctionCall, PMethodCall, PClass,
                                          PIfStatement, PWhileStatement,
                                          PForStatement, PReturnStatement,
                                          PBreakStatement, PContinueStatement,
                                          PAssertStatement, PVariableDeclaration,
                                          PClassField, PDotAttribute,
                                          PObjectInstantiation, PCast, PType,
                                          PArrayType, PBlock, PFunction, PThis)):
            raise TypingError(f"Cannot type the {type(statement)} element at location {statement.position}")
        typer_func = self._node_function_map.get(type(statement), None)
        if typer_func is None:
            raise TypingError(f"Cannot type the {type(statement)} element at location {statement.position}")
        return typer_func(statement)

    def _type_expression(self, expression: PExpression) -> Typ:
        """Type checks an expression definition and returns its type"""
        if not isinstance(expression, (PArrayIndexing, PArrayInstantiation,
                                          PIdentifier, PLiteral, PBinaryOperation,
                                          PUnaryOperation, PTernaryOperation,
                                          PFunctionCall, PMethodCall, PThis,
                                          PDotAttribute, PObjectInstantiation,
                                          PCast, PNoop, PVoid, PAssignment)):
            raise TypingError(f"Cannot type {type(expression)}, it's not a valid expression.")
        typer_func = self._node_function_map.get(type(expression), None)
        if typer_func is None:
            raise TypingError(f"Cannot type the {type(expression)} element at location {expression.position}")
        return typer_func(expression)
    
    def _type_noop(self, noop:PNoop):
        """Type check a Noop (optional entry) Always valid type checks to true"""
        noop.expr_type = self.known_types['bool']
        return noop.expr_type
    
    def _type_void(self, void:PVoid):
        """Type check a Noop (optional entry) Always valid type checks to true"""
        void.expr_type = self.known_types['void']
        return void.expr_type

    def _type_class(self, class_def: PClass) -> None:
        """Type checks a class definition and returns its type"""
        for prop in class_def.fields:
            self._type_class_property(prop)
        
        # self._scope_manager.enter_scope()
        self._in_class = PType(class_def.name, class_def.position)
        # self._scope_manager.current_scope.define("this", self._in_class, class_def)
        for method in class_def.methods:
            self.all_class_methods.append(method)
            self._type_function(method)
        # self._scope_manager.exit_scope()

    def _type_ptype(self, ptype:PType) -> Typ:
        """Type checks a class definition and returns its type"""
        if isinstance(ptype, PArrayType):
            base = ptype.base_type
            if base.type_string not in self.known_types:
                raise UnknownTypeError(base)
            return self.known_types['__array'].copy_with(str(ptype), is_array=True)
        if not ptype.type_string in self.known_types:
                raise UnknownTypeError(ptype)
        type_ = self.known_types[ptype.type_string]
        if not self.archProperties.type_is_supported(type_info = self.get_type_info(type_)):
            raise TypingError(f"Type {type_} is too large to be supported on this architecture")
        return type_

    def _type_function(self, function: PFunction|PMethod) -> None:
        """Type checks a function definition"""        
        if self.expected_return_type is not None:
            raise TypingError("Cannot define a function inside another function")
        if not isinstance(function, PMethod):
            self.all_functions.append(function)
        else: #method not function
            assert self._in_class is not None #if method: ensure we're in a function!
            function._class_type = self._type_ptype(self._in_class)
        
        self._scope_manager.enter_function_scope()
        self.expected_return_type = self._type_ptype(function.return_type)
        function._return_typ_typed = self.expected_return_type
        self._type_block(function.body, function.parameters)
        
        #add implicit return at the end of a void function if there isn't one already
        if self.get_type_info(self.expected_return_type).type_class == TypeClass.VOID:
            if len(function.body.statements) == 0:
                function.body.statements.append(
                    PReturnStatement.implicit_return(function.body.position))
            if not isinstance(function.body.statements[-1], PReturnStatement):
                function.body.statements.append(
                    PReturnStatement.implicit_return(
                        function.body.statements[-1].position))
        self.expected_return_type = None
        self._scope_manager.exit_function_scope()

    def _type_block(self, block: PBlock, params:Optional[List[PVariableDeclaration]]=None) -> None:
        """Type checks a block of statements, optionally verifying return type"""
        self._scope_manager.enter_scope()
        if params is not None:
            for param in params:
                self._type_variable_declaration(param)
                #Set is_assigned to true of all function params (they are always assigned)
                self._scope_manager.lookup(param.name, param).is_assigned = True
        #first pass for defined methods
        for statement in block.statements:
            if isinstance(statement, PFunction):
                if self.expected_return_type is not None:
                    raise TypingError("Cannot define a function inside another function")
                self._scope_manager.define_function(statement)

        for statement in block.statements:
            self._type_statement(statement)
        self._scope_manager.exit_scope()

    def _type_variable_declaration(self, var_decl: PVariableDeclaration) -> None:
        """Type checks a variable declaration"""
        symbol = self._scope_manager.define_variable(var_decl)
        self.all_symbols.append(symbol)
        var_type = self._type_ptype(var_decl.var_type)
        var_decl._typer_pass_var_type = var_type

        if var_decl.initial_value is None:
            return
        
        symbol.is_assigned = True
        expr_type = self._type_expression(var_decl.initial_value)
        if not self.check_types_match(var_type, expr_type):
            raise TypingConversionError(var_type, expr_type, var_decl)
        if expr_type != var_type:
            var_decl.initial_value = self._add_implicit_cast(
                                            var_decl.initial_value, var_type)

    def _type_discard(self, discard:PDiscard) -> None:
        self._type_expression(discard.expression)

    def _type_class_property(self, prop:PClassField) -> None:
        """Type checks a variable declaration"""
        var_type = self._type_ptype(prop.var_type)
        prop._typer_pass_var_type = var_type
        self.all_class_properties.append(prop)

        if prop.default_value is None:
            return
        prop.is_assigned = True
        expr_type = self._type_expression(prop.default_value)
        if not self.check_types_match(var_type, expr_type):
            raise TypingConversionError(var_type, expr_type, prop)

    def _type_assignment(self, assignment: PAssignment) -> Typ:
        """Type checks an assignment and returns the assigned type"""
        self.is_assignment = True
        ident_type = self._type_expression(assignment.target)
        self.is_assignment = False
        assignment.expr_type = ident_type
        expression_type = self._type_expression(assignment.value)
        
        if not self.check_types_match(ident_type, expression_type):
            raise TypingConversionError(expression_type, ident_type, assignment)
        if ident_type != expression_type:
            #implicit cast
            assignment.value = self._add_implicit_cast(assignment.value, ident_type)
        return ident_type

    def _type_binary_operation(self, binop: PBinaryOperation) -> Typ:
        """Type checks a binary operation and returns its result type"""
        left_type = self._type_expression(binop.left)
        right_type = self._type_expression(binop.right)
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

    def _type_unary_operation(self, unop: PUnaryOperation) -> Typ:
        """Type checks a unary operation and returns its result type"""
        operand_type = self._type_expression(unop.operand)
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
        if not self.get_type_info(condition_type).type_class == TypeClass.BOOLEAN:
            raise TypingConversionError(condition_type, self.known_types['bool'], if_stmt.condition)
        self._type_block(if_stmt.then_block)
        if if_stmt.else_block is not None:
            self._type_block(if_stmt.else_block)

    def _type_while_statement(self, while_stmt: PWhileStatement) -> None:
        """Type checks a while loop"""
        condition_type = self._type_expression(while_stmt.condition)
        if not self.get_type_info(condition_type).type_class == TypeClass.BOOLEAN:
            raise TypingConversionError(condition_type, self.known_types['bool'], while_stmt.condition)
        self._type_block(while_stmt.body)

    def _type_for_statement(self, for_stmt: PForStatement) -> None:
        """Type checks a for loop"""
        self._type_statement(for_stmt.initializer)
        
        if not isinstance(for_stmt.condition, PNoop):
            condition_type = self._type_expression(for_stmt.condition)
            if not self.get_type_info(condition_type).type_class == TypeClass.BOOLEAN:
                raise TypingConversionError(condition_type, self.known_types['bool'], for_stmt.condition)
        else:
            for_stmt.condition.expr_type = self.known_types['bool']
            
        self._type_statement(for_stmt.increment)
        
        self._type_block(for_stmt.body)

    def _type_return_statement(self, return_stmt: PReturnStatement) -> None:
        """Type checks a return statement against expected return type"""
        if self.expected_return_type is None:
            raise TypingError("Cannot return outside a function")
        expression_type = self._type_expression(return_stmt.value)
        if not self.check_types_match(self.expected_return_type, expression_type):
            raise TypingConversionError(expression_type, self.expected_return_type, return_stmt)
        
        if self.expected_return_type != return_stmt.value.expr_type:
            return_stmt.value = self._add_implicit_cast(
                                        return_stmt.value,
                                        self.expected_return_type)

    def _type_function_call(self, func_call: PFunctionCall) -> Typ:
        """Type checks a function call and returns its return type"""
        func = func_call.function
        symbol = self._scope_manager.lookup(func.name, func)
        
        if not symbol.is_function or symbol.parameters is None:
            raise TypingError(f"Symbol {symbol.name} is {symbol.type.type_string} and not a function at location {func_call.position}")
        
        assert isinstance(symbol.declaration, PFunction)
        symbol.declaration.is_called = True
        
        if len(symbol.parameters) != len(func_call.arguments):
            raise TypingError(f"The function expects {len(func_call.arguments)} arguments but got {len(symbol.parameters)}"+\
                              f"at location {func_call.position}")
        
        for i, (expected_param, actual) in enumerate(zip(symbol.parameters, func_call.arguments)):
            expected_type = self._type_ptype(expected_param.var_type)
            actual_type = self._type_expression(actual)
            if not self.check_types_match(expected_type, actual_type):
                raise TypingConversionError(actual_type, expected_type, actual)
            if expected_type != actual_type:
                func_call.arguments[i] = self._add_implicit_cast(actual, expected_type)
        
        func_call.expr_type = self._type_ptype(symbol.type)
        return func_call.expr_type

    def _type_method_call(self, method_call: PMethodCall) -> Typ:
        """Type checks a method call and returns its return type"""
        obj_type = self._type_expression(method_call.object)
        for method in obj_type.methods:
            if method_call.method_name == method.name:
                break
        else:
            raise TypingError(f"Method {method_call.method_name} of type {obj_type} if unknown at location {method_call.position}")
        
        method.is_called = True
        if len(method.parameters) != len(method_call.arguments):
            raise TypingError(f"The function expects {len(method_call.arguments)} arguments but got {len(method.parameters)}"+\
                              f"at location {method_call.position}")

        for expected_param, actual in zip(method.parameters, method_call.arguments):
            expected_type = self._type_ptype(expected_param.var_type)
            actual_type = self._type_expression(actual)
            if not self.check_types_match(expected_type, actual_type):
                raise TypingConversionError(actual_type, expected_type, actual)
        
        method_call.expr_type = self._type_ptype(method.return_type)
        return method_call.expr_type

    def _type_identifier(self, identifier: PIdentifier) -> Typ:
        """Type checks an identifier and returns its type"""
        symbol = self._scope_manager.lookup(identifier.name, identifier)
        identifier.expr_type = self._type_ptype(symbol.type)
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

    def _type_literal(self, literal: PLiteral) -> Typ:
        """Type checks a literal and returns its type"""
        # choses a default but can be cast if the user needs a bigger number (or suffixed)
        if literal.literal_type == 'int':
            if not isinstance(literal.value, int):
                raise TypingError(f"'{literal.value}' is not a int but described as an int")
            # Currently number out of range will be truncated and only least significant bits kept 
            literal.expr_type = self.known_types['i32']
        elif literal.literal_type == 'bool':
            if not isinstance(literal.value, bool):
                raise TypingError(f"'{literal.value}' is not a boolean but described as a boolean")
            literal.expr_type = self.known_types['bool']
        elif literal.literal_type == 'char':
            if not isinstance(literal.value, int):
                raise TypingError(f"'{literal.value}' is not a char but described as a char")
            literal.expr_type = self.known_types['char']
        elif literal.literal_type == 'string':
            if not isinstance(literal.value, str):
                raise TypingError(f"'{literal.value}' is not a string but described as a string")
            literal.expr_type = self.known_types['string']
        elif literal.literal_type == 'null':
            if literal.value is not None:
                raise TypingError(f"'{literal.value}' is not null but described as a null")
            literal.expr_type = self.known_types['__null']
        else:
            if not literal.literal_type == 'float':
                raise TypingError(f"Unknown literal type '{literal.literal_type}'")
            if not isinstance(literal.value, float):
                raise TypingError(f"'{literal.value}' is not a float but described as a float")
            # Currently number out of range will be truncated and cropped to f32 precision
            literal.expr_type = self.known_types['f32']
        return literal.expr_type

    def _type_this(self, _: PThis) -> Typ:
        """Type checks a cast expression and returns the target type"""
        if self._in_class is None:
            raise TypingError("'this' is not defined outside of a class")
        return self.known_types[self._in_class.type_string]

    def _type_cast(self, cast: PCast) -> Typ:
        """Type checks a cast expression and returns the target type"""
        #TODO always valid if numeric or bool beware of char, not if class/ref type
        expression_type = self._type_expression(cast.expression)
        target_type = self._type_ptype(cast.target_type)
        expression_type_info = self.get_type_info(expression_type)
        target_type_info = self.get_type_info(target_type)
        
        if expression_type.name == target_type.name:
            # TODO add warning for useless cast
            cast.expr_type = target_type
        elif self.is_numeric_type(expression_type) and self.is_numeric_type(target_type):
            cast.expr_type = target_type
            # TODO Add warning for loss of precision if reduction in bit-width
        elif target_type_info.type_class == TypeClass.BOOLEAN:
            cast.expr_type = target_type
        elif expression_type_info.type_class == TypeClass.BOOLEAN and self.is_numeric_type(target_type):
            cast.expr_type = target_type
        elif target_type_info.type_class == TypeClass.STRING:
            raise TypingError(f"Cannot cast to string. Use the .ToString() method instead")
        elif expression_type.name == self.known_types['__null']:
            # in case it's a null literal
            cast.expr_type = target_type
        else:
            raise TypingError(f"Unable to cast {expression_type} to {target_type} at location {cast.position}")
            
        return cast.expr_type

    def _type_array_indexing(self, array_index: PArrayIndexing) -> Typ:
        """Type checks an array indexing expression and returns the element type"""
        array_type = self._type_expression(array_index.array)
        if not array_type.name.endswith('[]'):
            TypingError(f"Expected array type but got '{array_type.name}'")     
        if array_type.name.endswith('[][]'):
            array_elem_type = array_type.copy_with(array_type.name[:-2], is_array=array_type.name[:-2].endswith('[]')) #strip of array from the end
        else:
            array_elem_type = self.known_types[array_type.name[:-2]]     
               
        index = self._type_expression(array_index.index)
        if self.get_type_info(index).type_class != TypeClass.INTEGER:
            raise TypingError(f"The index must be an integer type not '{index}'")
        if array_index.expr_type != self.known_types['u64']:
            #implicit convert array index to u64
            array_index.index = self._add_implicit_cast(
                array_index.index,
                self.known_types['u64'])
        
        array_index.expr_type = array_elem_type
        return array_elem_type

    def _type_object_instantiation(self, obj_init: PObjectInstantiation) -> Typ:
        """Type checks an object instantiation and returns the object type"""
        obj_init.expr_type = self._type_ptype(obj_init.class_type)
        return obj_init.expr_type

    def _type_array_instantiation(self, array_init: PArrayInstantiation) -> Typ:
        """Type checks an array instantiation and returns the array type"""
        array_init.expr_type = self._type_ptype(PArrayType(array_init.element_type, array_init.element_type.position))
        array_size_type = self._type_expression(array_init.size)
        if self.get_type_info(array_size_type).type_class != TypeClass.INTEGER:
            raise TypingError(f"Expected an array size of type Integer but got '{array_size_type}'")
        array_init._element_type_typ = self._type_ptype(array_init.element_type)
        return array_init.expr_type
        

    def _type_dot_attribute(self, dot_attr: PDotAttribute) -> Typ:
        """Type checks a dot attribute access and returns its type"""
        tmp_assignment = self.is_assignment
        self.is_assignment = False
        left_type = self._type_expression(dot_attr.left)
        for prop in left_type.fields:
            if prop.name == dot_attr.right.name:
                if dot_attr.right.expr_type is None:
                    dot_attr.right.expr_type = self._type_ptype(prop.var_type)
                dot_attr.expr_type = dot_attr.right.expr_type
                prop.is_assigned |= tmp_assignment
                break
        else:
            raise TypingError(f"'{dot_attr.right.name}' is not a known property of '{left_type}'")
        
        return dot_attr.expr_type

    def _type_ternary_operation(self, ternary: PTernaryOperation) -> Typ:
        """Type checks a ternary operation and returns its result type"""
        condition_type = self._type_expression(ternary.condition)
        if self.get_type_info(condition_type).type_class != TypeClass.BOOLEAN:
            raise TypingError(f"Cannot use a {condition_type} in the condition of a ternary operator. Are you missing a cast? {ternary.condition.position}")
        if_true_value_type = self._type_expression(ternary.true_value)
        if_false_value_type = self._type_expression(ternary.false_value)
        
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
        if self.get_type_info(condition_type).type_class != TypeClass.BOOLEAN:
            raise TypingError(f"An assertion expression must be a boolean. Are you missing a cast? {assert_stmt.condition.position}")
        
        if assert_stmt.message is not None:
            message_type = self._type_expression(assert_stmt.message)
            if self.get_type_info(message_type).type_class != TypeClass.STRING:
                raise TypingError(f"An assertion message must be a string!")
            
    def _cfg_check(self, program:Union[PProgram,PBlock]) -> None:
        """Check to ensure all functions have a valid return. Raises error if invalid otherwise returns None"""
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
            elif isinstance(statement, PIfStatement):
                self._cfg_check(statement.then_block)
                if statement.else_block is not None:
                    self._cfg_check(statement.else_block)
            elif isinstance(statement, (PForStatement, PWhileStatement)):
                self._cfg_check(statement.body)
            elif isinstance(statement, PBlock):
                self._cfg_check(statement)
    
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
    
    def _function_has_return(self, func:PFunction):
        # void functions are always valid because they do not need a return (implicitly added at the end)
        if self.get_type_info(self._type_ptype(func.return_type)).type_class == TypeClass.VOID:
            return True
        
        for statement in func.body.statements:
            if self._has_return(statement):
                return True
            
        return False
    
    def _add_implicit_cast(self, expression_to_cast:PExpression, target_type:Typ):
        cast = PCast(PType(target_type.name, expression_to_cast.position), expression_to_cast)
        cast.expr_type = target_type
        return cast

Typer.default = Typer('??', StringIO(''))