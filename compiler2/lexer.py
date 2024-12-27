from enum import Enum, auto
from collections import deque
from typing import TextIO, Generator, Optional

class LexemeType(Enum):
    # Keywords
    KEYWORD_CONTROL_IF = auto()
    KEYWORD_CONTROL_ELSE = auto()
    KEYWORD_CONTROL_RETURN = auto()
    KEYWORD_CONTROL_FOR = auto()
    KEYWORD_CONTROL_WHILE = auto()
    KEYWORD_CONTROL_CONTINUE = auto()
    KEYWORD_CONTROL_BREAK = auto()
    KEYWORD_CONTROL_ASSERT = auto()
    KEYWORD_TYPE_MOD_UNSIGNED = auto()
    KEYWORD_OBJECT_CLASS = auto()
    KEYWORD_OBJECT_THIS = auto()
    KEYWORD_OBJECT_NULL = auto()
    KEYWORD_OBJECT_TRUE = auto()
    KEYWORD_OBJECT_FALSE = auto()
    KEYWORD_OBJECT_NEW = auto()
    KEYWORD_TYPE_VOID = auto()
    KEYWORD_TYPE_INT8 = auto()
    KEYWORD_TYPE_INT16 = auto()
    KEYWORD_TYPE_INT32 = auto()
    KEYWORD_TYPE_INT64 = auto()
    KEYWORD_TYPE_UINT8 = KEYWORD_TYPE_CHAR = auto()
    KEYWORD_TYPE_UINT16 = auto()
    KEYWORD_TYPE_UINT32 = auto()
    KEYWORD_TYPE_UINT64 = auto()
    KEYWORD_TYPE_STRING = auto()
    KEYWORD_TYPE_FLOAT32 = auto()
    KEYWORD_TYPE_FLOAT64 = auto()
    KEYWORD_TYPE_BOOLEAN = auto()

    # Operators
    OPERATOR_BINARY_PLUS = auto()
    OPERATOR_BINARY_MINUS = auto()
    OPERATOR_BINARY_TIMES = auto()
    OPERATOR_BINARY_DIV = auto()
    OPERATOR_BINARY_MOD = auto()
    OPERATOR_BINARY_AND = auto()
    OPERATOR_BINARY_OR = auto()
    OPERATOR_BINARY_XOR = auto()
    OPERATOR_BINARY_SHL = auto()
    OPERATOR_BINARY_SHR = auto()
    OPERATOR_BINARY_BOOL_AND = auto()
    OPERATOR_BINARY_BOOL_OR = auto()
    OPERATOR_UNARY_NOT = auto()
    OPERATOR_BINARY_BOOL_EQ = auto()
    OPERATOR_BINARY_BOOL_NEQ = auto()
    OPERATOR_BINARY_BOOL_GEQ = auto()
    OPERATOR_BINARY_BOOL_LEQ = auto()
    OPERATOR_BINARY_BOOL_GT = auto()
    OPERATOR_BINARY_BOOL_LT = auto()
    OPERATOR_BINARY_COPY = auto()
    OPERATOR_BINARY_PLUSEQ = auto()
    OPERATOR_BINARY_MINUSEQ = auto()
    OPERATOR_BINARY_TIMESEQ = auto()
    OPERATOR_BINARY_DIVEQ = auto()
    OPERATOR_BINARY_ANDEQ = auto()
    OPERATOR_BINARY_OREQ = auto()
    OPERATOR_BINARY_XOREQ = auto()
    OPERATOR_BINARY_SHLEQ = auto()
    OPERATOR_BINARY_SHREQ = auto()
    OPERATOR_BINARY_ASSIGN = auto()
    OPERATOR_DOT = auto()

    # Punctuation
    PUNCTUATION_OPENPAREN = auto()
    PUNCTUATION_CLOSEPAREN = auto()
    PUNCTUATION_OPENBRACKET = auto()
    PUNCTUATION_CLOSEBRACKET = auto()
    PUNCTUATION_OPENBRACE = auto()
    PUNCTUATION_CLOSEBRACE = auto()
    PUNCTUATION_COMMA = auto()
    PUNCTUATION_SEMICOLON = auto()
    PUNCTUATION_TERNARYCONDITIONAL_QUESTIONMARK = auto()
    PUNCTUATION_TERNARYSEPARATOR_COLON = auto()

    # Literals
    STRING_LITERAL = auto()
    NUMBER_CHAR = auto()
    NUMBER_HEX = auto()
    NUMBER_INT = auto()
    NUMBER_FLOAT = auto()
    IDENTIFIER = auto()

    # Comments
    COMMENT_SINGLELINE = auto()
    COMMENT_MULTILINE = auto()

    # Special
    WHITESPACE = auto()
    EMPTY = auto()
    EOF = auto()

class Position:
    def __init__(self, line:int = 1, column:int = 1, index:int = 0):
        self.line = line
        self.column = column
        self.index = index

    def advance(self, char:str):
        if char == '\n':
            self.line += 1
            self.column = 1
        else:
            self.column += 1
        self.index += 1

    def copy(self) -> 'Position':
        return Position(self.line, self.column, self.index)

class Lexeme:
    @staticmethod
    def _default():
        return Lexeme(LexemeType.EMPTY, '', Position(), '')
    default = _default()

    def __init__(self, type:LexemeType, value:str, pos:Position, filename:str, end_pos:Position|None=None):
        self.type = type
        self.value = value
        self.pos = pos
        self.filename = filename

    def __str__(self):
        return f"{self.type.name}({self.value}) at {self.filename}:{self.pos.line}:{self.pos.column}"

class LexerError(Exception):
    def __init__(self, message:str, start_pos:Position, filename:str, end_pos:Position|None = None):
        self.message = message
        self.pos = start_pos
        self.end_pos = end_pos or Position(start_pos.line, start_pos.column+1, start_pos.index+1)
        self.filename = filename
        super().__init__(f"{message} at {filename}:{start_pos.line}:{start_pos.column}")

class CharacterStream:
    def __init__(self, file:TextIO):
        self.file = file
        self.buffer = deque()
        self.pos = Position()
        self.eof = False

    def peek(self) -> Optional[str]:
        if self.eof:
            return None

        if not self.buffer:
            char = self.file.read(1)
            if not char:
                self.eof = True
                return None
            self.buffer.append(char)

        return self.buffer[0]

    def advance(self) -> str:
        char = self.peek()
        if char is not None:
            self.buffer.popleft()
            self.pos.advance(char)
        if char is None:
            raise EOFError()
        return char

    def position(self) -> Position:
        return self.pos.copy()

class Lexer:
    def __init__(self, filename:str, file:TextIO):
        self.filename = filename
        self.stream = CharacterStream(file)
        self.keywords = {
            'if':LexemeType.KEYWORD_CONTROL_IF,
            'else':LexemeType.KEYWORD_CONTROL_ELSE,
            'return':LexemeType.KEYWORD_CONTROL_RETURN,
            'for':LexemeType.KEYWORD_CONTROL_FOR,
            'while':LexemeType.KEYWORD_CONTROL_WHILE,
            'continue':LexemeType.KEYWORD_CONTROL_CONTINUE,
            'break':LexemeType.KEYWORD_CONTROL_BREAK,
            'assert':LexemeType.KEYWORD_CONTROL_ASSERT,
            'unsigned':LexemeType.KEYWORD_TYPE_MOD_UNSIGNED,
            'class':LexemeType.KEYWORD_OBJECT_CLASS,
            'this':LexemeType.KEYWORD_OBJECT_THIS,
            'null':LexemeType.KEYWORD_OBJECT_NULL,
            'true':LexemeType.KEYWORD_OBJECT_TRUE,
            'false':LexemeType.KEYWORD_OBJECT_FALSE,
            'new':LexemeType.KEYWORD_OBJECT_NEW,
            'void':LexemeType.KEYWORD_TYPE_VOID,
            'i8':LexemeType.KEYWORD_TYPE_INT8,
            'i16':LexemeType.KEYWORD_TYPE_INT16,
            'i32':LexemeType.KEYWORD_TYPE_INT32,
            'i64':LexemeType.KEYWORD_TYPE_INT64,
            'string':LexemeType.KEYWORD_TYPE_STRING,
            'f32':LexemeType.KEYWORD_TYPE_FLOAT32,
            'f64':LexemeType.KEYWORD_TYPE_FLOAT64,
            'char':LexemeType.KEYWORD_TYPE_CHAR,
            'bool':LexemeType.KEYWORD_TYPE_BOOLEAN,
        }

    def lex(self) -> Generator[Lexeme, None, None]:
        while True:
            lexeme = self._next_lexeme()
            if lexeme.type == LexemeType.EOF:
                break
            if lexeme.type not in (LexemeType.WHITESPACE, LexemeType.COMMENT_SINGLELINE, LexemeType.COMMENT_MULTILINE):
                yield lexeme

    def _next_lexeme(self) -> Lexeme:
        char = self.stream.peek()

        # Handle EOF
        if char is None:
            return Lexeme(LexemeType.EOF, "", self.stream.position(), self.filename)

        # Handle whitespace
        if char.isspace():
            return self._lex_whitespace()

        # Handle comments
        if char == '/':
            return self._lex_comment_or_division()

        # Handle identifiers and keywords
        if char.isalpha() or char == '_':
            return self._lex_identifier()

        # Handle numbers
        if char.isdigit():
            return self._lex_number()

        # Handle strings
        if char == '"':
            return self._lex_string()

        # Handle character literals
        if char == "'":
            return self._lex_char()

        # Handle operators and punctuation
        return self._lex_operator()

    def _lex_whitespace(self) -> Lexeme:
        start_pos = self.stream.position()
        value = ""

        while (char := self.stream.peek()) and char.isspace():
            value += self.stream.advance()

        return Lexeme(LexemeType.WHITESPACE, value, start_pos, self.filename, self.stream.position())

    def _lex_comment_or_division(self) -> Lexeme:
        start_pos = self.stream.position()
        self.stream.advance()  # Consume '/'

        next_char = self.stream.peek()
        if next_char == '/': # Single-line comment
            value = '//'
            self.stream.advance()

            while (char := self.stream.peek()) and char != '\n':
                value += self.stream.advance()

            return Lexeme(LexemeType.COMMENT_SINGLELINE, value, start_pos, self.filename, self.stream.position())

        elif next_char == '*': # Multi-line comment
            value = '/*'
            self.stream.advance()

            while True:
                char = self.stream.peek()
                if char is None:
                    raise LexerError("Unterminated multi-line comment", start_pos, self.filename, self.stream.position())

                value += self.stream.advance()
                if char == '*' and self.stream.peek() == '/':
                    self.stream.advance()
                    value = value[:-1]+"*/"
                    break

            return Lexeme(LexemeType.COMMENT_MULTILINE, value, start_pos, self.filename, self.stream.position())

        else: # Division operator
            return Lexeme(LexemeType.OPERATOR_BINARY_DIV, "/", start_pos, self.filename, self.stream.position())

    def _lex_identifier(self) -> Lexeme:
        start_pos = self.stream.position()
        value = ""

        while (char := self.stream.peek()) and (char.isalnum() or char == '_'):
            value += self.stream.advance()

        if value in self.keywords:
            return Lexeme(self.keywords[value], value, start_pos, self.filename, self.stream.position())

        if value.startswith("PS_GC__"):
            raise LexerError("Identifiers cannot start with PS_GC__", start_pos, self.filename, self.stream.position())

        if value.startswith("__"):
            raise LexerError("Identifiers cannot start with double underscore", start_pos, self.filename, self.stream.position())

        return Lexeme(LexemeType.IDENTIFIER, value, start_pos, self.filename, self.stream.position())

    def _lex_number(self) -> Lexeme:
        start_pos = self.stream.position()
        value = ""

        # Handle hex numbers
        if self.stream.peek() == '0' and (next_char := self._peek_next()) and next_char.lower() == 'x':
            value += self.stream.advance() # '0'
            value += self.stream.advance() # 'x'

            has_digit = False
            while (char := self.stream.peek()) and (char.isdigit() or char.lower() in 'abcdef' or char == '_'):
                value += self.stream.advance()
                if char != '_':
                    has_digit = True

            if not has_digit:
                raise LexerError("Invalid hex number", start_pos, self.filename)

            return Lexeme(LexemeType.NUMBER_HEX, value, start_pos, self.filename)

        # Handle regular numbers
        is_float = False
        has_digit = False

        while (char := self.stream.peek()):
            if char.isdigit():
                value += self.stream.advance()
                has_digit = True
            elif char == '_' and has_digit:
                value += self.stream.advance()
            elif char == '.' and not is_float and has_digit:
                value += self.stream.advance()
                is_float = True
                has_digit = False
            elif char.lower() == 'e' and has_digit:
                value += self.stream.advance()
                if (next_char := self.stream.peek()) and next_char in '+-':
                    value += self.stream.advance()
                has_digit = False
            else:
                break

        if not has_digit:
            raise LexerError("Invalid number format", start_pos, self.filename)

        return Lexeme(
            LexemeType.NUMBER_FLOAT if is_float else LexemeType.NUMBER_INT,
            value,
            start_pos,
            self.filename
        )

    def _lex_string(self) -> Lexeme:
        start_pos = self.stream.position()
        value = self.stream.advance()  # Opening quote

        while True:
            char = self.stream.peek()
            if char is None:
                raise LexerError("Unterminated string", start_pos, self.filename)

            value += self.stream.advance()

            if char == '"' and value[-2] != '\\':
                break

        return Lexeme(LexemeType.STRING_LITERAL, value, start_pos, self.filename)

    def _lex_char(self) -> Lexeme:
        start_pos = self.stream.position()
        value = self.stream.advance()  # Opening quote

        char = self.stream.peek()
        if char is None:
            raise LexerError("Unterminated character literal", start_pos, self.filename)

        if char == '\\': # Handle escape sequences
            value += self.stream.advance()
            char = self.stream.peek()
            if char is None:
                raise LexerError("Unterminated character literal", start_pos, self.filename)
            if char == 'x': # Handle hex escape sequence
                value += self.stream.advance()  # 'x'
                for _ in range(2): # Expect exactly 2 hex digits
                    char = self.stream.peek()
                    if char is None or not (char.isdigit() or char.lower() in 'abcdef'):
                        raise LexerError("Invalid hex escape sequence in character literal", start_pos, self.filename)
                    value += self.stream.advance()
            else: # Handle other escape sequences
                value += self.stream.advance()
        else:
            value += self.stream.advance()

        # Expect closing quote
        char = self.stream.peek()
        if char != "'":
            raise LexerError("Unterminated character literal", start_pos, self.filename)
        value += self.stream.advance()

        return Lexeme(LexemeType.NUMBER_CHAR, value, start_pos, self.filename)

    def _lex_operator(self) -> Lexeme:
        start_pos = self.stream.position()
        char = self.stream.advance()

        # Build operator lookup table
        operators = {
            # Single character operators
            '+':LexemeType.OPERATOR_BINARY_PLUS,
            '-':LexemeType.OPERATOR_BINARY_MINUS,
            '*':LexemeType.OPERATOR_BINARY_TIMES,
            '%':LexemeType.OPERATOR_BINARY_MOD,
            '&':LexemeType.OPERATOR_BINARY_AND,
            '|':LexemeType.OPERATOR_BINARY_OR,
            '^':LexemeType.OPERATOR_BINARY_XOR,
            '.':LexemeType.OPERATOR_DOT,

            # Punctuation
            '(':LexemeType.PUNCTUATION_OPENPAREN,
            ')':LexemeType.PUNCTUATION_CLOSEPAREN,
            '[':LexemeType.PUNCTUATION_OPENBRACKET,
            ']':LexemeType.PUNCTUATION_CLOSEBRACKET,
            '{':LexemeType.PUNCTUATION_OPENBRACE,
            '}':LexemeType.PUNCTUATION_CLOSEBRACE,
            ',':LexemeType.PUNCTUATION_COMMA,
            ';':LexemeType.PUNCTUATION_SEMICOLON,
            '?':LexemeType.PUNCTUATION_TERNARYCONDITIONAL_QUESTIONMARK,
            ':':LexemeType.PUNCTUATION_TERNARYSEPARATOR_COLON,
        }

        # Multi-character operator combinations
        next_char = self.stream.peek()
        if next_char:
            two_char = char + next_char
            if two_char in ('+=', '-=', '*=', '/=', '&=', '|=', '^=', '==', '!=', '>=', '<=', ':=', '&&', '||', '<<', '>>'):
                self.stream.advance()

                # Handle three character operators
                if two_char in ('<<', '>>'):
                    if (third_char := self.stream.peek()) and third_char == '=':
                        self.stream.advance()
                        return Lexeme(
                            LexemeType.OPERATOR_BINARY_SHLEQ if two_char == '<<' else LexemeType.OPERATOR_BINARY_SHREQ,
                            two_char + '=',
                            start_pos,
                            self.filename
                        )
                    return Lexeme(
                        LexemeType.OPERATOR_BINARY_SHL if two_char == '<<' else LexemeType.OPERATOR_BINARY_SHR,
                        two_char,
                        start_pos,
                        self.filename
                    )

                # Map two character operators to types
                two_char_types = {
                    '+=':LexemeType.OPERATOR_BINARY_PLUSEQ,
                    '-=':LexemeType.OPERATOR_BINARY_MINUSEQ,
                    '*=':LexemeType.OPERATOR_BINARY_TIMESEQ,
                    '/=':LexemeType.OPERATOR_BINARY_DIVEQ,
                    '&=':LexemeType.OPERATOR_BINARY_ANDEQ,
                    '|=':LexemeType.OPERATOR_BINARY_OREQ,
                    '^=':LexemeType.OPERATOR_BINARY_XOREQ,
                    '==':LexemeType.OPERATOR_BINARY_BOOL_EQ,
                    '!=':LexemeType.OPERATOR_BINARY_BOOL_NEQ,
                    '>=':LexemeType.OPERATOR_BINARY_BOOL_GEQ,
                    '<=':LexemeType.OPERATOR_BINARY_BOOL_LEQ,
                    ':=':LexemeType.OPERATOR_BINARY_COPY,
                    '&&':LexemeType.OPERATOR_BINARY_BOOL_AND,
                    '||':LexemeType.OPERATOR_BINARY_BOOL_OR,
                }
                return Lexeme(two_char_types[two_char], two_char, start_pos, self.filename)

        # Handle single character operators and punctuation
        if char == '=':
            return Lexeme(LexemeType.OPERATOR_BINARY_ASSIGN, char, start_pos, self.filename)
        elif char == '>':
            return Lexeme(LexemeType.OPERATOR_BINARY_BOOL_GT, char, start_pos, self.filename)
        elif char == '<':
            return Lexeme(LexemeType.OPERATOR_BINARY_BOOL_LT, char, start_pos, self.filename)
        elif char == '!':
            return Lexeme(LexemeType.OPERATOR_UNARY_NOT, char, start_pos, self.filename)

        # Handle other single character operators from the lookup table
        if char in operators:
            return Lexeme(operators[char], char, start_pos, self.filename)

        raise LexerError(f"Invalid character:{char}", start_pos, self.filename)

    def _peek_next(self) -> Optional[str]:
        """Helper method to peek at the second character without advancing"""
        current = self.stream.peek()
        if current is not None:
            save_pos = self.stream.position()
            self.stream.advance()
            next_char = self.stream.peek()
            # Reset position
            self.stream.pos = save_pos
            self.stream.buffer = [current]
            return next_char
        return None