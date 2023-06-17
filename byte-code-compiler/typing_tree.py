from parser_tree import *
from enum import Enum
from math import log10

class ItemAndLoc:
    def __init__(self, item, location:Location|None) -> None:
        self.item = item
        self.location = location
    
    def __repr__(self) -> str:
        return repr(self.item)
    
class TypingError(Exception):
    def __init__(self, message:str, *args: object) -> None:
        super().__init__(message,*args)
        self.message = message
        
    def __str__(self) -> str:
        return self.message
        

class MultiTypingException(Exception):
    def __init__(self, exceptions:list[TypingError], *args: object) -> None:
        super().__init__(*args)
        self.exceptions = exceptions

    def __str__(self) -> str:
        return "\n**********\n".join([str(x) for x in self.exceptions])

class Type:
    def __init__(self, identifier:str, size:int, _is_primitive=False,*, location:Location|None=None, _methods:"dict[str,FunctionType]|None" = None):
        self.ident:str = identifier
        self.size:int = size
        self.fields:dict[str,Type] = {}
        self.methods: dict[str, FunctionType] = {}
        if _methods is not None:
            self.methods.update(_methods)
        self.is_primitive = _is_primitive
        self.can_implicit_cast_to:set[Type] = set()
        self.can_explicit_cast_to:set[Type] = set()
        self.location = location
        
        self._operators:dict[BinaryOperation,dict[Type, Type]] = {}
        self._unary_opertors:dict[UnaryOperation, Type] = {}
    
    def can_cast_to(self, cast_to:"Type") -> bool:
        return cast_to in self.can_implicit_cast_to or cast_to in self.can_explicit_cast_to
    
    def add_explicit_cast(self, cast_to:"Type|list[Type]|set[Type]"):
        if isinstance(cast_to, (list, set)):
            for t in cast_to:
                self.add_explicit_cast(t)
        else:
            self.can_explicit_cast_to.add(cast_to)
        
    def add_implicit_cast(self, cast_to:"Type|list[Type]|set[Type]"):
        if isinstance(cast_to, (list, set)):
            for t in cast_to:
                self.add_implicit_cast(t)
        else:
            self.can_implicit_cast_to.add(cast_to)
            self.add_explicit_cast(cast_to)
    
    def __eq__(self, __o: object) -> bool:
        if not isinstance(__o, Type):
            return False
        return __o.ident == self.ident
    
    def __str__(self) -> str:
        if self.ident == "":
            return '<TYPE_ERROR>'
        return self.ident
    
    def __repr__(self) -> str:
        return f'"Type({str(self)})"'

    def __hash__(self):
        return self.__str__().__hash__()
    
    @staticmethod
    def implicit_cast(t1:"Type", t2:"Type"):
        if t1.ident == t2.ident:
            return t1
        if t1 in t2.can_implicit_cast_to:
            return t1
        if t2 in t1.can_implicit_cast_to:
            return t2
        raise TypingError(f"Cannot find a compatible type for the operation between {t1} and {t2}")
    
    @staticmethod
    def get_type_from_ptype(typ:PType):
        if typ.identifier in CustomType.known_types:
            return CustomType.known_types[typ.identifier]
        raise TypingError(f"Type '{typ.identifier}' is unknown at location {typ.location}")
    
    @staticmethod
    def get_type_from_str(typ:str, location:Location|None=None):
        if BuiltinType.isBuiltin(typ):
            return BuiltinType.str_to_type(typ, location)
        if typ in CustomType.known_types:
            return CustomType.known_types
        else:
            return TypingError(f"Type '{typ}' is unknown at location {location}")

    def do_binop_with(self, right:"Type", op:BinaryOperation) -> "Type":
        return self._operators.get(op, {}).get(right, BuiltinType.MISSING.value)

class ArrayType(Type):
    def __init__(self, element_type: Type) -> None:
        """Size is 16: {ptr to first element|length or array in uint_64}"""
        super().__init__(str(element_type)+"[]", 16, _is_primitive=False)
        self.element_type = element_type
        
    def __str__(self) -> str:
        return str(self.element_type)+'[]'

class FunctionType(Type):
    def __init__(self, return_type: Type, args_type: list[Type]) -> None:
        """Size is 8: ptr to function start"""
        self.return_type = return_type
        self.args_type = args_type
        super().__init__(
            f"FUNC<{return_type.ident}({','.join(str(x) for x in args_type)})>", 8, _is_primitive=False)

    def __eq__(self, __o: object) -> bool:
        if not isinstance(__o, FunctionType):
            return False
        if __o.return_type != self.return_type:
            return False
        if len(__o.args_type) != len(self.args_type):
            return False
        for t1, t2 in zip(__o.args_type, self.args_type):
            if t1 != t2:
                return False
        return True
    
    def __str__(self) -> str:
        return f"FUNC<{self.return_type.ident}({','.join(str(x) for x in self.args_type)})>"


class CustomType(Type):
    known_types: dict[str, Type] = {}

    def __init__(self, identifier: str, size: int, location:Location|None=None, fields: list["TVarDecl"] = [], methods: list["TFuncDecl"] = []) -> None:
        # need to add fields and methods, or at least the underlying class
        super().__init__(identifier, size, location=location)
        self.add_implicit_cast(self)
        self.fields = {f.identifier: f.typ for f in fields}
        self.methods = {m.id: m.typ for m in methods}
        if identifier in BuiltinType._member_map_:
            raise TypingError(
                f"The type '{identifier}' at location {self.location} is already declared as a builtin-in type")
        if identifier in CustomType.known_types:
            raise TypingError(
                f"The type '{identifier}' at location {self.location} has already been declared at location {CustomType.known_types[identifier].location}")
        else:
            CustomType.known_types[identifier] = self

class BuiltinType(Enum):
    MISSING = Type("", -1)
    BOOL = Type("bool", 1, True)
    CHAR = Type("char", 1, True)
    INT_16 = Type("i16", 2, True)
    INT_32 = Type("i32", 4, True)
    INT_64 = Type("i64", 8, True)
    UINT_8 = Type("u8", 1, True)
    UINT_16 = Type("u16", 2, True)
    UINT_32 = Type("u32", 4, True)
    UINT_64 = Type("u64", 8, True)
    FLOAT_32 = Type("f32", 4, True)
    FLOAT_64 = Type("f64", 8, True)
    STRING = Type("string", 8)
    VOID = Type("void", 0)
    
    @staticmethod
    def get_numeric_types() -> set[Type]:
        return {BuiltinType.BOOL.value, BuiltinType.CHAR.value, BuiltinType.UINT_8.value,
                BuiltinType.INT_16.value, BuiltinType.UINT_16.value, BuiltinType.INT_32.value,
                BuiltinType.UINT_32.value, BuiltinType.INT_64.value, BuiltinType.UINT_64.value,
                BuiltinType.FLOAT_32.value, BuiltinType.FLOAT_64.value}
    
    @staticmethod
    def get_types() -> set[Type]:
        return {BuiltinType.BOOL.value, BuiltinType.CHAR.value, BuiltinType.UINT_8.value,
                BuiltinType.INT_16.value, BuiltinType.UINT_16.value, BuiltinType.INT_32.value,
                BuiltinType.UINT_32.value, BuiltinType.INT_64.value, BuiltinType.UINT_64.value,
                BuiltinType.FLOAT_32.value, BuiltinType.FLOAT_64.value, BuiltinType.STRING.value, 
                BuiltinType.VOID.value, BuiltinType.MISSING.value}
    
    @staticmethod
    def isBuiltin(type_identifier:str) -> bool:
        values = set(item.value.ident for item in BuiltinType)
        return type_identifier in values
        
    @staticmethod
    def str_to_type(str_typ: str, location:Location|None=None):
        for typ in BuiltinType.get_types():
            if typ.ident == str_typ:
                return typ
        raise TypingError(f"Incorrect use of builtin type {str_typ} at location {location}")            


def setup_builtin_types(root_vars: dict[str, ItemAndLoc]):
    numeric_and_bool = BuiltinType.get_types()
    numeric_and_bool.remove(BuiltinType.VOID.value)
    numeric_and_bool.remove(BuiltinType.MISSING.value)
    for typ in numeric_and_bool:
        typ.methods.update(
            {"ToString": FunctionType(BuiltinType.STRING.value, [])})
    
    for typ in numeric_and_bool:
        for op in BinaryOperation:
            typ._operators[op] = {}
    
    numeric_and_bool.remove(BuiltinType.STRING.value)
    
    #add explicit casts
    for typ in numeric_and_bool:
        typ.add_explicit_cast(numeric_and_bool)

    BuiltinType.STRING.value.add_implicit_cast(BuiltinType.STRING.value)
    BuiltinType.VOID.value.add_implicit_cast(BuiltinType.VOID.value)
    BuiltinType.FLOAT_64.value.add_implicit_cast(
        BuiltinType.FLOAT_64.value)
    BuiltinType.FLOAT_32.value.add_implicit_cast(
        BuiltinType.FLOAT_32.value)
    BuiltinType.FLOAT_32.value.add_implicit_cast(
        BuiltinType.FLOAT_64.value)
    BuiltinType.INT_64.value.add_implicit_cast(BuiltinType.INT_64.value)
    BuiltinType.INT_64.value.add_implicit_cast(
        BuiltinType.FLOAT_32.value.can_implicit_cast_to)
    BuiltinType.INT_32.value.add_implicit_cast(BuiltinType.INT_32.value)
    BuiltinType.INT_32.value.add_implicit_cast(
        BuiltinType.INT_64.value.can_implicit_cast_to)
    BuiltinType.INT_16.value.add_implicit_cast(BuiltinType.INT_16.value)
    BuiltinType.INT_16.value.add_implicit_cast(
        BuiltinType.INT_32.value.can_implicit_cast_to)
    BuiltinType.CHAR.value.add_implicit_cast(BuiltinType.CHAR.value)
    BuiltinType.CHAR.value.add_implicit_cast(
        BuiltinType.INT_16.value.can_implicit_cast_to)
    BuiltinType.BOOL.value.add_implicit_cast(BuiltinType.BOOL.value)
    BuiltinType.BOOL.value.add_implicit_cast(
        BuiltinType.CHAR.value.can_implicit_cast_to)
    BuiltinType.UINT_64.value.add_implicit_cast(
        [BuiltinType.UINT_64.value, BuiltinType.FLOAT_32.value, BuiltinType.FLOAT_64.value])
    BuiltinType.UINT_32.value.add_implicit_cast(
        BuiltinType.INT_64.value.can_implicit_cast_to)
    BuiltinType.UINT_32.value.add_implicit_cast(BuiltinType.UINT_32.value)
    BuiltinType.UINT_16.value.add_implicit_cast(BuiltinType.UINT_64.value)
    BuiltinType.UINT_16.value.add_implicit_cast(
        BuiltinType.INT_32.value.can_implicit_cast_to)
    BuiltinType.UINT_16.value.add_implicit_cast(BuiltinType.UINT_16.value)
    BuiltinType.UINT_8.value.add_implicit_cast(BuiltinType.UINT_8.value)
    BuiltinType.UINT_8.value.add_implicit_cast(
        BuiltinType.INT_16.value.can_implicit_cast_to)
    
    for typ in BuiltinType.get_types():
        CustomType.known_types[typ.ident] = typ
    # add shortcut to char as i8
    CustomType.known_types['i8'] = BuiltinType.CHAR.value
    
    for t1 in numeric_and_bool:
        for t2 in numeric_and_bool:
            #set +,-,* and / operator types
            for op in {BinaryOperation.PLUS, BinaryOperation.MINUS, BinaryOperation.TIMES,
                       BinaryOperation.DIVIDE}:
                if t1 == t2 and t1 == BuiltinType.BOOL.value:
                    #bool operators will be converted to char as operators on bool values will most likely over/underflow
                    t1._operators[op][t2] = BuiltinType.CHAR.value
                else:
                    try:
                        t1._operators[op][t2] = Type.implicit_cast(t1,t2)
                    except:
                        pass #skip operations between non corresponding types
            #for t2 not a float set mod and shift
            if t2 not in {BuiltinType.FLOAT_32.value, BuiltinType.FLOAT_64.value}:
                # set left and right shift ops for t2 integer
                t1._operators[BinaryOperation.SHIFT_LEFT][t2] = t1
                t1._operators[BinaryOperation.SHIFT_RIGHT][t2] = t1                
                # for t2 not a float set modulus, XOR and AND/OR operators (valid on integers and bool)
                if t1 not in {BuiltinType.FLOAT_32.value, BuiltinType.FLOAT_64.value}:
                    try:
                        t1._operators[BinaryOperation.MOD][t2] = Type.implicit_cast(t1,t2)
                        t1._operators[BinaryOperation.XOR][t2] = Type.implicit_cast(t1,t2)
                        t1._operators[BinaryOperation.LOGIC_AND][t2] = Type.implicit_cast(t1,t2)
                        t1._operators[BinaryOperation.LOGIC_OR][t2] = Type.implicit_cast(t1,t2)
                    except:
                        pass  # skip operations between incompatible types
                    t1._operators[BinaryOperation.BOOL_AND][t2] = BuiltinType.BOOL.value
                    t1._operators[BinaryOperation.BOOL_OR][t2] = BuiltinType.BOOL.value
            # and comparators 
            for op in {BinaryOperation.BOOL_EQ, BinaryOperation.BOOL_GEQ, BinaryOperation.BOOL_GT,
                       BinaryOperation.BOOL_LEQ, BinaryOperation.BOOL_LT, BinaryOperation.BOOL_NEQ}:
                t1._operators[op][t2] = BuiltinType.BOOL.value
                
    #add unary operators
    for t in BuiltinType.get_numeric_types():
        if t == BuiltinType.BOOL.value:
            continue #skip bool, it's a special case treat is separately
        t._unary_opertors[UnaryOperation.INCREMENT] = t
        t._unary_opertors[UnaryOperation.DECREMENT] = t
        t._unary_opertors[UnaryOperation.LOGIC_NOT] = t
        t._unary_opertors[UnaryOperation.MINUS] = t
        
    BuiltinType.BOOL.value._unary_opertors[UnaryOperation.BOOL_NOT] = BuiltinType.BOOL.value
    BuiltinType.BOOL.value._unary_opertors[UnaryOperation.LOGIC_NOT] = BuiltinType.BOOL.value

    #add concat
    BuiltinType.STRING.value._operators[BinaryOperation.PLUS][BuiltinType.STRING.value] = BuiltinType.STRING.value
    #Add builtin functions IDs
    root_vars.setdefault('print', ItemAndLoc(FunctionType(BuiltinType.VOID.value, [BuiltinType.STRING.value]),None))

class TTreeElem:
    def __init__(self, elem: PTreeElem, parent:"TTreeElem|None"=None) -> None:
        self.parent = parent
        self.location = elem.location
        self.location_end = elem.location_end
        if not hasattr(self, 'errors'):
            self.errors:list[TypingError] = []
        if not hasattr(self, '_known_vars'):
            self._known_vars:dict[str,ItemAndLoc] = {}
            
    def get_errors(self) ->list[TypingError]:
        err:list[TypingError] = self.errors[:]
        for k in self.__dict__.keys():
            if k == "parent":
                continue
            if isinstance(getattr(self,k), TTreeElem):
                err += getattr(self, k).get_errors()
            elif isinstance(getattr(self, k), list):
                for elem in getattr(self,k):
                    if isinstance(elem, TTreeElem):  # skip parsing errors attribute
                        err += elem.get_errors()
        return err
        
    def add_known_id(self, id:str, typ:Type, location:Location|None=None):
        var = self.find_corresponding_var_typ(id)
        if var is not None:
            p = self
            while p is not None:
                if id in p._known_vars and location != p._known_vars[id].location:
                    raise TypingError(f"The identifier '{id}' at location {location} "+
                                      "has already been defined in this scope at location "+
                                          str(p._known_vars[id].location))
                p = p.parent
        self._known_vars[id] = ItemAndLoc(typ,location)
    
    def find_corresponding_var_typ(self, id:str) -> Type|None:
        if id in self._known_vars:
            return self._known_vars[id].item
        elif not self.parent is None:
            return self.parent.find_corresponding_var_typ(id)
        else:
            return None

    def __repr__(self):
        d = dict(self.__dict__) #make copy
        del d["parent"] #remove parent to avoid infinite recursion 
        inner = str(d).replace("\'", "\"")
        return f'{{"{self.__class__.__name__}" : {inner}}}'
    
    def __str__(self) -> str:
        return self.__repr__()


class TStatement(TTreeElem):
    @staticmethod
    def get_correct_TTreeElem(statement):
        if isinstance(statement, PSkip):
            return TSkip
        if isinstance(statement, PExpression):
            return TExpression.get_correct_TTreeElem(statement)
        if isinstance(statement, PReturn):
            return TReturn
        if isinstance(statement, PAssert):
            return TAssert
        if isinstance(statement, PContinue):
            return TContinue
        if isinstance(statement, PBreak):
            return TBreak
        if isinstance(statement, PIf):
            return TIf
        if isinstance(statement, PTernary):
            return TTernary
        if isinstance(statement, PWhile):
            return TWhile
        if isinstance(statement, PFor):
            return TFor
        if isinstance(statement, PForeach):
            return TForeach
        if isinstance(statement, PImport):
            return TImport
        if isinstance(statement, PIdentifier): #just an empty statement like 'x;'
            return TSkip
        raise TypingError(f"Cannot find corresponding statement type for {type(statement)} (error at location {statement.location})")

    def __init__(self, statement: PStatement, parent: TTreeElem):
        super().__init__(statement, parent)

class TExpression(TTreeElem):
    @staticmethod
    def get_correct_TTreeElem(expr:PTreeElem):
        if isinstance(expr, PlValue):
            return TlValue.get_correct_TTreeElem(expr)
        if isinstance(expr, PNumeric):
            return TNumeric
        if isinstance(expr, PIndex):
            return TIndex
        if isinstance(expr, PBinOp):
            return TBinOp
        if isinstance(expr, PUnOp):
            return TUnOp
        if isinstance(expr, PCall):
            return TCall
        if isinstance(expr, PString):
            return TString
        if isinstance(expr, PCast):
            return TCast
        if isinstance(expr, PNewObj):
            return TNewObj
        if isinstance(expr, PNewArray):
            return TNewArray
        if isinstance(expr, PDot):
            return TDot
        if isinstance(expr, PIdentifier):
            return TVar
        if isinstance(expr, PBool):
            return TBool
        raise TypingError(f"Cannot find corresponding type for {type(expr)} (error at location {expr.location})")
        
    def __init__(self, elem: PTreeElem, parent: TTreeElem):
        super().__init__(elem, parent)
        self.typ = BuiltinType.MISSING.value

class TVar(TExpression):
    def __init__(self, elem:PIdentifier, parent:TTreeElem, parent_typ:Type|None=None):
        super().__init__(elem, parent)
        self.identifier = elem.identifier
        self.typ = BuiltinType.MISSING.value
        typ = self.find_corresponding_var_typ(elem.identifier)
        if typ is None and parent_typ is not None:
            typ = parent_typ.fields.get(elem.identifier, None)
        if typ is None:
            self.errors.append(TypingError(f"Unknown type for identifier: '{self.identifier}' at location {self.location}"))
        else:
            self.typ = typ

class TScope(TTreeElem):
    def __init__(self, elem:PScope, parent:TTreeElem|None):
        super().__init__(elem, parent)
        if isinstance(elem, PSkip):
            return
        #define global functions (just names and return types)
        for func in elem.funcDecl:
            assert(isinstance(func, PFuncDecl))
            try:
                self.add_known_id(func.id.identifier,
                                  FunctionType(
                                      CustomType.get_type_from_ptype(func.returnType),
                                      [CustomType.get_type_from_ptype(arg.typ) for arg in func.args]),
                                  func.id.location)
            except TypingError as e:
                self.errors.append(e)
                
        self.varDecl = [TVarDecl(pvardecl, self) for pvardecl in elem.varDecl]
        self.funcDecl = [TFuncDecl(pfuncdecl, self) for pfuncdecl in elem.funcDecl]
        self.statements = []
        for pstatement in elem.statements:
            try:
                self.statements.append(TStatement.get_correct_TTreeElem(pstatement)(pstatement, self))
            except TypingError as e:
                self.errors.append(e)

class TModule(TScope):
    def __init__(self, elem: PModule):
        self._known_vars:dict[str,ItemAndLoc] = {}
        self.errors: list[TypingError] = []
        self.parent = None
        setup_builtin_types(self._known_vars)
        #add defined classes into type list
        for c in elem.classDecl:
            try:
                CustomType(c.identifier.identifier,8, location=c.identifier.location)
            except TypingError as e:
                self.errors.append(e)
        #define global functions (just names and return types)
        for func in elem.funcDecl:
            assert (isinstance(func, PFuncDecl))
            try:
                self.add_known_id(func.id.identifier,
                                  FunctionType(
                                      CustomType.get_type_from_ptype(func.returnType),
                                      [CustomType.get_type_from_ptype(arg.typ) for arg in func.args]),
                                  func.id.location)
            except TypingError as e:
                self.errors.append(e)
        #define classes and types
        self.classDecl = [TClassDecl(c, self) for c in elem.classDecl]
        elem.location = Location(1,1)
        super().__init__(elem, None)

class TClassDecl(TTreeElem):
    def __init__(self, elem: PClassDecl, parent: TTreeElem):
        super().__init__(elem, parent)
        self.identifier = elem.identifier.identifier
        self.typ = CustomType.known_types.get(self.identifier, BuiltinType.MISSING.value)
        self.fields = [TVarDecl(field, self) for field in elem.inner_scope.varDecl]
        self.methods = [TFuncDecl(method, self) for method in elem.inner_scope.funcDecl]
        #set class type fields, methods and size in memory
        if self.typ != BuiltinType.MISSING.value:
            self.typ.size = 8+sum([f.typ.size if f.typ.is_primitive else 8 for f in self.fields])
            self.typ.methods.update({m.id:m.typ for m in self.methods})
            self.typ.fields.update({f.identifier:f.typ for f in self.fields})
        
    def get_type(self) -> Type:
        return self.typ

class TBool(TExpression):
    def __init__(self, elem: PBool, parent: TTreeElem, parent_typ: Type | None = None):
        super().__init__(elem, parent)
        self.value = elem.value
        self.typ = BuiltinType.BOOL.value

class TlValue(TExpression):
    def __init__(self, elem: PlValue, parent: TTreeElem, parent_typ: Type | None = None):
        super().__init__(elem, parent)

    @staticmethod
    def get_correct_TTreeElem(expr: PlValue):
        if isinstance(expr, PDot):
            return TDot
        if isinstance(expr, PVarDecl):
            return TVarDecl
        return TlValue


class TEnum(TScope):
    def __init__(self, elem: PEnum, parent: TTreeElem):
        super().__init__(elem, parent) 
        self.identifier = elem.identifier.identifier
        self.enum_values = [TVar(val, self) for val in elem.enum_values]
        #here TVar needs to be set first 

class TVarDecl(TTreeElem):
    def __init__(self, elem: PVarDecl, parent: TTreeElem, parent_typ:Type|None=None) -> None:
        super().__init__(elem, parent)
        try:
            self.typ = Type.get_type_from_ptype(elem.typ)
        except TypingError as e:
            self.errors.append(e)
            self.typ = BuiltinType.MISSING.value
        self.identifier = elem.identifier.identifier
        if self.typ != BuiltinType.MISSING.value:
            try:
                parent.add_known_id(self.identifier, self.typ, elem.identifier.location)
            except TypingError as e:
                self.errors.append(e)                

class TFuncDecl(TTreeElem):
    def __init__(self, elem: PFuncDecl, parent: TTreeElem):
        super().__init__(elem, parent=parent)
        self.id = elem.id.identifier
        self.typ = FunctionType(BuiltinType.MISSING.value,[])
        self.returnType = BuiltinType.MISSING.value
        self.args = [TVarDecl(v, self) for v in elem.args]
        try:
            self.returnType = Type.get_type_from_ptype(elem.returnType)
            arg_types = [arg.typ for arg in self.args]
            self.typ = FunctionType(self.returnType, arg_types)
        except TypingError as e:
            self.errors.append(e)
            self.returnType = None
        try:
            parent.add_known_id(elem.id.identifier, self.typ, elem.id.location)
        except TypingError as e:
            self.errors.append(e)
        self.body = TScope(elem.body, self)

class TCast(TExpression):
    def __init__(self, elem: PCast, parent: TTreeElem, parent_typ:Type|None=None):
        super().__init__(elem, parent)
        self.typ = BuiltinType.MISSING.value
        self.rvalue = TExpression.get_correct_TTreeElem(elem.rvalue)(elem.rvalue, self)
        try:
            typ = Type.get_type_from_ptype(elem.cast_to)
            if not self.rvalue.typ.can_cast_to(typ):
                self.errors.append(TypingError(f"Cannot cast {self.rvalue.typ} to {typ} at location {self.location}"))
            else:
                self.typ = typ
        except TypingError as e:
            self.errors.append(e)

class TNumeric(TExpression):
    def __init__(self, elem: PNumeric, parent: TTreeElem, parent_typ:Type|None=None):
        super().__init__(elem, parent)
        self.typ = BuiltinType.MISSING.value
        if isinstance(elem.value, float):
            #floating point and constant is within the float32 precision (~[2^-127, 2^127] with ~6 digits of precision)
            s = "{:e}".format(elem.value)
            if abs(log10(elem.value)) < 38 and len(s[:s.index('e')]) < 7:
                self.typ = BuiltinType.FLOAT_32.value
            else:
                self.typ = BuiltinType.FLOAT_64.value
        elif elem.value >= 0:
            if elem.value < 2**8:
                self.typ = BuiltinType.UINT_8.value
            elif elem.value < 2**16:
                self.typ = BuiltinType.UINT_16.value
            elif elem.value < 2**32:
                self.typ = BuiltinType.UINT_32.value
            elif elem.value < 2**64:
                self.typ = BuiltinType.UINT_64.value
            else:
                self.errors.append(TypingError(f"The value {elem.value} is outside the accepted range at location {elem.location}"))
        else:  # negative int
            if abs(elem.value) <= 2**7:
                self.typ = BuiltinType.CHAR.value
            elif abs(elem.value) <= 2**16:
                self.typ = BuiltinType.INT_16.value
            elif abs(elem.value) <= 2**32:
                self.typ = BuiltinType.INT_32.value
            elif abs(elem.value) <= 2**64:
                self.typ=BuiltinType.INT_64.value
            else:
                self.errors.append(TypingError(
                    f"The value {elem.value} is outside the accepted range at location {elem.location}"))
        self.value = elem.value

class TNewArray(TExpression):
    def __init__(self, elem: PNewArray, parent:TTreeElem, parent_typ:Type|None=None) -> None:
        super().__init__(elem, parent)
        self.rvalue = TExpression.get_correct_TTreeElem(elem.rvalue)(elem.rvalue, self)
        try:
            self.typ = ArrayType(Type.get_type_from_ptype(elem.typ))
        except TypingError as e:
            self.errors.append(e)
            self.typ = ArrayType(BuiltinType.MISSING.value)
        self.arr_len = self.rvalue
        
class TIndex(TExpression):
    """for indexing : array[idx]"""

    def __init__(self, elem: PIndex, parent: TTreeElem, parent_typ: Type | None = None):
        super().__init__(elem, parent)
        self.index = TExpression.get_correct_TTreeElem(elem.index)(elem.index, self)
        self.rvalue = TExpression.get_correct_TTreeElem(elem.rvalue)(elem.rvalue, self)
        self.typ = BuiltinType.MISSING.value
        if isinstance(self.rvalue.typ, ArrayType):
            self.typ = self.rvalue.typ.element_type
        else:
            self.errors.append(
                TypingError(f"Unable to index the type {self.rvalue.typ} at location {self.index.location}"))

class TDot(TlValue):
    def __init__(self, elem: PDot, parent:TTreeElem, parent_typ:Type|None=None):
        super().__init__(elem.rvalue, parent)
        self.left = TExpression.get_correct_TTreeElem(elem.left)(elem.left, self)
        self.rvalue = TExpression.get_correct_TTreeElem(elem.rvalue)(elem.rvalue, self, parent_typ=self.left.typ)
        self.typ:Type = self.rvalue.typ
        

class TBinOp(TExpression):
    def __init__(self, elem:PBinOp, parent:TTreeElem, parent_typ:Type|None=None):
        super().__init__(elem, parent)
        self.rvalue = TExpression.get_correct_TTreeElem(elem.rvalue)(elem.rvalue, self)
        self.left = TExpression.get_correct_TTreeElem(elem.left)(elem.left, self)
        self.operation = elem.op
        if self.operation in {BinaryOperation.ASSIGN, BinaryOperation.COPY}:
            self.typ = self.left.typ
            if self.rvalue.typ != BuiltinType.MISSING.value and self.left.typ not in self.rvalue.typ.can_implicit_cast_to:
                self.errors.append(TypingError(
                    f"Cannot implicitly convert '{self.rvalue.typ}' to '{self.left.typ}' at location {self.location}"))
            return
        if self.operation in self.left.typ._operators:
            self.typ = self.left.typ._operators[self.operation].get(self.rvalue.typ, BuiltinType.MISSING.value)
            if self.typ is BuiltinType.MISSING.value:
                self.errors.append(
                    TypingError(f"Cannot apply operator '{self.operation}' between types '{self.left.typ}' and '{self.rvalue.typ}' at location {self.location}"))
        else:
            self.errors.append(TypingError(
                f"The '{self.operation}' operator is not defined between types '{self.left.typ}' and '{self.rvalue.typ}' at location {self.location}"))

class TUnOp(TExpression):
    def __init__(self, elem:PUnOp, parent:TTreeElem, parent_typ:Type|None=None):
        super().__init__(elem, parent=parent)
        self.rvalue = TExpression.get_correct_TTreeElem(elem.rvalue)(elem.rvalue, self)
        self.op = elem.op
        if self.op in self.rvalue.typ._unary_opertors:
            self.typ = self.rvalue.typ._unary_opertors[self.op]
        else:
            self.errors.append(TypingError(f"The unary operator '{self.op.value}' is not implemented for this type at location {self.location}"))
            self.typ = self.rvalue.typ


class TCall(TExpression):
    def __init__(self, elem:PCall, parent:TTreeElem, parent_typ:Type|None=None):
        super().__init__(elem, parent)
        self.args = [TExpression.get_correct_TTreeElem(arg)(arg, self) for arg in elem.args]
        self.rvalue = TVar(elem.function_id, self, parent_typ=parent_typ)
        self.function_id:str = self.rvalue.identifier
        #find return value type
        self.typ = BuiltinType.MISSING.value
        func_typ = self.find_corresponding_var_typ(self.function_id)
        #if it's a known id
        if func_typ is not None:
            if isinstance(func_typ, FunctionType): # it's a function
                self.typ = func_typ.return_type
            else:
                self.errors.append(TypingError(f"'{self.function_id}' is not a callable function. Problem at location {self.location}"))
                return
        elif isinstance(parent_typ, Type) and self.function_id in parent_typ.methods:
            func_typ = parent_typ.methods[self.function_id]
            self.typ = func_typ.return_type
        else: #check if builtin
            self.errors.append(TypingError(f"Attempts to call unknown function '{self.function_id}' at location {elem.function_id.location}"))
            return
                        
        if len(func_typ.args_type) != len(self.args):
            self.errors.append(TypingError(
                f"Got {len(self.args)} arguments but expected {len(func_typ.args_type)} at location {self.location}"))
        for expected, gotten in zip(func_typ.args_type, self.args):
            if expected not in gotten.typ.can_implicit_cast_to:
                self.errors.append(TypingError(f"Expected type {expected} but got {gotten.typ} at location {gotten.location}"))

class TSkip(TStatement):
    def __init__(self, elem:PSkip, parent:TTreeElem):
        super().__init__(elem, parent)
        if isinstance(elem, PIdentifier):
            if self.find_corresponding_var_typ(elem.identifier) is None:
                raise TypingError(f"The identifier '{elem.identifier}' is unknown at location {elem.location}")

class TReturn(TStatement):
    def __init__(self, elem:PReturn, parent:TTreeElem):
        super().__init__(elem, parent)
        self.returnVal = TExpression.get_correct_TTreeElem(elem.returnVal)(elem.returnVal, self)
        self.typ = self.returnVal.typ

class TAssert(TStatement):
    def __init__(self, elem:PAssert, parent:TTreeElem):
        super().__init__(elem, parent)
        self.assertExpr = TExpression.get_correct_TTreeElem(elem.assertExpr)(elem.assertExpr, self)
        self.typ = self.assertExpr.typ

class TString(TExpression):
    def __init__(self,elem:PString, parent:TTreeElem, parent_typ:Type|None=None):
        super().__init__(elem, parent)
        self.typ = BuiltinType.STRING.value
        self.value = elem.string_value

class TContinue(TStatement):
    def __init__(self, elem:PContinue, parent:TTreeElem):
        super().__init__(elem, parent)

class TBreak(TStatement):
    def __init__(self, elem:PBreak, parent:TTreeElem):
        super().__init__(elem, parent)


class TIf(TStatement):
    def __init__(self, elem: PIf, parent: TTreeElem):
        super().__init__(elem, parent)
        self.condition = TExpression.get_correct_TTreeElem(elem.condition)(elem.condition, self)
        if not self.condition.typ.can_cast_to(BuiltinType.BOOL.value):
            self.errors.append(TypingError(f"The condition expression must be a boolean not a {self.condition.typ} at location {self.condition.location}"))
        self.if_true = TScope(elem.if_true, self)
        self.if_false = TScope(elem.if_false, self)


class TTernary(TExpression):
    def __init__(self, elem: PTernary, parent: TTreeElem):
        super().__init__(elem, parent)
        self.condition = TExpression.get_correct_TTreeElem(elem.condition)(elem.condition, self)
        if not self.condition.typ.can_cast_to(BuiltinType.BOOL.value):
            self.errors.append(TypingError(
                f"The condition expression must be a boolean not a {self.condition.typ} at location {self.condition.location}"))
        self.if_true = TExpression.get_correct_TTreeElem(elem.if_true)(elem.if_true, self)
        self.if_false = TExpression.get_correct_TTreeElem(elem.if_false)(elem.if_false, self)
        try:
            self.typ = CustomType.implicit_cast(self.if_true.typ, self.if_false.typ)
        except TypingError as e:
            self.errors.append(TypingError(e.message+f' at location {self.location}'))
            self.typ = BuiltinType.MISSING.value

class TWhile(TStatement):
    def __init__(self, elem: PWhile, parent: TTreeElem):
        super().__init__(elem, parent)
        self.condition = TExpression.get_correct_TTreeElem(elem.condition)(elem.condition, self)
        self.bloc = TScope(elem.bloc, self)


class TFor(TStatement):
    def __init__(self, elem: PFor, parent: TTreeElem):
        super().__init__(elem, parent)
        self.init = TStatement.get_correct_TTreeElem(elem.init)(elem.init, self)
        self.condition = TExpression.get_correct_TTreeElem(elem.condition)(elem.condition, self)
        self.postExpr = TStatement.get_correct_TTreeElem(elem.postExpr)(elem.postExpr, self)
        self.bloc = TScope(elem.bloc, self)


class TForeach(TStatement):
    def __init__(self, elem: PForeach, parent: TTreeElem):
        super().__init__(elem, parent)
        self.varDecl = TVarDecl(elem.varDecl, self)
        self.iterable = TVar(elem.iterable, self)
        self.bloc = TScope(elem.bloc, self)


class TNewObj(TExpression):
    def __init__(self, elem: PNewObj, parent: TTreeElem, parent_typ:Type|None=None):
        super().__init__(elem, parent)
        try:
            self.new_obj = CustomType.get_type_from_ptype(elem.object)
        except TypingError as e:
            self.errors.append(e)
            self.new_obj = BuiltinType.MISSING.value
        self.typ = self.new_obj
        self.args = [TExpression.get_correct_TTreeElem(arg)(arg, self) for arg in elem.args]


class TImport(TStatement):
    def __init__(self, elem: PImport, parent: TTreeElem):
        super().__init__(elem, parent)
        #TODO


def p_to_t_tree(ptree: PModule):
    ttree = TModule(ptree)
    errors = ttree.get_errors()
    if len(errors) > 0:
        raise MultiTypingException(errors)
    return ttree