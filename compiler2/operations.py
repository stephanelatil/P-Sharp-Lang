from enum import Enum, auto

class BinaryOperation(Enum):
    PLUS = auto()
    MINUS = auto()
    TIMES = auto()
    DIVIDE = auto()
    MOD = auto()
    BOOL_EQ = auto()
    BOOL_NEQ = auto()
    BOOL_GEQ = auto()
    BOOL_LEQ = auto()
    BOOL_GT = auto()
    BOOL_LT = auto()
    BOOL_AND = auto()
    BOOL_OR = auto()
    LOGIC_AND = auto()
    LOGIC_OR = auto()
    XOR = auto()
    SHIFT_LEFT = auto()
    SHIFT_RIGHT = auto()
    ASSIGN = auto()
    COPY = auto()

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
