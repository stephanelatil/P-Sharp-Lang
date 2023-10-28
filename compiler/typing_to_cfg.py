from typing_tree import *

class Context:
    def __init__(self) -> None:
        # A Dict with a cfgNode for UUIDs in the Ttree. Note that some elements may not have a CfgNode or simply be aCfgSkip
        # For example, function declerations don't have a CfgNode because there is no work to be done at runtime
        self.uuid_to_cfg_node: "dict[int, CfgNode]" = {}
        # A dict that contains the function body CGF given its name, for easy lookup
        self.known_functions:dict[int,'LazyGetFunction'] = {}
        
class LazyGetFunction:        
    def __init__(self, cfg_function_node_id:int):
        self.cfg_function_node_id = cfg_function_node_id
    
    def get(self, context:Context) -> 'CfgNode':
        if isinstance(self.cfg_function_node_id, int):
            self.cfg_function_node_id = context.uuid_to_cfg_node[self.cfg_function_node_id]
        return self.cfg_function_node_id
                

class CfgNode:    
    def __init__(self, elem: TTreeElem, context:Context) -> None:
        self.incoming:"set[CfgNode]" = set()
        self.outgoing: "set[CfgNode]" = set()
        self._UUID = elem._UUID
        self.location = elem.location
        self.location_end = elem.location_end
        self.typ = elem.typ
        self.context = context
        context.uuid_to_cfg_node[elem.UUID] = self
    
    @property
    def UUID(self) -> int:
        return self._UUID.uuid
        
    def add_outgoing(self, next:"CfgNode"):
        self.outgoing.add(next)

    def add_incoming(self, next: "CfgNode"):
        self.incoming.add(next)
        
        
    def to_llvm_ir(self):
        pass

class CfgErrorNode(CfgNode):
    def __init__(self, elem: TTreeElem, context:Context) -> None:
        super().__init__(elem, context)
        context.uuid_to_cfg_node[elem.UUID] = self

class CfgAssert(CfgNode):
    def __init__(self, elem: TAssert, context:Context) -> None:
        super().__init__(elem, context)
        context.uuid_to_cfg_node[elem.UUID] = self
        self.innerExpr = _Converter.ttree_elem_to_cfg(elem.assertExpr, context)
        #TODO handle outgoing error node?

class CfgAssign(CfgNode):
    def __init__(self, elem: TAssign, context:Context) -> None:
        super().__init__(elem, context)
        context.uuid_to_cfg_node[elem.UUID] = self
        self.rvalue = _Converter.ttree_elem_to_cfg(elem.rvalue, context)
        self.lvalue = _Converter.ttree_elem_to_cfg(elem.left, context)
        
class CfgBool(CfgNode):
    def __init__(self, elem: TBool, context:Context) -> None:
        super().__init__(elem, context)
        context.uuid_to_cfg_node[elem.UUID] = self
        self.value = elem.value == True #assert it's True or False (NULL is set to False)
        
class CfgBreak(CfgNode):
    def __init__(self, elem: TBreak, context:Context) -> None:
        super().__init__(elem, context)
        context.uuid_to_cfg_node[elem.UUID] = self

class CfgBinOp(CfgNode):
    def __init__(self, elem: TBinOp, context:Context) -> None:
        super().__init__(elem, context)
        context.uuid_to_cfg_node[elem.UUID] = self
        self.operation = elem.operation
        self.left = _Converter.ttree_elem_to_cfg(elem.left, context)
        self.right = _Converter.ttree_elem_to_cfg(
            elem.rvalue, context)

class CfgCall(CfgNode):
    def __init__(self, elem: TCall, context:Context) -> None:
        super().__init__(elem, context)
        context.uuid_to_cfg_node[elem.UUID] = self
        self.args = [_Converter.ttree_elem_to_cfg(arg, context) for arg in elem.args]
        self._function_body_cfg = context.known_functions[elem.function_body_uuid]
        
class CfgCast(CfgNode):
    def __init__(self, elem: TCast, context: Context) -> None:
        super().__init__(elem, context)
        context.uuid_to_cfg_node[elem.UUID] = self
        #TODO handle special casting (int to float or overloaded cast operator)
        self.old_val = _Converter.ttree_elem_to_cfg(elem.rvalue, context)
        self.cast_func = CfgSkip(elem, context)


class CfgClassDecl(CfgNode):
    def __init__(self, elem: TClassDecl, context: Context) -> None:
        super().__init__(elem, context)
        context.uuid_to_cfg_node[elem.UUID] = self
        self.identifier = elem.identifier
        self.constructor = _Converter.ttree_elem_to_cfg(
            elem.constructor, context)
        self.fields:list[CfgVarDecl] = [_Converter.ttree_elem_to_cfg(
            f, context) for f in elem.fields]
        self.methods:list[CfgFuncDecl] = [_Converter.ttree_elem_to_cfg(
            m, context) for m in elem.methods]


class CfgConstructor(CfgNode):
    def __init__(self, elem: TConstructor, context: Context) -> None:
        super().__init__(elem, context)
        context.uuid_to_cfg_node[elem.UUID] = self
        context.known_functions[self.body.UUID] = LazyGetFunction(elem.body.UUID)
        self.args:list[CfgVarDecl] = [_Converter.ttree_elem_to_cfg(arg, context) for arg in elem.args]
        self.body:CfgScope = _Converter.ttree_elem_to_cfg(elem, context)
        self.identifier = elem.id


class CfgContinue(CfgNode):
    def __init__(self, elem: TContinue, context: Context) -> None:
        super().__init__(elem, context)
        context.uuid_to_cfg_node[elem.UUID] = self


class CfgCopyAssign(CfgNode):
    def __init__(self, elem: TCopyAssign, context: Context) -> None:
        super().__init__(elem, context)
        context.uuid_to_cfg_node[elem.UUID] = self
        self.rvalue = _Converter.ttree_elem_to_cfg(elem.rvalue, context)
        self.lvalue = _Converter.ttree_elem_to_cfg(elem.left, context)
        
class CfgDot(CfgNode):
    def __init__(self, elem: TDot, context: Context) -> None:
        super().__init__(elem, context)
        context.uuid_to_cfg_node[elem.UUID] = self
        self.left = _Converter.ttree_elem_to_cfg(elem.left, context)
        self.right = _Converter.ttree_elem_to_cfg(elem.rvalue, context)


class CfgEnum(CfgNode):
    def __init__(self, elem: TEnum, context: Context) -> None:
        super().__init__(elem, context)
        context.uuid_to_cfg_node[elem.UUID] = self
        #TODO

 
class CfgFor(CfgNode):
    def __init__(self, elem: TFor, context: Context) -> None:
        super().__init__(elem, context)
        context.uuid_to_cfg_node[elem.UUID] = self
        self.init = _Converter.ttree_elem_to_cfg(elem.init, context)
        self.condition = _Converter.ttree_elem_to_cfg(elem.condition, context)
        self.postExpr = _Converter.ttree_elem_to_cfg(elem.postExpr, context)
        self.bloc = _Converter.ttree_elem_to_cfg(elem.bloc, context)
        
        
class CfgForeach(CfgNode):
    def __init__(self, elem: TForeach, context: Context) -> None:
        super().__init__(elem, context)
        context.uuid_to_cfg_node[elem.UUID] = self
        self.varDecl = _Converter.ttree_elem_to_cfg(elem.varDecl, context)
        self.iterable = _Converter.ttree_elem_to_cfg(elem.iterable, context)
        self.bloc = _Converter.ttree_elem_to_cfg(elem.bloc, context)
        

class CfgFuncDecl(CfgNode):
    def __init__(self, elem: TFuncDecl, context: Context) -> None:
        super().__init__(elem, context)
        context.uuid_to_cfg_node[elem.UUID] = self
        context.known_functions[elem.body.UUID] = LazyGetFunction(elem.body.UUID)
        self.body = _Converter.ttree_elem_to_cfg(elem.body, context)
        self.identifier = elem.id


class CfgIf(CfgNode):
    def __init__(self, elem: TIf, context: Context) -> None:
        super().__init__(elem, context)
        context.uuid_to_cfg_node[elem.UUID] = self
        self.condition = _Converter.ttree_elem_to_cfg(elem.condition, context)
        self.if_true = _Converter.ttree_elem_to_cfg(elem.if_true, context)
        self.if_false = _Converter.ttree_elem_to_cfg(elem.if_false, context)

class CfgIndex(CfgNode):
    def __init__(self, elem: TIndex, context: Context) -> None:
        super().__init__(elem, context)
        context.uuid_to_cfg_node[elem.UUID] = self
        self.rvalue = _Converter.ttree_elem_to_cfg(elem.rvalue, context)
        self.index = _Converter.ttree_elem_to_cfg(elem.index, context)


class CfgModule(CfgNode):
    def __init__(self, elem: TModule, context: Context) -> None:
        super().__init__(elem, context)
        context.uuid_to_cfg_node[elem.UUID] = self
        
        # TODO Do a first pass though all nodes once to fill in the $context.known_functions with function ids. 
        # Then carry out the rest
        
        self.vars:list[CfgVarDecl] = [_Converter.ttree_elem_to_cfg(var, context) for var in elem.varDecl]
        self.classes:list[CfgClassDecl] = [_Converter.ttree_elem_to_cfg(classDecl, context) for classDecl in elem.classDecl]
        self.functions: list[CfgFuncDecl] = [_Converter.ttree_elem_to_cfg(
            function, context) for function in elem.funcDecl]
        self.statements:list[CfgNode] = [_Converter.ttree_elem_to_cfg(statement, context) for statement in elem.statements]
        

class CfgNewArray(CfgNode):
    def __init__(self, elem: TNewArray, context: Context) -> None:
        super().__init__(elem, context)
        context.uuid_to_cfg_node[elem.UUID] = self
        self.array_length = _Converter.ttree_elem_to_cfg(elem.arr_len, context)


class CfgNewObject(CfgNode):
    def __init__(self, elem: TNewObj, context: Context) -> None:
        super().__init__(elem, context)
        context.uuid_to_cfg_node[elem.UUID] = self
        self.constructor = context.known_functions[elem.new_obj._constructor_uuid]
        self.args = [_Converter.ttree_elem_to_cfg(arg, context) for arg in elem.args]

class CfgNull(CfgNode):
    def __init__(self, elem: TNull, context: Context) -> None:
        super().__init__(elem, context)
        context.uuid_to_cfg_node[elem.UUID] = self

class CfgNumeric(CfgNode):
    def __init__(self, elem: TNumeric, context: Context) -> None:
        super().__init__(elem, context)
        context.uuid_to_cfg_node[elem.UUID] = self
        self.value = elem.value

class CfgReturn(CfgNode):
    def __init__(self, elem: TReturn, context: Context) -> None:
        super().__init__(elem, context)
        context.uuid_to_cfg_node[elem.UUID] = self
        self.returnVal = _Converter.ttree_elem_to_cfg(elem.returnVal, context)


class CfgScope(CfgNode):
    def __init__(self, elem: TScope, context: Context) -> None:
        super().__init__(elem, context)
        context.uuid_to_cfg_node[elem.UUID] = self
        self.vars:list[CfgVarDecl] = [_Converter.ttree_elem_to_cfg(var, context) for var in elem.varDecl]
        self.functions: list[CfgFuncDecl] = [_Converter.ttree_elem_to_cfg(
            function, context) for function in elem.funcDecl]
        self.statements = [_Converter.ttree_elem_to_cfg(statement, context) for statement in elem.statements]
        for i in range(len(self.statements)-1):
            self.statements[i].add_outgoing(self.statements[i+1])
            self.statements[i+1].add_incoming(self.statements[i])

class CfgSkip(CfgNode):
    def __init__(self, elem: TTreeElem, context: Context) -> None:
        super().__init__(elem, context)
        context.uuid_to_cfg_node[elem.UUID] = self


class CfgString(CfgNode):
    def __init__(self, elem: TString, context: Context) -> None:
        super().__init__(elem, context)
        context.uuid_to_cfg_node[elem.UUID] = self
        self.value = elem.value
        
class CfgTernary(CfgNode):
    #different from a simple if because a ternary returns a value depending on the condition! An if only executes statements
    def __init__(self, elem: TTernary, context: Context) -> None:
        super().__init__(elem, context)
        context.uuid_to_cfg_node[elem.UUID] = self
        self.if_true = _Converter.ttree_elem_to_cfg(elem.if_true, context)
        self.if_false = _Converter.ttree_elem_to_cfg(elem.if_false, context)
        self.condition = _Converter.ttree_elem_to_cfg(elem.condition, context)

class CfgUnOp(CfgNode):
    def __init__(self, elem: TUnOp, context: Context) -> None:
        super().__init__(elem, context)
        context.uuid_to_cfg_node[elem.UUID] = self
        self.rvalue = _Converter.ttree_elem_to_cfg(elem.rvalue, context)
        self.op = elem.op


class CfgVar(CfgNode):
    def __init__(self, elem: TVar, context: Context) -> None:
        super().__init__(elem, context)
        context.uuid_to_cfg_node[elem.UUID] = self
        self.identifier = elem.identifier


class CfgVarDecl(CfgNode):
    def __init__(self, elem: TVarDecl, context: Context) -> None:
        super().__init__(elem, context)
        context.uuid_to_cfg_node[elem.UUID] = self
        self.identifier = elem.identifier
        if isinstance(elem.initial_value, JSON_Val):
            self.initial_value = CfgNull(TNull(PNull(elem.location, last_token_end=elem.location_end),
                                               elem),
                                         context)
        else:
            _Converter.ttree_elem_to_cfg(elem.initial_value, context)

class CfgWhile(CfgNode):
    def __init__(self, elem: TWhile, context: Context) -> None:
        super().__init__(elem, context)
        context.uuid_to_cfg_node[elem.UUID] = self
        self.condition = _Converter.ttree_elem_to_cfg(elem.condition, context)
        self.loop_block = _Converter.ttree_elem_to_cfg(elem.bloc, context)
        
            
class _Converter:
    _function_map:dict[type[TTreeElem],type[CfgNode]] = {TAssert:CfgAssert,TAssign:CfgAssign,TBinOp:CfgBinOp,
                                                         TBool:CfgBool,TBreak:CfgBreak,TCall:CfgCall, TCast:CfgCast,
                                                         TClassDecl:CfgClassDecl,TConstructor:CfgConstructor, TDot:CfgDot,
                                                         TEnum:CfgEnum, TFor:CfgFor, TForeach:CfgForeach, TFuncDecl:CfgFuncDecl,
                                                         TIf:CfgIf, TIndex:CfgIndex, TModule:CfgModule, TNewArray:CfgNewArray,
                                                         TNewObj:CfgNewObject, TNull:CfgNull, TNumeric:CfgNumeric, TScope:CfgScope,
                                                         TSkip:CfgSkip,TString:CfgString, TTernary:CfgTernary, TUnOp:CfgUnOp,
                                                         TVar:CfgVar, TVarDecl:CfgVarDecl}
    
    @staticmethod
    def ttree_elem_to_cfg(elem: TTreeElem, context:Context) -> CfgNode:
        return _Converter._function_map[type(elem)](elem, context)
        
def typing_to_cfg(ttree: TModule) -> tuple[CfgModule, Context]:
    context:Context = Context()
    
    return CfgModule(ttree, context), context

#TODO: Lifetime analysis for elements on heap?
#TODO: Add CFG to LLVM IR for all nodes
#TODO Implement GC in CFG?