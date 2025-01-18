from enum import Enum, auto
from collections import deque
from typing import TextIO, Generator, Optional, Union

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
    KEYWORD_TYPE_FLOAT16 = auto()
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
    OPERATOR_UNARY_LOGIC_NOT = auto()
    OPERATOR_UNARY_BOOL_NOT = auto()
    OPERATOR_UNARY_INCREMENT = auto()
    OPERATOR_UNARY_DECREMENT = auto()
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
    DISCARD = auto()

    # Comments
    COMMENT_SINGLELINE = auto()
    COMMENT_MULTILINE = auto()

    # Special
    WHITESPACE = auto()
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

    def __add__(self, num_chars:int):
        return Position(self.line, self.column+num_chars, self.index+num_chars)
    
    def __str__(self):
        return f"line {self.line}, column {self.column}"

class Lexeme:
    @staticmethod
    def _default():
        return Lexeme(LexemeType.EOF, '', Position(), '')

    default:'Lexeme'

    def __init__(self, type:LexemeType, value:str, pos:Position, filename:str, end_pos:Position|None=None):
        self.type = type
        self.value = value
        self.pos = pos
        self.filename = filename
        self.end_pos = pos + len(value)

    def __str__(self):
        return f"{self.type.name}({self.value}) at {self.filename}:{self.pos.line}:{self.pos.column}"

    def __repr__(self) -> str:
        return str(self)

Lexeme.default = Lexeme._default()

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

    def peek(self, amount=0) -> Optional[str]:
        if self.eof and len(self.buffer) == 0:
            return None

        while len(self.buffer) <= amount:
            char = self.file.read(1)
            if not char:
                self.eof = True
                return None
            self.buffer.append(char)

        return self.buffer[amount]

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

class LexemeStream:
    def __init__(self, lexmes:Generator[Lexeme, None, None]):
        self.lexeme_gen = lexmes
        self.buffer = deque()
        self.pos = Position()
        self.eof = False

    def peek(self, amount=0) -> Lexeme:
        if self.eof and len(self.buffer) == 0:
            return Lexeme.default

        while len(self.buffer) <= amount:
            lexeme = next(self.lexeme_gen, None)
            if not lexeme:
                self.eof = True
                return Lexeme.default
            self.buffer.append(lexeme)

        return self.buffer[amount]

    def advance(self) -> Lexeme:
        lexeme = self.peek()
        if lexeme is not None:
            self.buffer.popleft()
            self.pos = lexeme.pos
        if lexeme is None:
            raise EOFError()
        return lexeme

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
            'char':LexemeType.KEYWORD_TYPE_CHAR,
            'u8':LexemeType.KEYWORD_TYPE_INT8,
            'u16':LexemeType.KEYWORD_TYPE_INT16,
            'u32':LexemeType.KEYWORD_TYPE_INT32,
            'u64':LexemeType.KEYWORD_TYPE_INT64,
            'string':LexemeType.KEYWORD_TYPE_STRING,
            'f16':LexemeType.KEYWORD_TYPE_FLOAT16,
            'f32':LexemeType.KEYWORD_TYPE_FLOAT32,
            'f64':LexemeType.KEYWORD_TYPE_FLOAT64,
            'char':LexemeType.KEYWORD_TYPE_CHAR,
            'bool':LexemeType.KEYWORD_TYPE_BOOLEAN,
            'and':LexemeType.OPERATOR_BINARY_BOOL_AND,
            'or':LexemeType.OPERATOR_BINARY_BOOL_OR,
            'not':LexemeType.OPERATOR_UNARY_BOOL_NOT,
            '_':LexemeType.DISCARD
        }

        # Build operator lookup table
        self.operators = {
            # Single character operators
            '+':LexemeType.OPERATOR_BINARY_PLUS,
            '-':LexemeType.OPERATOR_BINARY_MINUS,
            '/':LexemeType.OPERATOR_BINARY_DIV,
            '*':LexemeType.OPERATOR_BINARY_TIMES,
            '%':LexemeType.OPERATOR_BINARY_MOD,
            '&':LexemeType.OPERATOR_BINARY_AND,
            '|':LexemeType.OPERATOR_BINARY_OR,
            '^':LexemeType.OPERATOR_BINARY_XOR,
            '.':LexemeType.OPERATOR_DOT,
            '=':LexemeType.OPERATOR_BINARY_ASSIGN,
            '<':LexemeType.OPERATOR_BINARY_BOOL_LT,
            '>':LexemeType.OPERATOR_BINARY_BOOL_GT,
            '!':LexemeType.OPERATOR_UNARY_LOGIC_NOT,

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

    def lex(self, include_comments=False) -> Generator[Lexeme, None, None]:
        if include_comments:
            skip = (LexemeType.WHITESPACE,)
        else:
            skip = (LexemeType.WHITESPACE, LexemeType.COMMENT_SINGLELINE, LexemeType.COMMENT_MULTILINE)
        while True:
            lexeme = self._next_lexeme()
            if lexeme.type == LexemeType.EOF:
                break
            if lexeme.type not in skip:
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
            comment = self._try_lex_comment()
            if not comment is Lexeme.default:
                return comment
            #if it's not a comment, it's probably an operator

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

    def _try_lex_comment(self) -> Lexeme:
        start_pos = self.stream.position()

        next_char = self.stream.peek(1)
        if next_char == '/': # Single-line comment
            value = '//'
            self.stream.advance()
            self.stream.advance()

            while (char := self.stream.peek()) and char != '\n':
                value += self.stream.advance()

            return Lexeme(LexemeType.COMMENT_SINGLELINE, value, start_pos, self.filename, self.stream.position())

        elif next_char == '*': # Multi-line comment
            value = '/*'
            self.stream.advance()
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

        else: # it's an operator
            return Lexeme.default

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
        if self.stream.peek() == '0' and (next_char := self.stream.peek(1)) and next_char.lower() == 'x':
            value += self.stream.advance() # '0'
            value += self.stream.advance() # 'x'

            has_digit = False
            while (char := self.stream.peek()) and (char.isdigit() or char.lower() in 'abcdef' or char == '_'):
                if self.stream.peek() == '_':
                    self.stream.advance()
                    continue
                value += self.stream.advance()
                has_digit = True

            if not has_digit:
                raise LexerError("Invalid hex number", start_pos, self.filename)

            return Lexeme(LexemeType.NUMBER_HEX, value, start_pos, self.filename)

        # Handle regular numbers
        is_float = False
        has_digit = False #whether the last char in the current value is a digit

        while (char := self.stream.peek()):
            if char.isdigit():
                value += self.stream.advance()
                has_digit = True
            elif char == '_':
                self.stream.advance() #ignore underscores
            elif char == '.':
                if is_float or not has_digit:
                    raise LexerError("Invalid number format", start_pos, self.filename, start_pos+len(value)+1)
                value += self.stream.advance()
                is_float = True
                has_digit = False
            elif char.lower() == 'e' and has_digit:
                value += self.stream.advance()
                next_char = self.stream.peek()
                if next_char == '-':
                    value += self.stream.advance()
                elif next_char == '+':
                    self.stream.advance()
                is_float = True
                has_digit = False
            elif char in self.operators.keys() or char.isspace():
                break
                #stop parsing number if detects non-num value
            else:
                raise LexerError("Invalid number format", start_pos, self.filename, start_pos+len(value))

        # allow numbers to end with a period to auto-cast to float
        if value[-1] == '.':
            has_digit = True

        if not has_digit:
            raise LexerError("Invalid number format", start_pos, self.filename, start_pos+len(value))

        return Lexeme(
            LexemeType.NUMBER_FLOAT if is_float else LexemeType.NUMBER_INT,
            value,
            start_pos,
            self.filename
        )

    def _lex_string(self) -> Lexeme:
        """Parse a string literal with proper escape sequence handling.

        Valid escape sequences:
        - \\n - newline
        - \\r - carriage return
        - \\t - tab
        - \\\\ - backslash
        - \\" - double quote
        - \\' - single quote
        - \\b - backspace
        - \\f - form feed
        - \\0 - null character
        - \\xhh - hex escape (exactly 2 hex digits)

        Returns:
            Lexeme: A STRING_LITERAL lexeme containing the parsed string

        Raises:
            LexerError: If string is unterminated or contains invalid escape sequences
        """
        start_pos = self.stream.position()
        value = self.stream.advance()  # Opening quote

        # Map of valid simple escape sequences
        valid_escapes = {
            'n': '\n',
            'r': '\r',
            't': '\t',
            '\\': '\\',
            '"': '"',
            "'": "'",
            'b': '\b',
            'f': '\f',
            'v': '\v',
            '0': '\0'
        }

        while True:
            char = self.stream.peek()

            if char is None or char == '\n':
                raise LexerError("Unterminated string literal", start_pos, self.filename, self.stream.position())

            # Handle escape sequences
            if char == '\\':
                escape_start = self.stream.position()
                value += self.stream.advance()  # Add the backslash

                next_char = self.stream.peek()
                if next_char is None:
                    raise LexerError("Unterminated escape sequence", escape_start, self.filename, self.stream.position())

                # Handle hex escape sequence
                if next_char == 'x':
                    value += self.stream.advance()  # Add 'x'
                    hex_digits = ''

                    # Read exactly 2 hex digits
                    for _ in range(2):
                        digit = self.stream.peek()
                        if digit is None or not (digit.isdigit() or digit.lower() in 'abcdef'):
                            raise LexerError(
                                "Invalid hex escape sequence - must be exactly 2 hex digits",
                                escape_start,
                                self.filename,
                                self.stream.position()
                            )
                        hex_digits += self.stream.advance()
                    value += hex_digits
                    continue

                # Handle simple escape sequences
                if next_char not in valid_escapes:
                    raise LexerError(
                        f"Invalid escape sequence '\\{next_char}'",
                        escape_start,
                        self.filename,
                        self.stream.position() + 1
                    )

                value += self.stream.advance()
                continue

            # Handle string termination
            if char == '"':
                value += self.stream.advance()
                break

            # Add regular character
            value += self.stream.advance()

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

        # Map two character operators to types
        two_char_types = {
            '+=':LexemeType.OPERATOR_BINARY_PLUSEQ,
            '-=':LexemeType.OPERATOR_BINARY_MINUSEQ,
            '++':LexemeType.OPERATOR_UNARY_INCREMENT,
            '--':LexemeType.OPERATOR_UNARY_DECREMENT,
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
            '<<':LexemeType.OPERATOR_BINARY_SHL,
            '>>':LexemeType.OPERATOR_BINARY_SHR,
        }

        # Multi-character operator combinations
        next_char = self.stream.peek()
        if next_char:
            two_char = char + next_char
            if two_char in two_char_types.keys():
                self.stream.advance()

                # Handle three character operators
                if two_char in ('<<', '>>'):
                    third_char = self.stream.peek()
                    if third_char == '=':
                        self.stream.advance()
                        return Lexeme(
                            LexemeType.OPERATOR_BINARY_SHLEQ if two_char == '<<' else LexemeType.OPERATOR_BINARY_SHREQ,
                            two_char + '=',
                            start_pos,
                            self.filename,
                            end_pos=start_pos+3
                        )
                    return Lexeme(
                        LexemeType.OPERATOR_BINARY_SHL if two_char == '<<' else LexemeType.OPERATOR_BINARY_SHR,
                        two_char,
                        start_pos,
                        self.filename,
                        start_pos+2
                    )

                return Lexeme(two_char_types[two_char], two_char, start_pos, self.filename)

        # Handle other single character operators from the lookup table
        if char in self.operators:
            return Lexeme(self.operators[char], char, start_pos, self.filename)

        raise LexerError(f"Invalid character:{char}", start_pos, self.filename)
