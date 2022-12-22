from enum import Enum

class BinaryOperation(Enum):
    PLUS = '+'
    MINUS = '-'
    TIMES = '*'
    DIVIDE = '/'
    MOD = '%'
    BOOL_AND = "and"
    BOOL_OR = "or"
    LOGIC_AND = "&"
    LOGIC_OR = "|"
    LOGIC_XOR = "^"

class UnaryOperation(Enum):
    MINUS = '-'
    LOGIC_NOT = "!"
