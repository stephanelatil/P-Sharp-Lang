from parser_tree import *
from enum import Enum
from math import log10
from random import randbytes, randint
from typing import Callable

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


class TypeInternalStructureOffsets:
    @property
    def type_table(self):
        return 0

    @property
    def size(self):
        return 8
    
    def __init__(self, fields:"dict[str,Type]") -> None:
        self.field = {}
        self.size_on_heap = 16
        for name, typ in fields.items():
            self.field[name] = self.size_on_heap
            self.size_on_heap += 8 if not typ.is_primitive else typ.size
        

class ArrayInternalStructureOffsets:
    @property
    def type_table(self):
        return 0
    
    @property
    def arr_len(self):
        return 8
    
    @property
    def elements(self):
        return 16
    
    def __init__(self, typ:"Type") -> None:
        self.typ = typ
        
    def get_offset_of_index_zero(self):
        return self.elements
    
    def get_size_on_heap(self, num_elements:int):
        return num_elements * (self.typ.size if self.typ.is_primitive else 8)
    

class Type:
    def __init__(self, identifier:str, size:int, _is_primitive=False,*,
                 location:Location|None=None, _op_functions:dict[UnaryOperation|tuple[BinaryOperation,'Type'],Callable]={}, _methods:"dict[str,FunctionType]|None" = None):
        self.ident:str = identifier
        self.size:int = size
        if not hasattr(self, "fields"):
            self.fields:dict[str,Type] = {}
        if not hasattr(self, "methods"):
            self.methods: dict[str, FunctionType] = {}
        if _methods is not None:
            self.methods.update(_methods)
        self.is_primitive = _is_primitive
        self.can_implicit_cast_to:set[Type] = set()
        self.can_explicit_cast_to:set[Type] = set()
        self.location = location
        self.offsets = TypeInternalStructureOffsets(self.fields)
        
        self._operators:dict[BinaryOperation,dict[Type, Type]] = {}
        self._unary_opertors:dict[UnaryOperation, Type] = {}
        self._constructor_uuid = -1
        self._op_functions:dict[UnaryOperation|tuple[BinaryOperation,'Type'],Callable] = {}
        self._op_functions.update(_op_functions)
    
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
    def get_type_from_ptype(ptype:PType):
        if ptype.identifier in CustomType.known_types:
            return CustomType.known_types[ptype.identifier]
        raise TypingError(f"Type '{ptype.identifier}' is unknown at location {ptype.location}")
    
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
        
        self.offsets = ArrayInternalStructureOffsets(typ)
        
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
        self.fields.update({f.identifier: f.typ for f in fields})
        self.methods.update({m.id: m.typ for m in methods})
        self.offsets = TypeInternalStructureOffsets(self.fields)
        if identifier in BuiltinType._member_map_:
            raise TypingError(
                f"The type '{identifier}' at location {self.location} is already declared as a builtin-in type")
        if identifier in CustomType.known_types:
            raise TypingError(
                f"The type '{identifier}' at location {self.location} has already been declared at location {CustomType.known_types[identifier].location}")
        else:
            CustomType.known_types[identifier] = self
            
    @staticmethod
    def get_all_types():
        return set(CustomType.known_types.values())

class BuiltinType(Enum):
    MISSING = Type("", -1)
    BOOL = Type("bool", 1, True)
    INT_8 = Type("i8", 1, True)
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
        return {BuiltinType.BOOL.value, BuiltinType.INT_8.value, BuiltinType.UINT_8.value,
                BuiltinType.INT_16.value, BuiltinType.UINT_16.value, BuiltinType.INT_32.value,
                BuiltinType.UINT_32.value, BuiltinType.INT_64.value, BuiltinType.UINT_64.value,
                BuiltinType.FLOAT_32.value, BuiltinType.FLOAT_64.value}
    
    @staticmethod
    def get_types() -> set[Type]:
        return {BuiltinType.BOOL.value, BuiltinType.INT_8.value, BuiltinType.UINT_8.value,
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
    BuiltinType.INT_32.value.add_implicit_cast(BuiltinType.UINT_64.value)
    BuiltinType.INT_32.value.add_implicit_cast(
        BuiltinType.INT_64.value.can_implicit_cast_to)
    BuiltinType.INT_16.value.add_implicit_cast(BuiltinType.INT_16.value)
    BuiltinType.INT_16.value.add_implicit_cast(BuiltinType.UINT_32.value)
    BuiltinType.INT_16.value.add_implicit_cast(
        BuiltinType.INT_32.value.can_implicit_cast_to)
    BuiltinType.INT_8.value.add_implicit_cast(BuiltinType.INT_8.value)
    BuiltinType.INT_8.value.add_implicit_cast(BuiltinType.UINT_16.value)
    BuiltinType.INT_8.value.add_implicit_cast(
        BuiltinType.INT_16.value.can_implicit_cast_to)
    BuiltinType.BOOL.value.add_implicit_cast(BuiltinType.BOOL.value)
    BuiltinType.BOOL.value.add_implicit_cast(
        BuiltinType.INT_8.value.can_implicit_cast_to)
    BuiltinType.UINT_64.value.add_implicit_cast(
        [BuiltinType.UINT_64.value, BuiltinType.FLOAT_32.value, BuiltinType.FLOAT_64.value])
    BuiltinType.UINT_32.value.add_implicit_cast(
        BuiltinType.INT_64.value.can_implicit_cast_to)
    BuiltinType.UINT_32.value.add_implicit_cast(BuiltinType.UINT_32.value)
    BuiltinType.UINT_16.value.add_implicit_cast(BuiltinType.UINT_32.value.can_implicit_cast_to)
    BuiltinType.UINT_16.value.add_implicit_cast(
        BuiltinType.INT_32.value.can_implicit_cast_to)
    BuiltinType.UINT_16.value.add_implicit_cast(BuiltinType.UINT_16.value)
    BuiltinType.UINT_8.value.add_implicit_cast(BuiltinType.UINT_8.value)
    BuiltinType.UINT_8.value.add_implicit_cast(
        BuiltinType.INT_16.value.can_implicit_cast_to)
    
    for typ in BuiltinType.get_types():
        CustomType.known_types[typ.ident] = typ
    # add shortcut to char as i8
    CustomType.known_types['char'] = BuiltinType.UINT_8.value
    
    BuiltinType.BOOL.value._op_functions[UnaryOperation.LOGIC_NOT] = lambda x: not x
    BuiltinType.UINT_8.value._op_functions[UnaryOperation.LOGIC_NOT] = lambda x: x ^ 0xFF
    BuiltinType.INT_8.value._op_functions[UnaryOperation.LOGIC_NOT] = lambda x: x ^ 0xFF
    BuiltinType.UINT_16.value._op_functions[UnaryOperation.LOGIC_NOT] = lambda x: x ^ 0xFFFF
    BuiltinType.INT_16.value._op_functions[UnaryOperation.LOGIC_NOT] = lambda x: x ^ 0xFFFF
    BuiltinType.UINT_32.value._op_functions[UnaryOperation.LOGIC_NOT] = lambda x: x ^ 0xFFFFFFFF
    BuiltinType.INT_32.value._op_functions[UnaryOperation.LOGIC_NOT] = lambda x: x ^ 0xFFFFFFFF
    BuiltinType.UINT_64.value._op_functions[UnaryOperation.LOGIC_NOT] = lambda x: x ^ 0xFFFFFFFFFFFFFFFF
    BuiltinType.INT_64.value._op_functions[UnaryOperation.LOGIC_NOT] = lambda x: x ^ 0xFFFFFFFFFFFFFFFF
    for t1 in numeric_and_bool:
        t1._op_functions[UnaryOperation.BOOL_NOT] = lambda x: not x
        if t1 != BuiltinType.BOOL.value:
            t1._op_functions[UnaryOperation.MINUS] = lambda x : -x
            t1._op_functions[UnaryOperation.INCREMENT] = lambda x : x+1
            t1._op_functions[UnaryOperation.DECREMENT] = lambda x : x-1            
        for t2 in numeric_and_bool:
            #set +,-,* and / operator types
            for op in {BinaryOperation.PLUS, BinaryOperation.MINUS, BinaryOperation.TIMES,
                       BinaryOperation.DIVIDE}:
                if t1 == t2 and t1 == BuiltinType.BOOL.value:
                    #bool operators will be converted to char as operators on bool values will most likely over/underflow
                    t1._operators[op][t2] = BuiltinType.INT_8.value
                else:
                    try:
                        t1._operators[op][t2] = Type.implicit_cast(t1,t2)
                    except:
                        pass #skip operations between non corresponding types
            t1._op_functions.update({(BinaryOperation.PLUS, t2):lambda l,r:l+r,
                                     (BinaryOperation.MINUS, t2):lambda l,r:l-r,
                                     (BinaryOperation.TIMES, t2):lambda l,r:l*r,
                                     (BinaryOperation.DIVIDE, t2):lambda l,r:l/r})
            #for t2 not a float set mod and shift
            if t2 not in {BuiltinType.FLOAT_32.value, BuiltinType.FLOAT_64.value, BuiltinType.BOOL}:
                # set left and right shift ops for t2 integer
                t1._operators[BinaryOperation.SHIFT_LEFT][t2] = t1
                t1._op_functions[(BinaryOperation.SHIFT_LEFT, t2)] = lambda l, r: l << r
                t1._operators[BinaryOperation.SHIFT_RIGHT][t2] = t1
                t1._op_functions[(BinaryOperation.SHIFT_RIGHT, t2)] = lambda l, r: l >> r
                # for t2 not a float set modulus, XOR and AND/OR operators (valid on integers and bool)
                if t1 not in {BuiltinType.FLOAT_32.value, BuiltinType.FLOAT_64.value, BuiltinType.BOOL}:
                    try:
                        t1._operators[BinaryOperation.MOD][t2] = Type.implicit_cast(t1,t2)
                        t1._op_functions[(BinaryOperation.MOD, t2)] = lambda l, r: l % r
                        t1._operators[BinaryOperation.XOR][t2] = Type.implicit_cast(t1,t2)
                        t1._op_functions[(BinaryOperation.XOR, t2)] = lambda l, r: l ^ r
                        t1._operators[BinaryOperation.LOGIC_AND][t2] = Type.implicit_cast(
                            t1, t2)
                        t1._op_functions[(
                            BinaryOperation.LOGIC_AND, t2)] = lambda l, r: l & r
                        t1._operators[BinaryOperation.LOGIC_OR][t2] = Type.implicit_cast(t1,t2)
                        t1._op_functions[(BinaryOperation.LOGIC_OR, t2)] = lambda l, r: l | r
                    except:
                        pass  # skip operations between incompatible types
                    t1._operators[BinaryOperation.BOOL_AND][t2] = BuiltinType.BOOL.value
                    t1._op_functions[(BinaryOperation.BOOL_AND, t2)] = lambda l, r: bool(l) and bool(r)
                    t1._operators[BinaryOperation.BOOL_OR][t2] = BuiltinType.BOOL.value
                    t1._op_functions[(BinaryOperation.BOOL_OR, t2)] = lambda l, r: bool(l) or bool(r)
            # and comparators 
            for op in {BinaryOperation.BOOL_EQ, BinaryOperation.BOOL_GEQ, BinaryOperation.BOOL_GT,
                       BinaryOperation.BOOL_LEQ, BinaryOperation.BOOL_LT, BinaryOperation.BOOL_NEQ}:
                t1._operators[op][t2] = BuiltinType.BOOL.value
            t1._op_functions.update({
                (BinaryOperation.BOOL_EQ, t2): lambda l, r: l == r,
                (BinaryOperation.BOOL_GEQ, t2): lambda l,r: l>=r,
                (BinaryOperation.BOOL_GT, t2): lambda l,r: l>r,
                (BinaryOperation.BOOL_LEQ, t2): lambda l,r: l<=r,
                (BinaryOperation.BOOL_LT, t2): lambda l,r: l<r,
                (BinaryOperation.BOOL_NEQ, t2): lambda l,r: l!=r
            })
      
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
    TTreeElem._known_func_scope.setdefault((BuiltinType.MISSING.value, 'print'), -2)
    root_vars.setdefault('print', ItemAndLoc(FunctionType(BuiltinType.VOID.value, [BuiltinType.STRING.value]), None))
    
class ElemUUID:
    _next = int(randbytes(2).hex(), 16)
    def __init__(self) -> None:
        tmp = self.peekNext() #gets next value
        ElemUUID._next = randint(tmp+1, tmp+1000)
        object.__setattr__(self, "_value", tmp) #Sets attr which is readonly
    def __setattr__(self, __name: str, __value) -> None:
        raise AttributeError("Cannot set the attribute. All values are read only after __init__",
                             name=__name, obj=__value)
    @staticmethod
    def peekNext():
        return ElemUUID._next
    @property
    def uuid(self):
        return object.__getattribute__(self, "_value")
    
    def __str__(self) -> str:
        return str(self.uuid)
    
    def __repr__(self) -> str:
        return str(self)

    
class TTreeElem:    
    _known_func_scope: dict[tuple[Type, str], int] = {}
    
    def __init__(self, elem: PTreeElem, parent:"TTreeElem|None"=None) -> None:
        #unique ID used as hash
        self._UUID = ElemUUID()
        
        self.parent = parent
        self.location = elem.location
        self.location_end = elem.location_end
        if not hasattr(self, 'errors'):
            self.errors:list[TypingError] = []
        if not hasattr(self, '_known_vars_type'):
            self._known_vars_type:dict[str,ItemAndLoc] = {}
        if not hasattr(self, 'typ'):
            self.typ:Type = BuiltinType.MISSING.value
            
    @property
    def breakable(self):
        """True if it is syntactically correct to 'break' from this node"""
        node = self
        while not node is None:
            if isinstance(node, (TFuncDecl, TClassDecl,)):
                return False # can't break from a function or class
            if isinstance(node, (TFor, TForeach, TEnum, TWhile)):
                return True # Break allowed in for, while and enums
            node = node.parent
        #reached top without being breakable so not breakable
        return False
            
    @property
    def continueable(self):
        """True if it is syntactically correct to 'continue' from this node"""
        node = self
        while not node is None:
            if isinstance(node, (TFuncDecl, TEnum, TClassDecl,)):
                return False  # can't break from a function or class or enum
            if isinstance(node, (TFor, TForeach, TWhile)):
                return True  # Break allowed in for, while and enums
            node = node.parent
        # reached top without being breakable so not breakable
        return False

    @property
    def returnable(self):
        """True if it is syntactically correct to 'return' from this node"""
        node = self
        while not node is None:
            if isinstance(node, TFuncDecl):
                return True  # Can return from a function (includes constructors)
            node = node.parent
        # reached top without being breakable so not breakable
        return False
            
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

    @property
    def UUID(self) -> int:
        return self._UUID.uuid
        
    def add_known_id(self, id:str, typ:Type, location:Location|None=None):
        var = self.find_corresponding_var_typ(id)
        if var is not None:
            p = self
            while p is not None:
                if id in p._known_vars_type and location != p._known_vars_type[id].location:
                    raise TypingError(f"The identifier '{id}' at location {location} "+
                                      "has already been defined in this scope at location "+
                                          str(p._known_vars_type[id].location))
                p = p.parent
        self._known_vars_type[id] = ItemAndLoc(typ,location)
        
    def add_known_func_scope(self, typ:Type, id:str, scope_uuid:int):
        TTreeElem._known_func_scope[(typ,id)] = scope_uuid
    
    def find_corresponding_scope_id(self, typ: Type|None, id: str) -> int:
        """Gets the UUID of the corresponding function body given the function's name and parent's type. 
        Eg. "abdc".SubString(0,2), string is the parent type and SubString is the function name (or id).

        Args:
            typ (Type | None): The parent type of the function. It should be None or BuiltinType.Missing.value if the function is standalone (not declared in a class or a function like 'print')
            id (str): The name of the called function

        Returns:
            int: The uuid pointing to the body of the function. Or returns -1 if the function was not found. NB: Other stdlib functions have negative uuids like 'print' has the uuid -2
        """
        if typ is None:
            typ = BuiltinType.MISSING.value
        return TTreeElem._known_func_scope.get((typ,id), -1)
    
    def find_corresponding_var_typ(self, id:str) -> Type|None:
        if id in self._known_vars_type:
            return self._known_vars_type[id].item
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
    
    def __hash__(self) -> int:
        return self.UUID
    
    def __eq__(self, __value: object) -> bool:
        if not isinstance(__value, TTreeElem):
            return False
        return hash(__value) == hash(self) and self.location == __value.location


class TStatement(TTreeElem):
    @staticmethod
    def get_correct_TTreeElem(statement):
        if isinstance(statement, PVarDecl):
            #PVarDecl becomes TAssign
            # because the TVarDecl decleration is done at the beginning of the scope. 
            # Now it just needs the assignment statement to be done at the correct time
            # (Need to preserve the order of operations)
            return TAssign
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
        if isinstance(expr, JSON_Val):
            if expr._val is None:
                return TNull
            else:
                return TBool
        if isinstance(expr, PlValue):
            return TlValue.get_correct_TTreeElem(expr)
        if isinstance(expr, PAssign):
            return TAssign
        if isinstance(expr, PCopyAssign):
            return TCopyAssign
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
        if isinstance(expr, PNull):
            return TNull
        raise TypingError(f"Cannot find corresponding type for {type(expr)} (error at location {expr.location})")
        
    def __init__(self, elem: PTreeElem, parent: TTreeElem):
        super().__init__(elem, parent)
        self.typ = BuiltinType.MISSING.value

class TVar(TExpression):
    def __init__(self, elem:PIdentifier, parent:TTreeElem, parent_typ:Type|None=None):
        super().__init__(elem, parent)
        self.identifier = elem.identifier
        self.typ = BuiltinType.MISSING.value
        if isinstance(parent_typ, Type):
            if self.identifier in parent_typ.methods:
                func_typ = parent_typ.methods[self.identifier]
                self.typ = func_typ.return_type
            else:
                self.typ = parent_typ.fields.get(elem.identifier, BuiltinType.MISSING.value)
        else:
            typ = self.find_corresponding_var_typ(elem.identifier)
            if typ is not None:
                self.typ = typ
        if self.typ == BuiltinType.MISSING.value:
            self.errors.append(TypingError(f"Unknown type for identifier: '{self.identifier}' at location {self.location}"))

class TScope(TTreeElem):
    def __init__(self, elem:PScope, parent:TTreeElem|None):
        super().__init__(elem, parent)
        if isinstance(elem, PSkip):
            return
        #define global functions (just names and return types)
        for func in elem.funcDecl:
            if isinstance(func, TConstructor):
                continue
            try:
                self.add_known_id(func.id.identifier,
                                  FunctionType(
                                      CustomType.get_type_from_ptype(func.returnType),
                                      [CustomType.get_type_from_ptype(arg.typ) for arg in func.args]),
                                  func.id.location)
            except TypingError as e:
                self.errors.append(e)
                
        self.varDecl = [TVarDecl(pvardecl, self) for pvardecl in elem.varDecl]
        self.funcDecl = [TFuncDecl(pfuncdecl, self) if not isinstance(pfuncdecl, TConstructor) else TConstructor(pfuncdecl, self) for pfuncdecl in elem.funcDecl]
        self.statements:list[TTreeElem] = []
        for pstatement in elem.statements:
            try:
                self.statements.append(TStatement.get_correct_TTreeElem(pstatement)(pstatement, self))
            except TypingError as e:
                self.errors.append(e)

class TModule(TScope):
    def __init__(self, elem: PModule):
        self._known_vars_type:dict[str,ItemAndLoc] = {}
        self.errors: list[TypingError] = []
        self.parent = None
        setup_builtin_types(self._known_vars_type)
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
        self._known_vars_type['this'] = ItemAndLoc(
            self.typ, elem.identifier.location)
        self.fields = [TVarDecl(field, self) for field in elem.inner_scope.varDecl]
        self.methods = [TFuncDecl(pfuncdecl, self) for pfuncdecl in elem.inner_scope.funcDecl if not isinstance(pfuncdecl, PConstructor)]
        self.constructor = self._setup_constructor(elem.inner_scope.funcDecl, elem.inner_scope.varDecl)
        self.typ._constructor_uuid = self.constructor.body.UUID
        #set class type fields, methods and size in memory
        if self.typ != BuiltinType.MISSING.value:
            self.typ.size = 8+sum([f.typ.size if f.typ.is_primitive else 8 for f in self.fields])
            self.typ.methods.update({m.id:m.typ for m in self.methods})
            self.typ.methods.update({TConstructor._ID:self.constructor.typ,})
            self.typ.fields.update({f.identifier:f.typ for f in self.fields})
    
    def _setup_constructor(self, methods:list[PFuncDecl], fields:list[PVarDecl]) -> "TConstructor":
        """Returns class's constructor. Is none is defined it builds a default constructor """
        constructor:TConstructor|None = None
        for func in methods:
            if isinstance(func, PConstructor):
                constructor = TConstructor(func, self)
                break
        if constructor is None:
            constructor = TConstructor(PConstructor(self.location, PType(self.location,self.typ.ident, self.location),
                                                    PIdentifier(self.location,self.identifier, self.location),
                                                    list(),
                                                    PScope(self.location,functions=None, varDecl=None,statements=None, last_token_end=self.location))
                                       ,self)
        for field in fields:
            #assign default field values defined in field decleration 
            if not isinstance(field.init_value, PNull):
                constructor.body.statements.insert(0,TAssign(PAssign(self.location, field.identifier, field.init_value),constructor.body))
            else: #otherwise set to null or 0 if primitive
                constructor.body.statements.insert(0, TAssign(
                    PAssign(self.location, field.identifier,
                            PNumeric(self.location, 0) if CustomType.get_type_from_ptype(field.typ).is_primitive
                            else PNull(self.location, self.location)),
                    constructor.body))
            
        return constructor
        
    def get_type(self) -> Type:
        return self.typ

class TBool(TExpression):
    def __init__(self, elem: PBool, parent: TTreeElem, parent_typ: Type | None = None):
        super().__init__(elem, parent)
        if isinstance(elem, JSON_Val):
            self.value = elem._val
        else:
            self.value = elem.value._val
        self.typ = BuiltinType.BOOL.value
        
    def __str__(self) -> str:
        return repr(self)
    
    def __repr__(self):
        val = "true" if self.value else "false"
        return f'{{"{self.__class__.__name__}" : {val}}}'

class TNull(TExpression):
    def __init__(self, elem: PNull, parent: TTreeElem, parent_typ: Type = BuiltinType.MISSING.value):
        super().__init__(elem, parent)
        self.value = None
        self.typ = parent_typ
        if parent_typ.is_primitive:
            self.errors.append(TypingError(
                f"Error at {self.location}. Primitive types (like {parent_typ}) are not nullable."))

    def __str__(self) -> str:
        return repr(self)

    def __repr__(self):
        return f'{{"{self.__class__.__name__}" : null}}'

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
        self.initial_value = JSON_Val(None) if isinstance(elem.init_value, JSON_Val) else\
                    TExpression.get_correct_TTreeElem(elem.init_value)(elem.init_value, self)
        if self.typ != BuiltinType.MISSING.value:
            if isinstance(self.initial_value, TNull):
                pass #TODO
            elif self.initial_value != None and not isinstance(self.initial_value, TNull):
                try:
                    CustomType.implicit_cast(self.initial_value.typ, self.typ)
                except TypingError as e:
                    self.errors.append(e)
            try:
                parent.add_known_id(self.identifier, self.typ, elem.identifier.location)
            except TypingError as e:
                self.errors.append(e)                

class TFuncDecl(TTreeElem):
    def __init__(self, elem: PFuncDecl, parent: TTreeElem):
        super().__init__(elem, parent=parent)
        self.id = elem.id.identifier
        #gets the parent class if there is one. Otherwise the function is standalone (parent type is builtin.missing)
        self.parent_class_typ = BuiltinType.MISSING.value
        tmp_parent = parent
        while not tmp_parent is None:
            if isinstance(tmp_parent, TClassDecl):
                self.parent_class_typ = tmp_parent.typ
                del tmp_parent
                break
            tmp_parent = tmp_parent.parent
        self.typ = FunctionType(BuiltinType.MISSING.value,[])
        self.returnType = BuiltinType.MISSING.value
        self.args = [TVarDecl(v, self) for v in elem.args]
        try:
            self.returnType = Type.get_type_from_ptype(elem.returnType)
            arg_types = [arg.typ for arg in self.args]
            self.typ = FunctionType(self.returnType, arg_types)
        except TypingError as e:
            self.errors.append(e)
        try:
            parent.add_known_id(elem.id.identifier, self.typ, elem.id.location)
        except TypingError as e:
            self.errors.append(e)
        parent.add_known_func_scope(self.parent_class_typ, self.id,
                                    ElemUUID.peekNext()) #adds the Scope ID (next used uuid)
        self.body = TScope(elem.body, self)


class TConstructor(TFuncDecl):
    _ID = "<CONSTRUCTOR>"
    
    def __init__(self, elem: PConstructor, parent: TTreeElem):
        elem.id.identifier = TConstructor._ID
        super().__init__(elem, parent=parent)

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
                self.typ = BuiltinType.INT_8.value
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
        self.left = TExpression.get_correct_TTreeElem(elem.left)(elem.left, self, parent_typ=parent_typ)
        self.rvalue = TExpression.get_correct_TTreeElem(elem.rvalue)(elem.rvalue, self, parent_typ=self.left.typ)
        self.typ:Type = self.rvalue.typ
        

class TBinOp(TExpression):
    def __init__(self, elem:PBinOp, parent:TTreeElem, parent_typ:Type|None=None):
        super().__init__(elem, parent)
        self.left = TExpression.get_correct_TTreeElem(elem.left)(elem.left, self)
        self.rvalue = TExpression.get_correct_TTreeElem(elem.rvalue)(elem.rvalue, self)
        self.operation = elem.op
        self.typ = BuiltinType.MISSING.value
        if self.operation in {BinaryOperation.ASSIGN, BinaryOperation.COPY}:
            if isinstance(elem.rvalue, PNull):
                self.rvalue = TNull(elem.rvalue, self,self.left.typ)
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
            
class TAssign(TBinOp):
    def __init__(self, elem: PBinOp | PVarDecl, parent: TTreeElem, parent_typ: Type | None = None):
        if isinstance(elem, PVarDecl):
            elem = PBinOp(elem.location, left=elem.identifier,
                          op=BinaryOperation.ASSIGN,
                          right=elem.init_value._val if isinstance(elem.init_value, JSON_Val) else elem.init_value,
                          last_token_end=elem.location_end)
        super().__init__(elem, parent, parent_typ)
        
class TCopyAssign(TBinOp):
    def __init__(self, elem: PBinOp, parent: TTreeElem, parent_typ: Type | None = None):
        super().__init__(elem, parent, parent_typ)

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
        self.function_name:str = self.rvalue.identifier
        #find return value type
        self.typ = BuiltinType.MISSING.value
        func_typ = self.find_corresponding_var_typ(self.function_name)
        #if it's a known id
        self.function_body_uuid = 0
        if func_typ is not None:
            if isinstance(func_typ, FunctionType): # it's a function
                self.typ = func_typ.return_type
                self.function_body_uuid = self.find_corresponding_scope_id(parent_typ, self.function_name)
            else:
                self.errors.append(TypingError(f"'{self.function_name}' is not a callable function. Problem at location {self.location}"))
                return
        elif isinstance(parent_typ, Type) and self.function_name in parent_typ.methods:
            func_typ = parent_typ.methods[self.function_name]
            self.typ = func_typ.return_type
            self.function_body_uuid = self.find_corresponding_scope_id(parent_typ, self.function_name)
        else: #check if builtin
            self.errors.append(TypingError(f"Attempts to call unknown function '{self.function_name}' at location {elem.function_id.location}"))
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
        if not self.returnable:
            self.errors.append(TypingError(f'return at location {self.location} is not valid in this context'))
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
        if not self.continueable:
            self.errors.append(TypingError(
                f'continue at location {self.location} is not valid in this context'))

class TBreak(TStatement):
    def __init__(self, elem:PBreak, parent:TTreeElem):
        super().__init__(elem, parent)
        if not self.breakable:
            self.errors.append(TypingError(
                f'break at location {self.location} is not valid in this context'))


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
        if self.new_obj.is_primitive:
            self.errors.append(TypingError(f"Cannot create new primitive object. The new keyword must be used with a defined class type (or string), not {self.new_obj}."))
        if self.new_obj == BuiltinType.VOID.value:
            self.errors.append(TypingError("Cannot create new void item. It is not a reference object type."))
        self.typ = self.new_obj
        self.args = [TExpression.get_correct_TTreeElem(arg)(arg, self) for arg in elem.args]

        self.constructor = self.typ.methods.get(TConstructor._ID, FunctionType(BuiltinType.MISSING.value, []))
        if self.constructor.return_type == BuiltinType.MISSING.value:
            self.errors.append(TypingError(f"Unable to find constructor for type '{self.typ}' at location {self.location}"))
            return

        if len(self.constructor.args_type) != len(self.args):
            self.errors.append(TypingError(
                f"Got {len(self.args)} arguments but expected {len(self.constructor.args_type)} at location {self.location}"))
        for expected, gotten in zip(self.constructor.args_type, self.args):
            if expected not in gotten.typ.can_implicit_cast_to:
                self.errors.append(TypingError(
                    f"Expected type {expected} but got {gotten.typ} at location {gotten.location}"))        


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