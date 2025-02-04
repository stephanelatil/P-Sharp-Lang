from enum import Enum, auto

class BinaryOperation(Enum):
    PLUS = '+'
    MINUS = '-'
    TIMES = '*'
    DIVIDE = '/'
    MOD = '%'
    BOOL_EQ = '=='
    BOOL_NEQ = '!='
    BOOL_GEQ = '>='
    BOOL_LEQ = '<='
    BOOL_GT = '>'
    BOOL_LT = '<'
    BOOL_AND = 'and'
    BOOL_OR = 'or'
    LOGIC_AND = '&'
    LOGIC_OR = '|'
    XOR = '^'
    SHIFT_LEFT = "<<"
    SHIFT_RIGHT = ">>"
    ASSIGN = "="
    COPY = ':='

    def __repr__(self):
        return f"\"BinaryOperation.{self.name}\""

class UnaryOperation(Enum):
    MINUS = auto()
    BOOL_NOT = auto()
    LOGIC_NOT = auto()
    POST_INCREMENT = auto()
    POST_DECREMENT = auto()
    PRE_INCREMENT = auto()
    PRE_DECREMENT = auto()

    def __repr__(self):
        return f"\"UnaryOperation.{self.name}\""

class TernaryOperator(Enum):
    QUESTIONMARK = auto()
    COLON = auto()
