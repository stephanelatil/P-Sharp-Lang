import ply.yacc as yacc
from ply.yacc import YaccProduction
from lexer import tokens
from operations import BinaryOperation, UnaryOperation
from copy import deepcopy


class Location:
    """Track the location of a token in the code"""

    def __init__(self, lineno, col) -> None:
        self.line = str(lineno)
        self.col = str(col)

    def __str__(self) -> str:
        return f"Line {' '*(5-len(self.line))+self.line} " +\
            f"and column {' '*(5-len(self.col))+self.col}"

    def __repr__(self) -> str:
        return '"'+str(self)+'"'

# P.... classes are there to build the abstract syntax tree


class PTreeElem:
    def __init__(self, location) -> None:
        self.location = location

    def __repr__(self):
        return self.__class__.__name__+f"({self.__dict__})"


class PIdentifier(PTreeElem):
    def __init__(self, location, identifier):
        self.identifier = identifier
        super().__init__(location)


class PType(PTreeElem):
    def __init__(self, location, typ: str) -> None:
        self.typ = typ
        super().__init__(location)


class PArray(PType):
    def __init__(self, location, arrType: PType) -> None:
        super().__init__(arrType)


class PScope(PTreeElem):
    def __init__(self, location, *, functions=None, varDecl=None, statements=None):
        self.funcDecl = functions
        self.varDecl = varDecl
        self.statements = statements
        super().__init__(location)


class PModule(PScope):
    def __init__(self, location, *, functions=None, varDecl=None, classDecl=None, statements=None):
        self.classDecl = classDecl
        super().__init__(location, functions=functions,
                         varDecl=varDecl, statements=statements)


class PClassDecl(PScope):
    def __init__(self, location, identifier, inner_scope, parentClassId=None, interfaces=None):
        self.identifier = identifier
        self.inner_scope = inner_scope
        super().__init__(location)
        # no inheritance yet


class PStatement(PTreeElem):
    def __init__(self, location):
        super().__init__(location)


class PExpression(PStatement):
    def __init__(self, location, rvalue):
        self.rvalue = rvalue
        super().__init__(location)


class PEnum(PScope):
    def __init__(self, location, identifier, values: list[PStatement]):
        self.identifier = identifier
        self.enum_values = values
        super().__init__(statements=values)


class PVarDecl(PTreeElem):
    def __init__(self, location, typ: PType, id: PIdentifier):
        self.typ = typ
        self.id = id
        super().__init__(location)


class PFuncDecl(PTreeElem):
    def __init__(self, location, returnType: PType, id: PIdentifier, args: list[PVarDecl], body: PScope):
        self.returnType = returnType
        self.id = id
        self.args = args
        self.body = body
        super().__init__(location)


class PlValue(PExpression):
    def __init__(self, location, rvalue):
        super().__init__(location, rvalue)


class PType(PTreeElem):
    def __init__(self, location, type_identifier):
        self.type_identifier = type_identifier
        super().__init__(location)


class PUType(PType):
    def __init__(self, location, type_identifier):
        super().__init__(location, type_identifier)


class PNumeric(PExpression):
    def __init__(self, location, value):
        if isinstance(value, float):
            self.typ = "float"
        else:
            self.typ = "int"
        super().__init__(location, value)


class PIndex(PExpression):
    """for indexing : array[idx]"""

    def __init__(self, location, array: PExpression, idx: PExpression):
        if location is None:
            location = idx.location
        self.index = idx.rvalue
        super().__init__(location, array)


class PDot(PlValue):
    def __init__(self, location, left, right):
        self.left = left
        super().__init__(location, rvalue=right)


class PBinOp(PExpression):
    def __init__(self, location, left: PExpression, op: BinaryOperation, right: PExpression):
        self.left = left
        self.op = op
        super().__init__(location, right)


class PAssign(PBinOp):
    def __init__(self, location, lvalue: PlValue, rvalue: PExpression):
        super().__init__(location, left=lvalue, right=rvalue, op=None)


class PCopyAssign(PBinOp):
    def __init__(self, location, lvalue: PlValue, rvalue: PExpression):
        super().__init__(location, left=lvalue, right=rvalue, op=None)


class PUnOp(PExpression):
    def __init__(self, location, op: UnaryOperation, right: PExpression):
        self.op = op
        super().__init__(location, right)


class PCall(PExpression):
    def __init__(self, location, id: PIdentifier, args=list[PExpression]):
        self.id = id
        self.args = args
        super().__init__(location, id)


class PSkip(PStatement):
    def __init__(self, location):
        super().__init__(location)
        # do nothing empty block

class PReturn(PStatement):
    def __init__(self, location, returnVal: PExpression):
        self.returnVal = returnVal
        super().__init__(location)

class PAssert(PStatement):
    def __init__(self, location, assertExpr: PExpression):
        self.assertExpr = assertExpr
        super().__init__(location)

class PString(PExpression):
    def __init__(self, location, value: str):
        super().__init__(location, value)


class PContinue(PStatement):
    def __init__(self, location):
        super().__init__(location)


class PBreak(PStatement):
    def __init__(self, location):
        super().__init__(location)


class PIf(PStatement):
    def __init__(self, location, condition: PExpression, if_true: PScope, if_false: PScope = None):
        self.condition = condition
        self.if_true = if_true
        self.if_false = if_false
        super().__init__(location)


class PTernary(PStatement):
    def __init__(self, location, condition: PExpression, if_true: PReturn, if_false: PReturn):
        self.condition = condition
        self.if_true = if_true
        self.if_false = if_false
        super().__init__(location)


class PWhile(PStatement):
    def __init__(self, location, condition: PExpression, bloc: PScope):
        self.condition = condition
        self.bloc = bloc
        super().__init__(location)


class PFor(PStatement):
    def __init__(self, location, init: PStatement, condition: PExpression, postExpr: PStatement, bloc: PScope):
        self.init = init
        self.condition = condition
        self.postExpr = postExpr
        self.bloc = bloc
        super().__init__(location)


class PForeach(PStatement):
    def __init__(self, location, varDecl: PVarDecl, iterable: PIdentifier, bloc: PScope):
        self.varDecl = varDecl
        self.iterable = iterable
        self.bloc = bloc
        super().__init__(location)


class PImport(PStatement):
    def __init__(self, location, module: PIdentifier, item: PIdentifier):
        self.module = module
        self.item = item
        super().__init__(location)


# p_..... functions are for building the grammar

precedence = (
    ('nonassoc',
     'Operator_Binary_Bool_Eq',
     'Operator_Binary_Bool_Neq',
     'Operator_Binary_Bool_Geq',
     'Operator_Binary_Bool_Leq',
     'Operator_Binary_Bool_Gt',
     'Operator_Binary_Bool_Lt'),  # Nonassociative operators
    ('left', 'Operator_Binary_PlusEq', 'Operator_Binary_MinusEq',
        'Operator_Binary_TimesEq', 'Operator_Binary_DivEq',
        'Operator_Binary_AndEq', 'Operator_Binary_OrEq',
        'Operator_Binary_XorEq', 'Operator_Binary_ShlEq',
        'Operator_Binary_ShrEq'),
    ('left', 'Operator_Binary_Mod', 'Operator_Binary_And',
        'Operator_Binary_Or', 'Operator_Binary_Xor', 'Operator_Binary_Shl',
     'Operator_Binary_Shr'),
    ('left', 'Operator_Binary_Plus', 'Operator_Minus'),
    ('left', 'Operator_Binary_Times', 'Operator_Binary_Div'),
    ('right', 'UMINUS'),            # Unary minus operator
    ('right', 'UNOT'),            # Unary not operator
    ('right', 'UDEC'),            # Unary dec operator
    ('right', 'UINC')            # Unary inc operator
)

start = 'Module'


def p_module(p: YaccProduction):
    """Module : GlobalStatementList"""
    p[0] = deepcopy(p[1])


def p_statement(p: YaccProduction):
    """Statement : VarDecl
                 | VarAssign
                 | FuncDecl
                 | FuncCall
                 | IfBloc
                 | ForBloc
                 | WhileBloc
                 | Scope
                 | Return
                 | Break
                 | Continue
                 | ignore"""
    loc = Location(p.lineno(1), p.lexspan(1)[0])
    if p[1] is None:
        p[0] = PSkip(loc)
    else:
        p[0] = p[1]


def p_scope(p: YaccProduction):
    """Scope : Punctuation_OpenBrace StatementList Punctuation_CloseBrace"""
    p[0] = p[2]


def p_all_statements_statement(p: YaccProduction):
    """GlobalStatementList : StatementList"""
    loc = Location(p.lineno(1), p.lexspan(1)[0])
    p[0] = PModule(loc, functions=deepcopy(p[1].funcDecl), varDecl=deepcopy(
        p[1].varDecl), classDecl=[], statements=deepcopy(p[1].statements))


def p_all_statements_classDecl(p: YaccProduction):
    """GlobalStatementList : ClassDecl"""
    loc = Location(p.lineno(1), p.lexspan(1)[0])
    p[0] = PModule(loc, functions=[], varDecl=[],
                   classDecl=[p[1]], statements=[])

def p_all_statements_addStatement(p: YaccProduction):
    """GlobalStatementList : Statement GlobalStatementList"""
    loc = Location(p.lineno(1), p.lexspan(1)[0])
    if isinstance(p[1], PVarDecl):
        p[0] = PModule(loc, functions=deepcopy(p[2].funcDecl), varDecl=[p[1]]+deepcopy(
            p[2].varDecl), classDecl=deepcopy(p[2].classDecl), statements=deepcopy(p[2].statements))
    elif isinstance(p[1], PFuncDecl):
        p[0] = PModule(loc, functions=[p[1]]+deepcopy(p[2].funcDecl), varDecl=deepcopy(
            p[2].varDecl), classDecl=deepcopy(p[2].classDecl), statements=deepcopy(p[2].statements))
    else:
        p[0] = PModule(loc, functions=deepcopy(p[2].funcDecl), varDecl=deepcopy(
            p[2].varDecl), classDecl=deepcopy(p[2].classDecl), statements=[p[1]]+deepcopy(p[2].statements))

def p_all_statements_addSClassDecl(p: YaccProduction):
    """GlobalStatementList : ClassDecl GlobalStatementList"""
    loc = Location(p.lineno(1), p.lexspan(1)[0])
    p[0] = PModule(loc, functions=deepcopy(p[2].funcDecl), varDecl=deepcopy(
        p[2].varDecl), classDecl=[p[1]]+deepcopy(p[2].classDecl), statements=deepcopy(p[2].statements))

def p_bloc_single(p: YaccProduction):
    """StatementList : Statement"""
    loc = Location(p.lineno(1), p.lexspan(1)[0])
    p[0] = PScope(loc, functions=[], varDecl=[], statements=[p[1]])


def p_bloc_list(p: YaccProduction):
    """StatementList : Statement StatementList"""
    loc = Location(p.lineno(1), p.lexspan(1)[0])
    if isinstance(p[1], PVarDecl):
        p[0] = PScope(loc, functions=deepcopy(p[2].funcDecl), varDecl=[p[1]]+deepcopy(
            p[2].varDecl), statements=deepcopy(p[2].statements))
    elif isinstance(p[1], PVarDecl):
        p[0] = PScope(loc, functions=[p[1]]+deepcopy(p[2].funcDecl), varDecl=deepcopy(
            p[2].varDecl), statements=deepcopy(p[2].statements))
    else:
        p[0] = PScope(loc, functions=deepcopy(p[2].funcDecl), varDecl=deepcopy(
            p[2].varDecl), statements=[p[1]]+deepcopy(p[2].statements))

def p_empty(p: YaccProduction):
    'empty :'
    pass


def p_utype(p: YaccProduction):
    """Type : Keyword_Type_Mod_Unsigned Keyword_Type_Int16
            | Keyword_Type_Mod_Unsigned Keyword_Type_Int32
            | Keyword_Type_Mod_Unsigned Keyword_Type_Int64
            | Keyword_Type_Mod_Unsigned Keyword_Type_Char"""
    loc = Location(p.lineno(1), p.lexspan(1)[0])
    p[0] = PUType(loc, p[2])


def p_type(p: YaccProduction):
    """Type : Keyword_Type_Void
            | Keyword_Type_Int16
            | Keyword_Type_Int32
            | Keyword_Type_Int64
            | Keyword_Type_String
            | Keyword_Type_Float_32
            | Keyword_Type_Float_64
            | Keyword_Type_Char
            | Keyword_Type_Boolean
            | ID"""
    loc = Location(p.lineno(1), p.lexspan(1)[0])
    p[0] = PType(loc, p[1])


def p_var_declaration(p: YaccProduction):
    """VarDecl : Type ID Punctuation_EoL"""
    loc = Location(p.lineno(1), p.lexspan(1)[0])
    loc2 = Location(p.lineno(2), p.lexspan(2)[0])
    p[0] = PVarDecl(loc, p[1], PIdentifier(loc2,p[2]))

# For now cannot declare and define variable in the same statement
# Will be fixed later
# def p_var_declaration_and_assignment(p:YaccProduction):
#     """VarDecl : Type ID Operator_Binary_Affectation Expr Punctuation_EoL"""
#     loc = Location(p.lineno(1), p.lexspan(1)[0])
#     p[0] = PAssign(loc, PVarDecl(p[1],p[2]), p[4])


def p_break(p: YaccProduction):
    """Break : Keyword_Control_Break Punctuation_EoL"""
    loc = Location(p.lineno(1), p.lexspan(1)[0])
    p[0] = PBreak(loc)


def p_continue(p: YaccProduction):
    """Continue : Keyword_Control_Continue Punctuation_EoL"""
    loc = Location(p.lineno(1), p.lexspan(1)[0])
    p[0] = PContinue(loc)


def p_return_void(p: YaccProduction):
    """Return : Keyword_Control_Return Punctuation_EoL"""
    loc = Location(p.lineno(1), p.lexspan(1)[0])
    p[0] = PReturn(loc, None)


def p_return_value(p: YaccProduction):
    """Return : Keyword_Control_Return Expr Punctuation_EoL"""
    loc = Location(p.lineno(1), p.lexspan(1)[0])
    p[0] = PReturn(loc, p[2])


def p_var_assignment(p: YaccProduction):
    """VarAssign : Var Operator_Binary_Affectation Expr Punctuation_EoL"""
    loc = Location(p.lineno(1), p.lexspan(1)[0])
    p[0] = PAssign(loc, p[1], p[3])


def p_expr(p: YaccProduction):
    """Expr : Var
            | Number
            | ArrayLiteral
            | ArrayIndex
            | FuncCall
            | String"""
    loc = Location(p.lineno(1), p.lexspan(1)[0])
    p[0] = PExpression(loc, p[1])

def p_string(p: YaccProduction):
    """String : Literal_String"""
    loc = Location(p.lineno(1), p.lexspan(1)[0])
    p[0] = PString(loc, p[1])


def p_number(p: YaccProduction):
    """Number : Number_Char
              | Number_Hex
              | Number_Int
              | Number_Float"""
    loc = Location(p.lineno(1), p.lexspan(1)[0])
    p[0] = PNumeric(loc, p[1])


def p_expr_list(p: YaccProduction):
    """ExprList : empty
                | Expr
                | ExprList Punctuation_Comma Expr"""
    p[0] = [p[i] for i in range(1, len(p))]


def p_index(p: YaccProduction):
    """ArrayIndex : Var Punctuation_OpenBracket Expr Punctuation_CloseBracket
                  | Expr Punctuation_OpenBracket Expr Punctuation_CloseBracket
                  | ArrayLiteral Punctuation_OpenBracket Expr Punctuation_CloseBracket"""
    loc = Location(p.lineno(1), p.lexspan(1)[0])
    p[0] = PIndex(loc, p[1], p[3])


def p_binop(p: YaccProduction):
    """Expr : Expr Operator_Binary_Bool_Eq Expr
            | Expr Operator_Binary_Bool_Neq Expr
            | Expr Operator_Binary_Bool_Geq Expr
            | Expr Operator_Binary_Bool_Leq Expr
            | Expr Operator_Binary_Bool_Gt Expr
            | Expr Operator_Binary_Bool_Lt Expr
            | Expr Operator_Minus Expr
            | Expr Operator_Binary_Plus Expr
            | Expr Operator_Binary_Times Expr
            | Expr Operator_Binary_Div Expr
            | Expr Operator_Binary_Mod Expr
            | Expr Operator_Binary_And Expr
            | Expr Operator_Binary_Or Expr
            | Expr Operator_Binary_Xor Expr
            | Expr Operator_Binary_Shl Expr
            | Expr Operator_Binary_Shr Expr
            | Expr Operator_Binary_Bool_Or Expr
            | Expr Operator_Binary_Bool_And Expr"""
    loc = Location(p.lineno(1), p.lexspan(1)[0])
    p[0] = PBinOp(loc, p[1], BinaryOperation(p[2]), p[3])


def p_UnOp(p: YaccProduction):
    '''Expr : Operator_Minus Expr %prec UMINUS
            | Operator_Unary_Not Expr %prec UNOT
            | Operator_Unary_Dec Expr %prec UDEC
            | Operator_Unary_Inc Expr %prec UINC'''
    loc = Location(p.lineno(1), p.lexspan(1)[0])
    p[0] = PUnOp(loc, UnaryOperation(p[1]), p[2])


def p_paren(p: YaccProduction):
    """Expr : Punctuation_OpenParen Expr Punctuation_CloseParen"""
    p[0] = p[1]


def p_ignore(p: YaccProduction):
    """ignore : Comment_Singleline
              | Comment_Multiline
              | Whitespace
              | Punctuation_EoL"""
    loc = Location(p.lineno(1), p.lexspan(1)[0])
    p[0] = PSkip(loc)


def p_binop_assign(p: YaccProduction):
    """ VarAssign : Var Operator_Binary_MinusEq Expr
                  | Var Operator_Binary_PlusEq Expr
                  | Var Operator_Binary_TimesEq Expr
                  | Var Operator_Binary_DivEq Expr
                  | Var Operator_Binary_AndEq Expr
                  | Var Operator_Binary_OrEq Expr
                  | Var Operator_Binary_XorEq Expr
                  | Var Operator_Binary_ShlEq Expr
                  | Var Operator_Binary_ShrEq Expr"""
    loc = Location(p.lineno(1), p.lexspan(1)[0])
    p[0] = PAssign(loc, p[1], PBinOp(
        loc, p[1], BinaryOperation(p[2].strip('=')), p[3]))


def p_copy_assign(p: YaccProduction):
    """VarAssign : Var Operator_Binary_Copy Expr Punctuation_EoL"""
    loc = Location(p.lineno(1), p.lexspan(1)[0])
    p[0] = PCopyAssign(loc, p[1], p[3])


def p_array_literal(p: YaccProduction):
    """ArrayLiteral : Punctuation_OpenBracket ExprList Punctuation_CloseBracket"""
    loc = Location(p.lineno(1), p.lexspan(1)[0])
    p[0] = PExpression(loc, p[1])


def p_call(p: YaccProduction):
    """FuncCall : ID Punctuation_OpenParen ExprList Punctuation_CloseParen"""
    loc = Location(p.lineno(1), p.lexspan(1)[0])
    p[0] = PCall(loc, p[1], p[3])


def p_true(p: YaccProduction):
    """Expr : Keyword_Object_True"""
    loc = Location(p.lineno(1), p.lexspan(1)[0])
    p[0] = PExpression(loc, True)


def p_false(p: YaccProduction):
    """Expr : Keyword_Object_False"""
    loc = Location(p.lineno(1), p.lexspan(1)[0])
    p[0] = PExpression(loc, False)


def p_null(p: YaccProduction):
    """Expr : Keyword_Object_Null"""
    loc = Location(p.lineno(1), p.lexspan(1)[0])
    p[0] = PExpression(loc, None)


def p_typed_args_none(p: YaccProduction):
    """TypedArgs : empty"""
    p[0] = []

def p_typed_args_single(p: YaccProduction):
    """TypedArgs : Type ID"""
    loc = Location(p.lineno(1), p.lexspan(1)[0])
    loc2 = Location(p.lineno(2), p.lexspan(2)[0])
    p[0] = [PVarDecl(loc, p[1], PIdentifier(loc2, p[2]))]

def p_typed_args_multiple(p: YaccProduction):
    """TypedArgs : Type ID Punctuation_Comma TypedArgs"""
    loc = Location(p.lineno(1), p.lexspan(1)[0])
    loc2 = Location(p.lineno(2), p.lexspan(2)[0])
    p[0] = [PVarDecl(loc, p[1], PIdentifier(loc2, p[2]))] + deepcopy(p[4])


def p_func_declaration(p: YaccProduction):
    """FuncDecl : Type ID Punctuation_OpenParen TypedArgs Punctuation_CloseParen Punctuation_OpenBrace StatementList Punctuation_CloseBrace"""
    loc = Location(p.lineno(1), p.lexspan(1)[0])
    p[0] = PFuncDecl(loc, p[1], p[2], p[4], p[7])


def p_class_declaration(p: YaccProduction):
    """ClassDecl : Keyword_Object_Class ID Punctuation_OpenBrace StatementList Punctuation_CloseBrace"""
    loc = Location(p.lineno(1), p.lexspan(1)[0])
    p[0] = PClassDecl(loc, p[2], p[4])

# For
# def p_class_declaration(p:YaccProduction):
#     """ClassDecl : Keyword_Object_Class ID Punctuation_OpenParen ID Punctuation_CloseParen Punctuation_OpenBrace StatementList Punctuation_CloseBrace"""
#     loc = Location(p.lineno(1), p.lexspan(1)[0])
#     p[0] = PClassDecl(loc, p[1], p[2], p[4], p[7])


def p_if(p: YaccProduction):
    """IfBloc : Keyword_Control_If Punctuation_OpenParen Expr Punctuation_CloseParen Punctuation_OpenBrace StatementList Punctuation_CloseBrace"""
    loc = Location(p.lineno(1), p.lexspan(1)[0])
    p[0] = PIf(loc, p[3], p[6], PSkip())


def p_if_else(p: YaccProduction):
    """IfBloc : Keyword_Control_If Punctuation_OpenParen Expr Punctuation_CloseParen Punctuation_OpenBrace StatementList Punctuation_CloseBrace Keyword_Control_Else Punctuation_OpenBrace StatementList Punctuation_CloseBrace"""
    loc = Location(p.lineno(1), p.lexspan(1)[0])
    p[0] = PIf(loc, p[3], p[6], PSkip())


def p_for(p: YaccProduction):
    """ForBloc : Keyword_Control_For Punctuation_OpenParen Statement Statement Statement Punctuation_CloseParen Punctuation_OpenBrace StatementList Punctuation_CloseBrace"""
    loc = Location(p.lineno(1), p.lexspan(1)[0])
    p[0] = PFor(loc, p[3], p[4], p[5], p[8])


def p_foreach(p: YaccProduction):
    """ForBloc : Keyword_Control_For Punctuation_OpenParen VarDecl Punctuation_TernarySeparator Expr Punctuation_CloseParen Punctuation_OpenBrace StatementList Punctuation_CloseBrace"""
    loc = Location(p.lineno(1), p.lexspan(1)[0])
    p[0] = PForeach(loc, p[3], p[5], p[8])


def p_while(p: YaccProduction):
    """WhileBloc : Keyword_Control_While Punctuation_OpenParen Expr Punctuation_CloseParen Punctuation_OpenBrace StatementList Punctuation_CloseBrace"""
    loc = Location(p.lineno(1), p.lexspan(1)[0])
    p[0] = PWhile(loc, p[3], p[6])

def p_assert(p: YaccProduction):
    """Statement : Keyword_Control_Assert Punctuation_OpenParen Expr Punctuation_CloseParen Punctuation_EoL"""
    loc = Location(p.lineno(1), p.lexspan(1)[0])
    p[0] = PAssert(loc, p[3])

def p_var(p: YaccProduction):
    """Var : ID"""
    loc = Location(p.lineno(1), p.lexspan(1)[0])
    p[0] = PIdentifier(loc, p[1])


def p_dot(p: YaccProduction):
    """Var : Var Operator_Dot Var"""
    loc = Location(p.lineno(1), p.lexspan(1)[0])
    p[0] = PDot(loc, p[1], p[3])


def p_ternary(p: YaccProduction):
    """Expr : Expr Punctuation_TernaryConditional Expr Punctuation_TernarySeparator Expr"""
    loc = Location(p.lineno(1), p.lexspan(1)[0])
    p[0] = PTernary(loc, p[1], p[3], p[5])


def p_error(p: YaccProduction):
    if p is None:
        raise SyntaxError("Missing Terminating symbol")
    raise SyntaxError(str(p) + "\n" + repr(p))


parser = yacc.yacc()
