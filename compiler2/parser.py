from typing import List, Optional, Dict, Any, Union, Generator
from collections import deque
from dataclasses import dataclass, field
from enum import Enum, auto
from lexer import Lexer, LexemeType, Lexeme, Position
from operations import BinaryOperation, UnaryOperation, TernaryOperator
from llvmlite import ir, binding
from constants import *

class LexemeStream:
    def __init__(self, lexmes:Generator[Lexeme, None, None], filename:str):
        self.lexeme_gen = lexmes
        self.buffer = deque()
        self.pos = Position(filename=filename)
        self.eof = False

    def peek(self, amount=0) -> Lexeme:
        if self.eof and len(self.buffer) == 0:
            return Lexeme.default

        while len(self.buffer) <= amount:
            lexeme = next(self.lexeme_gen, None)
            if not lexeme:
                self.eof = True
                return Lexeme.default
            self.buffer.append(lexeme)

        return self.buffer[amount]

    def advance(self) -> Lexeme:
        lexeme = self.peek()
        if lexeme is not None:
            self.buffer.popleft()
            self.pos = lexeme.pos
        if lexeme is None:
            raise EOFError()
        return lexeme

    def position(self) -> Position:
        return self.pos.copy()

@dataclass
class Typ:
    """Represents a type in the P# language with its methods and fields"""
    name:str
    methods: List['PMethod']
    fields: List['PClassField']
    is_reference_type:bool = True
    
    def __hash__(self) -> int:
        return hash(self.name)
    
    def __eq__(self, value: object) -> bool:
        if not isinstance(value, Typ):
            return False
        return self.name == value.name \
            #    and all((m1 == m2 for m1, m2 in zip(self.methods, value.methods))) \
            #    and all((f1 == f2 for f1, f2 in zip(self.fields, value.fields)))
    
    def __post_init__(self):
        for function in self.methods:
            if function.name == "ToString" and len(function.function_args) == 0:
                return
        # Add default ToString method if it does not exist
        # Default ToString calls the builtin default
        method = PMethod("ToString",
                         PType('string', Lexeme.default),
                         PType(self.name, Lexeme.default),
                         [],
                         PBlock([
                             PReturnStatement(
                                 PFunctionCall(
                                     PIdentifier(FUNC_DEFAULT_TOSTRING, Lexeme.default),
                                     [PThis(Lexeme.default)],
                                     Lexeme.default
                                 ),
                                 Lexeme.default)
                             ], Lexeme.default, BlockProperties(
                                     is_top_level=False,
                                     in_function=True
                             )),
                         Lexeme.default, is_builtin=True)
        self.methods.append(method)
    
    def get_llvm_value_type(self, context:Optional['CodeGenContext']) -> Union[ir.IntType,ir.HalfType,ir.FloatType,ir.DoubleType,ir.VoidType,ir.PointerType]:
        """Returns the llvm value-Type corresponding to the Typ. All reference types will return an ir.PointerType

        Returns:
            ir.Type: The value type of this type. It's either a PointerType, VoidType, IntType or some FloatType (depending on bit-width)
        """
        type_map = {
            'void': ir.VoidType(),
            'char': ir.IntType(8),
            'i8': ir.IntType(8),
            'i16': ir.IntType(16),
            'i32': ir.IntType(32),
            'i64': ir.IntType(64),
            'u8': ir.IntType(8),
            'u16': ir.IntType(16),
            'u32': ir.IntType(32),
            'u64': ir.IntType(64),
            'f16': ir.HalfType(),
            'f32': ir.FloatType(),
            'f64': ir.DoubleType(),
            'bool': ir.IntType(1),
            'null': ir.PointerType() # null is a point type (points to nothing but still a pointer technically)
        }
        
        if self.name in type_map:
            return type_map[self.name]
        if self.is_reference_type:
            if context is None:
                return ir.PointerType()
            else:
                return ir.PointerType(context.type_map[self])
        raise TypingError(f"Unknown value type {self.name}")

    def __str__(self):
        return self.name
    
    def default_llvm_value(self, context:'CodeGenContext'):
        # return ir.Constant(context.type_map[self], None)
        return ir.Constant(self.get_llvm_value_type(context), None)
    
class ArrayTyp(Typ):
    def __init__(self, element_type:Typ):
        self.element_typ:Typ = element_type
        methods:List[PMethod] = []
        fields:List[PClassField] = []
        super().__init__(f'{element_type.name}[]',
                         methods=methods,
                         fields=fields,
                         is_reference_type=True)
    
    def __post_init__(self):
        """Adds .Length field and other methods"""
        super().__post_init__()
        for field in self.fields:
            if field.name == "Length":
                return
        # Add default Length method if it does not exist
        # Default Length calls the builtin default
        field = PClassField("Length",
                            PType('u64', Lexeme.default), 
                            lexeme=Lexeme.default,
                            is_public=True,
                            is_builtin=True,
                            default_value=None)
        #it's the only field of an array! (others are the actual array elements)
        self.fields = [field]
    
    def __hash__(self) -> int:
        return super().__hash__()
    
    def __eq__(self, value: object) -> bool:
        return super().__eq__(value)

class ParserError(Exception):
    """Custom exception for parser-specific errors"""
    def __init__(self, message: str, lexeme: Lexeme):
        self.message = message
        self.lexeme = lexeme
        super().__init__(f"{message} at {lexeme.pos} with lexeme: {lexeme}")

class TypingError(Exception):
    def __init__(self, msg) -> None:
        super().__init__(msg)

class TypeClass(Enum):
    """Classification of types for conversion rules"""
    VOID = auto()
    BOOLEAN = auto()
    INTEGER = auto()
    FLOAT = auto()
    STRING = auto()
    ARRAY = auto()
    CLASS = auto()

@dataclass
class TypeInfo:
    """Information about a type including its class and size"""
    type_class: TypeClass
    bit_width: int = 0  # For numeric types
    is_signed: bool = True  # For integer types
    is_builtin: bool = True

# Mapping of type names to their TypeInfo
TYPE_INFO: Dict[str, TypeInfo] = {
    "void": TypeInfo(TypeClass.VOID),
    "bool": TypeInfo(TypeClass.BOOLEAN, 1, False),
    "string": TypeInfo(TypeClass.STRING),
    "char": TypeInfo(TypeClass.INTEGER, 8, False),

    # Signed integers
    "i8": TypeInfo(TypeClass.INTEGER, 8, True),
    "i16": TypeInfo(TypeClass.INTEGER, 16, True),
    "i32": TypeInfo(TypeClass.INTEGER, 32, True),
    "i64": TypeInfo(TypeClass.INTEGER, 64, True),

    # Unsigned integers
    "u8": TypeInfo(TypeClass.INTEGER, 8, False),
    "u16": TypeInfo(TypeClass.INTEGER, 16, False),
    "u32": TypeInfo(TypeClass.INTEGER, 32, False),
    "u64": TypeInfo(TypeClass.INTEGER, 64, False),

    # Floating point
    "f16": TypeInfo(TypeClass.FLOAT, 16),
    "f32": TypeInfo(TypeClass.FLOAT, 32),
    "f64": TypeInfo(TypeClass.FLOAT, 64),
}


@dataclass
class VarInfo:
    name:str
    type_:ir.Type
    alloca:Optional[ir.NamedValue]=None
    """This is useful to know if the var needs to be explicitly dereferenced! A global var is a pointer to the given type"""
    is_global:bool=False
    func_ptr:Optional[ir.Function]=None
    
    @property
    def is_function(self) -> bool:
        return self.func_ptr is not None

class ScopeVars:
    def __init__(self):
        self.scope_vars = {}
        
    def declare_func(self, name:str, return_type:ir.Type, function_ptr:ir.Function):
        if name in self.scope_vars:
            raise CompilerError(f"Variable already exists!")
        self.scope_vars[name] = VarInfo(name, return_type, func_ptr=function_ptr)
        
    def declare_var(self, name:str, type_:ir.Type, alloca:ir.NamedValue, is_global:bool=False):
        if name in self.scope_vars:
            raise CompilerError(f"Variable already exists!")
        self.scope_vars[name] = VarInfo(name, type_, alloca=alloca, is_global=is_global)
        
    def get_symbol(self, name:str) -> Optional[VarInfo]:
        return self.scope_vars.get(name, None)

class Scopes:
    def __init__(self):
        self.scopes:List[ScopeVars] = []
        self.tmp_func_stack = []
        
    @property
    def current_function_scope_depth(self):
        depth = len(self.scopes) - 1 #1 is the global scope where the global functions and global vars are defined
        assert depth > 0
        return depth

    def enter_scope(self):
        self.scopes.append(ScopeVars())

    def leave_scope(self):
        self.scopes.pop()

    def declare_var(self, name:str, type_:ir.Type, alloca:ir.NamedValue, is_global:bool=False):
        self.scopes[-1].declare_var(name, type_, alloca, is_global)
        
    def declare_func(self, name:str, return_type:ir.Type, function_ptr:ir.Function):
        self.scopes[-1].declare_func(name, return_type, function_ptr)
        
    def has_symbol(self, name:str) -> bool:
        """Checks if a given symbol is known

        Args:
            name (str): _description_

        Returns:
            bool: _description_
        """
        for scope in self.scopes[::-1]:
            var_info = scope.get_symbol(name)
            if var_info is not None:
                return True
        return False

    def get_symbol(self, name:str) -> VarInfo:
        for scope in self.scopes[::-1]:
            var_info = scope.get_symbol(name)
            if var_info is not None:
                return var_info
        
        raise CompilerError(f"Unable to find variable {name}")
    
    def get_global_scope(self):
        return self.scopes[0]

class CompilerError(Exception):
    def __init__(self, msg):
        super().__init__(msg)
        self.msg = msg
        
    def __str__(self):
        return f"Compiler Error: {self.msg}"

@dataclass
class LoopContext:
    continue_loop_block:ir.Block
    end_of_loop_block:ir.Block
    is_for_loop:bool
    current_loop_scope_depth:int = 0

@dataclass
class CodeGenContext:
    """Context needed by various node when generating IR in the codegen pass"""
    module:ir.Module
    scopes:Scopes
    target_data:binding.TargetData
    # """A function that take a Typ and returns a ir.Type associated (int, float ot struct types or pointers for all other types)"""
    # get_llvm_type: Callable[['Typ'],ir.Type]
    """A dict containing all Types known to the typer and it's corresponding ir.Type"""
    type_map:Dict[Typ, Union[ir.IntType,ir.HalfType,ir.FloatType,ir.DoubleType,ir.VoidType,ir.LiteralStructType]]
    """A stack of tuples pointing to (condition block of loop: for continues, end of loop for break)"""
    loopinfo:List[LoopContext] = field(default_factory=list)
    builder:ir.IRBuilder = ir.IRBuilder()
    global_exit_block:Optional[ir.Block]=None
    type_ids:Dict[str, int] = field(default_factory=dict)
    """A Dict where for every given string there is an associated constant string PS object. constant because strings are immutable"""
    _global_string_objs:Dict[str, ir.GlobalValue] = field(default_factory=dict)
    
    def get_string_const(self, string:str):
        if string in self._global_string_objs:
            return self._global_string_objs[string]
        #take length before null termination to properly handle manual strings which may contain null chars (\x00)
        string_length = len(string)
        # ensure string is null terminated to be a proper c_str
        if not string.endswith('\x00'):
            null_terminated_string = string + '\x00'
        else:
            null_terminated_string = string
            
        #Build c string
        string_bytes = null_terminated_string.encode('utf-8')
        string_typ = ir.LiteralStructType([
            ir.IntType(64),
            ir.ArrayType(ir.IntType(8), len(string_bytes))
        ])
        #store constant value globally
        string_obj = ir.GlobalVariable(module=self.module,
                                       typ=string_typ,
                                       name=f".__str_obj_{len(self._global_string_objs)}")
        string_obj.initializer = ir.Constant(string_typ, [string_length, bytearray(string_bytes)])
        #cache value to avoid saturating executable
        self._global_string_objs[string] = string_obj
        return string_obj
    
    def get_char_ptr_from_string(self, string:str):
        """Adds a Global string with the given value (if none already exists) and returns a GEP pointer to the first character (char* c string style)

        Args:
            string (str): The python string to convert to a llvm c-style string

        Returns:
            GEPInstr: a GEP instruction pointer value to the c-string
        """
        string_obj = self.get_string_const(string)
        assert isinstance(string_obj.type, ir.types._TypedPointerType)
        string_typ = string_obj.type.pointee
        zero = ir.Constant(ir.IntType(32), 0)
        one = ir.Constant(ir.IntType(32), 1)
        return self.builder.gep(string_obj, [zero, one, zero], inbounds=True, source_etype=string_typ)
    
    def get_method_symbol_name(self, class_name:str, method_identifier:str):
        return f"__{class_name}.__{method_identifier}"
    
    def enter_scope(self, ref_vars:int=0):
        """Enter a scope both in the GC and context scope manager"""
        # scope manager enters scope
        self.scopes.enter_scope()
        # GC create scope
        size_t_type = ir.IntType(ir.PointerType().get_abi_size(self.target_data)*8)
        enter_scope_func = self.scopes.get_symbol(FUNC_GC_ENTER_SCOPE).func_ptr
        assert enter_scope_func is not None
        self.builder.call(enter_scope_func,
                             [ir.Constant(size_t_type, ref_vars)])
    
    def leave_scope(self, scopes_to_leave:int=1):            
        """Leave N scopes both in the GC and a single one in the context scope manager.
        The context scope if popped only once because we will continue to parse other statement in the parent block"""
        if scopes_to_leave < 1:
            return
        size_t_type = ir.IntType(ir.PointerType().get_abi_size(self.target_data)*8)
        leave_scope_func = self.scopes.get_symbol(FUNC_GC_LEAVE_SCOPE).func_ptr
        assert leave_scope_func is not None
        self.builder.call(leave_scope_func,
                          #leave a single scope
                          [ir.Constant(size_t_type, scopes_to_leave)])
        #pop the scope we are currently leaving
        self.scopes.leave_scope()
        
    def add_root_to_gc(self, alloca:ir.NamedValue, type_:Typ, var_name:str):
        """Adds variable root location to GC"""
        if type_.is_reference_type:
            if isinstance(type_, ArrayTyp):
                if type_.element_typ.is_reference_type:
                    type_id = REFERENCE_ARRAY_TYPE_ID
                else:
                    type_id = VALUE_ARRAY_TYPE_ID
            else:
                type_id = self.type_ids[type_.name]
            
            size_t_type = ir.IntType(ir.PointerType().get_abi_size(self.target_data) * 8)
            register_root_func = self.scopes.get_symbol(FUNC_GC_REGISTER_ROOT_VARIABLE_IN_CURRENT_SCOPE).func_ptr
            assert register_root_func is not None
            self.builder.call(register_root_func,
                                 [alloca, #location of root in memory. (ptr to the held ref vars)
                                  ir.Constant(size_t_type, type_id), #type id
                                  self.get_char_ptr_from_string(var_name) #variable name TODO: remove this. It should be in the debug symbols!
                                  ])

class NodeType(Enum):
    """Enumeration of all possible node types in the parser tree"""
    EMPTY = auto()
    PROGRAM = auto()
    FUNCTION = auto()
    TYPE = auto()
    CLASS = auto()
    BLOCK = auto()
    VARIABLE_DECLARATION = auto()
    ASSIGNMENT = auto()
    DISCARD = auto()
    BINARY_OPERATION = auto()
    UNARY_OPERATION = auto()
    IF_STATEMENT = auto()
    WHILE_STATEMENT = auto()
    FOR_STATEMENT = auto()
    RETURN_STATEMENT = auto()
    FUNCTION_CALL = auto()
    IDENTIFIER = auto()
    LITERAL = auto()
    OBJECT_INSTANTIATION = auto()
    ARRAY_INSTANTIATION = auto()
    CAST = auto()
    ATTRIBUTE = auto()
    CLASS_PROPERTY = auto()
    METHOD_CALL = auto()
    BREAK_STATEMENT = auto()
    CONTINUE_STATEMENT = auto()
    ASSERT_STATEMENT = auto()
    TERNARY_OPERATION = auto()
    ARRAY_ACCESS = auto()

@dataclass
class BlockProperties:
    """The properties of the current block to be passed to statements and lower blocks"""
    
    """Whether the block is contained in a class"""
    is_class:bool = False
    """Whether this block is the top level block of the module"""
    is_top_level:bool = True
    """Whether this block is contained in a loop (Note that this keeps the value True if nested multiple loops deep and is False only if it's not within a loop)"""
    is_loop:bool = False
    """Whether this block is contained inside a function block"""
    in_function:bool = False
    """The list of variables declared in this scope"""
    block_vars:List['PVariableDeclaration'] = field(default_factory=list)

    def copy_with(self, is_loop:bool=False,
                  is_class:bool=False, in_function:bool=False,
                  is_top_level:bool=False):
        return BlockProperties(
            is_loop=self.is_loop or is_loop,
            is_class= self.is_class or is_class,
            is_top_level= self.is_top_level and is_top_level,
            in_function=in_function or self.in_function)

@dataclass
class PStatement:
    """Base class for all AST nodes"""
    node_type: NodeType
    position: Position
    
    def __post_init__(self):
        #add field to progress backwards though the tree
        self._parent: Optional["PStatement"] = None
        
    @property
    def children(self) -> Generator["PStatement", None, None]:
        if False:
            yield
        return

    @property
    def parent(self) -> "PStatement":
        """The parent element in the tree. Used to calculate the element's depth/scope depth"""
        if self._parent is None:
            assert isinstance(self, PProgram) #only PProgram does not have a parent
            raise CompilerError("The top level PProgram node does not have a parent!")
        return self._parent
    
    @property
    def depth_from_next_loop(self) -> int:
        """How many scopes deep this statement is from the above loop
        a loop has a depth of 0. Any statement inside has a depth of 1 (or more if scoped within)
        This is used to count how many scopes to leave when breaking/continuing from a loop"""
        if isinstance(self, (PWhileStatement, PForStatement)):
            return 0 #At the loop level
            # Here it's still 0 even for a for loop which has an extra scope encompassing it
            # because it leaves the for-scope at the first instruction at the loop exit block
        elif isinstance(self, PBlock):
            # In a block increase scope by 1 and look above
            return self.parent.depth_from_next_loop + 1
        return self.parent.depth_from_next_loop
    
    @property
    def depth_from_next_function(self) -> int:
        """How many scopes deep this statement is within a function
        A statement in a function's top scope has a depth of 1 including its params
        This is used to calculate how many scopes to leave when returning from a function"""
        # TODO: populate this in every node and use to fix leaving scopes in functions
        if isinstance(self, (PFunction)):
            return 1 #At the Function level (1 scope for the parameters!)
        elif isinstance(self, (PForStatement, PBlock)):
            # In a block increase scope by 1 and look above
            # (for) Loops also create an intermediate scope for the initializer
            return self.parent.depth_from_next_function + 1
        return self.parent.depth_from_next_function
    
    #TODO: Convert to method with checks with given depth
        # that way you can allocate a GC scope larger than a single scope to avoid nesting too many
        # use a heuristic to evaluate how deep to go.
        # NB: will need to reevaluate how the "depth_from_next_XX" is calculated
    
    @property
    def count_ref_vars_declared_in_scope(self):
        """Counts the number of reference Variables are defined in the scope"""
        return 0
    
    def _setup_parents(self):
        if self._parent is not None:
            return #speedup and prevents cycles
        for child in self.children:
            child._setup_parents()
            child._parent = self

    def generate_llvm(self, context:CodeGenContext) -> None:
        raise NotImplementedError(f"Code generation for {type(self)} is not yet implemented")
    
    def exit_with_error(self, context:CodeGenContext, error_code:int=1, error_message:str="Error "):
        printf = context.scopes.get_symbol("fprintf").func_ptr
        assert printf is not None
        exit_func = context.scopes.get_symbol("exit").func_ptr
        assert exit_func is not None
        error_message += f" in file %s at line %d:%d\n"
        error_message_c_str_with_format = context.get_char_ptr_from_string(error_message)
        context.builder.call(printf, [
            ir.Constant(ir.IntType(32), 2), #stderr
            error_message_c_str_with_format,
            context.get_char_ptr_from_string(self.position.filename), # filename
            ir.Constant(ir.IntType(32), self.position.line), # line number
            ir.Constant(ir.IntType(32), self.position.column), # Column number
        ])
        context.builder.call(exit_func, [ir.Constant(ir.IntType(32), error_code)])
        context.builder.unreachable()
        

@dataclass
class PExpression(PStatement):
    """Base class for all expression nodes - nodes that produce a value"""
    
    def __post_init__(self):
        super().__post_init__()
        self.expr_type:Optional[Typ] = None  # Will be set during typing pass
        self.is_compile_time_constant:bool = False
        self.is_lvalue = getattr(self, "is_lvalue", False)

    def generate_llvm(self, context:CodeGenContext, get_ptr_to_expression=False) -> ir.NamedValue:
        raise NotImplementedError(f"Code generation for {type(self)} is not yet implemented")

@dataclass
class PNoop(PExpression):
    def __init__(self, lexeme:Lexeme):
        super().__init__(NodeType.EMPTY, lexeme.pos)
        self.is_compile_time_constant = True
    
    def generate_llvm(self, context:CodeGenContext, get_ptr_to_expression=False) -> ir.Value:
        assert not get_ptr_to_expression, "Cannot get pointer to a NoOp"
        return ir.Constant(ir.IntType(1), True)

@dataclass
class PProgram(PStatement):
    """Root node of the program"""
    statements: List[PStatement]
        
    @property
    def children(self) -> Generator["PStatement", None, None]:
        for stmt in self.statements:
            yield stmt
        return

    def __init__(self, statements: List[PStatement], lexeme: Lexeme):
        super().__init__(NodeType.PROGRAM, lexeme.pos)
        self.statements = statements

@dataclass
class PFunction(PStatement):
    """Function definition node"""
    name: str
    return_type: 'PType'
    function_args: List['PVariableDeclaration']  # List of (type, name) tuples
    body: 'PBlock'
    is_called: bool = False
    _return_typ_typed:Optional[Typ] = None
    is_builtin:bool=False
        
    @property
    def children(self) -> Generator["PStatement", None, None]:
        for stmt in (self.return_type, 
                     *self.function_args,
                     self.body):
            yield stmt
        return
        
    @property
    def count_ref_vars_declared_in_scope(self) -> int:
        """Returns the number of reference variables defined in the scope defined by this block"""
        ref_vars = 0
        for stmt in self.function_args:
            if stmt.is_root_to_declare_to_gc:
                ref_vars += 1
        return ref_vars
    
    def __hash__(self) -> int:
        return hash(self.name) + hash(self.return_type) + sum([hash(func) for func in self.function_args])
    
    @property
    def return_typ_typed(self) -> Typ:
        if self._return_typ_typed is None:
            raise TypingError(f"Function has not been typed yet")
        return self._return_typ_typed

    def __init__(self, name: str, return_type: 'PType', parameters: List['PVariableDeclaration'],
                 body: 'PBlock', lexeme: Lexeme, is_builtin:bool=False):
        super().__init__(NodeType.FUNCTION, lexeme.pos)
        self.name = name
        self.return_type = return_type
        self.function_args = parameters
        self.body = body
        self.is_builtin = is_builtin
        
    def generate_llvm(self, context: CodeGenContext) -> None:
        if not context.scopes.has_symbol(self.name):
            assert False, "The function should be declared already"
            func_type = ir.FunctionType(self.return_typ_typed.get_llvm_value_type(context),
                                        [arg.typer_pass_var_type.get_llvm_value_type(context) for arg in self.function_args])
            func = ir.Function(context.module, func_type, name=self.name)
        else:
            func = context.scopes.get_symbol(self.name).func_ptr
            assert func is not None
        
        context.builder.position_at_start(func.append_basic_block(f'__{self.name}_entrypoint_{self.position.index}'))

        context.enter_scope(self.count_ref_vars_declared_in_scope)
        # defined args in scoper:
        assert len(self.function_args) == len(func.args)
        for param, arg_value in zip(self.function_args, func.args):
            # build alloca to a function argument
            # In llvm function arguments are just NamedValues and don't have a mem address.
            # We define a location on the stack for them so they can be written to.
            # This will be optimized out by the mem2reg pass
                # NB: written to just means that an argument x can be written to.
                # The caller will not have the value changed from his point of view, he just passed a value not a reference!
            arg_alloca = context.builder.alloca(arg_value.type)
            context.builder.store(arg_value, arg_alloca)
            context.scopes.declare_var(param.name,
                                       param.typer_pass_var_type.get_llvm_value_type(context),
                                       arg_alloca
                                       )
            if param.is_root_to_declare_to_gc:
                context.add_root_to_gc(arg_alloca,
                                       param.typer_pass_var_type,
                                       param.name)
        # run body statements
        self.body.generate_llvm(context)
        
        #ensure all block are properly terminated
        for block in list(func.basic_blocks):
            assert isinstance(block, ir.Block)
            if not block.is_terminated:
                with context.builder.goto_block(block):
                    # add default return to ensure branch is terminated
                    # will be optimized out if unreachable
                    if func.function_type.return_type == ir.VoidType():
                        context.builder.ret_void()
                    else:
                        context.builder.ret(self.return_typ_typed.default_llvm_value(context))

        # GC scope leaving handled by the return instruction (implicit for void methods)
        # but still need to go up a scope outside of the function block
        context.scopes.leave_scope()

@dataclass    
class PMethod(PFunction):
    _class_type:Optional[Typ]=None

    def __init__(self, name: str, return_type: 'PType', class_type:'PType',
                 parameters: List['PVariableDeclaration'],
                 body: 'PBlock', lexeme: Lexeme, is_builtin:bool = False):
        super().__init__(name, return_type, parameters, body, lexeme, is_builtin=is_builtin)
        
        # Add implicit "this" argument
        # TODO: Do not include for static methods!
        self.function_args.insert(0, PVariableDeclaration('this', class_type,
                                                          None, class_type.position))
        
    @property
    def explicit_arguments(self):
        return self.function_args[1:]
    
    @property
    def class_type(self):
        if self._class_type is None:
            raise TypingError(f"Function has not been typed yet")
        return self._class_type
    
    def __hash__(self) -> int:
        return super().__hash__()
    
    def __eq__(self, value: object) -> bool:
        if not isinstance(value, PMethod):
            return False
        return super().__eq__(value)
        
    def generate_llvm(self, context: CodeGenContext) -> None:        
        method_name = context.get_method_symbol_name(self.class_type.name, self.name)
        if not context.scopes.has_symbol(method_name):
            assert False, "This should not happen. Method should be declared already"
            func_type = ir.FunctionType(self.return_typ_typed.get_llvm_value_type(context),
                                        [arg.typer_pass_var_type.get_llvm_value_type(context) for arg in self.function_args])
            func = ir.Function(context.module, func_type, name=self.name)
        else:
            func = context.scopes.get_symbol(method_name).func_ptr
            assert func is not None
        
        context.builder.position_at_start(func.append_basic_block(f'__{self.name}_entrypoint_{self.position.index}'))

        context.enter_scope(self.count_ref_vars_declared_in_scope)
        # defined args in scoper:
        assert len(self.function_args) == len(func.args)
        for param, arg_value in zip(self.function_args, func.args):
            # build alloca to a function argument
            # In llvm function arguments are just NamedValues and don't have a mem address.
            # We define a location on the stack for them so they can be written to.
            # This will be optimized out by the mem2reg pass
                # NB: written to just means that an argument x can be written to.
                # The caller will not have the value changed from his point of view, he just passed a value not a reference!
            arg_alloca = context.builder.alloca(arg_value.type)
            context.builder.store(arg_value, arg_alloca)
            context.scopes.declare_var(param.name,
                                       param.typer_pass_var_type.get_llvm_value_type(context),
                                       arg_alloca
                                       )
            if param.typer_pass_var_type.is_reference_type:
                context.add_root_to_gc(arg_alloca,
                                       param.typer_pass_var_type,
                                       param.name)
        # run body statements
        self.body.generate_llvm(context)

        # scope leaving handled by the return instruction (implicit for void methods)

@dataclass
class PClass(PStatement):
    """Class definition node"""
    name: str
    fields: List['PClassField']
    methods: List[PMethod]
    _class_typ:Optional[Typ] = None
    
    @property
    def class_typ(self) ->Typ:
        if self._class_typ is None:
            raise TypingError('Class has not been typed yet')
        return self._class_typ
        
    @property
    def children(self) -> Generator["PStatement", None, None]:
        for stmt in (*self.fields, 
                     *self.methods):
            yield stmt
        return

    def __init__(self, name: str, fields: List['PClassField'],
                 methods: List[PMethod], lexeme: Lexeme):
        super().__init__(NodeType.CLASS, lexeme.pos)
        self.name = name
        self.fields = fields
        self.methods = methods

@dataclass
class PClassField(PStatement):
    """Class field definition node"""
    name: str
    var_type: 'PType'
    is_public: bool
    default_value: Optional[PExpression]
    _typer_pass_var_type: Optional[Typ] = None
    is_assigned: bool = False
    is_read: bool = False
    is_builtin: bool = False
    
    @property
    def typer_pass_var_type(self) -> Typ:
        if self._typer_pass_var_type is None:
            raise TypingError("Typer has not typed this node yet!")
        return self._typer_pass_var_type
        
    @property
    def children(self) -> Generator["PStatement", None, None]:
        yield self.var_type
        if self.default_value is not None:
            yield self.default_value
        return

    def __init__(self, name: str, type: 'PType', is_public: bool, lexeme: Lexeme, default_value:Optional[PExpression],
                 is_builtin:bool = False):
        super().__init__(NodeType.CLASS_PROPERTY, lexeme.pos)
        self.name = name
        self.var_type = type
        self.is_public = is_public
        self.default_value = default_value
        self.is_builtin = is_builtin
        
    def __hash__(self) -> int:
        return hash(self.name) + hash(self.var_type)
    
    def __eq__(self, value: object) -> bool:
        if not isinstance(value, PClassField):
            return False
        return self.name == value.name and self.var_type == value.var_type

@dataclass
class PBlock(PStatement):
    """Block of statements"""
    statements: List[PStatement]
    block_properties:BlockProperties

    def __init__(self, statements: List[PStatement], lexeme: Lexeme, block_properties:BlockProperties):
        super().__init__(NodeType.BLOCK, lexeme.pos)
        self.statements = statements
        self.block_properties = block_properties
        
    @property
    def children(self) -> Generator["PStatement", None, None]:
        for stmt in self.statements:
            yield stmt
        return
        
    @property
    def count_ref_vars_declared_in_scope(self) -> int:
        """Returns the number of reference variables defined in the scope defined by this block"""
        ref_vars = 0
        for stmt in self.children:
            if isinstance(stmt, PVariableDeclaration) and stmt.is_root_to_declare_to_gc:
                ref_vars += 1
        return ref_vars
    
    def generate_llvm(self, context: CodeGenContext, build_gc_scope=True) -> None:
        """Generates the llvm IR code for this PBlock

        Args:
            context (CodeGenContext): The context containing the current module
            build_basic_block (bool, optional): Whether to generate a new basic block for this PBlock.
            Also terminates the  current basic block and creates a new one to continue after this one. Defaults to True.
        """        
        #TODO: optimize this to only create a scope when ref-vars are present.
            # need to make sure to count correctly when exiting a function scope from anywhere within a
            # function or when leaving a loop (break/continue)!
        #create scope
        context.enter_scope(self.count_ref_vars_declared_in_scope)
        for stmt in self.statements:
            stmt.generate_llvm(context)
            assert isinstance(context.builder.block, ir.Block)
            if context.builder.block.is_terminated:
                #TODO: add warning here if it still has statements in terminated block
                break
        else:
            #otherwise leave the current scope for the block if the block has not been terminated by a return, break or continue
            context.leave_scope()

@dataclass
class PVariableDeclaration(PStatement):
    """Variable declaration node"""
    name: str
    var_type: 'PType'
    _typer_pass_var_type: Optional[Typ]
    initial_value: Optional[PExpression]
    
    @property
    def typer_pass_var_type(self) -> Typ:
        if self._typer_pass_var_type is None:
            raise CompilerError('PVarDecl fas not been typed')
        return self._typer_pass_var_type
        
    @property
    def children(self) -> Generator["PStatement", None, None]:
        yield self.var_type
        if self.initial_value is not None:
            yield self.initial_value
        return
    
    @property
    def is_root_to_declare_to_gc(self) -> bool:
        """Flag which says whether this variable declaration should be declared to the GC to track its objects"""
        return self.typer_pass_var_type.is_reference_type

    def __init__(self, name: str, var_type: 'PType', initial_value: Optional[PExpression], lexeme_pos: Union[Lexeme, Position]):
        super().__init__(NodeType.VARIABLE_DECLARATION, lexeme_pos.pos if isinstance(lexeme_pos, Lexeme) else lexeme_pos)
        self.name = name
        self.var_type = var_type
        self.initial_value = initial_value
    
    def __hash__(self) -> int:
        return hash(self.name) + hash(self.var_type)
    
    def __eq__(self, value: object) -> bool:
        if not isinstance(value, PVariableDeclaration):
            return False
        return self.name == value.name and self.var_type == value.var_type
    
    def generate_llvm(self, context: CodeGenContext) -> None:        
        type_ = self.typer_pass_var_type.get_llvm_value_type(context)
        alloca = context.builder.alloca(type_,name=self.name)
        
        if self.is_root_to_declare_to_gc:
            context.add_root_to_gc(alloca,
                                self.typer_pass_var_type,
                                self.name)
        
        if self.initial_value is None:
            init = self.typer_pass_var_type.default_llvm_value(context)
        else:
            init = self.initial_value.generate_llvm(context, False)
        
        context.scopes.declare_var(self.name, type_, alloca)
        context.builder.store(init, alloca)

@dataclass
class PAssignment(PExpression):
    """Assignment operation node"""
    target: Union['PIdentifier', 'PDotAttribute', 'PArrayIndexing']
    value: PExpression

    def __init__(self, target: Union['PIdentifier', 'PDotAttribute', 'PArrayIndexing'], value: PExpression, lexeme: Lexeme):
        super().__init__(NodeType.ASSIGNMENT, lexeme.pos)
        self.target = target
        self.target.is_lvalue = True
        self.value = value
        
    @property
    def children(self) -> Generator["PStatement", None, None]:
        yield self.target
        yield self.value
        return
        
    def generate_llvm(self, context:CodeGenContext, get_ptr_to_expression=False) -> ir.Value:
        assert not get_ptr_to_expression, "Cannot get pointer to an assignment value"
        # get ptr to assign to
        if isinstance(self.target, PIdentifier):
            target = context.scopes.get_symbol(self.target.name).alloca
        elif isinstance(self.target, (PDotAttribute, PArrayIndexing)):
            #should return GEP ptr value
            target = self.target.generate_llvm(context, get_ptr_to_expression=True)
        else:
            raise NotImplementedError()
        
        assert target is not None
        #get value to assign
        value = self.value.generate_llvm(context)
        #assign to target
        context.builder.store(value, target)
        #return the value
        return value

class PDiscard(PStatement):
    """Discard an expression result"""
    expression:PExpression
        
    @property
    def children(self) -> Generator["PStatement", None, None]:
        yield self.expression
        return
    
    def __init__(self, expression:PExpression, lexeme: Lexeme):
        super().__init__(NodeType.DISCARD, lexeme.pos)
        self.expression = expression
    
    def generate_llvm(self, context: CodeGenContext) -> None:
        self.expression.generate_llvm(context)
        #discard result

@dataclass
class PBinaryOperation(PExpression):
    """Binary operation node"""
    operation: BinaryOperation
    left: PExpression
    right: PExpression

    def __init__(self, operation: BinaryOperation, left: PExpression, right: PExpression, lexeme: Lexeme):
        super().__init__(NodeType.BINARY_OPERATION, lexeme.pos)
        self.operation = operation
        self.left = left
        self.right = right
        # TODO : This value can be true, calculated at compile time and optimized out if left and right are compile time constants
        self.is_compile_time_constant = False
        
    @property
    def children(self) -> Generator["PStatement", None, None]:
        yield self.left
        yield self.right
        return
        
    def generate_and_short_circuit(self, left:ir.Value, context:CodeGenContext):
        # Create basic blocks for different paths
        curr_block = context.builder.block
        true_block = context.builder.append_basic_block(f'and_true_{self.position.index}')
        end_block = context.builder.append_basic_block(f'and_end_{self.position.index}')
        
        # Conditional branch based on left side
        context.builder.cbranch(left, true_block, end_block)

        # True block: evaluate right side
        context.builder.position_at_end(true_block)
        right = self.right.generate_llvm(context)
        context.builder.branch(end_block)

        # Merge block: PHI node to combine results
        context.builder.position_at_end(end_block)
        phi = context.builder.phi(ir.IntType(1))
        phi.add_incoming(right, true_block)
        phi.add_incoming(ir.Constant(ir.IntType(1), 0), curr_block)

        return phi
        
    def generate_or_short_circuit(self, left:ir.Value, context:CodeGenContext):
        # Create basic blocks for different paths
        curr_block = context.builder.block
        false_block = context.builder.append_basic_block(f'or_false_{self.position.index}')
        end_block = context.builder.append_basic_block(f'or_end_{self.position.index}')
        
        # Conditional branch based on left side
        context.builder.cbranch(left, end_block, false_block)

        # False block: evaluate right side
        context.builder.position_at_end(false_block)
        right = self.right.generate_llvm(context)
        context.builder.branch(end_block)

        # Merge block: PHI node to combine results
        context.builder.position_at_end(end_block)
        phi = context.builder.phi(ir.IntType(1))
        phi.add_incoming(right, false_block)
        phi.add_incoming(ir.Constant(ir.IntType(1), 1), curr_block)

        return phi

    def generate_llvm(self, context:CodeGenContext, get_ptr_to_expression=False) -> ir.NamedValue:
        assert not get_ptr_to_expression, "Cannot get pointer to an operation result"
        left = self.left.generate_llvm(context)
        if self.expr_type is None:
            raise CompilerError(f"AST Node has not been typed at location {self.position}")
        if self.expr_type.is_reference_type:
            raise NotImplementedError() #here should call the builtin's Equals() function
        if self.expr_type.name not in TYPE_INFO:
            raise NotImplementedError() # Should never happen
        type_info = TYPE_INFO[self.expr_type.name]
        
        if self.operation == BinaryOperation.LOGIC_AND:
            ret_val = context.builder.and_(left, self.right.generate_llvm(context))
        elif self.operation == BinaryOperation.LOGIC_OR:
            ret_val = context.builder.or_(left, self.right.generate_llvm(context))
        elif self.operation == BinaryOperation.BOOL_AND:
            ret_val = self.generate_and_short_circuit(left, context)
        elif self.operation == BinaryOperation.BOOL_OR:
            ret_val = self.generate_or_short_circuit(left, context)
        elif self.operation in (BinaryOperation.BOOL_EQ,
                                BinaryOperation.BOOL_GEQ,
                                BinaryOperation.BOOL_GT,
                                BinaryOperation.BOOL_LEQ,
                                BinaryOperation.BOOL_LT,
                                BinaryOperation.BOOL_NEQ):
            if type_info.type_class == TypeClass.FLOAT:
                ret_val = context.builder.fcmp_ordered(self.operation.value, left, self.right.generate_llvm(context))
            elif type_info.type_class in (TypeClass.INTEGER,TypeClass.BOOLEAN):
                if type_info.is_signed:
                    ret_val = context.builder.icmp_signed(self.operation.value, left, self.right.generate_llvm(context))
                else:
                    ret_val = context.builder.icmp_unsigned(self.operation.value, left, self.right.generate_llvm(context))
        elif self.operation == BinaryOperation.DIVIDE:
            if type_info.type_class == TypeClass.FLOAT:
                ret_val = context.builder.fdiv(left, self.right.generate_llvm(context))
            elif type_info.type_class == TypeClass.INTEGER:
                ret_val = context.builder.sdiv(left, self.right.generate_llvm(context)) if type_info.is_signed else context.builder.udiv(left, self.right.generate_llvm(context))
            else:
                raise NotImplementedError()
        elif self.operation == BinaryOperation.MINUS:
            if type_info.type_class == TypeClass.FLOAT:
                ret_val = context.builder.fsub(left, self.right.generate_llvm(context))
            elif type_info.type_class == TypeClass.INTEGER:
                ret_val = context.builder.sub(left, self.right.generate_llvm(context))
            else:
                raise NotImplementedError()
        elif self.operation == BinaryOperation.PLUS:
            if type_info.type_class == TypeClass.FLOAT:
                ret_val = context.builder.fadd(left, self.right.generate_llvm(context))
            elif type_info.type_class == TypeClass.INTEGER:
                ret_val = context.builder.add(left, self.right.generate_llvm(context))
            else:
                raise NotImplementedError()
        elif self.operation == BinaryOperation.MOD:
            if type_info.type_class == TypeClass.FLOAT:
                ret_val = context.builder.frem(left, self.right.generate_llvm(context))
            elif type_info.type_class == TypeClass.INTEGER:
                ret_val = context.builder.srem(left, self.right.generate_llvm(context)) if type_info.is_signed else context.builder.urem(left, self.right.generate_llvm(context))
            else:
                raise NotImplementedError()
        elif self.operation == BinaryOperation.SHIFT_LEFT:
            if type_info.type_class == TypeClass.INTEGER:
                ret_val = context.builder.shl(left, self.right.generate_llvm(context))
            else:
                raise NotImplementedError()
        elif self.operation == BinaryOperation.SHIFT_RIGHT:
            if type_info.type_class == TypeClass.INTEGER:
                ret_val = context.builder.ashr(left, self.right.generate_llvm(context)) if type_info.is_signed else context.builder.lshr(left, self.right.generate_llvm(context))
            else:
                raise NotImplementedError()
        elif self.operation == BinaryOperation.TIMES:
            if type_info.type_class == TypeClass.FLOAT:
                ret_val = context.builder.fmul(left, self.right.generate_llvm(context))
            elif type_info.type_class == TypeClass.INTEGER:
                ret_val = context.builder.mul(left, self.right.generate_llvm(context))
            else:
                raise NotImplementedError()
        elif self.operation == BinaryOperation.XOR:
            if type_info.type_class in (TypeClass.INTEGER, TypeClass.BOOLEAN):
                ret_val = context.builder.xor(left, self.right.generate_llvm(context))
            else:
                raise NotImplementedError()
        else:
            raise NotImplementedError()
        assert isinstance(ret_val, ir.NamedValue)
        return ret_val

@dataclass
class PUnaryOperation(PExpression):
    """Unary operation node"""
    operation: UnaryOperation
    operand: PExpression

    def __init__(self, operation: UnaryOperation, operand: PExpression, lexeme: Lexeme):
        super().__init__(NodeType.UNARY_OPERATION, lexeme.pos)
        self.operation = operation
        self.operand = operand
        # TODO : This value can be true, calculated at compile time and optimized out if the operator is not inc/dec and the operand is const
        self.is_compile_time_constant = False
        # TODO: This should always be false no?
        self.operand.is_lvalue = self.operation in (UnaryOperation.PRE_INCREMENT, UnaryOperation.PRE_DECREMENT,
                                                    UnaryOperation.POST_INCREMENT, UnaryOperation.POST_DECREMENT)
        
    @property
    def children(self) -> Generator["PStatement", None, None]:
        yield self.operand
        return

    def generate_llvm(self, context:CodeGenContext, get_ptr_to_expression=False) -> ir.Value:
        assert not get_ptr_to_expression, "Cannot get pointer to an operation result"
        
        operand = self.operand.generate_llvm(context, get_ptr_to_expression=self.operand.is_lvalue)
        assert self.operand.expr_type is not None
        assert self.expr_type is not None
        typeinfo = TYPE_INFO.get(self.operand.expr_type.name, TypeInfo(TypeClass.CLASS))
        if self.operation in (UnaryOperation.BOOL_NOT, UnaryOperation.LOGIC_NOT, UnaryOperation.MINUS):
            if self.operation == UnaryOperation.BOOL_NOT:
                if typeinfo.type_class == TypeClass.FLOAT:
                    ret_val = context.builder.fcmp_ordered('==', operand, self.operand.expr_type.default_llvm_value(context))
                elif typeinfo.type_class == TypeClass.BOOLEAN:
                    ret_val = context.builder.not_(operand)
                else:
                    ret_val = context.builder.icmp_unsigned('==', operand, self.operand.expr_type.default_llvm_value(context))
            elif self.operation == UnaryOperation.LOGIC_NOT:
                if typeinfo.type_class in [TypeClass.FLOAT, TypeClass.BOOLEAN, TypeClass.INTEGER]:
                    ret_val = context.builder.not_(operand)
                else:
                    raise NotImplementedError()
            elif self.operation == UnaryOperation.MINUS:
                if typeinfo.type_class == TypeClass.FLOAT:
                    ret_val = context.builder.fneg(operand)
                else:
                    ret_val = context.builder.neg(operand)
        elif self.operation in (UnaryOperation.POST_DECREMENT, UnaryOperation.POST_INCREMENT,
                                UnaryOperation.PRE_DECREMENT, UnaryOperation.PRE_INCREMENT):
            operand_ptr = operand
            operand = context.builder.load(operand_ptr,
                                           typ=self.operand.expr_type.get_llvm_value_type(context))
            if self.operation == UnaryOperation.PRE_INCREMENT:
                ret_val = context.builder.add(operand, ir.Constant(self.expr_type.get_llvm_value_type(context),1))
                # self.operand is a ptr (or NamedValue)
                assert isinstance(self.operand, (PIdentifier, PArrayIndexing, PThis, PDotAttribute))
                context.builder.store(ret_val, operand_ptr)
            elif self.operation == UnaryOperation.PRE_DECREMENT:
                ret_val = context.builder.sub(operand, ir.Constant(self.expr_type.get_llvm_value_type(context),1))
                assert isinstance(self.operand, (PIdentifier, PArrayIndexing, PThis, PDotAttribute))
                context.builder.store(ret_val, operand_ptr)
            elif self.operation == UnaryOperation.POST_INCREMENT:
                ret_val = operand
                after_op_val = context.builder.add(operand, ir.Constant(self.expr_type.get_llvm_value_type(context),1))
                assert isinstance(self.operand, (PIdentifier, PArrayIndexing, PThis, PDotAttribute))
                context.builder.store(after_op_val, operand_ptr)
            elif self.operation == UnaryOperation.POST_DECREMENT:
                ret_val = operand
                after_op_val = context.builder.sub(operand, ir.Constant(self.expr_type.get_llvm_value_type(context),1))
                assert isinstance(self.operand, (PIdentifier, PArrayIndexing, PThis, PDotAttribute))
                context.builder.store(after_op_val, operand_ptr)
        else:
            raise NotImplementedError()
        assert isinstance(ret_val, ir.NamedValue)
        return ret_val

@dataclass
class PIfStatement(PStatement):
    """If statement node"""
    condition: PExpression
    then_block: PBlock
    else_block: Optional[PBlock]

    def __init__(self, condition: PExpression, then_block: PBlock,
                 else_block: Optional[PBlock], lexeme: Lexeme):
        super().__init__(NodeType.IF_STATEMENT, lexeme.pos)
        self.condition = condition
        self.then_block = then_block
        self.else_block = else_block
        
    @property
    def children(self) -> Generator["PStatement", None, None]:
        yield self.condition 
        yield self.then_block
        if self.else_block is not None:
            yield self.else_block
        return
    
    def generate_llvm(self, context: CodeGenContext) -> None:
        if self.else_block is not None:
            with context.builder.if_else(self.condition.generate_llvm(context)) as (then, otherwise):
                with then:
                    self.then_block.generate_llvm(context)
                with otherwise:
                    self.else_block.generate_llvm(context)
        else:
            with context.builder.if_then(self.condition.generate_llvm(context)):
                self.then_block.generate_llvm(context)
                

@dataclass
class PWhileStatement(PStatement):
    """While loop node"""
    condition: PExpression
    body: PBlock

    def __init__(self, condition: PExpression, body: PBlock, lexeme: Lexeme):
        super().__init__(NodeType.WHILE_STATEMENT, lexeme.pos)
        self.condition = condition
        self.body = body
        
    @property
    def children(self) -> Generator["PStatement", None, None]:
        yield self.condition
        yield self.body
        return
        
    def generate_llvm(self, context: CodeGenContext) -> None:
        # Create basic blocks for loop structure
        cond_block = context.builder.append_basic_block(f"w_cond_{self.condition.position.index}")
        body_block = context.builder.append_basic_block(f"w_body_{self.body.position.index}")
        after_block = context.builder.append_basic_block(f"w_after_{self.body.position.index}")
        #add info pointing to condition and end of loop for continue/break
        context.loopinfo.append(LoopContext(cond_block,after_block, is_for_loop=False, current_loop_scope_depth=0))

        context.builder.branch(cond_block)
        # Generate condition in condition block
        context.builder.position_at_end(cond_block)
        cond_value = self.condition.generate_llvm(context)
        context.builder.cbranch(cond_value, body_block, after_block)

        # Generate loop body in body block
        context.builder.position_at_end(body_block)
        self.body.generate_llvm(context)
        
        # make sure end of body is reachable:
        assert isinstance(context.builder.block, ir.Block)
        if context.builder.block.is_terminated:
            context.loopinfo.pop()
            return
        # Branch back to condition block after body execution
        context.builder.branch(cond_block)

        # Set insertion point to after block for subsequent code
        context.builder.position_at_end(after_block)
        #pop loop info, we're leaving block
        context.loopinfo.pop()

@dataclass
class PForStatement(PStatement):
    """For loop node"""
    initializer: Union[PVariableDeclaration, PAssignment, PNoop]
    condition: Union[PExpression, PNoop]
    increment: Union[PStatement, PNoop]
    body: PBlock

    def __init__(self, initializer: Union[PVariableDeclaration, PAssignment, PNoop], condition: Union[PExpression, PNoop],
                 increment: Union[PStatement, PNoop], body: PBlock, lexeme: Lexeme):
        super().__init__(NodeType.FOR_STATEMENT, lexeme.pos)
        self.initializer = initializer
        self.condition = condition
        self.increment = increment
        self.body = body
        
    @property
    def children(self) -> Generator["PStatement", None, None]:
        yield self.initializer
        yield self.condition
        yield self.increment
        yield self.body
        return
        
    def generate_llvm(self, context: CodeGenContext) -> None:
        for_initializer_ref_vars = 0
        if isinstance(self.initializer, PVariableDeclaration):
            for_initializer_ref_vars = int(self.initializer.typer_pass_var_type.is_reference_type)
        
        context.enter_scope(for_initializer_ref_vars)
        
        self.initializer.generate_llvm(context)
        # Create basic blocks for loop structure
        increment_block:ir.Block = context.builder.append_basic_block(f"for_inc_{self.condition.position.index}")
        cond_block:ir.Block = context.builder.append_basic_block(f"for_cond_{self.condition.position.index}")
        body_block:ir.Block = context.builder.append_basic_block(f"for_body_{self.body.position.index}")
        after_block:ir.Block = context.builder.append_basic_block(f"for_after_{self.body.position.index}")
        #add info pointing to condition and end of loop for continue/break
        context.loopinfo.append(LoopContext(increment_block,after_block,
                                            is_for_loop=True, current_loop_scope_depth=1))
        
        context.builder.branch(cond_block)
        # Generate condition in condition block
        context.builder.position_at_end(cond_block)
        cond_value = self.condition.generate_llvm(context)
        context.builder.cbranch(cond_value, body_block, after_block)

        # Generate loop body in body block
        context.builder.position_at_end(body_block)
        self.body.generate_llvm(context)
        assert isinstance(context.builder.block, ir.Block)
        if not context.builder.block.is_terminated:
            context.builder.branch(increment_block)
        # at the end of the for loop run the increment statement
        context.builder.position_at_end(increment_block)
        self.increment.generate_llvm(context)
        # Branch back to condition block after body execution
        context.builder.branch(cond_block)

        # Set insertion point to after block for subsequent code
        context.builder.position_at_end(after_block)
        #pop loop info, we're leaving block
        context.loopinfo.pop()
        #remove initializer scope
        context.leave_scope()

@dataclass
class PReturnStatement(PStatement):
    """Return statement node"""
    value: PExpression

    def __init__(self, value: Optional[PExpression], lexeme: Lexeme):
        super().__init__(NodeType.RETURN_STATEMENT, lexeme.pos)
        self.value = value or PVoid(lexeme)
        
    @property
    def children(self) -> Generator["PStatement", None, None]:
        if self.value is not None:
            yield self.value
        return
        
    def generate_llvm(self, context: CodeGenContext) -> None:
        # if we are within the module's main function
        if context.global_exit_block is not None:
            #make sure the main function returns the correct return type
            assert self.value.expr_type is not None
            assert self.value.expr_type.get_llvm_value_type(context) == ir.IntType(32)
            exit_code = context.scopes.get_symbol(EXIT_CODE_GLOBAL_VAR_NAME).alloca
            assert exit_code is not None
            context.builder.store(self.value.generate_llvm(context), exit_code)
            # leave all scopes not needed as GC cleanup will handle destroying all scopes
            # go to exit
            context.builder.branch(context.global_exit_block)
            return
            
        if isinstance(self.value, PVoid):
            context.leave_scope(self.depth_from_next_function)
            context.builder.ret_void()
        else:
            ret_val = self.value.generate_llvm(context)
            context.leave_scope(self.depth_from_next_function)
            context.builder.ret(ret_val)
    
    @staticmethod
    def implicit_return(position:Position):
        ret = PReturnStatement(None, Lexeme.default)
        ret.position = position
        return ret

@dataclass
class PFunctionCall(PExpression):
    """Function call node"""
    function: 'PIdentifier'
    arguments: List[PExpression]

    def __init__(self, function: 'PIdentifier', arguments: List[PExpression], lexeme: Lexeme):
        super().__init__(NodeType.FUNCTION_CALL, lexeme.pos)
        self.function = function
        self.arguments = arguments
        if function.name == 'main':
            raise CompilerError(f"Cannot call main function directly")
        
    @property
    def children(self) -> Generator["PStatement", None, None]:
        for stmt in (self.function, 
                     *self.arguments):
            yield stmt
        return
    
    def generate_llvm(self, context:CodeGenContext, get_ptr_to_expression=False) -> ir.Value:
        assert not get_ptr_to_expression, "Cannot get pointer to a function result"
        # get function pointer
        fun = self.function.generate_llvm(context)
        assert isinstance(fun, ir.Function)
        # get ptrs to all arguments
        args = [context.builder.bitcast(arg.generate_llvm(context),expected_arg.type) 
                for arg, expected_arg in zip(self.arguments, fun.args)]
        assert isinstance(fun, ir.Function)
        #call function
        ret_val = context.builder.call(fun, args)        
        return ret_val

@dataclass
class PMethodCall(PExpression):
    """Method call node"""
    object: PExpression
    method_name: "PIdentifier"
    arguments: List[PExpression]

    def __init__(self, object: PExpression, method: "PIdentifier", arguments: List[PExpression], lexeme: Lexeme):
        super().__init__(NodeType.METHOD_CALL, lexeme.pos)
        self.object = object
        self.method_name = method
        self.arguments = arguments
        
    @property
    def children(self) -> Generator["PStatement", None, None]:
        for stmt in (self.object,
                     self.method_name, 
                     *self.arguments):
            yield stmt
        return
    
    def generate_llvm(self, context:CodeGenContext, get_ptr_to_expression=False) -> ir.Value:
        assert not get_ptr_to_expression, "Cannot get pointer to a function return value"
        assert self.object.expr_type is not None
        # TODO: get method function pointer from a v-table
        this = self.object.generate_llvm(context, False)
        # null_check on "this" ONLY if it's a reference type
        if self.object.expr_type.is_reference_type:
            null_check_func = context.scopes.get_symbol(FUNC_NULL_REF_CHECK).func_ptr
            assert null_check_func is not None
            context.builder.call(null_check_func, [this, context.get_char_ptr_from_string(self.position.filename),
                                                ir.Constant(ir.IntType(32), self.position.line),
                                                ir.Constant(ir.IntType(32), self.position.column)])

        method_name = context.get_method_symbol_name(self.object.expr_type.name, self.method_name.name)
        fun = context.scopes.get_symbol(method_name).func_ptr
        assert isinstance(fun, ir.Function)
        #setup arguments
        args = [this] + [a.generate_llvm(context) for a in self.arguments]
        args = [context.builder.bitcast(arg,expected_arg.type) 
                for arg, expected_arg in zip(args, fun.args)]
        assert isinstance(fun, ir.Function)
        ret_val = context.builder.call(fun, args)
        return ret_val

@dataclass
class PIdentifier(PExpression):
    """Identifier node"""
    name: str

    def __init__(self, name: str, lexeme: Lexeme):
        super().__init__(NodeType.IDENTIFIER, lexeme.pos)
        self.name = name
    
    def generate_llvm(self, context: CodeGenContext, get_ptr_to_expression=False) -> ir.Value:
        variable = context.scopes.get_symbol(self.name)
        if variable.is_function:
            assert variable.func_ptr is not None
            return variable.func_ptr
        assert variable.alloca is not None
        assert self.expr_type is not None
        var_type = self.expr_type.get_llvm_value_type(context)
        if get_ptr_to_expression:
            return variable.alloca
        else:
            return context.builder.load(variable.alloca, typ=var_type)

@dataclass
class PThis(PExpression):
    """This node: reference to the current instance"""
    def __init__(self, lexeme:Lexeme):
        super().__init__(NodeType.IDENTIFIER, lexeme.pos)
    
    def generate_llvm(self, context: CodeGenContext, get_ptr_to_expression=False) -> ir.Value:
        this = context.scopes.get_symbol('this').alloca
        assert this is not None
        assert self.expr_type is not None
        var_type = self.expr_type.get_llvm_value_type(context)
        if get_ptr_to_expression:
            return this
        else:
            return context.builder.load(this, typ=var_type)
    
@dataclass
class PVoid(PExpression):
    """Node used for empty return statement"""
    def __init__(self, lexeme:Lexeme):
        super().__init__(NodeType.EMPTY, lexeme.pos)

@dataclass
class PLiteral(PExpression):
    """Literal value node"""
    value: Any
    literal_type: str  # "int", "float", "string", "char", "bool" or "null"

    def __init__(self, value: Any, literal_type: str, lexeme: Lexeme):
        super().__init__(NodeType.LITERAL, lexeme.pos)
        self.value = value
        self.literal_type = literal_type
        self.is_compile_time_constant = True
        
    def generate_llvm(self, context:CodeGenContext, get_ptr_to_expression=False) -> ir.Value:
        assert not get_ptr_to_expression, "Cannot get pointer to a literal value"
        assert self.expr_type is not None
        const_typ = self.expr_type.get_llvm_value_type(context)
        if self.literal_type == "string":
            string_obj = context.get_string_const(self.value)
            # Bitcast from anon-type to actual string type
            string_obj = context.builder.bitcast(string_obj, const_typ)
            assert isinstance(string_obj, ir.CastInstr)
            return string_obj
        return ir.Constant(const_typ, self.value)

@dataclass
class PCast(PExpression):
    """Type cast expression node"""
    target_type: 'PType'  # The type to cast to
    expression: PExpression  # The expression being cast

    def __init__(self, target_type:'PType', expression:PExpression):
        super().__init__(NodeType.CAST, target_type.position)
        self.target_type = target_type
        self.expression = expression
        # TODO : This value can be true, calculated at compile time and optimized out if inner expression is const
        self.is_compile_time_constant = False
        
    @property
    def children(self) -> Generator["PStatement", None, None]:
        yield self.target_type
        yield self.expression
        return
    
    def generate_llvm(self, context:CodeGenContext, get_ptr_to_expression=False) -> ir.Value:
        assert not get_ptr_to_expression, "Cannot get pointer to a casted value"
        expr = self.expression.generate_llvm(context)
        original_type = self.expression.expr_type
        target_type = self.expr_type
        assert original_type is not None and target_type is not None

        if target_type == original_type:
            return expr #nothing to do
        
        original_type_info = TYPE_INFO.get(original_type.name, TypeInfo(TypeClass.CLASS, is_builtin=False))
        target_type_info = TYPE_INFO.get(target_type.name, TypeInfo(TypeClass.CLASS, is_builtin=False))
        
        if original_type_info.type_class == TypeClass.BOOLEAN:
            return context.builder.select(
                    cond=expr,
                    lhs=ir.Constant(target_type.get_llvm_value_type(context), 1),
                    rhs=ir.Constant(target_type.get_llvm_value_type(context), 0)
                )
        elif (target_type.is_reference_type or original_type.is_reference_type):
            if target_type.name == "null":
                #cast to void ptr
                result = context.builder.bitcast(expr, ir.PointerType())
                assert isinstance(result, ir.NamedValue)
                return result
            raise CompilerError("Cannot cast reference types yet")
        elif target_type_info.type_class == TypeClass.FLOAT:
            #convert to float
            if original_type_info.type_class in [TypeClass.INTEGER]:
                if original_type_info.is_signed:
                    val = context.builder.sitofp(expr, target_type.get_llvm_value_type(context))
                    assert isinstance(val, ir.NamedValue)
                    return val
                else:
                    val = context.builder.uitofp(expr, target_type.get_llvm_value_type(context))
                    assert isinstance(val, ir.NamedValue)
                    return val
            elif original_type_info.type_class == TypeClass.FLOAT:
                if original_type_info.bit_width > target_type_info.bit_width:
                    #truncate
                    val = context.builder.fptrunc(expr, target_type.get_llvm_value_type(context))
                    assert isinstance(val, ir.NamedValue)
                    return val
                else: #increase size of FP
                    val = context.builder.fpext(expr, target_type.get_llvm_value_type(context))
                    assert isinstance(val, ir.NamedValue)
                    return val
            else:
                raise TypingError(f"Cannot Cast from {original_type} to {target_type}")
        elif target_type_info.type_class == TypeClass.INTEGER:
            #convert to int
            if original_type_info.type_class in [TypeClass.INTEGER]:
                if original_type_info.bit_width < target_type_info.bit_width: #cast to larger int
                    if original_type_info.is_signed:
                        val = context.builder.sext(expr, target_type.get_llvm_value_type(context))
                        assert isinstance(val, ir.NamedValue)
                        return val
                    else:
                        val = context.builder.zext(expr, target_type.get_llvm_value_type(context))
                        assert isinstance(val, ir.NamedValue)
                        return val
                elif original_type_info.bit_width > target_type_info.bit_width:
                    val = context.builder.trunc(expr, target_type.get_llvm_value_type(context))
                    assert isinstance(val, ir.NamedValue)
                    return val
                else:
                    #sign to unsigned or vice versa
                    val = context.builder.bitcast(expr, target_type.get_llvm_value_type(context))
                    assert isinstance(val, ir.NamedValue)
                    return val
            elif original_type_info.type_class == TypeClass.FLOAT:
                #float to int
                if target_type_info.is_signed:
                    val = context.builder.fptosi(expr, target_type.get_llvm_value_type(context))
                    assert isinstance(val, ir.NamedValue)
                    return val
                else:
                    val = context.builder.fptoui(expr, target_type.get_llvm_value_type(context))
                    assert isinstance(val, ir.NamedValue)
                    return val
        elif target_type_info.type_class == TypeClass.BOOLEAN:
            #do zero check
            if original_type_info.type_class == TypeClass.INTEGER:
                return context.builder.select(
                    cond=context.builder.icmp_unsigned('!=', expr, ir.Constant(ir.IntType(1), 0)),
                    lhs=ir.Constant(ir.IntType(1), True),
                    rhs=ir.Constant(ir.IntType(1), False)
                )
            elif original_type_info.type_class == TypeClass.FLOAT:
                return context.builder.select(
                    cond=context.builder.fcmp_ordered('!=', expr, ir.Constant(original_type.get_llvm_value_type(context), 0)),
                    lhs=ir.Constant(ir.IntType(1), True),
                    rhs=ir.Constant(ir.IntType(1), False)
                )
            else:
                return context.builder.select(
                    cond=context.builder.icmp_unsigned('!=', expr, ir.Constant(ir.PointerType(), ir.PointerType.null)),
                    lhs=ir.Constant(ir.IntType(1), True),
                    rhs=ir.Constant(ir.IntType(1), False)
                )
        raise TypingError(f"Cannot Cast from {original_type} to {target_type}")

@dataclass
class PBreakStatement(PStatement):
    """Break statement node"""

    def __init__(self, lexeme: Lexeme):
        super().__init__(NodeType.BREAK_STATEMENT, lexeme.pos)
        
    def generate_llvm(self, context: CodeGenContext) -> None:
        end_of_loop_block = context.loopinfo[-1].end_of_loop_block
        context.leave_scope(self.depth_from_next_loop)
        context.builder.branch(end_of_loop_block)

@dataclass
class PContinueStatement(PStatement):
    """Continue statement node"""

    def __init__(self, lexeme: Lexeme):
        super().__init__(NodeType.CONTINUE_STATEMENT, lexeme.pos)
        
    def generate_llvm(self, context: CodeGenContext) -> None:
        continue_loop_block = context.loopinfo[-1].continue_loop_block
        context.leave_scope(self.depth_from_next_loop)
        context.builder.branch(continue_loop_block)

@dataclass
class PAssertStatement(PStatement):
    """Assert statement node"""
    condition: PExpression
    message: Optional[PLiteral]

    def __init__(self, condition: PExpression, message: Optional[PLiteral], lexeme: Lexeme):
        super().__init__(NodeType.ASSERT_STATEMENT, lexeme.pos)
        self.condition = condition
        self.message = message
        
    @property
    def children(self) -> Generator["PStatement", None, None]:
        yield self.condition
        if self.message is not None:
            yield self.message
        return
    
    def generate_llvm(self, context: CodeGenContext) -> None:
        condition_is_false = context.builder.not_(self.condition.generate_llvm(context))
        with context.builder.if_then(condition_is_false, False):
            if self.message is not None:
                self.exit_with_error(context, error_code=125, error_message="Assertion Failed: " + str(self.message.value))
            else:
                self.exit_with_error(context, error_code=125, error_message="Assertion Failed:")
            
@dataclass
class PDotAttribute(PExpression):
    left:PExpression
    right:PIdentifier

    def __init__(self, left: PExpression, right:PIdentifier):
        super().__init__(NodeType.ATTRIBUTE, left.position)
        self.left = left
        self.right = right
        
    @property
    def children(self) -> Generator["PStatement", None, None]:
        yield self.left
        yield self.right
        return
    
    def generate_llvm(self, context: CodeGenContext, get_ptr_to_expression=False) -> ir.Value:
        # left**
        left_mem_loc = self.left.generate_llvm(context, get_ptr_to_expression=True)
        assert isinstance(left_mem_loc, ir.NamedValue)
        assert self.left.expr_type is not None
        left_type = self.left.expr_type.get_llvm_value_type(context)
        assert isinstance(left_type, ir.types._TypedPointerType)
        # left* (a pointer to the object on the heap/stack)
        left_ptr = context.builder.load(left_mem_loc, typ=left_type)
        #Do null check here
        null_check_func = context.scopes.get_symbol(FUNC_NULL_REF_CHECK).func_ptr
        assert null_check_func is not None
        context.builder.call(null_check_func, [left_ptr, context.get_char_ptr_from_string(self.position.filename),
                                               ir.Constant(ir.IntType(32), self.position.line),
                                               ir.Constant(ir.IntType(32), self.position.column)])
        
        assert isinstance(left_ptr.type, ir.PointerType)
        for i, field in enumerate(self.left.expr_type.fields):
            if field.name == self.right.name:
                # found the correct field
                field_ptr = context.builder.gep(left_ptr, [ir.Constant(ir.IntType(32), 0), # *left
                                                           ir.Constant(ir.IntType(32), i) #(*left).ith element
                                                           ],
                                                source_etype=left_type.pointee)
                #fix typing of the element gotten
                field_ptr_type = ir.PointerType(field.typer_pass_var_type.get_llvm_value_type(context))
                field_ptr = context.builder.bitcast(field_ptr, field_ptr_type)
                assert isinstance(field_ptr, (ir.CastInstr, ir.GEPInstr))
                
                if get_ptr_to_expression:
                    return field_ptr
                else:
                    return context.builder.load(field_ptr,
                                                typ=field.typer_pass_var_type.get_llvm_value_type(context))
        raise TypingError(f"Cannot find field {self.right.name} in type {self.left.expr_type}")

@dataclass
class PTernaryOperation(PExpression):
    """Ternary operation node"""
    condition: PExpression
    true_value: PExpression
    false_value: PExpression

    def __init__(self, condition: PExpression, true_value: PExpression, false_value: PExpression, lexeme: Lexeme):
        super().__init__(NodeType.TERNARY_OPERATION, lexeme.pos)
        self.condition = condition
        self.true_value = true_value
        self.false_value = false_value
        # TODO : This value can be true, calculated at compile time and optimized out if condition and its result are compile time constants
        self.is_compile_time_constant = False
        
    @property
    def children(self) -> Generator["PStatement", None, None]:
        yield self.condition
        yield self.true_value
        yield self.false_value
        return
    
    def generate_llvm(self, context:CodeGenContext, get_ptr_to_expression=False) -> ir.Value:
        return context.builder.select(
            self.condition.generate_llvm(context),
            self.true_value.generate_llvm(context, get_ptr_to_expression),
            self.false_value.generate_llvm(context, get_ptr_to_expression)
        )

@dataclass
class PObjectInstantiation(PExpression):
    """Represents a class instantiation expression """
    class_type: 'PType'  # The type of class being instantiated

    def __init__(self, class_type: 'PType', lexeme):
        """
        Initialize object instantiation node

        Args:
            class_type: The type/name of the class being instantiated
            lexeme: The lexeme containing position information (the 'new' keyword)
        """
        super().__init__(NodeType.OBJECT_INSTANTIATION, lexeme.pos)
        self.class_type = class_type
        
    @property
    def children(self) -> Generator["PStatement", None, None]:
        yield self.class_type
        return
    
    def generate_llvm(self, context:CodeGenContext, get_ptr_to_expression=False) -> ir.Value:
        size_t_type = ir.IntType(ir.PointerType().get_abi_size(context.target_data)*8)
        
        assert not get_ptr_to_expression, "Cannot get ptr to Object reference"
        alloc_func = context.scopes.get_symbol(FUNC_GC_ALLOCATE_OBJECT).func_ptr
        assert alloc_func is not None
        assert self.expr_type is not None
        allocated_ptr = context.builder.call(alloc_func,
            [ir.Constant(size_t_type, context.type_ids[self.expr_type.name])])
        assert self.expr_type is not None
        class_ref_type = self.expr_type.get_llvm_value_type(context)
        assert isinstance(class_ref_type, ir.types._TypedPointerType)
        allocated_ptr = context.builder.bitcast(allocated_ptr, class_ref_type)
        assert isinstance(allocated_ptr, ir.NamedValue)
        
        # Implicit constructor
        # Element is allocated
        # Now we need to allocate all of its fields
        for field_num, field in enumerate(self.expr_type.fields):
            if field.default_value is None:
                continue #not set it's a null_ptr (zero-ed out field for value types)
            field_ptr = context.builder.gep(allocated_ptr, 
                                            [
                                                ir.Constant(ir.IntType(32), 0),
                                                ir.Constant(ir.IntType(32), field_num)
                                            ],
                                            source_etype=class_ref_type.pointee)
            context.builder.store(field.default_value.generate_llvm(context, get_ptr_to_expression=False),
                                  field_ptr)
        
        return allocated_ptr

@dataclass
class PArrayInstantiation(PExpression):
    """Represents array instantiation like new int[10]"""
    element_type: 'PType'  # The base type of array elements
    size: PExpression  # The size expression for the array
    _element_type_typ:Optional[Typ] = None
    
    @property
    def element_type_typ(self):
        if self._element_type_typ is None:
            raise TypingError(f"Element type has not been typed yet")
        return self._element_type_typ

    def __init__(self, element_type: 'PType', size: PExpression, lexeme):
        """
        Initialize array instantiation node

        Args:
            element_type: The type of elements in the array
            size: Expression defining the array size
            lexeme: The lexeme containing position information (the 'new' keyword)
        """
        super().__init__(NodeType.ARRAY_INSTANTIATION, lexeme.pos)
        self.element_type = element_type
        self.size = size
        
    @property
    def children(self) -> Generator["PStatement", None, None]:
        yield self.size
        yield self.element_type
        return
    
    def generate_llvm(self, context: CodeGenContext, get_ptr_to_expression=False) -> ir.Value:
        assert not get_ptr_to_expression, "Cannot get ptr to array reference"
        n_elements = self.size.generate_llvm(context)
        
        if self.element_type_typ.is_reference_type:
            # Each element is a reference type
            alloc_func = context.scopes.get_symbol(FUNC_GC_ALLOCATE_REFERENCE_OBJ_ARRAY).func_ptr
            assert alloc_func is not None
            # void* __PS_AllocateRefArray(size_t num_elements)
            ptr_to_array = context.builder.call(alloc_func, [n_elements])
        else:
            # Each element is a value type
            element_size = self.element_type_typ.get_llvm_value_type(context).get_abi_size(
                                                                context.target_data,
                                                                context.module.context)
            assert element_size in [1,2,4,8]
            element_size = ir.Constant(ir.IntType(8), element_size)
            alloc_func = context.scopes.get_symbol(FUNC_GC_ALLOCATE_VALUE_ARRAY).func_ptr
            assert alloc_func is not None
            # void* __PS_AllocateValueArray(size_t element_size, size_t num_elements)
            ptr_to_array = context.builder.call(alloc_func, [element_size, n_elements])
        
        # return pointer to array casted to correct type
        # assert self.expr_type is not None
        # arr = context.builder.bitcast(ptr_to_array, self.expr_type.get_llvm_value_type(context))
        # assert isinstance(arr, ir.CastInstr) or isinstance(arr, ir.CallInstr)

        return ptr_to_array

@dataclass
class PType(PStatement):
    type_string:str
    expr_type:Optional[Typ]

    def __init__(self, base_type:str, lexeme_pos:Union[Lexeme,Position]):
        super().__init__(NodeType.TYPE, lexeme_pos if isinstance(lexeme_pos, Position) else lexeme_pos.pos)
        self.type_string = base_type
        self.expr_type = None

    def __str__(self):
        if isinstance(self.type_string, str):
            return self.type_string
        return str(self.type_string)
    
    def __hash__(self) -> int:
        return hash(str(self))
    
    def __eq__(self, value: object) -> bool:
        if not isinstance(value, PType):
            return False
        return str(self) == str(value)

@dataclass
class PArrayType(PType):
    """
    Represents an array type in the AST.
    For example: int[] or MyClass[][]
    """
    element_type: Union['PArrayType',PType]

    def __init__(self, base_type:Union['PArrayType',PType], lexeme_pos:Union[Lexeme, Position]):
        self.element_type = base_type
        super().__init__(str(self), lexeme_pos)

    def __str__(self) -> str:
        """Convert array type to string representation"""
        return f"{str(self.element_type)}[]"
    
    def __hash__(self) -> int:
        return hash(str(self))
    
    def __eq__(self, value: object) -> bool:
        if not isinstance(value, PArrayType):
            return False
        return str(self) == str(value)
    
    @property
    def dimensions(self):
        dim = 1
        base_type = self.element_type
        while isinstance(base_type, PArrayType):
            base_type = base_type.element_type
            dim += 1
        return dim
    
    @property
    def base_type(self):
        base_type = self.element_type
        while isinstance(base_type, PArrayType):
            base_type = base_type.element_type
        return base_type

@dataclass
class PArrayIndexing(PExpression):
    """
    Represents an array access expression in the AST.
    For example: arr[0] or arr[i][j]
    """
    array: PExpression # The array being accessed
    index: PExpression  # The index expression

    def __init__(self, array: PExpression, index: PExpression, lexeme):
        """Initialize array access node with position from lexeme"""
        super().__init__(NodeType.ARRAY_ACCESS, lexeme.pos)
        self.array = array
        self.index = index
        
    @property
    def children(self) -> Generator["PStatement", None, None]:
        yield self.array
        yield self.index
        return
    
    def generate_llvm(self, context: CodeGenContext, get_ptr_to_expression=False) -> ir.Value:
        #get type of array
        assert self.array.expr_type is not None
        assert self.expr_type is not None
        array_struct_type = self.array.expr_type.get_llvm_value_type(context)
        assert isinstance(array_struct_type, ir.types._TypedPointerType)
        array_element_type = self.expr_type.get_llvm_value_type(context)
        
        array_obj = self.array.generate_llvm(context, False)
        array_element_size_in_bytes = array_element_type.get_abi_size(context.target_data)
        assert array_element_size_in_bytes in [1,2,4,8], f"Array element should be 1,2,4 or 8 bytes long not {array_element_size_in_bytes}"
        array_element_size_in_bytes = ir.Constant(ir.IntType(8), array_element_size_in_bytes)
        index = self.index.generate_llvm(context, False)
        
        element_fetch_function = context.scopes.get_symbol(FUNC_GET_ARRAY_ELEMENT_PTR)
        assert element_fetch_function.func_ptr is not None
        array_element_ptr = context.builder.call(element_fetch_function.func_ptr,
                                                 [
                                                     array_obj, #the array ref
                                                     array_element_size_in_bytes, #the element size (should be 1,2,4 or 8)
                                                     index, # the array index to fetch (negative values are accepted)
                                                     context.get_char_ptr_from_string(self.position.filename),
                                                     ir.Constant(ir.IntType(32), self.position.line),
                                                     ir.Constant(ir.IntType(32), self.position.column)
                                                 ])
        #make sure it's the correct type because the fetcg function returns a void*
        array_element_ptr = context.builder.bitcast(array_element_ptr, ir.PointerType(array_element_type))
        assert isinstance(array_element_ptr, ir.NamedValue)
        if get_ptr_to_expression:
            return array_element_ptr
        else:
            return context.builder.load(array_element_ptr, typ=array_element_type)
    
    def _bounds_check(self, index_ptr:ir.Value, arr_length:ir.Value, context:CodeGenContext):
        """Check the index is within the bounds. Crashes otherwise"""
        out_of_bounds = context.builder.or_(
            context.builder.icmp_unsigned('>=', index_ptr, arr_length),
            context.builder.icmp_unsigned('<', index_ptr, ir.Constant(ir.IntType(64),0))
        )
        with context.builder.if_then(out_of_bounds, False):
            self.exit_with_error(context, 1, f"Cannot access outside of the bounds of the array")

class Parser:
    """Parser for P# language that builds an AST from lexemes"""

    def __init__(self, lexer: Lexer):
        self.lexer = lexer
        self.lexeme_stream = LexemeStream(lexer.lex(), lexer.filename)

        # Define operator precedence
        self.precedence: Dict[Union[BinaryOperation, UnaryOperation, TernaryOperator], int] = {
            BinaryOperation.ASSIGN:0,
            BinaryOperation.COPY:0,
            TernaryOperator.QUESTIONMARK:2,
            BinaryOperation.BOOL_OR: 4,
            BinaryOperation.BOOL_AND: 6,
            BinaryOperation.BOOL_EQ: 8,
            BinaryOperation.BOOL_NEQ: 8,
            BinaryOperation.BOOL_GT: 8,
            BinaryOperation.BOOL_LT: 8,
            BinaryOperation.BOOL_GEQ: 8,
            BinaryOperation.BOOL_LEQ: 8,
            BinaryOperation.LOGIC_OR: 10,
            BinaryOperation.LOGIC_AND: 12,
            BinaryOperation.XOR: 14,
            BinaryOperation.PLUS: 16,
            BinaryOperation.MINUS: 16,
            BinaryOperation.SHIFT_LEFT: 18,
            BinaryOperation.SHIFT_RIGHT: 18,
            BinaryOperation.TIMES: 20,
            BinaryOperation.DIVIDE: 20,
            BinaryOperation.MOD: 20,
            UnaryOperation.BOOL_NOT:22,
            UnaryOperation.LOGIC_NOT:22,
            UnaryOperation.MINUS:22,
            UnaryOperation.POST_INCREMENT:24,
            UnaryOperation.POST_DECREMENT:24,
            UnaryOperation.PRE_INCREMENT:26,
            UnaryOperation.PRE_DECREMENT:26
        }

        self.unary_binary_ops: Dict[LexemeType, Union[BinaryOperation,UnaryOperation, TernaryOperator]] = {
            LexemeType.OPERATOR_BINARY_PLUS: BinaryOperation.PLUS,
            LexemeType.OPERATOR_BINARY_MINUS: BinaryOperation.MINUS,
            LexemeType.OPERATOR_BINARY_TIMES: BinaryOperation.TIMES,
            LexemeType.OPERATOR_BINARY_DIV: BinaryOperation.DIVIDE,
            LexemeType.OPERATOR_BINARY_MOD: BinaryOperation.MOD,
            LexemeType.OPERATOR_BINARY_BOOL_EQ: BinaryOperation.BOOL_EQ,
            LexemeType.OPERATOR_BINARY_BOOL_NEQ: BinaryOperation.BOOL_NEQ,
            LexemeType.OPERATOR_BINARY_BOOL_GT: BinaryOperation.BOOL_GT,
            LexemeType.OPERATOR_BINARY_BOOL_LT: BinaryOperation.BOOL_LT,
            LexemeType.OPERATOR_BINARY_BOOL_GEQ: BinaryOperation.BOOL_GEQ,
            LexemeType.OPERATOR_BINARY_BOOL_LEQ: BinaryOperation.BOOL_LEQ,
            LexemeType.OPERATOR_BINARY_BOOL_AND: BinaryOperation.BOOL_AND,
            LexemeType.OPERATOR_BINARY_BOOL_OR: BinaryOperation.BOOL_OR,
            LexemeType.OPERATOR_BINARY_AND: BinaryOperation.LOGIC_AND,
            LexemeType.OPERATOR_BINARY_OR: BinaryOperation.LOGIC_OR,
            LexemeType.OPERATOR_BINARY_XOR: BinaryOperation.XOR,
            LexemeType.OPERATOR_BINARY_SHL: BinaryOperation.SHIFT_LEFT,
            LexemeType.OPERATOR_BINARY_SHR: BinaryOperation.SHIFT_RIGHT,

            LexemeType.OPERATOR_UNARY_INCREMENT:UnaryOperation.POST_INCREMENT,
            LexemeType.OPERATOR_UNARY_DECREMENT:UnaryOperation.POST_DECREMENT,
            LexemeType.OPERATOR_UNARY_BOOL_NOT:UnaryOperation.BOOL_NOT,
            LexemeType.OPERATOR_UNARY_LOGIC_NOT:UnaryOperation.LOGIC_NOT,

            LexemeType.PUNCTUATION_TERNARYCONDITIONAL_QUESTIONMARK:TernaryOperator.QUESTIONMARK,
        }
        # Set of type keywords
        self.type_keywords: set[LexemeType] = {
            LexemeType.KEYWORD_TYPE_VOID,
            LexemeType.KEYWORD_TYPE_INT8,
            LexemeType.KEYWORD_TYPE_INT16,
            LexemeType.KEYWORD_TYPE_INT32,
            LexemeType.KEYWORD_TYPE_INT64,
            LexemeType.KEYWORD_TYPE_CHAR,
            LexemeType.KEYWORD_TYPE_UINT8,
            LexemeType.KEYWORD_TYPE_UINT16,
            LexemeType.KEYWORD_TYPE_UINT32,
            LexemeType.KEYWORD_TYPE_UINT64,
            LexemeType.KEYWORD_TYPE_STRING,
            LexemeType.KEYWORD_TYPE_FLOAT16,
            LexemeType.KEYWORD_TYPE_FLOAT32,
            LexemeType.KEYWORD_TYPE_FLOAT64,
            LexemeType.KEYWORD_TYPE_CHAR,
            LexemeType.KEYWORD_TYPE_BOOLEAN
        }

    @property
    def current_lexeme(self):
        return self.lexeme_stream.peek()

    def _expect(self, lexeme_type: LexemeType) -> Lexeme:
        """Verify current lexeme is of expected type and advance"""
        if self.current_lexeme is Lexeme.default:
            raise ParserError(f"Got Empty Lexeme instead of {lexeme_type.name}",
                              Lexeme.default)
        if self.current_lexeme.type != lexeme_type:
            raise ParserError(
                f"Expected {lexeme_type.name}, got {self.current_lexeme.type.name if self.current_lexeme else 'EOF'}",
                self.current_lexeme)
        lexeme = self.lexeme_stream.advance()
        return lexeme

    def _match(self, *lexeme_types: LexemeType) -> bool:
        """Check if current lexeme matches any of the given types"""
        return self._peek_matches(0, *lexeme_types)

    def _peek_matches(self, offset, *lexeme_types: LexemeType) -> bool:
        """Check if next lexeme matches any of the given types at index offset without advancing"""
        assert offset >= 0, "Cannot peek into the past (offset < 0)"
        lexeme = self.lexeme_stream.peek(offset)
        return lexeme is not None and lexeme.type in lexeme_types

    def parse(self) -> PProgram:
        """Parse the entire program"""
        statements = []
        start_lexeme = self.current_lexeme

        while self.current_lexeme and self.current_lexeme.type != LexemeType.EOF:
            statements.append(self._parse_statement(BlockProperties()))

        pprogram = PProgram(statements, start_lexeme)
        return pprogram

    def _parse_object_instantiation(self) -> Union[PObjectInstantiation,PArrayInstantiation]:
        """Parse a class instantiation expression."""
        # Consume 'new' keyword
        new_lexeme = self._expect(LexemeType.KEYWORD_OBJECT_NEW)

        # Parse class name
        if self._match(LexemeType.IDENTIFIER, *self.type_keywords):
            class_name_lexeme = self.current_lexeme
            object_type = self._parse_type()
        else:
            raise ParserError("Expected class name or type after 'new' keyword", self.current_lexeme)

        # Parse parentheses (required, but empty since constructors aren't supported yet)
        if self._match(LexemeType.PUNCTUATION_OPENPAREN):
            self._expect(LexemeType.PUNCTUATION_OPENPAREN)
            self._expect(LexemeType.PUNCTUATION_CLOSEPAREN)

            return PObjectInstantiation(object_type, new_lexeme)
        
        elif self._match(LexemeType.PUNCTUATION_OPENBRACKET):
            if isinstance(object_type, PArrayType):
                raise ParserError(f"Cannot create sub-array before creating parent array.", self.current_lexeme)
            self._expect(LexemeType.PUNCTUATION_OPENBRACKET)
            size = self._parse_expression()
            self._expect(LexemeType.PUNCTUATION_CLOSEBRACKET)
            
            while self._match(LexemeType.PUNCTUATION_OPENBRACKET) and self._peek_matches(1, LexemeType.PUNCTUATION_CLOSEBRACKET):
                self._expect(LexemeType.PUNCTUATION_OPENBRACKET)
                self._expect(LexemeType.PUNCTUATION_CLOSEBRACKET)
                object_type = PArrayType(object_type, object_type.position)
            return PArrayInstantiation(object_type, size, class_name_lexeme)
        else:
            raise ParserError("Invalid Lexeme: Expected opening bracket or opening parenthesis", self.current_lexeme)

    def _parse_statement(self, block_properties:BlockProperties) -> PStatement:
        """Parse a single statement"""
        if self.current_lexeme is Lexeme.default:
            raise ParserError("Unexpected end of file", self.current_lexeme)

        # Match statement type
        if self._match(*self.type_keywords):
            return self._parse_declaration(block_properties)
        elif (self._match(LexemeType.IDENTIFIER)
              and (self._peek_matches(1, LexemeType.IDENTIFIER) \
                   or (self._peek_matches(1, LexemeType.PUNCTUATION_OPENBRACKET)
                       and self._peek_matches(2, LexemeType.PUNCTUATION_CLOSEBRACKET)))):
            #starts with a type 
            return self._parse_declaration(block_properties)
        elif self._match(LexemeType.KEYWORD_CONTROL_IF):
            return self._parse_if_statement(block_properties.copy_with(is_top_level=False))
        elif self._match(LexemeType.KEYWORD_CONTROL_WHILE):
            return self._parse_while_statement(block_properties.copy_with(is_top_level=False))
        elif self._match(LexemeType.KEYWORD_CONTROL_FOR):
            return self._parse_for_statement(block_properties.copy_with(is_top_level=False))
        elif self._match(LexemeType.KEYWORD_CONTROL_RETURN):
            if not block_properties.in_function:
                raise ParserError("Cannot have a return statement outside of a function", self.current_lexeme)
            return self._parse_return_statement()
        elif self._match(LexemeType.KEYWORD_CONTROL_BREAK):
            if not block_properties.is_loop:
                raise ParserError("Cannot have a break statement outside of a loop block", self.current_lexeme)
            return self._parse_break_statement()
        elif self._match(LexemeType.KEYWORD_CONTROL_CONTINUE):
            if not block_properties.is_loop:
                raise ParserError("Cannot have a continue statement outside of a loop block", self.current_lexeme)
            return self._parse_continue_statement()
        elif self._match(LexemeType.KEYWORD_CONTROL_ASSERT):
            return self._parse_assert_statement()
        elif self._match(LexemeType.DISCARD):
            return self._parse_discard()
        elif self._match(LexemeType.KEYWORD_OBJECT_CLASS):
            if not block_properties.is_top_level:
                raise ParserError("Cannot have a break statement outside of a loop block", self.current_lexeme)
            return self._parse_class_definition(block_properties.copy_with(is_class=True,
                                                                           is_top_level=False))
        elif self._match(LexemeType.PUNCTUATION_OPENBRACE):
            return self._parse_block(block_properties.copy_with(is_top_level=False))

        # Expression statement (assignment, function call, etc.)
        expr = self._parse_expression()
        self._expect(LexemeType.PUNCTUATION_SEMICOLON)
        return expr

    def _parse_declaration(self, block_properties:BlockProperties) -> Union[PVariableDeclaration, PFunction]:
        """Parse a variable or function declaration"""
        type_lexeme = self.current_lexeme
        var_type = self._parse_type()

        name_lexeme = self._expect(LexemeType.IDENTIFIER)
        name = name_lexeme.value

        # Function declaration
        if self._match(LexemeType.PUNCTUATION_OPENPAREN):
            if not block_properties.is_top_level:
                raise ParserError("Functions cannot be defined in a scope. They must be defined at the top level.", self.current_lexeme)
            if block_properties.in_function:
                raise ParserError("Functions cannot be defined inside another function. They must be defined at the top level.", self.current_lexeme)
            return self._parse_function_declaration(name, var_type, type_lexeme,
                                                    block_properties.copy_with(
                                                        is_top_level=False,
                                                        in_function=True))

        # Variable declaration
        initial_value = None
        if self._match(LexemeType.OPERATOR_BINARY_ASSIGN):
            self.lexeme_stream.advance()
            initial_value = self._parse_expression()

        elif self._match(LexemeType.OPERATOR_BINARY_COPY):
            raise NotImplementedError("Copy operation is not implemented yet")

        self._expect(LexemeType.PUNCTUATION_SEMICOLON)
        return PVariableDeclaration(name, var_type, initial_value, type_lexeme)

    def _parse_function_declaration(self, name: str, return_type: PType, start_lexeme: Lexeme,
                                    block_properties:BlockProperties) -> PFunction:
        """Parse a function declaration"""
        self._expect(LexemeType.PUNCTUATION_OPENPAREN)
        parameters:List[PVariableDeclaration] = []

        # Parse parameters
        if not self._match(LexemeType.PUNCTUATION_CLOSEPAREN):
            while True:
                if not self._match(*self.type_keywords, LexemeType.IDENTIFIER):
                    raise ParserError("Expected type in function parameters", self.current_lexeme)
                param_type = self._parse_type()

                param_name_lexeme = self._expect(LexemeType.IDENTIFIER)
                parameters.append(PVariableDeclaration(param_name_lexeme.value, param_type, None, param_name_lexeme))

                if not self._match(LexemeType.PUNCTUATION_COMMA):
                    break # Arrived at the end of the params
                # Has more parameters: consume comma
                self._expect(LexemeType.PUNCTUATION_COMMA)

        self._expect(LexemeType.PUNCTUATION_CLOSEPAREN)
        body = self._parse_block(block_properties)

        return PFunction(name, return_type, parameters, body, start_lexeme)

    def _parse_block(self, block_properties:BlockProperties) -> PBlock:
        """Parse a block of statements"""
        start_lexeme = self._expect(LexemeType.PUNCTUATION_OPENBRACE)
        statements = []

        while not self._match(LexemeType.PUNCTUATION_CLOSEBRACE):
            if not self.current_lexeme:
                raise ParserError("Unterminated block", start_lexeme)
            statements.append(self._parse_statement(block_properties))

        self._expect(LexemeType.PUNCTUATION_CLOSEBRACE)
        return PBlock(statements, start_lexeme, 
                      block_properties=block_properties)

    def _parse_type(self) -> PType:
        """
        Parse a type declaration, which can be either a simple type or an array type.
        Examples:
            - int
            - MyClass
            - int[]
            - MyClass[][]

        Returns:
            Union[str, PArrayType]: The parsed type (either a string for simple types
                                or PArrayType for array types)
        """
        # Parse base type first
        if not self._match(*self.type_keywords, LexemeType.IDENTIFIER):
            raise ParserError("Expected type name", self.current_lexeme)

        type_lexeme = self.lexeme_stream.advance()
        base_type = PType(type_lexeme.value, type_lexeme)

        # Check for array brackets
        while self._match(LexemeType.PUNCTUATION_OPENBRACKET) and self._peek_matches(1, LexemeType.PUNCTUATION_CLOSEBRACKET):
            self._expect(LexemeType.PUNCTUATION_OPENBRACKET)
            self._expect(LexemeType.PUNCTUATION_CLOSEBRACKET)
            base_type = PArrayType(base_type, type_lexeme)

        return base_type

    def _parse_array_indexing(self, array: PExpression) -> PArrayIndexing:
        """
        Parse an array access expression (e.g., arr[index]).
        Called after seeing an opening bracket during expression parsing.

        Args:
            array (PExpression): The array expression being accessed

        Returns:
            PArrayAccess: Node representing the array access

        Raises:
            ParserError: If array access syntax is invalid
        """
        if not isinstance(array, PExpression):
            raise ParserError("Cannot index any other than an expression", self.current_lexeme)
        open_bracket = self._expect(LexemeType.PUNCTUATION_OPENBRACKET)
        index = self._parse_expression()
        self._expect(LexemeType.PUNCTUATION_CLOSEBRACKET)

        return PArrayIndexing(array, index, open_bracket)

    def _parse_expression(self, min_precedence: int = 0, is_lvalue=True) -> PExpression:
        """Parse an expression using precedence climbing"""
        left = self._parse_primary(is_lvalue)
        is_lvalue = is_lvalue and left.node_type in (NodeType.ARRAY_ACCESS,
                                       NodeType.ATTRIBUTE,
                                       NodeType.CLASS_PROPERTY,
                                       NodeType.IDENTIFIER)
        
        # Add matching member access in expression
        if self._match(LexemeType.OPERATOR_DOT):
            left = self._parse_member_access(left)

        while (not self.current_lexeme is Lexeme.default and
               self.current_lexeme.type in self.unary_binary_ops and
               (self.precedence[self.unary_binary_ops[self.current_lexeme.type]] >= min_precedence)):
            is_lvalue = False
            op_lexeme = self.current_lexeme
            op = self.unary_binary_ops[op_lexeme.type]

            if isinstance(op, TernaryOperator):
                left = self._parse_ternary_operation(left)
                continue

            # consume op
            self.lexeme_stream.advance()

            if isinstance(op, UnaryOperation):
                if not isinstance(left, (PArrayIndexing, PIdentifier, PDotAttribute, PThis)):
                    raise ParserError("Cannot increment or decrement something other than a variable or array index", op_lexeme)
                if op_lexeme.type == LexemeType.OPERATOR_UNARY_INCREMENT:
                    left = PUnaryOperation(UnaryOperation.POST_INCREMENT,
                                           left, op_lexeme)
                elif op_lexeme.type == LexemeType.OPERATOR_UNARY_DECREMENT:
                    left = PUnaryOperation(UnaryOperation.POST_DECREMENT,
                                           left, op_lexeme)
                else:
                    raise ParserError("Cannot have a Unary Operator other than ++ or -- after an identifier",
                                      op_lexeme)
                continue

            current_precedence = self.precedence[op]

            right = self._parse_expression(current_precedence + 1, is_lvalue=False)
            left = PBinaryOperation(op, left, right, op_lexeme)

        #parse assignments
        if is_lvalue and not (self.current_lexeme is Lexeme.default):
            if self._match(LexemeType.OPERATOR_BINARY_ASSIGN):
                if not isinstance(left, (PDotAttribute, PIdentifier, PArrayIndexing)):
                    raise ParserError("Cannot assign to anything else than a variable, array or field",
                                      self.current_lexeme)
                self._expect(LexemeType.OPERATOR_BINARY_ASSIGN)
                assign_lexeme = self.current_lexeme
                left = PAssignment(left, self._parse_expression(is_lvalue=False), assign_lexeme)
            elif self._match(LexemeType.OPERATOR_BINARY_COPY):
                raise NotImplementedError("Copy Operator is not yet supported")
                if not isinstance(left, (PDotAttribute, PIdentifier)):
                    raise ParserError("Cannot assign to anything else than a variable or property", self.current_lexeme)
            else:
                #handle +=, -=, *= ... and other binop assignments
                for lexeme_type, op in ((LexemeType.OPERATOR_BINARY_PLUSEQ, BinaryOperation.PLUS),
                                        (LexemeType.OPERATOR_BINARY_MINUSEQ, BinaryOperation.MINUS),
                                        (LexemeType.OPERATOR_BINARY_TIMESEQ, BinaryOperation.TIMES),
                                        (LexemeType.OPERATOR_BINARY_DIVEQ, BinaryOperation.DIVIDE),
                                        (LexemeType.OPERATOR_BINARY_ANDEQ, BinaryOperation.LOGIC_AND),
                                        (LexemeType.OPERATOR_BINARY_OREQ, BinaryOperation.LOGIC_OR),
                                        (LexemeType.OPERATOR_BINARY_XOREQ, BinaryOperation.XOR),
                                        (LexemeType.OPERATOR_BINARY_SHLEQ, BinaryOperation.SHIFT_LEFT),
                                        (LexemeType.OPERATOR_BINARY_SHREQ, BinaryOperation.SHIFT_RIGHT)):
                    if self._match(lexeme_type):
                        curr_lexeme = self.current_lexeme
                        self._expect(lexeme_type)
                        assert isinstance(left, (PIdentifier, PDotAttribute, PArrayIndexing))
                        left = PAssignment(left,
                                           # do binop
                                           PBinaryOperation(op,
                                                            left,
                                                            self._parse_expression(is_lvalue=False),
                                                            self.current_lexeme),
                                           curr_lexeme)
                        break
        return left

    def _parse_discard(self) -> PDiscard:
        """Parse an expression and discard the value"""
        discard_lexeme = self._expect(LexemeType.DISCARD)
        
        self._expect(LexemeType.OPERATOR_BINARY_ASSIGN)
        expression = self._parse_expression()
        self._expect(LexemeType.PUNCTUATION_SEMICOLON)
        
        return PDiscard(expression, discard_lexeme)

    def _parse_cast(self) -> PCast:
        """Parse a C-style cast expression: (type)expr"""
        cast_lexeme = self._expect(LexemeType.PUNCTUATION_OPENPAREN)

        # Parse the target type - can be primitive type or custom class name
        if not (self._match(*self.type_keywords, LexemeType.IDENTIFIER)):
            raise ParserError("Expected type name in cast expression", self.current_lexeme)

        target_type = self._parse_type()

        self._expect(LexemeType.PUNCTUATION_CLOSEPAREN)

        # Parse the expression being cast (with high precedence to bind tightly)
        expression = self._parse_primary()

        return PCast(target_type, expression)

    def _parse_primary(self, is_lvalue=True) -> PExpression:
        """Parse a primary expression (identifier, literal, parenthesized expr, cast, etc.)"""
        if self.current_lexeme is Lexeme.default:
            raise ParserError("Unexpected end of file", self.current_lexeme)

        # Handle opening parenthesis - could be cast or grouped expression
        if self._match(LexemeType.PUNCTUATION_OPENPAREN):

            # Look ahead to check if this is a type cast
            if self._peek_matches(1, *self.type_keywords, LexemeType.IDENTIFIER):
                # Possible type cast - need one more check

                # If next token is closing parenthesis, this is definitely a cast
                if self._peek_matches(2, LexemeType.PUNCTUATION_CLOSEPAREN):
                    return self._parse_cast()

            # Not a cast - parse as normal parenthesized expression
            self.lexeme_stream.advance()  # consume opening paren
            expr = self._parse_expression(is_lvalue=is_lvalue)
            self._expect(LexemeType.PUNCTUATION_CLOSEPAREN)
            return expr

        # Handle literals
        elif self._match(LexemeType.NUMBER_INT, LexemeType.NUMBER_FLOAT,
                        LexemeType.STRING_LITERAL, LexemeType.NUMBER_CHAR):
            return self._parse_literal()

        # Handle identifiers and function calls
        elif self._match(LexemeType.IDENTIFIER, LexemeType.KEYWORD_OBJECT_THIS):
            return self._parse_identifier_or_call_or_array_indexing()

        # Handle unary operators
        elif self._match(LexemeType.OPERATOR_BINARY_MINUS,
                         LexemeType.OPERATOR_UNARY_BOOL_NOT,
                         LexemeType.OPERATOR_UNARY_LOGIC_NOT,
                         LexemeType.OPERATOR_UNARY_INCREMENT,
                         LexemeType.OPERATOR_UNARY_DECREMENT):
            op_map = {
                LexemeType.OPERATOR_BINARY_MINUS:UnaryOperation.MINUS,
                LexemeType.OPERATOR_UNARY_BOOL_NOT: UnaryOperation.BOOL_NOT,
                LexemeType.OPERATOR_UNARY_INCREMENT:UnaryOperation.PRE_INCREMENT,
                LexemeType.OPERATOR_UNARY_DECREMENT: UnaryOperation.PRE_DECREMENT,
                LexemeType.OPERATOR_UNARY_LOGIC_NOT: UnaryOperation.LOGIC_NOT
            }

            op_lexeme = self.lexeme_stream.advance()
            op = op_map[op_lexeme.type]
            operand = self._parse_primary()

            if (op in (UnaryOperation.PRE_DECREMENT, UnaryOperation.PRE_INCREMENT)
                and not isinstance(operand, (PArrayIndexing, PIdentifier, PDotAttribute, PThis))):
                raise ParserError("Cannot increment or decrement something other than a variable", op_lexeme)

            return PUnaryOperation(op, operand, op_lexeme)

        # Handle boolean literals
        elif self._match(LexemeType.KEYWORD_OBJECT_TRUE, LexemeType.KEYWORD_OBJECT_FALSE):
            value = self.current_lexeme.type == LexemeType.KEYWORD_OBJECT_TRUE
            lexeme = self.lexeme_stream.advance()
            return PLiteral(value, "bool", lexeme)

        # Handle null literal
        elif self._match(LexemeType.KEYWORD_OBJECT_NULL):
            lexeme = self.lexeme_stream.advance()
            return PLiteral(None, "null", lexeme)

        elif self._match(LexemeType.KEYWORD_OBJECT_NEW):
            return self._parse_object_instantiation()

        raise ParserError("Unexpected token in expression", self.current_lexeme)

    def _parse_literal(self) -> PLiteral:
        """Parse a literal value"""
        lexeme = self.lexeme_stream.advance()

        #TODO implement integer and float suffixing to change default literal bit_size (default is i32 or f32)
        if lexeme.type == LexemeType.NUMBER_INT:
            return PLiteral(int(lexeme.value), "int", lexeme)
        elif lexeme.type == LexemeType.NUMBER_FLOAT:
            return PLiteral(float(lexeme.value), "float", lexeme)
        elif lexeme.type == LexemeType.STRING_LITERAL:
            # Remove quotes from string literal
            return PLiteral(lexeme.value[1:-1], "string", lexeme)
        elif lexeme.type == LexemeType.NUMBER_CHAR:
            # Handle char literal
            return PLiteral(ord(lexeme.value[1:-1]), "char", lexeme)

        raise ParserError("Invalid literal", lexeme)

    def _parse_identifier_or_call_or_array_indexing(self) -> Union[PThis, PIdentifier, PFunctionCall, PMethodCall, PDotAttribute, PArrayIndexing]:
        """Parse an identifier and any subsequent field accesses, method calls, or function calls.

        This method handles the following patterns:
        - Simple identifier: myVar
        - Function call: myFunction()
        - Property access: myObject.field
        - Method call: myObject.method()
        - Chained access: myObject.field.subField.method()

        Returns:
            Union[PExpression, PIdentifier, PFunctionCall, PMethodCall, PDotAttribute]: The parsed expression

        Raises:
            ParserError: If there's an invalid token in the expression
        """
        # Parse the initial identifier
        if self._match(LexemeType.KEYWORD_OBJECT_THIS):
            expr = PThis(self._expect(LexemeType.KEYWORD_OBJECT_THIS))
        else:
            id_lexeme = self._expect(LexemeType.IDENTIFIER)
            expr = PIdentifier(id_lexeme.value, id_lexeme)
            # Check for function call first (no dot)
            if self._match(LexemeType.PUNCTUATION_OPENPAREN):
                expr = self._parse_function_arguments(expr)

        while True:
            # Check for field access or method call
            if self._match(LexemeType.OPERATOR_DOT):
                expr = self._parse_member_access(expr)

            # Handle indexing identifier
            elif self._match(LexemeType.PUNCTUATION_OPENBRACKET):
                expr = self._parse_array_indexing(expr)

            # No more chaining
            else:
                break

        return expr

    def _parse_function_arguments(self, function: PIdentifier) -> PFunctionCall:
        """Parse function call arguments.

        Args:
            function (PExpression): The function expression to be called

        Returns:
            PFunctionCall: The parsed function call

        Raises:
            ParserError: If there's a syntax error in the argument list
        """
        open_paren_lexeme = self._expect(LexemeType.PUNCTUATION_OPENPAREN)
        arguments = []

        # Parse arguments if any
        if not self._match(LexemeType.PUNCTUATION_CLOSEPAREN):
            while True:
                arguments.append(self._parse_expression())
                if not self._match(LexemeType.PUNCTUATION_COMMA):
                    break
                self._expect(LexemeType.PUNCTUATION_COMMA)

        self._expect(LexemeType.PUNCTUATION_CLOSEPAREN)
        return PFunctionCall(function, arguments, open_paren_lexeme)

    def _parse_member_access(self, left: PExpression) -> Union[PMethodCall, PDotAttribute]:
        """Parse a member access expression (either field access or method call).

        Args:
            left (PExpression): The expression before the dot operator

        Returns:
            Union[PMethodCall, PDotAttribute]: The parsed member access

        Raises:
            ParserError: If there's a syntax error in the member access
        """
        # Consume the dot
        self._expect(LexemeType.OPERATOR_DOT)

        # Get identifier after dot
        member_lexeme = self._expect(LexemeType.IDENTIFIER)
        member_identifier = PIdentifier(member_lexeme.value, member_lexeme)

        # If followed by parentheses, it's a method call
        if self._match(LexemeType.PUNCTUATION_OPENPAREN):
            return self._parse_method_call(left, member_identifier)

        # Otherwise it's a field access
        return PDotAttribute(left, member_identifier)

    def _parse_method_call(self, object_expr: PExpression, method_name: PIdentifier) -> PMethodCall:
        """Parse a method call including its arguments.

        Args:
            object_expr (PExpression): The object expression being called on
            method_name (str): The name of the method

        Returns:
            PMethodCall: The parsed method call

        Raises:
            ParserError: If there's a syntax error in the method call
        """
        open_paren_lexeme = self._expect(LexemeType.PUNCTUATION_OPENPAREN)
        arguments = []

        # Parse arguments if any
        if not self._match(LexemeType.PUNCTUATION_CLOSEPAREN):
            while True:
                arguments.append(self._parse_expression())
                if not self._match(LexemeType.PUNCTUATION_COMMA):
                    break
                self._expect(LexemeType.PUNCTUATION_COMMA)

        self._expect(LexemeType.PUNCTUATION_CLOSEPAREN)
        return PMethodCall(object_expr, method_name, arguments, open_paren_lexeme)

    def _parse_if_statement(self, block_properties:BlockProperties) -> PIfStatement:
        """Parse an if statement"""
        if_lexeme = self._expect(LexemeType.KEYWORD_CONTROL_IF)
        self._expect(LexemeType.PUNCTUATION_OPENPAREN)
        condition = self._parse_expression()
        self._expect(LexemeType.PUNCTUATION_CLOSEPAREN)

        # Then block can be a single statement or be a {braced block}
        if self._match(LexemeType.PUNCTUATION_OPENBRACE):
            then_block = self._parse_block(block_properties)
        else:
            start_lexeme = self.current_lexeme
            then_block = self._parse_statement(block_properties)
            then_block = PBlock([then_block], start_lexeme,
                                block_properties=block_properties)

        else_block = None

        if self._match(LexemeType.KEYWORD_CONTROL_ELSE):
            self.lexeme_stream.advance()
            # Then block can be a single statement or be a {braced block}
            if self._match(LexemeType.PUNCTUATION_OPENBRACE):
                else_block = self._parse_block(block_properties)
            else:
                start_lexeme = self.current_lexeme
                else_block = self._parse_statement(block_properties)
                else_block = PBlock([else_block], start_lexeme,
                                    block_properties=block_properties)

        return PIfStatement(condition, then_block, else_block, if_lexeme)

    def _parse_while_statement(self, block_properties:BlockProperties) -> PWhileStatement:
        """Parse a while loop statement"""
        while_lexeme = self._expect(LexemeType.KEYWORD_CONTROL_WHILE)
        self._expect(LexemeType.PUNCTUATION_OPENPAREN)
        condition = self._parse_expression()
        self._expect(LexemeType.PUNCTUATION_CLOSEPAREN)


        if self._match(LexemeType.PUNCTUATION_OPENBRACE):
            body = self._parse_block(block_properties.copy_with(is_loop=True))
        else:
            start_lexeme = self.current_lexeme
            body = PBlock([self._parse_statement(block_properties.copy_with(is_loop=True))],
                          start_lexeme,
                          block_properties=block_properties)
        return PWhileStatement(condition, body, while_lexeme)

    def _parse_for_statement(self, block_properties:BlockProperties) -> PForStatement:
        """Parse a for loop statement"""
        for_lexeme = self._expect(LexemeType.KEYWORD_CONTROL_FOR)
        self._expect(LexemeType.PUNCTUATION_OPENPAREN)

        # Initialize statement (optional)
        if self._match(LexemeType.PUNCTUATION_SEMICOLON):
            initializer = PNoop(self.current_lexeme)
            self._expect(LexemeType.PUNCTUATION_SEMICOLON)
        else:
            initializer = self._parse_statement(block_properties)
            assert isinstance(initializer, (PAssignment, PVariableDeclaration))

        # Condition (optional)
        if self._match(LexemeType.PUNCTUATION_SEMICOLON):
            condition = PNoop(self.current_lexeme)
        else:
            condition = self._parse_expression()
        self._expect(LexemeType.PUNCTUATION_SEMICOLON)

        # Increment statement (optional)
        if self._match(LexemeType.PUNCTUATION_CLOSEPAREN):
            increment = PNoop(self.current_lexeme)
        else:
            increment = self._parse_expression()

        self._expect(LexemeType.PUNCTUATION_CLOSEPAREN)

        if self._match(LexemeType.PUNCTUATION_OPENBRACE):
            body = self._parse_block(block_properties.copy_with(is_loop=True))
        else:
            start_lexeme = self.current_lexeme
            body = PBlock([self._parse_statement(block_properties)],
                          start_lexeme,
                          block_properties=block_properties)

        return PForStatement(initializer, condition, increment, body, for_lexeme)

    def _parse_return_statement(self) -> PReturnStatement:
        """Parse a return statement"""
        return_lexeme = self._expect(LexemeType.KEYWORD_CONTROL_RETURN)
        value = None

        if not self._match(LexemeType.PUNCTUATION_SEMICOLON):
            value = self._parse_expression()

        self._expect(LexemeType.PUNCTUATION_SEMICOLON)
        return PReturnStatement(value, return_lexeme)

    def _parse_break_statement(self) -> PBreakStatement:
        """Parse a break statement"""
        break_lexeme = self._expect(LexemeType.KEYWORD_CONTROL_BREAK)
        self._expect(LexemeType.PUNCTUATION_SEMICOLON)
        return PBreakStatement(break_lexeme)

    def _parse_continue_statement(self) -> PContinueStatement:
        """Parse a continue statement"""
        continue_lexeme = self._expect(LexemeType.KEYWORD_CONTROL_CONTINUE)
        self._expect(LexemeType.PUNCTUATION_SEMICOLON)
        return PContinueStatement(continue_lexeme)

    def _parse_assert_statement(self) -> PAssertStatement:
        """Parse an assert statement"""
        assert_lexeme = self._expect(LexemeType.KEYWORD_CONTROL_ASSERT)
        self._expect(LexemeType.PUNCTUATION_OPENPAREN)
        condition = self._parse_expression()

        message = None
        if self._match(LexemeType.PUNCTUATION_COMMA):
            self.lexeme_stream.advance()
            message = self._parse_expression()
            assert isinstance(message, PLiteral)

        self._expect(LexemeType.PUNCTUATION_CLOSEPAREN)
        self._expect(LexemeType.PUNCTUATION_SEMICOLON)
        return PAssertStatement(condition, message, assert_lexeme)

    def _parse_class_definition(self, block_properties:BlockProperties) -> PClass:
        """Parse a class definition"""
        class_lexeme = self._expect(LexemeType.KEYWORD_OBJECT_CLASS)
        class_name_lexeme = self._expect(LexemeType.IDENTIFIER)

        self._expect(LexemeType.PUNCTUATION_OPENBRACE)
        fields: List[PClassField] = []
        methods: List[PMethod] = []

        while not self._match(LexemeType.PUNCTUATION_CLOSEBRACE):
            if self._match(*self.type_keywords, LexemeType.IDENTIFIER):
                # Parse field or method type
                type_lexeme = self.current_lexeme
                type_name = self._parse_type()

                name_lexeme = self._expect(LexemeType.IDENTIFIER)
                member_name = name_lexeme.value

                if self._match(LexemeType.PUNCTUATION_OPENPAREN):
                    # Method
                    method = self._parse_function_declaration(member_name, type_name, type_lexeme,
                                                              block_properties.copy_with(is_class=True,
                                                                                         in_function=True))
                    methods.append(
                        PMethod(method.name, method.return_type, PType(class_name_lexeme.value, class_name_lexeme),
                                method.function_args, method.body, name_lexeme))
                else:
                    # Property
                    is_public = True  # TODO: Handle visibility modifiers
                    default_value = None
                    if self._match(LexemeType.OPERATOR_BINARY_ASSIGN):
                        self._expect(LexemeType.OPERATOR_BINARY_ASSIGN)
                        default_value = self._parse_expression(is_lvalue=False)
                    self._expect(LexemeType.PUNCTUATION_SEMICOLON)
                    fields.append(PClassField(member_name, type_name, is_public,
                                                     type_lexeme, default_value=default_value))
            else:
                raise ParserError("Expected class member definition", self.current_lexeme)

        self._expect(LexemeType.PUNCTUATION_CLOSEBRACE)
        #sort fields to place all pointers (reference types) at the begining of the struct
        #it ise useful for the GC to tarverse the object's fields that are reference types
        fields.sort(key= lambda p:
                    int(p.var_type.type_string in ['bool', 'char', 'i8', 'u8', 'i16', 'u16', 'f16', 
                                                    'i32', 'u32', 'f32', 'i64', 'u64', 'f64'])
            )
        return PClass(class_name_lexeme.value, fields, methods, class_lexeme)

    def _parse_ternary_operation(self, condition) -> PTernaryOperation:
        """Parse a ternary operation (condition ? true_value : false_value)"""

        self._expect(LexemeType.PUNCTUATION_TERNARYCONDITIONAL_QUESTIONMARK)
        true_value = self._parse_expression()

        self._expect(LexemeType.PUNCTUATION_TERNARYSEPARATOR_COLON)
        false_value = self._parse_expression()

        return PTernaryOperation(condition, true_value, false_value, self.current_lexeme)