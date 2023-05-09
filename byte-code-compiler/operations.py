from enum import Enum

class BinaryOperation(Enum):
    PLUS = '+'
    MINUS = '-'
    TIMES = '*'
    DIVIDE = '/'
    MOD = '%'
    BOOL_EQ = "=="
    BOOL_NEQ = "!="
    BOOL_GEQ = ">="
    BOOL_LEQ = "<="
    BOOL_GT = ">"
    BOOL_LT = "<"
    BOOL_AND = "and"
    BOOL_OR = "or"
    LOGIC_AND = "&"
    LOGIC_OR = "|"
    LOGIC_XOR = "^"
    SHIFT_LEFT = "<<"
    SHIFT_RIGHT = ">>"
    ASSIGN="assign"
    COPY="copy"

    def __repr__(self):
        return f"\"BinaryOperation.{self.name}\""

class UnaryOperation(Enum):
    MINUS = '-'
    LOGIC_NOT = "not"
    INCREMENT = "++"
    DECREMENT = "--"

    def __repr__(self):
        return f"\"UnaryOperation.{self.name}\""
    