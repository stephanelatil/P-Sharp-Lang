from copy import deepcopy
from ..typing_to_cfg import *


class UserDefinedClass:
    user_classes: dict[str, 'UserDefinedClass'] = {}
    def __init__(self, classDecl:CfgClassDecl) -> None:
        self.classDecl = classDecl
    
    def buildNew(self, scope, *args) -> dict[str,None|int|bool|float|dict|CfgFuncDecl]:
        """_summary_ Creates a new class dict with empty fields. Then the constructor CFG must populate them

        Returns:
            dict[str,None|int|bool|float|dict|CfgNode]: A dict representing the an instance of the class
        """
        new_obj = {}
        
        #set all fields and methods
        for method in self.classDecl.methods:
            new_obj[method.identifier] = method.context.known_functions[method.body.UUID].get(method.context)
        for field in self.classDecl.fields:
            new_obj[field.identifier] = None
        
        return new_obj

class Scope:
    """
    _summary_ Defines a scope. A scope has defined functions and variables
    """
    def __init__(self, vars:list[CfgVarDecl], functions:list[CfgFuncDecl]) -> None:
        self.declared_vars:dict[str, None|bool|int|str|dict] = {v.identifier:0 for v in vars}
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
        
    @property
    def last(self):
        return self.stack[-1]
    
    def push(self, vars: list[CfgVarDecl], functions: list[CfgFuncDecl])-> None:
        self.stack.append(Scope(vars, functions))
        
    def pop(self) -> Scope:
        scope = self.stack.pop()
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
    
    def get_var(self, identifier) -> None | bool | int | str | dict:
        for i in range(-1, -len(self.stack)-1, -1):
            var = self.stack[i].declared_vars.get(identifier, None)
            if var:
                return var
        raise AttributeError(
            "Cannot find the function from it's ID in the scope stack", name=identifier, obj=None)
        
    def set_var(self, identifier, value) -> None:
        for i in range(-1,-len(self.stack)-1,-1):
            if identifier in self.stack[i].declared_vars:
                self.stack[i].declared_functions[identifier] = value
                return 
        raise AttributeError(
            "Cannot find the function from it's ID in the scope stack", name=identifier, obj=None)

class CfgWrapper:
    context:Context = Context()
    
    def __init__(self, node: CfgNode) -> None:
        self.node = node

    def execute(self, stack:ScopeStack, *args, **kwargs) -> None|int|bool|str|dict:
        if isinstance(self.node, CfgConstructor):
            stack.push(self.node.body.vars+self.node.args, self.node.body.functions)
            #add 'this' to stack: the object being created
            stack.last.declared_vars['this'] = UserDefinedClass.user_classes[self.node.identifier].buildNew(*args)
            #pushes new scope
            for i in range(len(self.node.args)):
                #sets the arguments for the constructor in the local vars stack
                stack.set_var(self.node.args[i].identifier, args[i])
            #for all statements
            for statement in self.node.body.statements:
                #if return in sub-scope
                if stack.last.must_return:
                    obj = stack.get_var('this')
                    _ = stack.pop()
                    stack.last.unset_return()
                    return obj
                #if break or continue triggered in sub-scope: error occurred
                if stack.last.must_break or stack.last.must_continue:
                    raise Exception("Cannot break/continue out of a constructor block. must be in a loop!"+
                                    f"\n\tError exiting at {statement.location}")
                #execute statement
                CfgWrapper(statement).execute(stack)
                
        elif isinstance(self.node, CfgNewObject):
            #parse args
            constructor_arguments = [CfgWrapper(arg).execute(stack) for arg in self.node.args]
            #run and return object from constructor
            return CfgWrapper(self.node.constructor.get(self.context)).execute(stack,
                                                                               *constructor_arguments)
        elif isinstance(self.node, CfgCast):
            pass
        elif isinstance(self.node, CfgAssign):
            pass
        elif isinstance(self.node, CfgBinOp):
            pass
        elif isinstance(self.node, CfgVarDecl):
            pass
        elif isinstance(self.node, CfgEnum):
            pass
        elif isinstance(self.node, CfgString):
            pass
        elif isinstance(self.node, CfgSkip):
            pass
        elif isinstance(self.node, CfgIndex):
            pass
        elif isinstance(self.node, CfgBreak):
            pass
        elif isinstance(self.node, CfgModule):
            pass
        elif isinstance(self.node, CfgFuncDecl):
            pass
        elif isinstance(self.node, CfgNewArray):
            pass
        elif isinstance(self.node, CfgNumeric):
            pass
        elif isinstance(self.node, CfgBool):
            pass
        elif isinstance(self.node, CfgDot):
            pass
        elif isinstance(self.node, CfgUnOp):
            pass
        elif isinstance(self.node, CfgVar):
            pass
        elif isinstance(self.node, CfgScope):
            pass
        elif isinstance(self.node, CfgTernary):
            pass
        elif isinstance(self.node, CfgFor):
            pass
        elif isinstance(self.node, CfgNull):
            pass
        elif isinstance(self.node, CfgForeach):
            pass
        elif isinstance(self.node, CfgIf):
            pass
        elif isinstance(self.node, CfgAssert):
            pass
        elif isinstance(self.node, CfgClassDecl):
            pass

class Env:
    def __init__(self, module:CfgModule, context:Context) -> None:
        # Here classes are defined as a dict.
        # Each element in the dict is either a field (has a value that can be a primitive type, str or dict other class)
        # Methods are also an element in the dict but of type CfgFuncDecl.
        CfgWrapper.context = context
        UserDefinedClass.user_classes.update({c.identifier:UserDefinedClass(c) for c in module.classes})
        self.stack = ScopeStack(module.vars, module.functions)
        self.module = module
        
    def run(self) -> None:
        CfgWrapper(self.module).execute(self.stack)