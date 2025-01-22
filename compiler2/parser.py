from typing import List, Optional, Dict, Any, Union, Tuple
from dataclasses import dataclass
from enum import Enum, auto
from lexer import Lexer, LexemeType, Lexeme, Position, LexemeStream
from operations import BinaryOperation, UnaryOperation, TernaryOperator

@dataclass
class Typ:
    """Represents a type in the P# language with its methods and properties"""
    name:str
    methods: List['PFunction']
    properties: List['PClassProperty']
    is_reference_type:bool = True
    is_array:bool = False
    
    def __post_init__(self):
        for function in self.methods:
            if function.name == "ToString" and len(function.parameters) == 0:
                return
        #add default ToString method if it does not exist. Just returns the Type name
        self.methods.append(PFunction("ToString", 
                                      PType('string', Lexeme.default), 
                                      [],
                                      PBlock([], Lexeme.default),
                                      Lexeme.default))

    def copy_with(self, name, is_array):
        return Typ(name, self.methods, self.properties, is_array=is_array)
    
    def __str__(self):
        return self.name

class ParserError(Exception):
    """Custom exception for parser-specific errors"""
    def __init__(self, message: str, lexeme: Lexeme):
        self.message = message
        self.lexeme = lexeme
        super().__init__(f"{message} at {lexeme.pos} with lexeme: {lexeme}")

class NodeType(Enum):
    """Enumeration of all possible node types in the parser tree"""
    EMPTY = auto()
    PROGRAM = auto()
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
    is_top_level:bool = True
    is_function:bool = False
    is_loop:bool = False
    return_type:Optional['PType'] = None

    def copy_with(self, current_lexeme, is_function:bool=False, is_loop:bool=False,
                  is_class:bool=False, return_type:Optional['PType']=None,
                  is_top_level:bool=False):
        if return_type and self.return_type is not None and return_type != self.return_type:
            raise ParserError("Error setting block return type different from existing return type", current_lexeme)
        return BlockProperties(
            is_function=self.is_function or is_function,
            is_loop=self.is_loop or is_loop,
            is_class= self.is_class or is_class,
            is_top_level= self.is_top_level and is_top_level,
            return_type=return_type)

@dataclass
class PStatement:
    """Base class for all AST nodes"""
    node_type: NodeType
    position: Position

@dataclass
class PExpression(PStatement):
    """Base class for all expression nodes - nodes that produce a value"""
    def __post_init__(self):
        self.expr_type:Optional[Typ] = None  # Will be set during typing pass

@dataclass
class PNoop(PExpression):
    def __init__(self, lexeme:Lexeme):
        super().__init__(NodeType.EMPTY, lexeme.pos)

@dataclass
class PProgram(PStatement):
    """Root node of the program"""
    statements: List[PStatement]

    def __init__(self, statements: List[PStatement], lexeme: Lexeme):
        super().__init__(NodeType.PROGRAM, lexeme.pos)
        self.statements = statements

@dataclass
class PFunction(PStatement):
    """Function definition node"""
    name: str
    return_type: 'PType'
    parameters: List['PVariableDeclaration']  # List of (type, name) tuples
    body: 'PBlock'

    def __init__(self, name: str, return_type: 'PType', parameters: List['PVariableDeclaration'],
                 body: 'PBlock', lexeme: Lexeme):
        super().__init__(NodeType.FUNCTION, lexeme.pos)
        self.name = name
        self.return_type = return_type
        self.parameters = parameters
        self.body = body

@dataclass
class PClass(PStatement):
    """Class definition node"""
    name: str
    properties: List['PClassProperty']
    methods: List[PFunction]

    def __init__(self, name: str, properties: List['PClassProperty'],
                 methods: List[PFunction], lexeme: Lexeme):
        super().__init__(NodeType.CLASS, lexeme.pos)
        self.name = name
        self.properties = properties
        self.methods = methods

@dataclass
class PClassProperty(PStatement):
    """Class property definition node"""
    name: str
    var_type: 'PType'
    is_public: bool
    default_value: Optional[PExpression]

    def __init__(self, name: str, type: 'PType', is_public: bool, lexeme: Lexeme, default_value:Optional[PExpression]):
        super().__init__(NodeType.CLASS_PROPERTY, lexeme.pos)
        self.name = name
        self.var_type = type
        self.is_public = is_public
        self.default_value = default_value

@dataclass
class PBlock(PStatement):
    """Block of statements"""
    statements: List[PStatement]
    block_properties:BlockProperties

    def __init__(self, statements: List[PStatement], lexeme: Lexeme):
        super().__init__(NodeType.BLOCK, lexeme.pos)
        self.statements = statements

@dataclass
class PVariableDeclaration(PStatement):
    """Variable declaration node"""
    name: str
    var_type: 'PType'
    initial_value: Optional[PExpression]

    def __init__(self, name: str, var_type: 'PType', initial_value: Optional[PExpression], lexeme: Lexeme):
        super().__init__(NodeType.VARIABLE_DECLARATION, lexeme.pos)
        self.name = name
        self.var_type = var_type
        self.initial_value = initial_value

@dataclass
class PAssignment(PExpression):
    """Assignment operation node"""
    target: Union['PIdentifier', 'PDotAttribute', 'PArrayIndexing']
    value: PExpression

    def __init__(self, target: Union['PIdentifier', 'PDotAttribute', 'PArrayIndexing'], value: PExpression, lexeme: Lexeme):
        super().__init__(NodeType.ASSIGNMENT, lexeme.pos)
        self.target = target
        self.value = value

class PDiscard(PStatement):
    """Discard an expression result"""
    expression:PExpression
    
    def __init__(self, expression:PExpression, lexeme: Lexeme):
        super().__init__(NodeType.DISCARD, lexeme.pos)
        self.expression = expression

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

@dataclass
class PUnaryOperation(PExpression):
    """Unary operation node"""
    operation: UnaryOperation
    operand: PExpression

    def __init__(self, operation: UnaryOperation, operand: PExpression, lexeme: Lexeme):
        super().__init__(NodeType.UNARY_OPERATION, lexeme.pos)
        self.operation = operation
        self.operand = operand

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

@dataclass
class PWhileStatement(PStatement):
    """While loop node"""
    condition: PExpression
    body: PBlock

    def __init__(self, condition: PExpression, body: PBlock, lexeme: Lexeme):
        super().__init__(NodeType.WHILE_STATEMENT, lexeme.pos)
        self.condition = condition
        self.body = body

@dataclass
class PForStatement(PStatement):
    """For loop node"""
    initializer: Union[PStatement, PNoop]
    condition: Union[PExpression, PNoop]
    increment: Union[PStatement, PNoop]
    body: PBlock

    def __init__(self, initializer: Union[PStatement, PNoop], condition: Union[PExpression, PNoop],
                 increment: Union[PStatement, PNoop], body: PBlock, lexeme: Lexeme):
        super().__init__(NodeType.FOR_STATEMENT, lexeme.pos)
        self.initializer = initializer
        self.condition = condition
        self.increment = increment
        self.body = body

@dataclass
class PReturnStatement(PStatement):
    """Return statement node"""
    value: PExpression

    def __init__(self, value: Optional[PExpression], lexeme: Lexeme):
        super().__init__(NodeType.RETURN_STATEMENT, lexeme.pos)
        self.value = value or PVoid(lexeme)

@dataclass
class PFunctionCall(PExpression):
    """Function call node"""
    function: 'PIdentifier'
    arguments: List[PExpression]

    def __init__(self, function: 'PIdentifier', arguments: List[PExpression], lexeme: Lexeme):
        super().__init__(NodeType.FUNCTION_CALL, lexeme.pos)
        self.function = function
        self.arguments = arguments

@dataclass
class PMethodCall(PExpression):
    """Method call node"""
    object: PExpression
    method_name: str
    arguments: List[PExpression]

    def __init__(self, object: PExpression, method: str, arguments: List[PExpression], lexeme: Lexeme):
        super().__init__(NodeType.METHOD_CALL, lexeme.pos)
        self.object = object
        self.method_name = method
        self.arguments = arguments

@dataclass
class PIdentifier(PExpression):
    """Identifier node"""
    name: str

    def __init__(self, name: str, lexeme: Lexeme):
        super().__init__(NodeType.IDENTIFIER, lexeme.pos)
        self.name = name

@dataclass
class PThis(PExpression):
    """This node: reference to the current instance"""
    def __init__(self, lexeme:Lexeme):
        super().__init__(NodeType.IDENTIFIER, lexeme.pos)
    
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

@dataclass
class PCast(PExpression):
    """Type cast expression node"""
    target_type: 'PType'  # The type to cast to
    expression: PExpression  # The expression being cast

    def __init__(self, target_type:'PType', expression):
        super().__init__(NodeType.CAST, target_type.position)
        self.target_type = target_type
        self.expression = expression

@dataclass
class PBreakStatement(PStatement):
    """Break statement node"""

    def __init__(self, lexeme: Lexeme):
        super().__init__(NodeType.BREAK_STATEMENT, lexeme.pos)

@dataclass
class PContinueStatement(PStatement):
    """Continue statement node"""

    def __init__(self, lexeme: Lexeme):
        super().__init__(NodeType.CONTINUE_STATEMENT, lexeme.pos)

@dataclass
class PAssertStatement(PStatement):
    """Assert statement node"""
    condition: PExpression
    message: Optional[PExpression]

    def __init__(self, condition: PExpression, message: Optional[PExpression], lexeme: Lexeme):
        super().__init__(NodeType.ASSERT_STATEMENT, lexeme.pos)
        self.condition = condition
        self.message = message

@dataclass
class PDotAttribute(PExpression):
    left:PExpression
    right:PIdentifier

    def __init__(self, left: PExpression, right:PIdentifier):
        super().__init__(NodeType.ATTRIBUTE, left.position)
        self.left = left
        self.right = right

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

@dataclass
class PArrayInstantiation(PExpression):
    """Represents array instantiation like new int[10]"""
    element_type: 'PType'  # The base type of array elements
    size: PExpression  # The size expression for the array

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

@dataclass
class PType(PStatement):
    type_string:str

    def __init__(self, base_type:str, lexeme_pos:Union[Lexeme,Position]):
        super().__init__(NodeType.TYPE, lexeme_pos if isinstance(lexeme_pos, Position) else lexeme_pos.pos)
        self.type_string = base_type

    def __str__(self):
        if isinstance(self.type_string, str):
            return self.type_string
        return str(self.type_string)

@dataclass
class PArrayType(PType):
    """
    Represents an array type in the AST.
    For example: int[] or MyClass[][]
    """
    element_type: Union['PArrayType',PType]

    def __init__(self, base_type:Union['PArrayType',PType], lexeme_pos:Union[Lexeme, Position]):
        self.element_type = base_type
        super().__init__(str(self), lexeme_pos)

    def __str__(self) -> str:
        """Convert array type to string representation"""
        return f"{str(self.element_type)}[]"
    
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

    def _expect(self, lexeme_type: LexemeType) -> Lexeme:
        """Verify current lexeme is of expected type and advance"""
        if self.current_lexeme is Lexeme.default:
            raise ParserError(f"Got Empty Lexeme instead of {lexeme_type.name}",
                              Lexeme.default)
        if self.current_lexeme.type != lexeme_type:
            raise ParserError(
                f"Expected {lexeme_type.name}, got {self.current_lexeme.type.name if self.current_lexeme else 'EOF'}",
                self.current_lexeme)
        lexeme = self.lexeme_stream.advance()
        return lexeme

    def _match(self, *lexeme_types: LexemeType) -> bool:
        """Check if current lexeme matches any of the given types"""
        return self._peek_matches(0, *lexeme_types)

    def _peek_matches(self, offset, *lexeme_types: LexemeType) -> bool:
        """Check if next lexeme matches any of the given types at index offset without advancing"""
        assert offset >= 0, "Cannot peek into the past (offset < 0)"
        lexeme = self.lexeme_stream.peek(offset)
        return lexeme is not None and lexeme.type in lexeme_types

    def parse(self) -> PProgram:
        """Parse the entire program"""
        statements = []
        start_lexeme = self.current_lexeme

        while self.current_lexeme and self.current_lexeme.type != LexemeType.EOF:
            statements.append(self._parse_statement(BlockProperties()))

        return PProgram(statements, start_lexeme)

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

    def _parse_statement(self, block_properties:BlockProperties) -> PStatement:
        """Parse a single statement"""
        if self.current_lexeme is Lexeme.default:
            raise ParserError("Unexpected end of file", self.current_lexeme)

        # Match statement type
        if self._match(*self.type_keywords):
            return self._parse_declaration(block_properties)
        elif (self._match(LexemeType.IDENTIFIER)
              and (self._peek_matches(1, LexemeType.IDENTIFIER) \
                   or (self._peek_matches(1, LexemeType.PUNCTUATION_OPENBRACKET)
                       and self._peek_matches(2, LexemeType.PUNCTUATION_CLOSEBRACKET)))):
            #starts with a type 
            return self._parse_declaration(block_properties)
        elif self._match(LexemeType.KEYWORD_CONTROL_IF):
            return self._parse_if_statement(block_properties.copy_with(self.current_lexeme, is_top_level=False))
        elif self._match(LexemeType.KEYWORD_CONTROL_WHILE):
            return self._parse_while_statement(block_properties.copy_with(self.current_lexeme, is_top_level=False))
        elif self._match(LexemeType.KEYWORD_CONTROL_FOR):
            return self._parse_for_statement(block_properties.copy_with(self.current_lexeme, is_top_level=False))
        elif self._match(LexemeType.KEYWORD_CONTROL_RETURN):
            if not block_properties.is_function:
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
        elif self._match(LexemeType.DISCARD):
            return self._parse_discard()
        elif self._match(LexemeType.KEYWORD_OBJECT_CLASS):
            if not block_properties.is_top_level:
                raise ParserError("Cannot have a break statement outside of a loop block", self.current_lexeme)
            return self._parse_class_definition(block_properties.copy_with(self.current_lexeme,
                                                                           is_class=True,
                                                                           is_top_level=False))
        elif self._match(LexemeType.PUNCTUATION_OPENBRACE):
            return self._parse_block(block_properties.copy_with(self.current_lexeme, is_top_level=False))

        # Expression statement (assignment, function call, etc.)
        expr = self._parse_expression()
        self._expect(LexemeType.PUNCTUATION_SEMICOLON)
        return expr

    def _parse_declaration(self, block_properties:BlockProperties) -> Union[PVariableDeclaration, PFunction]:
        """Parse a variable or function declaration"""
        type_lexeme = self.current_lexeme
        var_type = self._parse_type()

        name_lexeme = self._expect(LexemeType.IDENTIFIER)
        name = name_lexeme.value

        # Function declaration
        if self._match(LexemeType.PUNCTUATION_OPENPAREN):
            return self._parse_function_declaration(name, var_type, type_lexeme,
                                                    block_properties.copy_with(
                                                        self.current_lexeme,
                                                        is_function=True,
                                                        return_type=var_type))

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

        # Parse parameters
        if not self._match(LexemeType.PUNCTUATION_CLOSEPAREN):
            while True:
                if not self._match(*self.type_keywords, LexemeType.IDENTIFIER):
                    raise ParserError("Expected type in function parameters", self.current_lexeme)
                param_type = self._parse_type()

                param_name_lexeme = self._expect(LexemeType.IDENTIFIER)
                parameters.append(PVariableDeclaration(param_name_lexeme.value, param_type, None, param_name_lexeme))

                if not self._match(LexemeType.PUNCTUATION_COMMA):
                    break # Arrived at the end of the params
                # Has more parameters: consume comma
                self._expect(LexemeType.PUNCTUATION_COMMA)

        self._expect(LexemeType.PUNCTUATION_CLOSEPAREN)
        body = self._parse_block(block_properties)

        return PFunction(name, return_type, parameters, body, start_lexeme)

    def _parse_block(self, block_properties:BlockProperties) -> PBlock:
        """Parse a block of statements"""
        start_lexeme = self._expect(LexemeType.PUNCTUATION_OPENBRACE)
        statements = []

        while not self._match(LexemeType.PUNCTUATION_CLOSEBRACE):
            if not self.current_lexeme:
                raise ParserError("Unterminated block", start_lexeme)
            statements.append(self._parse_statement(block_properties))

        self._expect(LexemeType.PUNCTUATION_CLOSEBRACE)
        return PBlock(statements, start_lexeme)

    def _parse_type(self) -> PType:
        """
        Parse a type declaration, which can be either a simple type or an array type.
        Examples:
            - int
            - MyClass
            - int[]
            - MyClass[][]

        Returns:
            Union[str, PArrayType]: The parsed type (either a string for simple types
                                or PArrayType for array types)
        """
        # Parse base type first
        if not self._match(*self.type_keywords, LexemeType.IDENTIFIER):
            raise ParserError("Expected type name", self.current_lexeme)

        type_lexeme = self.lexeme_stream.advance()
        base_type = PType(type_lexeme.value, type_lexeme)

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
        is_lvalue = is_lvalue and left.node_type in (NodeType.ARRAY_ACCESS,
                                       NodeType.ATTRIBUTE,
                                       NodeType.CLASS_PROPERTY,
                                       NodeType.IDENTIFIER)

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

        #parse assignments
        if is_lvalue and not (self.current_lexeme is Lexeme.default):
            if self._match(LexemeType.OPERATOR_BINARY_ASSIGN):
                if not isinstance(left, (PDotAttribute, PIdentifier, PArrayIndexing)):
                    raise ParserError("Cannot assign to anything else than a variable or property",
                                      self.current_lexeme)
                self._expect(LexemeType.OPERATOR_BINARY_ASSIGN)
                assign_lexeme = self.current_lexeme
                left = PAssignment(left, self._parse_expression(is_lvalue=False), assign_lexeme)
            elif self._match(LexemeType.OPERATOR_BINARY_COPY):
                raise NotImplementedError("Copy Operator is not yet supported")
                if not isinstance(left, (PDotAttribute, PIdentifier)):
                    raise ParserError("Cannot assign to anything else than a variable or property", self.current_lexeme)

        return left

    def _parse_discard(self) -> PDiscard:
        """Parse an expression and discard the value"""
        discard_lexeme = self._expect(LexemeType.DISCARD)
        
        self._expect(LexemeType.OPERATOR_BINARY_ASSIGN)
        expression = self._parse_expression()
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
        expression = self._parse_primary()

        return PCast(target_type, expression)

    def _parse_primary(self, is_lvalue=True) -> PExpression:
        """Parse a primary expression (identifier, literal, parenthesized expr, cast, etc.)"""
        if self.current_lexeme is Lexeme.default:
            raise ParserError("Unexpected end of file", self.current_lexeme)

        # Handle opening parenthesis - could be cast or grouped expression
        if self._match(LexemeType.PUNCTUATION_OPENPAREN):

            # Look ahead to check if this is a type cast
            if self._peek_matches(1, *self.type_keywords, LexemeType.IDENTIFIER):
                # Possible type cast - need one more check

                # If next token is closing parenthesis, this is definitely a cast
                if self._peek_matches(2, LexemeType.PUNCTUATION_CLOSEPAREN):
                    return self._parse_cast()

            # Not a cast - parse as normal parenthesized expression
            self.lexeme_stream.advance()  # consume opening paren
            expr = self._parse_expression(is_lvalue=is_lvalue)
            self._expect(LexemeType.PUNCTUATION_CLOSEPAREN)
            return expr

        # Handle literals
        elif self._match(LexemeType.NUMBER_INT, LexemeType.NUMBER_FLOAT,
                        LexemeType.STRING_LITERAL, LexemeType.NUMBER_CHAR):
            return self._parse_literal()

        # Handle identifiers and function calls
        elif self._match(LexemeType.IDENTIFIER, LexemeType.KEYWORD_OBJECT_THIS):
            return self._parse_identifier_or_call_or_array_indexing()

        # Handle unary operators
        elif self._match(LexemeType.OPERATOR_BINARY_MINUS,
                         LexemeType.OPERATOR_UNARY_BOOL_NOT,
                         LexemeType.OPERATOR_UNARY_LOGIC_NOT,
                         LexemeType.OPERATOR_UNARY_INCREMENT,
                         LexemeType.OPERATOR_UNARY_DECREMENT):
            op_map = {
                LexemeType.OPERATOR_BINARY_MINUS:UnaryOperation.MINUS,
                LexemeType.OPERATOR_UNARY_BOOL_NOT: UnaryOperation.BOOL_NOT,
                LexemeType.OPERATOR_UNARY_INCREMENT:UnaryOperation.PRE_INCREMENT,
                LexemeType.OPERATOR_UNARY_DECREMENT: UnaryOperation.PRE_DECREMENT,
                LexemeType.OPERATOR_UNARY_LOGIC_NOT: UnaryOperation.LOGIC_NOT
            }

            op_lexeme = self.lexeme_stream.advance()
            op = op_map[op_lexeme.type]
            operand = self._parse_primary()

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

    def _parse_identifier_or_call_or_array_indexing(self) -> Union[PThis, PIdentifier, PFunctionCall, PMethodCall, PDotAttribute, PArrayIndexing]:
        """Parse an identifier and any subsequent property accesses, method calls, or function calls.

        This method handles the following patterns:
        - Simple identifier: myVar
        - Function call: myFunction()
        - Property access: myObject.property
        - Method call: myObject.method()
        - Chained access: myObject.property.subProperty.method()

        Returns:
            Union[PExpression, PIdentifier, PFunctionCall, PMethodCall, PDotAttribute]: The parsed expression

        Raises:
            ParserError: If there's an invalid token in the expression
        """
        # Parse the initial identifier
        if self._match(LexemeType.KEYWORD_OBJECT_THIS):
            expr = PThis(self._expect(LexemeType.KEYWORD_OBJECT_THIS))
        else:
            id_lexeme = self._expect(LexemeType.IDENTIFIER)
            expr = PIdentifier(id_lexeme.value, id_lexeme)
            # Check for function call first (no dot)
            if self._match(LexemeType.PUNCTUATION_OPENPAREN):
                expr = self._parse_function_arguments(expr)

        while True:
            # Check for property access or method call
            if self._match(LexemeType.OPERATOR_DOT):
                expr = self._parse_member_access(expr)

            # Handle indexing identifier
            elif self._match(LexemeType.PUNCTUATION_OPENBRACKET):
                expr = self._parse_array_indexing(expr)

            # No more chaining
            else:
                break

        return expr

    def _parse_function_arguments(self, function: PIdentifier) -> PFunctionCall:
        """Parse function call arguments.

        Args:
            function (PExpression): The function expression to be called

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
        return PFunctionCall(function, arguments, open_paren_lexeme)

    def _parse_member_access(self, left: PExpression) -> Union[PMethodCall, PDotAttribute]:
        """Parse a member access expression (either property access or method call).

        Args:
            left (PExpression): The expression before the dot operator

        Returns:
            Union[PMethodCall, PDotAttribute]: The parsed member access

        Raises:
            ParserError: If there's a syntax error in the member access
        """
        # Consume the dot
        self._expect(LexemeType.OPERATOR_DOT)

        # Get identifier after dot
        member_lexeme = self._expect(LexemeType.IDENTIFIER)
        member_identifier = PIdentifier(member_lexeme.value, member_lexeme)

        # If followed by parentheses, it's a method call
        if self._match(LexemeType.PUNCTUATION_OPENPAREN):
            return self._parse_method_call(left, member_identifier.name)

        # Otherwise it's a property access
        return PDotAttribute(left, member_identifier)

    def _parse_method_call(self, object_expr: PExpression, method_name: str) -> PMethodCall:
        """Parse a method call including its arguments.

        Args:
            object_expr (PExpression): The object expression being called on
            method_name (str): The name of the method

        Returns:
            PMethodCall: The parsed method call

        Raises:
            ParserError: If there's a syntax error in the method call
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
        return PMethodCall(object_expr, method_name, arguments, open_paren_lexeme)

    def _parse_if_statement(self, block_properties:BlockProperties) -> PIfStatement:
        """Parse an if statement"""
        if_lexeme = self._expect(LexemeType.KEYWORD_CONTROL_IF)
        self._expect(LexemeType.PUNCTUATION_OPENPAREN)
        condition = self._parse_expression()
        self._expect(LexemeType.PUNCTUATION_CLOSEPAREN)

        # Then block can be a single statement or be a {braced block}
        if self._match(LexemeType.PUNCTUATION_OPENBRACE):
            then_block = self._parse_block(block_properties)
        else:
            start_lexeme = self.current_lexeme
            then_block = self._parse_statement(block_properties)
            then_block = PBlock([then_block], start_lexeme)

        else_block = None

        if self._match(LexemeType.KEYWORD_CONTROL_ELSE):
            self.lexeme_stream.advance()
            # Then block can be a single statement or be a {braced block}
            if self._match(LexemeType.PUNCTUATION_OPENBRACE):
                else_block = self._parse_block(block_properties)
            else:
                start_lexeme = self.current_lexeme
                else_block = self._parse_statement(block_properties)
                else_block = PBlock([else_block], start_lexeme)

        return PIfStatement(condition, then_block, else_block, if_lexeme)

    def _parse_while_statement(self, block_properties:BlockProperties) -> PWhileStatement:
        """Parse a while loop statement"""
        while_lexeme = self._expect(LexemeType.KEYWORD_CONTROL_WHILE)
        self._expect(LexemeType.PUNCTUATION_OPENPAREN)
        condition = self._parse_expression()
        self._expect(LexemeType.PUNCTUATION_CLOSEPAREN)


        if self._match(LexemeType.PUNCTUATION_OPENBRACE):
            body = self._parse_block(block_properties.copy_with(self.current_lexeme, is_loop=True))
        else:
            start_lexeme = self.current_lexeme
            body = PBlock([self._parse_statement(block_properties.copy_with(start_lexeme, is_loop=True))],
                          start_lexeme)
        return PWhileStatement(condition, body, while_lexeme)

    def _parse_for_statement(self, block_properties:BlockProperties) -> PForStatement:
        """Parse a for loop statement"""
        for_lexeme = self._expect(LexemeType.KEYWORD_CONTROL_FOR)
        self._expect(LexemeType.PUNCTUATION_OPENPAREN)

        # Initialize statement (optional)
        if self._match(LexemeType.PUNCTUATION_SEMICOLON):
            initializer = PNoop(self.current_lexeme)
            self._expect(LexemeType.PUNCTUATION_SEMICOLON)
        else:
            initializer = self._parse_statement(block_properties)

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
            body = self._parse_block(block_properties.copy_with(self.current_lexeme, is_loop=True))
        else:
            start_lexeme = self.current_lexeme
            body = PBlock([self._parse_statement(block_properties)],
                          start_lexeme)

        return PForStatement(initializer, condition, increment, body, for_lexeme)

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
        self._expect(LexemeType.PUNCTUATION_OPENPAREN)
        condition = self._parse_expression()

        message = None
        if self._match(LexemeType.PUNCTUATION_COMMA):
            self.lexeme_stream.advance()
            message = self._parse_expression()

        self._expect(LexemeType.PUNCTUATION_CLOSEPAREN)
        self._expect(LexemeType.PUNCTUATION_SEMICOLON)
        return PAssertStatement(condition, message, assert_lexeme)

    def _parse_class_definition(self, block_properties:BlockProperties) -> PClass:
        """Parse a class definition"""
        class_lexeme = self._expect(LexemeType.KEYWORD_OBJECT_CLASS)
        name = self._expect(LexemeType.IDENTIFIER).value

        self._expect(LexemeType.PUNCTUATION_OPENBRACE)
        properties: List[PClassProperty] = []
        methods: List[PFunction] = []

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
                                                              block_properties.copy_with(self.current_lexeme,
                                                                                         is_class=True,
                                                                                         is_function=True,
                                                                                         return_type=type_name))
                    methods.append(method)
                else:
                    # Property
                    is_public = True  # TODO: Handle visibility modifiers
                    default_value = None
                    if self._match(LexemeType.OPERATOR_BINARY_ASSIGN):
                        self._expect(LexemeType.OPERATOR_BINARY_ASSIGN)
                        default_value = self._parse_expression(is_lvalue=False)
                    self._expect(LexemeType.PUNCTUATION_SEMICOLON)
                    properties.append(PClassProperty(member_name, type_name, is_public,
                                                     type_lexeme, default_value=default_value))
            else:
                raise ParserError("Expected class member definition", self.current_lexeme)

        self._expect(LexemeType.PUNCTUATION_CLOSEBRACE)
        return PClass(name, properties, methods, class_lexeme)

    def _parse_ternary_operation(self, condition) -> PTernaryOperation:
        """Parse a ternary operation (condition ? true_value : false_value)"""

        self._expect(LexemeType.PUNCTUATION_TERNARYCONDITIONAL_QUESTIONMARK)
        true_value = self._parse_expression()

        self._expect(LexemeType.PUNCTUATION_TERNARYSEPARATOR_COLON)
        false_value = self._parse_expression()

        return PTernaryOperation(condition, true_value, false_value, self.current_lexeme)