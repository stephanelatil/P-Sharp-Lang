from typing_to_cfg import *
import numpy as np

#TODO should all Membox objects be ClassVar? (special care for value objects)
# it would simplify method calls like ToString etc.

class MemBox:
    """
    A place in memory where a value is stored
    A simple use would be something like: i32 a = b;
    which is translated to a_MemBox.set_val(b_MemBox.get_val())
    
    It greatly simplifies accessing objects. i.e. a.x = 3
    is translated to a_Membox.get_field('x').set_val(3)
    """
    def __init__(self, val) -> None:
        self._val = val
    def set_val(self, val) -> None:
        if isinstance(val, MemBox):
            val = val.get_val()
        self._val = val

    @staticmethod
    def default_value(*args):
        raise NotImplementedError('This method should be implemented')
    @property
    def type(self):
        return type(self)
    def get_val(self):
        return self._val
    def cast(self, new_typ):
        raise NotImplementedError("Method should be overridden")
    def get_method_callable(self, identifier:str):
        pass  # TODO Should return a callable for the method.
    @property
    def is_null(self) -> bool:
        raise NotImplementedError("Method should be overridden")

class NullVar(MemBox):
    def __init__(self) -> None:
        super().__init__(None)
    @staticmethod
    def default_value(*args):
        return None

    def cast(self, new_typ):
        raise RuntimeError('Cannot cast null value')

    def get_method_callable(self, identifier: str):
        raise RuntimeError("Null ptr error")

    @property
    def is_null(self) -> bool:
        return True

class BoolVar(MemBox):
    @staticmethod
    def default_value(*args):
        """Return the default internal value

        Returns:
            bool: False
        """
        return False
        
    def __init__(self, val:bool) -> None:
        assert (isinstance(val, bool))
        super().__init__(val)
    def set_val(self, val) -> None:
        assert(isinstance(val, bool))
        return super().set_val(val)
    def get_val(self) -> bool:
        return super().get_val()
    def cast(self, new_typ):
        if new_typ in FixedSizeNumVar._typ_dict:
            return FixedSizeNumVar(int(self._val), new_typ)
        elif new_typ == 'bool':
            return self
        raise TypeError(f"Cannot cast bool to {new_typ}")
    @property
    def is_null(self):
        return False
    
class ArrayVar(MemBox):
    def __init__(self, baseClass:type[MemBox], val=None, size=0) -> None:
        """_summary_

        Args:
            baseClass (Membox): The class of the type to be placed in the array
            size (int, optional): _description_. Defaults to 0.
            val (list[Membox] | None, optional): The value to fill the internal value with.
            If None is given it will take the default_value()
        """
        assert(isinstance(size, int) and size >= 0)
        self.size = size
        self.baseClass = baseClass
        super().__init__(val)

    @staticmethod
    def default_value(baseClass:type[MemBox], size=-1):
        """Return the default internal value

        Returns:
            None|list: None if no size if given (or if size <0).
            Otherwise gives a list of default valuesfor the given type
        """
        if size < 0:
            return None
        return [baseClass.default_value(size)]
        
    def set_index_val(self, val, index):
        assert(isinstance(index, int))
        assert (index >= 0 and index < self.size)
        super().get_val()[index].set_val(val)
    def get_index_val(self, index):
        assert (isinstance(index, int))
        assert (index >= 0 and index < self.size)
        return super().get_val()[index].get_val()
    @property
    def is_null(self):
        return self.get_val() == None
            

class StringVar(MemBox):
    def __init__(self, val:str|None) -> None:
        assert (isinstance(val, str))
        super().__init__(val)

    @staticmethod
    def default_value(*args):
        """Return the default internal value (here 'null')

        Returns:
            None: None
        """
        return None
    
    def set_val(self, val) -> None:
        assert (isinstance(val, str))
        return super().set_val(val)
    def get_val(self) -> str|None:
        return super().get_val()
    def cast(self, new_typ):
        raise NotImplementedError(
            "Strings can't be casted yet, as they are a reference type")
    @property
    def is_null(self):
        return self.get_val() == None

class ClassVar(MemBox):
    def __init__(self, val: dict|None, typ=None) -> None:
        super().__init__(val)
        if not typ is None:
            self._typ = typ
            self._val['META-type'] = typ
        else:
            self._typ = self._val.get('META-type')

    @staticmethod
    def default_value(*args):
        """Return the default internal value (here 'null')

        Returns:
            None: None
        """
        return None
    
    def get_val(self):
        return self._val
    def set_val(self, val:dict):
        assert(val.get('META-type') == self._typ)
        self._val = val

    def get_field(self, field: str) -> MemBox:
        field = self._val.get(field, None)
        if not isinstance(field, MemBox):
            raise AttributeError(f'Unable to find field {field}')
        return field

    def set_field(self, field: str, value:MemBox):
        field_var = self.get_field(field)
        assert isinstance(value, MemBox)
        field_var.set_val(value.get_val())
    def cast(self, new_typ):
        raise NotImplementedError("Cannot cast a user defined class yet")
    @property
    def is_null(self):
        return self.get_val() == None

class FixedSizeNumVar(MemBox):
    _typ_dict = {'u8': 'uint8', 'i8': 'int8', 'u16': 'uint16', 'i16': 'int16',
                 'u32': 'uint32', 'i32': 'int32', 'u64': 'uint64', 'i64': 'int64',
                 'f32': 'float32', 'f64': 'float64'}
    
    def __init__(self, value: int | float = 0, typ='i32') -> None:
        assert isinstance(value, (int, float)) or np.issubdtype(
            value, np.integer) or np.issubdtype(value, np.floating)
        self._typ = self._typ_dict[typ]
        super().__init__(np.zeros((1, 1), dtype=self._typ))
        self.set_val(value)

    @staticmethod
    def default_value(*args):
        """Return the default internal value

        Returns:
            float: 0
        """
        return 0
    
    def get_val(self) -> int|float:
        return self._val[0,0]
    def set_val(self, val):
        assert isinstance(val, (int, float)) or np.issubdtype(val, np.integer) or np.issubdtype(val, np.floating)
        self._val[0,0] = val        
    def cast(self, new_typ) -> MemBox:
        if new_typ == self._typ:
            return self
        if new_typ in self._typ_dict:
            obj = FixedSizeNumVar(self._val[0,0], self._typ)
            obj._val.astype(self._typ_dict[new_typ], casting='unsafe')
            return obj
        elif new_typ == 'bool':
            return BoolVar(self._val[0,0] == 0)
        raise TypeError(f"Cannot cast {self._typ} to {new_typ}")

    @property
    def is_null(self):
        return False

class BuiltinFunctions:
    @staticmethod
    def builtin_ToString(this: MemBox):
        if isinstance(this, StringVar):
            return this
        elif isinstance(this, FixedSizeNumVar):
            return StringVar(str(this.get_val()))
        elif isinstance(this, BoolVar):
            return StringVar(str(this.get_val()))
        else:
            print(f"Error: type {this.type.__class__}")

    @staticmethod
    def builtin_print(s: StringVar):
        assert (isinstance(s, StringVar))
        print(s.get_val(), end='')

class UserDefinedClass:
    _classes:dict[Type, CfgClassDecl] = {}
    #used for memoisation
    _empty_object_dicts: dict[str, dict] = {}
    
    @staticmethod
    def build_empty(typ:Type) -> ClassVar:
        """_summary_ Creates a new class dict with empty fields. Then the constructor CFG must populate them

        Returns:
            dict[str,None|bool|str|FixedSizeNum|dict|CfgFuncDecl]: A dict representing the an instance of the class
        """
        classDecl = UserDefinedClass._classes.get(typ, None)
        if classDecl is None:
            raise RuntimeError(f"Cannot define new empty class dict for class with type {typ}")
        if classDecl.identifier in UserDefinedClass._empty_object_dicts:
            return ClassVar(deepcopy(UserDefinedClass._empty_object_dicts.get(classDecl.identifier)), classDecl.typ)
        new_obj_dict:dict[str,str|MemBox|CfgNode] = {"META-type":classDecl.identifier}
        
        #set all fields and methods
        for method in classDecl.methods:
            new_obj_dict[method.identifier] = method.context.known_functions[method.body.UUID].get(method.context)
        for field in classDecl.fields:
            val:MemBox = ClassVar(None, field.typ)
            if field.typ.ident == 'string':
                val = StringVar(StringVar.default_value())
            elif field.typ.ident == 'bool':
                val = BoolVar(BoolVar.default_value())
            if field.typ.ident in FixedSizeNumVar._typ_dict:
                val = FixedSizeNumVar(
                    FixedSizeNumVar.default_value(), field.typ.ident)
            new_obj_dict[field.identifier] = val
        UserDefinedClass._empty_object_dicts[classDecl.identifier] = new_obj_dict
        #return classvar with default values for all fields
        return ClassVar(deepcopy(new_obj_dict), classDecl.typ)

class Scope:
    """
    _summary_ Defines a scope. A scope has defined functions and variables
    """
    def __init__(self, vars:list[CfgVarDecl], functions:list[CfgFuncDecl]) -> None:
        self.declared_vars: dict[str, MemBox] = {
            v.identifier: None for v in vars}
        self.declared_functions: dict[str, CfgFuncDecl] = {f.identifier:f for f in functions}
        self.must_break = False
        self.must_continue = False
        self.must_return = False
        
    def set_return(self):
        self.must_return = True
        
    def set_continue(self):
        self.must_continue = True
        
    def set_break(self):
        self.must_return = True

    def unset_return(self):
        self.must_return = False

    def unset_continue(self):
        self.must_continue = False

    def unset_break(self):
        self.must_return = False

class ScopeStack:
    def __init__(self, vars: list[CfgVarDecl], functions: list[CfgFuncDecl]) -> None:
        self.stack:list[Scope] = [Scope(vars, functions)]
        self._return_val = None
        
    @property
    def top(self) -> Scope:
        if len(self.stack) > 0:
            return self.stack[0]
        raise ValueError("Stack is empty!")
        
    @property
    def last(self) -> Scope:
        if len(self.stack) > 0:
            return self.stack[-1]
        raise ValueError("Stack is empty!")
    
    @property
    def has_return_val(self) -> bool:
        return not self._return_val is None
    
    def set_return_value(self, value:MemBox) -> None:
        self._return_val = value
        
    def pop_return_value(self) -> MemBox:
        if self._return_val is None:
            raise RuntimeError("Attempting to get return value but it has already been popped (Or void function)")
        val = self._return_val
        self._return_val = None
        return val
    
    def push(self, vars: list[CfgVarDecl], functions: list[CfgFuncDecl])-> None:
        self.stack.append(Scope(vars, functions))
        
    def pop(self, propagate_return_break_continue:bool=True) -> Scope:
        scope = self.stack.pop()
        if propagate_return_break_continue:
            if scope.must_return:
                self.last.set_return()
            if scope.must_continue:
                self.last.set_continue()
            if scope.must_break:
                self.last.set_break()
        return scope
        
    def get_func(self, identifier):
        for i in range(-1, -len(self.stack)-1, -1):
            func = self.stack[i].declared_functions.get(identifier, None)
            if func:
                return func
        raise AttributeError("Cannot find the function from it's ID in the scope stack", name=identifier, obj=None)
    
    def get_var(self, identifier) -> MemBox:
        for i in range(-1, -len(self.stack)-1, -1):
            var = self.stack[i].declared_vars.get(identifier, None)
            if var:
                return var
        raise AttributeError(
            "Cannot find the function from it's ID in the scope stack", name=identifier, obj=None)

def type_to_membox(typ:Type) -> type[MemBox]:
    if typ.ident == 'bool':
        return BoolVar
    elif typ.ident in FixedSizeNumVar._typ_dict:
        return FixedSizeNumVar
    elif typ.ident == 'string':
        return StringVar
    elif isinstance(typ, ArrayType):
        return ArrayVar
    else:
        return ClassVar

class CfgWrapper:
    context:Context = Context()
    
    def __init__(self, node: CfgNode) -> None:
        self.node = node

    def execute(self, stack:ScopeStack, *args, **kwargs) -> None|MemBox:
        if isinstance(self.node, CfgConstructor):
            return #nothing to do just a declaration

        elif isinstance(self.node, CfgNewObject):
            #parse args
            constructor_arguments = [CfgWrapper(arg).execute(stack) for arg in self.node.args]
            function = self.node.constructor.get(self.context)
            assert isinstance(function, CfgConstructor)
            stack.push([],[])
            for varDecl, arg in zip(function.args, constructor_arguments):
                if not arg is None:
                    stack.last.declared_vars[varDecl.identifier] = arg
            assert isinstance(function.typ, FunctionType)
            class_dict = UserDefinedClass.build_empty(self.node.typ)
            stack.last.declared_vars['this'] = ClassVar(class_dict, typ=function.typ.return_type)
            #run and return object from constructor
            CfgWrapper(function.body).execute(stack)
            this = stack.get_var('this')
            stack.pop(False)
            return this

        elif isinstance(self.node, CfgCast):
            original_val = CfgWrapper(self.node.old_val).execute(stack)
            #get old value and attempt to cast to new type
            if original_val is None:
                raise ValueError(f'Cannot cast None. Code at location {self.node.old_val.location} returns no value')
            return original_val.cast(self.node.typ.ident)

        elif isinstance(self.node, CfgAssign):
            rvalue = CfgWrapper(self.node.rvalue).execute(stack)
            if rvalue is None:
                raise ValueError(f'Cannot evaluate code at location {self.node.rvalue.location}, it returns no value')
            lvalue = CfgWrapper(self.node.lvalue).execute(stack)
            if lvalue is None:
                raise ValueError(
                    f'Cannot evaluate code at location {self.node.lvalue.location}, it is not an lvalue')
            lvalue.set_val(rvalue.get_val())

        elif isinstance(self.node, CfgBinOp):
            left = CfgWrapper(self.node.left).execute(stack)
            if left is None:
                raise ValueError(
                    f'Error evaluating code at location {self.node.left.location}, it returns no value')
            right = CfgWrapper(self.node.right).execute(stack)
            if right is None:
                raise ValueError(
                    f'Error evaluating code at location {self.node.right.location}, it returns no value')
            op_func = self.node.left.typ._op_functions[(self.node.operation, self.node.right.typ)]
            if self.node.typ.ident in FixedSizeNumVar._typ_dict:
                return FixedSizeNumVar(op_func(left.get_val(), right.get_val()), self.node.typ.ident)
            elif self.node.typ.ident == 'bool':
                return BoolVar(op_func(left.get_val(), right.get_val()))
            elif self.node.typ.ident == 'string':
                return StringVar(op_func(left.get_val(), right.get_val()))

        elif isinstance(self.node, CfgVarDecl):
            #add var to stack but do not initialize. It will be done with its first CfgAssign
            if self.node.typ.ident == 'bool':
                stack.last.declared_vars[self.node.identifier] = BoolVar(BoolVar.default_value())
            elif self.node.typ.ident in FixedSizeNumVar._typ_dict:
                stack.last.declared_vars[self.node.identifier] = FixedSizeNumVar(
                    FixedSizeNumVar.default_value(), typ=self.node.typ.ident)
            elif self.node.typ.ident == 'string':
                stack.last.declared_vars[self.node.identifier] = StringVar(
                    StringVar.default_value())
            elif isinstance(self.node.typ, ArrayType):
                stack.last.declared_vars[self.node.identifier] = ArrayVar(MemBox)
            else:
                stack.last.declared_vars[self.node.identifier] = ClassVar(ClassVar.default_value(), self.node.typ.ident)

        elif isinstance(self.node, CfgEnum):
            pass #not implemented

        elif isinstance(self.node, CfgString):
            return StringVar(self.node.value)

        elif isinstance(self.node, CfgSkip):
            return #nothing to do

        elif isinstance(self.node, CfgIndex):
            idx = CfgWrapper(self.node.index).execute(stack)
            parent_val = CfgWrapper(self.node.rvalue).execute(stack)
            assert(isinstance(parent_val, ArrayVar))
            return parent_val.get_index_val(idx)

        elif isinstance(self.node, CfgBreak):
            stack.last.set_break()

        elif isinstance(self.node, CfgContinue):
            stack.last.set_continue()

        elif isinstance(self.node, CfgModule):
            for classDecl in self.node.classes:
                CfgWrapper(classDecl).execute(stack)
            for funcDecl in self.node.functions:
                CfgWrapper(funcDecl).execute(stack)
            for varDecl in self.node.vars:
                CfgWrapper(varDecl).execute(stack)
            for statement in self.node.statements:
                CfgWrapper(statement).execute(stack)

        elif isinstance(self.node, CfgFuncDecl):
            return #nothing to do just a decleration

        elif isinstance(self.node, CfgNewArray):
            length = CfgWrapper(self.node.array_length).execute(stack)
            assert isinstance(length, FixedSizeNumVar)
            assert length.type in ('u8', 'i8', 'u16', 'i16', 'u32', 'i32', 'u64', 'i64')
            assert isinstance(self.node.typ, ArrayType)
            typ = self.node.typ.element_type
            return ArrayVar(type_to_membox(typ), size=length.get_val()) # type: ignore (checked in second assert)

        elif isinstance(self.node, CfgNumeric):
            return FixedSizeNumVar(self.node.value, typ=self.node.typ.ident)

        elif isinstance(self.node, CfgBool):
            return BoolVar(self.node.value)

        elif isinstance(self.node, CfgDot):
            left = CfgWrapper(self.node.left).execute(stack)
            assert not left is None and not left.is_null
            return CfgWrapper(self.node.right).execute(stack, left)

        elif isinstance(self.node, CfgUnOp):
            rval = self.node.rvalue
            rvalue_membox = CfgWrapper(rval).execute(stack)
            assert isinstance(rvalue_membox, MemBox)
            operator = self.node.op
            result = rval.typ._op_functions[operator](rvalue_membox.get_val())
            assert self.node.typ.is_primitive
            if self.node.typ.ident in FixedSizeNumVar._typ_dict:
                return FixedSizeNumVar(result, self.node.typ.ident)
            else:
                return BoolVar(result)

        elif isinstance(self.node, CfgVar):
            if not args is None and len(args) > 0:
                parent:ClassVar = args[0]
                return parent.get_field(self.node.identifier)
            else:
                return stack.get_var(self.node.identifier)

        elif isinstance(self.node, CfgScope):
            stack.push(self.node.vars, self.node.functions)
            for varDecl in self.node.vars:
                CfgWrapper(varDecl).execute(stack)
            for statement in self.node.statements:
                if stack.last.must_return or stack.last.must_break or stack.last.must_continue:
                    return
                CfgWrapper(statement).execute(stack)
            stack.pop()

        elif isinstance(self.node, CfgTernary):
            condition = CfgWrapper(self.node.condition).execute(stack)
            assert isinstance(condition, BoolVar)
            if condition.get_val():
                return CfgWrapper(self.node.if_true).execute(stack)
            else:
                return CfgWrapper(self.node.if_false).execute(stack)

        elif isinstance(self.node, CfgFor):
            # For initialisation
            if isinstance(self.node.init, CfgVarDecl):
                stack.push([self.node.init], list()) 
            else:
                stack.push([], list()) 
            if isinstance(self.node.init, CfgVarDecl):
                CfgWrapper(self.node.init).execute(stack)
                var = stack.get_var(self.node.init.identifier)
                if not self.node.init.initial_value is None:
                    init_val = CfgWrapper(self.node.init.initial_value).execute(stack)
                    assert not init_val is None
                    var.set_val(init_val.get_val())
            elif isinstance(self.node.init, CfgAssign):
                CfgWrapper(self.node.init).execute(stack)
            
            #check condition and to loop
            condition = CfgWrapper(self.node.condition).execute(stack)
            condition = True if condition is None else condition.get_val()
            while condition:
                #execute for bloc
                CfgWrapper(self.node.bloc).execute(stack)
                stack.last.unset_continue() #unset continue
                #if continue just recheck condition and loop
                #handle break/continue/return flags
                if stack.last.must_break:
                    stack.pop(False)
                    return
                if stack.last.must_return:
                    stack.pop()
                    return

                if not self.node.postExpr is None:
                    CfgWrapper(self.node.postExpr).execute(stack)
                    
                condition = CfgWrapper(self.node.condition).execute(stack)
                condition = True if condition is None else condition.get_val()
            # exit loop normally after clearing loop scope
            stack.pop()

        elif isinstance(self.node, CfgNull):
            return NullVar()

        elif isinstance(self.node, CfgForeach):
            # Handle stack.last.clear must continue/break flag
            # TODO later when iterators are implemented
            pass

        elif isinstance(self.node, CfgIf):
            condition = CfgWrapper(self.node.condition).execute(stack)
            assert isinstance(condition, BoolVar)
            if condition.get_val():
                CfgWrapper(self.node.if_true).execute(stack)
            elif isinstance(self.node.if_false, CfgNode):
                #else block if there is one
                CfgWrapper(self.node.if_false).execute(stack)

        elif isinstance(self.node, CfgAssert):
            assertion = CfgWrapper(self.node.innerExpr).execute(stack)
            assert isinstance(assertion, BoolVar)
            if not assertion.get_val():
                raise AssertionError(f"Assertion failed at loaction {self.node.location}")

        elif isinstance(self.node, CfgClassDecl):
            pass
        # TODO

        elif isinstance(self.node, CfgCall):
            #gets function
            function = self.node._function_cfg
            # Set args in new scope
            passed_args = [CfgWrapper(arg).execute(stack) for arg in self.node.args]
            if function is None: #not a user defined function
                def err(*args): #default error function
                    raise RuntimeError(
                        f"Unable to find function {self.node.function_name} called at location {self.node.location}")
                #looks for builtin function
                v = dict(vars(BuiltinFunctions))
                f = v.get(f"builtin_{self.node.function_name}", err)
                return f(*passed_args) if args is None or len(args) == 0 else f(*args, *passed_args)

            # Function found and defined in file/import
            assert isinstance(function, (CfgFuncDecl, CfgConstructor))
            stack.push([], [])
            for varDecl, arg_value in zip(function.args, passed_args):
                assert isinstance(varDecl, CfgVarDecl)
                if not arg_value is None:
                    stack.last.declared_vars[varDecl.identifier] = arg_value
            # Handle CfgDot 
            if not args is None and len(args) > 0:
                stack.last.declared_vars['this'] = args[0]
            # Call Func
            CfgWrapper(function.body).execute(stack)
            # Pop scope
            stack.pop(False)
            # Handle return value here
            assert isinstance(function.typ, FunctionType)
            if function.typ.return_type != BuiltinType.VOID.value:
                return stack.pop_return_value()
            return

        elif isinstance(self.node, CfgCopyAssign):
            # TODO
            pass

        elif isinstance(self.node, CfgReturn):
            stack.last.set_return()
            if not self.node.returnVal is None:
                return_val = CfgWrapper(self.node.returnVal).execute(stack)
                assert(isinstance(return_val, MemBox))
                stack.set_return_value(return_val)

        elif isinstance(self.node, CfgWhile):
            # check condition and to loop
            condition = CfgWrapper(self.node.condition).execute(stack)
            condition = True if condition is None else condition.get_val()
            while condition:
                # execute for bloc
                CfgWrapper(self.node.bloc).execute(stack)
                stack.last.unset_continue()  # unset continue
                # if continue just recheck condition and loop
                # handle break/continue/return flags
                if stack.last.must_break:
                    stack.pop(False)
                    return
                if stack.last.must_return:
                    stack.pop()
                    return
                #recheck condition and return and continue to loop if needed
                condition = CfgWrapper(self.node.condition).execute(stack)
                condition = True if condition is None else condition.get_val()
            #exit loop normally after clearing loop scope
            stack.pop()
        
        else:
            raise RuntimeError(f"Unknown node and type: {self.node},  {type(self.node)}")

class Env:
    def __init__(self, module:CfgModule, context:Context) -> None:
        # Here classes are defined as a dict.
        # Each element in the dict is either a field (has a value that can be a primitive type, str or dict other class)
        # Methods are also an element in the dict but of type CfgFuncDecl.
        CfgWrapper.context = context
        UserDefinedClass._classes.update({c.typ:c for c in module.classes})
        self.stack = ScopeStack(module.vars, module.functions)
        self.module = module
        
    def run(self) -> None:
        CfgWrapper(self.module).execute(self.stack)