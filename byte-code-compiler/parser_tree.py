import ply.yacc as yacc
from ply.lex import LexToken
from ply.yacc import YaccProduction
from lexer import tokens, Location
from operations import BinaryOperation, UnaryOperation
from copy import deepcopy
import sys

class ParsingError(Exception):
    def __init__(self, *args: object, location:Location=Location(-1,-1), problem_token=None) -> None:
        self.location = location
        self.problem_token = problem_token
        super().__init__(*args)
    
    def __str__(self) -> str:
        return f"Parsing error on line {self.location.line} and column {self.location.col}.\n\tProblem Token:{repr(self.problem_token)}"
    

class MultiParsingException(ParsingError):
    def __init__(self, *args: object, exceptions:list=None) -> None:
        super().__init__(args)
        self.exceptions = exceptions

    def __str__(self) -> str:
        return "\n**********\n".join([str(x) for x in self.exceptions])


# P.... classes are there to build the abstract syntax tree

class JSON_Val:
    def __init__(self, val) -> None:
        self._val = val
    
    def __repr__(self):
        return str(self)
    
    def __str__(self):
        if self._val is None:
            return 'null'
        return 'true' if self._val else 'false'

class PTreeElem:
    def __init__(self, location:Location, *, last_token_end=None) -> None:
        def max_loc(loc:Location):
            return 100000*loc.line+loc.col if loc is not None else 1
        def min_loc(loc:Location):
            return 100000*loc.line+loc.col if loc is not None else 9999999999999999
        
        self.location = location
        self.parsing_errors = []
        self.location_end = last_token_end
        for attr in self.__dict__.values():
            if isinstance(attr, PTreeElem):
                self.parsing_errors += getattr(attr, "parsing_errors", [])
                self.location_end = max(self.location_end, attr.location_end, key=max_loc)
                self.location = min(self.location, attr.location, key=min_loc)
            elif isinstance(attr, list):
                for elem in attr:
                    if isinstance(elem, ParsingError): #skip parsing errors attribute
                        break
                    self.parsing_errors += getattr(elem, "parsing_errors", [])
                    self.location_end = max(
                        self.location_end, elem.location_end, key=max_loc)
                    self.location = min(self.location, elem.location, key=min_loc)
                    
        if self.location is None:
            self.location = Location(-1,-1)
        if self.location_end is None:
            if last_token_end is None:
                self.location_end = Location(self.location.line, self.location.col)
            else:
                self.location_end = last_token_end

    def __repr__(self):
        def replace(d:dict, old_val, new_val):
            for key in d.keys():
                if isinstance(d[key], dict):
                    replace(d,old_val, new_val)
                else:
                    if isinstance(d[key], bool):
                        d[key] = JSON_Val(d[key])
                    elif d[key] == old_val:
                        d[key] = new_val
                        
        inner = deepcopy(self.__dict__)
        replace(inner, None, JSON_Val(None))
        inner = str(inner).replace("\'", "\"")
        return f'{{"{self.__class__.__name__}" : {inner}}}'


class PIdentifier(PTreeElem):
    def __init__(self, location, identifier:str, last_token_end=None):
        self.identifier = identifier
        super().__init__(location, last_token_end=last_token_end)


class PThis(PIdentifier):
    def __init__(self, location, last_token_end=None):
        super().__init__(location, identifier="this", last_token_end=last_token_end)


class PType(PIdentifier):
    def __init__(self, location, type_identifier, last_token_end=None):
        self.type_identifier = type_identifier
        super().__init__(location, type_identifier, last_token_end=last_token_end)


class PArray(PType):
    def __init__(self, location, arrType: PType, last_token_end=None) -> None:
        super().__init__(location, arrType, last_token_end=last_token_end)


class PScope(PTreeElem):
    def __init__(self, location, *, functions=None, varDecl=None, statements=None, last_token_end=None):
        self.funcDecl = [] if functions is None else functions
        self.varDecl = [] if varDecl is None else varDecl
        self.statements = [] if statements is None else statements
        super().__init__(location, last_token_end=last_token_end)


class PModule(PScope):
    def __init__(self, location, *, functions=None, varDecl=None, classDecl=None, statements=None, quiet=False):
        self.classDecl = classDecl
        super().__init__(location, functions=functions,
                         varDecl=varDecl, statements=statements)
        if len(self.parsing_errors) > 0:
            prob = MultiParsingException(exceptions = self.parsing_errors)
            raise prob


class PClassDecl(PScope):
    def __init__(self, location, identifier:PIdentifier, inner_scope:PScope,last_token_end=None, *, parentClassId=None, interfaces=None):
        self.identifier = identifier
        self.inner_scope = inner_scope
        super().__init__(location, last_token_end=last_token_end)
        # no inheritance yet
        if isinstance(identifier, PThis):
            self.parsing_errors.append(ParsingError(
                "'this' cannot be used in this context", location=self.location, problem_token="this"))


class PStatement(PTreeElem):
    def __init__(self, location, last_token_end=None):
        super().__init__(location, last_token_end=last_token_end)


class PExpression(PStatement):
    def __init__(self, location, rvalue, last_token_end=None):
        self.rvalue = rvalue
        super().__init__(location, last_token_end = last_token_end)


class PEnum(PScope):
    def __init__(self, location, identifier:PIdentifier, values: list[PIdentifier], last_token_end=None):
        super().__init__(location, statements = values, last_token_end = last_token_end)
        self.identifier = identifier
        self.enum_values = values

class PVarDecl:
    pass

class PFuncDecl(PTreeElem):
    def __init__(self, location, returnType: PType, id: PIdentifier, args: list[PVarDecl], body: PScope, last_token_end=None):
        self.returnType = returnType
        self.id = id
        self.args = args
        self.body = body
        super().__init__(location, last_token_end=last_token_end)
        if isinstance(id, PThis):
            self.parsing_errors.append(ParsingError(
                "'this' is a reserved keyword", location=self.location, problem_token="this"))


class PlValue(PExpression):
    def __init__(self, location, value, last_token_end=None):
        super().__init__(location, value, last_token_end=last_token_end)


class PUType(PType):
    def __init__(self, location, type_identifier, last_token_end=None):
        super().__init__(location, type_identifier, last_token_end=last_token_end)


class PNumeric(PExpression):
    def __init__(self, location, value, last_token_end=None):
        super().__init__(location, value, last_token_end=last_token_end)
        
class PIndex(PExpression):
    """for indexing : array[idx]"""

    def __init__(self, location, array: PExpression, idx: PExpression,  last_token_end:tuple=None):
        if location is None:
            location = idx.location
        self.index = idx.rvalue
        super().__init__(location, array)


class PDot(PlValue):
    def __init__(self, location, left:PIdentifier, right:PIdentifier):
        def has_this(elem):
            if isinstance(elem, PThis):
                return True
            if isinstance(elem, PDot):
                return has_this(elem.left) or has_this(elem.rvalue)
            if isinstance(elem, PExpression):
                return has_this(elem.rvalue)
            return False
        
        self.left = left
        super().__init__(location, right)
        if has_this(right):
            self.parsing_errors.append(ParsingError(
                "'this' is not a valid field", location=self.location, problem_token="this"))


class PVarDecl(PlValue):
    def __init__(self, location, typ: PType, id: PIdentifier, init_value:PExpression=None,  last_token_end=None):
        self.typ = typ
        self.init_value = init_value
        super().__init__(location, id, last_token_end=last_token_end)
        if isinstance(id, PThis):
            self.parsing_errors.append(ParsingError("'this' cannot be used in this context", location=self.location, problem_token="this"))
        

class PBinOp(PExpression):
    def __init__(self, location, left: PExpression, op: BinaryOperation, right: PExpression, last_token_end=None):
        self.left = left
        self.op = op
        super().__init__(location, right)


class PAssign(PBinOp):
    def __init__(self, location, lvalue: PlValue, rvalue: PExpression, last_token_end=None):
        super().__init__(location, left=lvalue, right=rvalue, op=None, last_token_end=last_token_end)


class PCopyAssign(PBinOp):
    def __init__(self, location, lvalue: PlValue, rvalue: PExpression, last_token_end=None):
        super().__init__(location, left=lvalue, right=rvalue, op=None, last_token_end=last_token_end)


class PUnOp(PExpression):
    def __init__(self, location, op: UnaryOperation, right: PExpression, last_token_end=None):
        self.op = op
        super().__init__(location, right)


class PCall(PExpression):
    def __init__(self, location, id: PIdentifier, args=list[PExpression], last_token_end=None):
        self.args = args
        super().__init__(location, id, last_token_end=last_token_end)


class PSkip(PStatement):
    def __init__(self, location):
        super().__init__(location)
        # do nothing empty block

class PReturn(PStatement):
    def __init__(self, location, returnVal: PExpression, last_token_end=None):
        self.returnVal = returnVal
        super().__init__(location, last_token_end=last_token_end)

class PAssert(PStatement):
    def __init__(self, location, assertExpr: PExpression, last_token_end=None):
        self.assertExpr = assertExpr
        super().__init__(location, last_token_end = last_token_end)

class PString(PExpression):
    def __init__(self, location, value: str, last_token_end=None):
        super().__init__(location, value, last_token_end = last_token_end)


class PContinue(PStatement):
    def __init__(self, location, last_token_end=None):
        super().__init__(location, last_token_end=last_token_end)


class PBreak(PStatement):
    def __init__(self, location, last_token_end=None):
        super().__init__(location, last_token_end = last_token_end)


class PIf(PStatement):
    def __init__(self, location, condition: PExpression, if_true: PScope, if_false: PScope = None, last_token_end=None):
        self.condition = condition
        self.if_true = if_true
        self.if_false = if_false
        super().__init__(location, last_token_end = last_token_end)


class PTernary(PStatement):
    def __init__(self, location, condition: PExpression, if_true: PReturn, if_false: PReturn, last_token_end=None):
        self.condition = condition
        self.if_true = if_true
        self.if_false = if_false
        super().__init__(location, last_token_end=last_token_end)


class PWhile(PStatement):
    def __init__(self, location, condition: PExpression, bloc: PScope, last_token_end=None):
        self.condition = condition
        self.bloc = bloc
        super().__init__(location, last_token_end=last_token_end)


class PFor(PStatement):
    def __init__(self, location, init: PStatement, condition: PExpression, postExpr: PStatement, bloc: PScope, last_token_end=None):
        self.init = init
        self.condition = condition
        self.postExpr = postExpr
        self.bloc = bloc
        super().__init__(location, last_token_end = last_token_end)
        
class PCast(PExpression):
    def __init__(self, location, cast_to:PType, rvalue:PExpression, last_token_end=None):
        self.cast_to = cast_to
        super().__init__(location, rvalue, last_token_end=last_token_end)


class PForeach(PStatement):
    def __init__(self, location, varDecl: PVarDecl, iterable: PIdentifier, bloc: PScope, last_token_end=None):
        self.varDecl = varDecl
        self.iterable = iterable
        self.bloc = bloc
        super().__init__(location, last_token_end = last_token_end)
        
class PNewObj(PExpression):
    def __init__(self, location, object:PType, arguments:list[PExpression], last_token_end=None):
        self.object = object
        self.args = arguments
        super().__init__(location, object, last_token_end=last_token_end)
        
class PNewArray(PExpression):
    def __init__(self, location, typ:PType, array_length:PExpression, last_token_end=None):
        self.typ = typ
        super().__init__(location, array_length, last_token_end = last_token_end)

class PImport(PStatement):
    def __init__(self, location, module: PIdentifier, item: PIdentifier, last_token_end=None):
        self.module = module
        self.item = item
        super().__init__(location, last_token_end=last_token_end)
        if isinstance(item, PThis):
            self.parsing_errors.append(ParsingError(
                "'this' is a reserved keyword", location=self.location, problem_token="this"))


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
    ('right', 'Operator_Binary_Mod', 'Operator_Binary_And',
        'Operator_Binary_Or'),
    ('left', 'Operator_Binary_Xor', 'Operator_Binary_Shl',
     'Operator_Binary_Shr'),
    ('left', 'Operator_Binary_Plus', 'Operator_Minus'),
    ('left', 'Operator_Binary_Times', 'Operator_Binary_Div'),
    ('right', 'UNOP'),           # Unary operator precedence
)

start = 'Module'

def p_module(p: YaccProduction):
    """Module : GlobalStatementList"""
    p[0] = p[1]


def p_statement(p: YaccProduction):
    """Statement : VarDecl
                 | VarAssign
                 | FuncDecl
                 | IfBloc
                 | ForBloc
                 | WhileBloc
                 | Scope
                 | Return
                 | Break
                 | Continue
                 | ignore"""
    p[0] = p[1]
    
def p_statement_2(p: YaccProduction):
    """Statement : Expr Punctuation_EoL
                 | FuncCall Punctuation_EoL"""
    p[0] = p[1]
    p[0].location_end =  p.slice[2].location_end


def p_scope(p: YaccProduction):
    """Scope : Punctuation_OpenBrace StatementList Punctuation_CloseBrace"""
    p[0] = p[2]
    p[0].location_end = p.slice[3].location_end
    p[0].location= p.slice[1].location
    
    
def p_scope_err(p: YaccProduction):
    """Scope : Punctuation_OpenBrace error Punctuation_CloseBrace"""
    p[0] = PSkip()

def p_all_statements_statement(p: YaccProduction):
    """GlobalStatementList : StatementList"""
    p[0] = PModule(None, functions=deepcopy(p[1].funcDecl), varDecl=deepcopy(
        p[1].varDecl), classDecl=list(), statements=deepcopy(p[1].statements))


def p_all_statements_classDecl(p: YaccProduction):
    """GlobalStatementList : ClassDecl"""
    p[0] = PModule(None, functions=[], varDecl=[],
                   classDecl=[p[1]], statements=[])

def p_all_statements_addStatement(p: YaccProduction):
    """GlobalStatementList : Statement GlobalStatementList"""
    if isinstance(p[1], PVarDecl):
        p[0] = PModule(None, functions=deepcopy(p[2].funcDecl), varDecl=[p[1]]+deepcopy(
            p[2].varDecl), classDecl=deepcopy(p[2].classDecl), statements=deepcopy(p[2].statements))
    elif isinstance(p[1], PFuncDecl):
        p[0] = PModule(None, functions=[p[1]]+deepcopy(p[2].funcDecl), varDecl=deepcopy(
            p[2].varDecl), classDecl=deepcopy(p[2].classDecl), statements=deepcopy(p[2].statements))
    else:
        p[0] = PModule(None, functions=deepcopy(p[2].funcDecl), varDecl=deepcopy(
            p[2].varDecl), classDecl=deepcopy(p[2].classDecl), statements=[p[1]]+deepcopy(p[2].statements))

def p_all_statements_addSClassDecl(p: YaccProduction):
    """GlobalStatementList : ClassDecl GlobalStatementList"""
    p[0] = PModule(None, functions=deepcopy(p[2].funcDecl), varDecl=deepcopy(
        p[2].varDecl), classDecl=[p[1]]+deepcopy(p[2].classDecl), statements=deepcopy(p[2].statements))

def p_bloc_empty(p: YaccProduction):
    """StatementList : empty"""
    if parser.symstack[-1].type == '$end':
        loc = Location(-1,-1)
    else:
        loc = parser.symstack[-1].location
    p[0] = PScope(loc, functions=[], varDecl=[], statements=[])

def p_bloc_single(p: YaccProduction):
    """StatementList : Statement"""
    if isinstance(p[1], PVarDecl):
        p[0] = PScope(p[1].location, functions=[], varDecl=[
                      p[1]], statements=[], last_token_end=p[1].location_end)
    elif isinstance(p[1], PFuncDecl):
        p[0] = PScope(p[1].location, functions=[p[1]], varDecl=[], statements=[],
                      last_token_end=p[1].location_end)
    else:
        p[0] = PScope(p[1].location, functions=[],
                      varDecl=[], statements=[p[1]], last_token_end=p[1].location_end)


def p_bloc_list(p: YaccProduction):
    """StatementList : Statement StatementList"""
    loc = Location(p.lineno(1), p.lexspan(1)[0])
    if isinstance(p[1], PVarDecl):
        p[0] = PScope(loc, functions=deepcopy(p[2].funcDecl), varDecl=[p[1]]+deepcopy(
            p[2].varDecl), statements=deepcopy(p[2].statements))
    elif isinstance(p[1], PFuncDecl):
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
    loc, loc2 = p.slice[1].location, p.slice[2].location_end
    p[0] = PUType(loc, p[2], loc2)


def p_type(p: YaccProduction):
    """Type : Keyword_Type_Void
            | Keyword_Type_Int16
            | Keyword_Type_Int32
            | Keyword_Type_Int64
            | Keyword_Type_String
            | Keyword_Type_Float_32
            | Keyword_Type_Float_64
            | Keyword_Type_Char
            | Keyword_Type_Boolean"""
    loc, loc2 = p.slice[1].location, p.slice[1].location_end
    p[0] = PType(loc, p[1], last_token_end=loc2)
    
    
def p_cast(p:YaccProduction):
    """Expr : Punctuation_OpenParen Type Punctuation_CloseParen Expr"""
    loc = p.slice[1].location
    p[0] = PCast(loc, p[2], p[4])
    
    
def p_cast_2(p:YaccProduction):
    """Expr : Punctuation_OpenParen Ident Punctuation_CloseParen Expr"""
    loc = p.slice[1].location
    typ = PType(None, p[2].identifier)
    p[0] = PCast(loc, typ, p[4])


def p_var_declaration(p: YaccProduction):
    """VarDecl : Ident Ident Punctuation_EoL"""
    loc2 = p.slice[3].location_end
    typ = PType(None, p[1].identifier)
    p[0] = PVarDecl(None, typ, p[2], last_token_end=loc2)
    
def p_var_declaration_2(p: YaccProduction):
    """VarDecl : Type Ident Punctuation_EoL"""
    loc2 = p.slice[3].location_end
    p[0] = PVarDecl(None, p[1], p[2], last_token_end=loc2)

def p_var_declaration_and_assignment(p:YaccProduction):
    """VarDecl : Ident Ident Operator_Binary_Affectation Expr Punctuation_EoL"""
    loc2 = p.slice[5].location_end
    p[0] = PVarDecl(None, PType(None, p[1].identifier), p[2], p[4], last_token_end=loc2)

def p_var_declaration_and_assignment_2(p:YaccProduction):
    """VarDecl : Type Ident Operator_Binary_Affectation Expr Punctuation_EoL"""
    loc2 = p.slice[5].location_end
    p[0] = PVarDecl(None, p[1], p[2], p[4], last_token_end=loc2)


def p_break(p: YaccProduction):
    """Break : Keyword_Control_Break Punctuation_EoL"""
    loc2 = p[2].location_end
    p[0] = PBreak(None, last_token_end=loc2)


def p_continue(p: YaccProduction):
    """Continue : Keyword_Control_Continue Punctuation_EoL"""
    loc2 = p[2].location_end
    p[0] = PContinue(None, last_token_end=loc2)


def p_return_void(p: YaccProduction):
    """Return : Keyword_Control_Return Punctuation_EoL"""
    loc2 = p[2].location_end
    p[0] = PReturn(None, None, last_token_end=loc2)


def p_return_value(p: YaccProduction):
    """Return : Keyword_Control_Return Expr Punctuation_EoL"""
    loc2 = p.slice[3].location_end
    p[0] = PReturn(None, p[2], last_token_end=loc2)


def p_var_assignment(p: YaccProduction):
    """VarAssign : Ident Operator_Binary_Affectation Expr Punctuation_EoL"""
    loc2 = p.slice[4].location_end
    p[0] = PAssign(None, p[1], p[3], loc2)


def p_expr(p: YaccProduction):
    """Expr : Ident
            | Number
            | ArrayLiteral
            | ArrayIndex
            | FuncCall
            | String"""
    p[0] = PExpression(None, p[1])

def p_string(p: YaccProduction):
    """String : Literal_String"""
    loc,loc2 = p.slice[1].location, p.slice[1].location_end
    p[0] = PString(loc, p[1], last_token_end=loc2)


def p_number(p: YaccProduction):
    """Number : Number_Char
              | Number_Hex
              | Number_Int
              | Number_Float"""
    loc, loc2 = p.slice[1].location, p.slice[1].location_end
    p[0] = PNumeric(loc, p[1], loc2)


def p_expr_list(p: YaccProduction):
    """ExprList : empty
                | Expr
                | ExprList Punctuation_Comma Expr"""
    if p.slice[1].value is None: #empty
        p[0] = []
    elif not isinstance(p[1], list): #second regex
        p[0] = [p[1]]
    else:
        p[0] = p[1] + [p[3]]


def p_index(p: YaccProduction):
    """ArrayIndex : Expr Punctuation_OpenBracket Expr Punctuation_CloseBracket"""
    loc2 = p.slice[4].location_end
    p[0] = PIndex(None, p[1], p[3], last_token_end=loc2)


def p_array(p: YaccProduction):
    """Type : Ident Punctuation_OpenBracket Punctuation_CloseBracket"""
    loc2 = p.slice[3].location_end
    p[0] = PArray(None, PType(p[1].location, p[1].identifier), last_token_end=loc2)


def p_array_2(p: YaccProduction):
    """Type : Type Punctuation_OpenBracket Punctuation_CloseBracket"""
    loc2 = p.slice[3].location_end
    p[0] = PArray(None, p[1], last_token_end=loc2)


def p_new_array(p: YaccProduction):
    """Expr : Keyword_Object_New Ident Punctuation_OpenBracket Expr Punctuation_CloseBracket"""
    loc, loc2 = p.slice[1].location, p.slice[5].location_end
    p[0] = PNewArray(loc, PType(p[2].location, p[2].identifier), p[4], last_token_end=loc2)


def p_new_array_2(p: YaccProduction):
    """Expr : Keyword_Object_New Type Punctuation_OpenBracket Expr Punctuation_CloseBracket"""
    loc, loc2 = p.slice[1].location, p.slice[5].location_end
    p[0] = PNewArray(loc, p[2], p[4])


def p_new_obj(p: YaccProduction):
    """Expr : Keyword_Object_New Ident Punctuation_OpenParen ExprList Punctuation_CloseParen"""
    loc, loc2 = p.slice[1].location, p.slice[5].location_end
    p[0] = PNewObj(loc, PType(p[2].location, p[2].identifier), p[4], last_token_end=loc2)

def p_new_obj_2(p: YaccProduction):
    """Expr : Keyword_Object_New Type Punctuation_OpenParen ExprList Punctuation_CloseParen"""
    loc, loc2 = p.slice[1].location, p.slice[5].location_end
    p[0] = PNewObj(loc, p[2], p[4], last_token_end=loc2)


def p_new_obj_no_args(p: YaccProduction):
    """Expr : Keyword_Object_New Ident Punctuation_OpenParen Punctuation_CloseParen"""
    loc, loc2 = p.slice[1].location, p.slice[4].location_end
    p[0] = PNewObj(loc, PType(p[2].location, p[2].identifier),
                   [], last_token_end=loc2)


def p_new_obj_no_args_2(p: YaccProduction):
    """Expr : Keyword_Object_New Type Punctuation_OpenParen Punctuation_CloseParen"""
    loc, loc2 = p.slice[1].location, p.slice[4].location_end
    p[0] = PNewObj(loc, p[2], [], last_token_end=loc2)


def p_binop(p: YaccProduction):
    #prec avoids a-b being reduced to a (-b) and ending up with 'Expr Expr'
    """Expr : Expr Operator_Minus Expr %prec UNOP
            | Expr Operator_Binary_Bool_Eq Expr
            | Expr Operator_Binary_Bool_Neq Expr
            | Expr Operator_Binary_Bool_Geq Expr
            | Expr Operator_Binary_Bool_Leq Expr
            | Expr Operator_Binary_Bool_Gt Expr
            | Expr Operator_Binary_Bool_Lt Expr
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
    p[0] = PBinOp(None, p[1], BinaryOperation(p[2]), p[3])


def p_paren(p: YaccProduction):
    """Expr : Punctuation_OpenParen Expr Punctuation_CloseParen"""
    loc, loc2 = p.slice[1].location, p.slice[3].location_end
    p[0] = p[2]
    p[0].location, p[0].location_end = loc,loc2
    


def p_UnOp(p: YaccProduction):
    '''Expr : Operator_Minus Expr
            | Operator_Unary_Not Expr %prec UNOP'''
    loc = p.slice[1].location
    p[0] = PUnOp(loc, UnaryOperation(p[1]), p[2])


def p_UnOp_IncDec(p: YaccProduction):
    '''Expr : Ident Operator_Unary_Dec %prec UNOP
            | Ident Operator_Unary_Inc %prec UNOP
            | ArrayIndex Operator_Unary_Dec %prec UNOP
            | ArrayIndex Operator_Unary_Inc %prec UNOP'''
    loc2 = p.slice[2].location_end
    p[0] = PUnOp(None, UnaryOperation(p[2]), p[1], last_token_end=loc2)


def p_ignore(p: YaccProduction):
    """ignore : Comment_Singleline
              | Comment_Multiline
              | Whitespace
              | Punctuation_EoL"""
    p[0] = PSkip(None)


def p_binop_assign(p: YaccProduction):
    """ VarAssign : Ident Operator_Binary_MinusEq Expr
                  | Ident Operator_Binary_PlusEq Expr
                  | Ident Operator_Binary_TimesEq Expr
                  | Ident Operator_Binary_DivEq Expr
                  | Ident Operator_Binary_AndEq Expr
                  | Ident Operator_Binary_OrEq Expr
                  | Ident Operator_Binary_XorEq Expr
                  | Ident Operator_Binary_ShlEq Expr
                  | Ident Operator_Binary_ShrEq Expr
                  | ArrayIndex Operator_Binary_MinusEq Expr
                  | ArrayIndex Operator_Binary_PlusEq Expr
                  | ArrayIndex Operator_Binary_TimesEq Expr
                  | ArrayIndex Operator_Binary_DivEq Expr
                  | ArrayIndex Operator_Binary_AndEq Expr
                  | ArrayIndex Operator_Binary_OrEq Expr
                  | ArrayIndex Operator_Binary_XorEq Expr
                  | ArrayIndex Operator_Binary_ShlEq Expr
                  | ArrayIndex Operator_Binary_ShrEq Expr"""
    p[0] = PAssign(None, p[1], 
                   PBinOp(None, p[1], BinaryOperation(p[2].strip('=')), p[3]))


def p_copy_assign(p: YaccProduction):
    """VarAssign : Ident Operator_Binary_Copy Expr Punctuation_EoL
                 | ArrayIndex Operator_Binary_Copy Expr Punctuation_EoL"""
    loc2 = p.slice[4].location_end
    p[0] = PCopyAssign(None, p[1], p[3], last_token_end=loc2)


def p_array_literal(p: YaccProduction):
    """ArrayLiteral : Punctuation_OpenBracket ExprList Punctuation_CloseBracket"""
    loc, loc2 = p.slice[1].location, p.slice[3].location_end
    p[0] = PExpression(loc, p[1], last_token_end=loc2)


def p_call(p: YaccProduction):
    """FuncCall : Ident Punctuation_OpenParen ExprList Punctuation_CloseParen %prec UNOP
                | Ident Punctuation_OpenParen Expr Punctuation_CloseParen %prec UNOP""" 
    #add precedence to avoid 'Ident (Expr)' getting reduced to 'Ident Expr'
    def place_pcall(node):
        if isinstance(node.rvalue, PDot):
            place_pcall(node.rvalue)
        else:
            node.rvalue = PCall(None, node.rvalue, p[3] if isinstance(p[3], list) else p[3],
                                p.slice[4].location_end)
            
    if isinstance(p[1], PDot):
        place_pcall(p[1])
        p[0] = p[1]
    else: # p[1] is PIdent
        p[0] = PCall(None, p[1], p[3] if isinstance(p[3], list) else p[3],
                     p.slice[4].location_end)
    

def p_call_no_Args(p: YaccProduction):
    """FuncCall : Ident Punctuation_OpenParen Punctuation_CloseParen %prec UNOP"""
    def place_pcall(node):
        if isinstance(node.rvalue, PDot):
            place_pcall(node.rvalue)
        else:
            node.rvalue = PCall(None, node.rvalue, p.slice[3].location_end)

    if isinstance(p[1], PDot):
        place_pcall(p[1])
        p[0] = p[1]
    else:  # p[1] is PIdent
        p[0] = PCall(None, p[1], [], p.slice[3].location_end)


def p_true(p: YaccProduction):
    """Expr : Keyword_Object_True"""
    loc = p.slice[1].location
    last_token_end = p.slice[1].location_end
    p[0] = PExpression(loc, True, last_token_end=last_token_end)


def p_false(p: YaccProduction):
    """Expr : Keyword_Object_False"""
    loc = p.slice[1].location
    last_token_end = p.slice[1].location_end
    p[0] = PExpression(loc, False, last_token_end=last_token_end)


def p_null(p: YaccProduction):
    """Expr : Keyword_Object_Null"""
    loc = p.slice[1].location
    last_token_end = p.slice[1].location_end
    p[0] = PExpression(loc, None, last_token_end=last_token_end)

def p_typed_args_single(p: YaccProduction):
    """TypedArgs : Type Ident"""
    p[0] = [PVarDecl(None, p[1], p[2])]
    
def p_typed_args_single_2(p: YaccProduction):
    """TypedArgs : Ident Ident"""
    p[0] = [PVarDecl(None, PType(p.slice[1].location, p[1].identifier, p.slice[1].last_token_end), p[2])]

def p_typed_args_multiple(p: YaccProduction):
    """TypedArgs : Type Ident Punctuation_Comma TypedArgs"""
    p[0] = [PVarDecl(None, p[1], p[2])] + deepcopy(p[4])

def p_typed_args_multiple_2(p: YaccProduction):
    """TypedArgs : Ident Ident Punctuation_Comma TypedArgs"""
    p[0] = [PVarDecl(None, PType(p.slice[1].location, p[1].identifier,
                     p.slice[1].last_token_end), p[2])] + deepcopy(p[4])

def p_func_declaration(p: YaccProduction):
    """FuncDecl : Type Ident Punctuation_OpenParen TypedArgs Punctuation_CloseParen Punctuation_OpenBrace StatementList Punctuation_CloseBrace"""
    p[0] = PFuncDecl(None, p[1], p[2], p[4], p[7], last_token_end=p.slice[8].location_end)

def p_func_declaration_2(p: YaccProduction):
    """FuncDecl : Ident Ident Punctuation_OpenParen TypedArgs Punctuation_CloseParen Punctuation_OpenBrace StatementList Punctuation_CloseBrace"""
    p[0] = PFuncDecl(None, PType(p.slice[1].location, p[1].identifier,
                     p.slice[1].last_token_end), p[2], p[4], p[7], last_token_end=p.slice[8].location_end)

def p_func_declaration_no_args(p: YaccProduction):
    """FuncDecl : Type Ident Punctuation_OpenParen Punctuation_CloseParen Punctuation_OpenBrace StatementList Punctuation_CloseBrace"""
    p[0] = PFuncDecl(p[1].location, p[1], p[2], [], p[6],
                     last_token_end=p.slice[7].location_end)
    
def p_void_constructor_decl(p:YaccProduction):
    """FuncDecl : Ident Punctuation_OpenParen Punctuation_CloseParen Punctuation_OpenBrace StatementList Punctuation_CloseBrace"""
    p[0] = PFuncDecl(p[1].location, p[1], p[1], [], p[5],
                     last_token_end=p.slice[6].location_end)
    
def p_constructor_decl(p:YaccProduction):
    """FuncDecl : Ident Punctuation_OpenParen TypedArgs Punctuation_CloseParen Punctuation_OpenBrace StatementList Punctuation_CloseBrace"""
    p[0] = PFuncDecl(p[1].location, p[1], p[1], p[3], p[6],
                            last_token_end=p[7].location_end)
    
def p_this(p:YaccProduction):
    """Ident : Keyword_Object_This"""
    p[0] = PThis(p.slice[1].location, p.slice[1].location_end)


def p_func_declaration_no_args_2(p: YaccProduction):
    """FuncDecl : Ident Ident Punctuation_OpenParen Punctuation_CloseParen Punctuation_OpenBrace StatementList Punctuation_CloseBrace"""
    p[0] = PFuncDecl(p[1].location, PType(p.slice[1].location, p[1].identifier, p.slice[1].last_token_end),
                     p[2], [], p[6], last_token_end=p.slice[7].location_end)

def p_class_declaration(p: YaccProduction):
    """ClassDecl : Keyword_Object_Class Ident Punctuation_OpenBrace StatementList Punctuation_CloseBrace"""
    p[0] = PClassDecl(p.slice[1].location, p[2], p[4], last_token_end=p.slice[5].location_end)

# For extension / implementing interfaces
# def p_class_declaration(p:YaccProduction):
#     """ClassDecl : Keyword_Object_Class Ident Punctuation_OpenParen Ident Punctuation_CloseParen Punctuation_OpenBrace StatementList Punctuation_CloseBrace"""
#     loc = Location(p.lineno(1), p.lexspan(1)[0])
#     p[0] = PClassDecl(loc, p[1], p[2], p[4], p[7])


def p_if(p: YaccProduction):
    """IfBloc : Keyword_Control_If Punctuation_OpenParen Expr Punctuation_CloseParen Punctuation_OpenBrace StatementList Punctuation_CloseBrace"""
    p[0] = PIf(None, p[3], p[6], PSkip(),
               last_token_end=p.slice[7].location_end)


def p_if_else(p: YaccProduction):
    """IfBloc : Keyword_Control_If Punctuation_OpenParen Expr Punctuation_CloseParen Punctuation_OpenBrace StatementList Punctuation_CloseBrace Keyword_Control_Else Punctuation_OpenBrace StatementList Punctuation_CloseBrace"""
    p[0] = PIf(None, p[3], p[6], p[10],
               last_token_end=p.slice[11].location_end)


def p_for(p: YaccProduction):
    """ForBloc : Keyword_Control_For Punctuation_OpenParen VarDecl Expr Statement Punctuation_CloseParen Punctuation_OpenBrace StatementList Punctuation_CloseBrace"""
    p[0] = PFor(None, p[3], p[4], p[5], p[8],
                last_token_end=p.slice[9].location_end)


def p_foreach(p: YaccProduction):
    """ForBloc : Keyword_Control_For Punctuation_OpenParen VarDecl Punctuation_TernarySeparator Expr Punctuation_CloseParen Punctuation_OpenBrace StatementList Punctuation_CloseBrace"""
    p[0] = PForeach(None, p[3], p[5], p[8],
                    last_token_end=p.slice[9].location_end)


def p_while(p: YaccProduction):
    """WhileBloc : Keyword_Control_While Punctuation_OpenParen Expr Punctuation_CloseParen Punctuation_OpenBrace StatementList Punctuation_CloseBrace"""
    p[0] = PWhile(None, p[3], p[6], last_token_end=p.slice[7].location_end)

def p_assert(p: YaccProduction):
    """Statement : Keyword_Control_Assert Punctuation_OpenParen Expr Punctuation_CloseParen Punctuation_EoL"""
    p[0] = PAssert(None, p[3], last_token_end=p.slice[5].location_end)

def p_var(p: YaccProduction):
    """Ident : ID"""
    p[0] = PIdentifier(p.slice[1].location, p[1],
                       last_token_end=p.slice[1].location_end)


def p_dot(p: YaccProduction):
    """Ident : Ident Operator_Dot Ident  %prec UNOP"""
    if isinstance(p.slice[1], PDot):
        p.slice[1] = PDot(p.slice[3].location, p.slice[1], p.slice[3].left)
        p.slice[3] = p[3].rvalue
    if isinstance(p.slice[3], PDot):
        p.slice[1] = PDot(p.slice[3].location, p.slice[1], p.slice[3].left)
        p.slice[3] = p[3].rvalue
    p[0] = PDot(None, p[1], p[3])


def p_dot_2(p: YaccProduction):
    """Ident : Expr Operator_Dot Ident %prec UNOP"""
    if isinstance(p.slice[1], PDot):
        p.slice[1] = PDot(p.slice[3].location, p.slice[1], p.slice[3].left)
        p.slice[3] = p[3].rvalue
    if isinstance(p.slice[3], PDot):
        p.slice[1] = PDot(p.slice[3].location, p.slice[1], p.slice[3].left)
        p.slice[3] = p[3].rvalue
    p[0] = PDot(None, p[1], p[3])


def p_ternary(p: YaccProduction):
    """Expr : Expr Punctuation_TernaryConditional Expr Punctuation_TernarySeparator Expr"""
    p[0] = PTernary(None, p[1], p[3], p[5])

def p_error(p: LexToken):
    if p is None:
        if hasattr(parser.symstack[-1],"location_end"):
            loc = parser.symstack[-1].location_end
        else:
            loc = parser.symstack[-1].value.location_end
        raise ParsingError(f"End of file found when a symbol was expected at location {loc}",
                           location=loc,
                           problem_token='EOF')
    loc = p.location
    raise ParsingError(f"Unexpected symbol '{p.value}' on "+str(loc), location=loc, problem_token=p.value)


parser = yacc.yacc()
