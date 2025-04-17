import pytest
from io import StringIO
from typing import List, Type
from tempfile import TemporaryDirectory
from llvm_transpiler import CodeGen, LLVM_Version, OutputFormat, CompilationOptions
import re
from llvmlite.binding import (Target, parse_assembly, create_mcjit_compiler,
                              ModuleRef, parse_bitcode)
from constants import (ENTRYPOINT_FUNCTION_NAME, FUNC_POPULATE_GLOBALS,
                       FUNC_GC_ENTER_SCOPE, FUNC_GC_LEAVE_SCOPE)
import ctypes
import math
from pathlib import Path

def create_execution_engine():
    """
    Create an ExecutionEngine suitable for JIT code generation on
    the host CPU.  The engine is reusable for an arbitrary number of
    modules.
    """
    # Create a target machine representing the host
    target = Target.from_default_triple()
    target_machine = target.create_target_machine()
    # And an execution engine with an empty backing module
    backing_mod = parse_assembly("")
    engine = create_mcjit_compiler(backing_mod, target_machine)
    return engine

class CodeGenTestCase:    
    def setup_method(self):
        self.generator = CodeGen()
        self._engine = create_execution_engine()
    
    def compile_to_llvm_ir(self, source:str) -> str:
        gen = CodeGen()
        with TemporaryDirectory() as tmpdir:
            outfile = str(Path(tmpdir,'outfile.ll'))
            outfile = gen.compile_module(Path('/tmp/test.cs'),
                                           StringIO(source),
                                           emit_format=OutputFormat.IntermediateRepresentation,
                                           output_file=outfile,
                                           llvm_version=LLVM_Version.v15)
            with open(outfile, 'rt') as ir:
                return ir.read()

    def generate_module(self, source: str) -> ModuleRef:
        """Helper method to generate LLVM IR from source code"""
        gen = CodeGen()
        with TemporaryDirectory() as tmpdir:
            outfile = str(Path(tmpdir,'outfile.bc'))
            outfile = gen.compile_module(Path('/tmp/test.cs'),
                                StringIO(source),
                                emit_format=OutputFormat.BitCode,
                                output_file=outfile,
                                llvm_version=LLVM_Version.v15)
            with open(outfile, 'rb') as bc:
                return parse_bitcode(bc.read())
    
    def get_function_ir(self, module:ModuleRef, func_name:str='main'):
        func = module.get_function(func_name)
        blocks = func.blocks
        return '\n'.join([str(block) for block in blocks])
    
    def compile_ir(self, module:ModuleRef):
        """
        Compile the LLVM IR string with the given engine.
        The compiled module object is returned.
        """
        # Now add the module and make sure it is ready for execution
        self._engine.add_module(module)
        self._engine.finalize_object()
        self._engine.run_static_constructors()
        return module
    
    def compile_and_run_main(self, source:str):
        mod = self.generate_module(source)
        self.compile_ir(mod)
        main_proto = [ctypes.c_int32]
        return self._run_function(ENTRYPOINT_FUNCTION_NAME, main_proto)
    
    def _run_function(self, func_name:str, func_prototype_ctypes:List[Type], *args):
        """Runs a function compiled in the engine using ctypes and returns the result"""
        func_ptr = self._engine.get_function_address(func_name)

        # Run the function via ctypes
        cfunc = ctypes.CFUNCTYPE(*func_prototype_ctypes)(func_ptr)
        return cfunc(*args)


class TestCodeGeneratorBasicDeclarations(CodeGenTestCase):
    """Test basic variable and function declarations"""

    @pytest.mark.parametrize("source, var_name",[
            ("i32 x = 42;", "x"),
            ("f64 pi = 3.14159;", "pi"),
            ("bool flag = true;", "flag"),
            ("char c = 'a';", "c"),
            ("string msg = \"hello\";", "msg")
        ])
    def test_valid_primitive_global_literal_declarations(self, source, var_name):
        """Test valid primitive type declarations"""
        module = self.generate_module(source)
        global_ir = str(module)
        main_ir = self.get_function_ir(module, FUNC_POPULATE_GLOBALS)
        assert f"@{var_name} = global" in global_ir
        assert "store" in main_ir

    @pytest.mark.parametrize("source, expected_result",[
            ("""i32 main()
            {
                i32 x = 42;
                return x;
            }""", 42),
            ("""i32 main()
            {
                char c = 'a';
                return c;
            }""", 97),
            ("""i32 main()
            {
                bool flag = true;
                return flag;
            }""", 1)
        ])
    def test_valid_primitive_literal_declarations(self, source, expected_result):
        """Test valid primitive type declarations"""
        ret_val = self.compile_and_run_main(source)
        assert ret_val == expected_result

    @pytest.mark.parametrize("source, alloc_func",[
            ("i32[] arr = new i32[10];", "@__PS_AllocateValueArray"),
            ("string[] arr = new string[5];", "@__PS_AllocateRefArray"),
            ("bool[] arr = new bool[3];", "@__PS_AllocateValueArray"),
            ("i32[][] arr = new i32[3][];", "@__PS_AllocateRefArray")
        ])
    def test_valid_array_declarations(self, source, alloc_func):
        """Test valid array declarations"""
        module = self.generate_module(source)
        main_code = self.get_function_ir(module, FUNC_POPULATE_GLOBALS)
        global_code = str(module)
        # assert array var is globally known
        assert "@arr = global ptr" in global_code
        # assert value is initialized in main func
        assert f"call ptr {alloc_func}" in main_code

class TestCodeGeneratorFunctionDeclarations(CodeGenTestCase):
    """Test function declarations and return types"""

    @pytest.mark.parametrize("source, f_name",[
            ("""
            void empty() {
            }
            i32 main(){
                empty();
                return 0;
            }
            """, "empty"),
            ("""
            void printInt(i32 int) {
                // Empty function with parameter
            }
            i32 main(){
                printInt(123);
                return 0;
            }
            ""","printInt")
        ])
    def test_valid_void_functions(self, source, f_name):
        """Test valid void function declarations"""
        module = self.generate_module(source)
        try:
            self.get_function_ir(module, func_name=f_name)
            self.compile_ir(module)
        except:
            raise AssertionError(f"Unable to find function {f_name}")
        assert 0 == self.compile_and_run_main(source)
                

    @pytest.mark.parametrize("source, f_name, res",[
            ("""
            i32 add(i32 a, i32 b) {
                return a + b;
            }
            i32 main(){
                return add(3,2);
            }
            """, "add",5),
            ("""
            f32 mul(f32 a, f32 b) {
                return a * b;
            }
            i32 main(){
                return (i32) mul(2,3);
            }
            """, "mul", 6)
        ])
    def test_valid_return_type_functions(self, source, f_name, res):
        """Test valid functions with return values"""
        module = self.generate_module(source)
        try:
            ir_code = self.get_function_ir(module, func_name=f_name)
            assert "ret" in ir_code
            self.compile_ir(module)
        except:
            raise AssertionError(f"Unable to find function {f_name}")
        assert res == self.compile_and_run_main(source)


class TestCodeGeneratorClassDeclarations(CodeGenTestCase):
    """Test class declarations and member access"""

    def test_valid_class_with_methods(self):
        """Test valid class with method declarations"""
        source = """
        class Rectangle {
            i32 width;
            i32 height;

            i32 GetArea() {
                return this.width * this.height;
            }

            void SetSize(i32 w, i32 h) {
                this.width = w;
                this.height = h;
            }
        }
        """
        module = self.generate_module(source)
        self.get_function_ir(module, "__Rectangle.__GetArea")
        self.get_function_ir(module, "__Rectangle.__SetSize")

class TestCodeGeneratorMethodCalls(CodeGenTestCase):
    """Test method calls and method chaining"""

    def test_valid_simple_method_calls(self):
        """Test valid simple method calls"""
        source = """
        class Calculator {
            i32 Add(i32 a, i32 b) {
                return a + b;
            }
        }
        i32 main(){
            Calculator calc = new Calculator();
            return calc.Add(5, 3);   
        }
        """
        module = self.generate_module(source)
        ir_code = self.get_function_ir(module, "__Calculator.__Add")
        ir_code = self.get_function_ir(module)
        assert "call" in ir_code
        assert "i32" in ir_code
        res = self.compile_and_run_main(source)
        assert res == 3+5

    def test_valid_method_chaining(self):
        """Test valid method chaining"""
        source = """
        class IntBuilder {
            i32 total = 0;

            IntBuilder inc(i32 value) {
                this.total = this.total + value;
                return this;
            }
        }
        i32 main()
        {
            IntBuilder ib = new IntBuilder();
            ib.inc(1).inc(2).inc(3);
            return ib.total;
        }
        """
        result = self.compile_and_run_main(source)
        assert result == 1 + 2 + 3
        

class TestCodeGeneratorBuiltins(CodeGenTestCase):
    """Test builtin methods and fields"""
    
    @pytest.mark.parametrize("source, expected_value",[
            ("i32 main() { string s = true.ToString(); return (i32) s.Length; }", 4),
            ("i32 main() { string s = (123).ToString(); return (i32) s.Length; }", 3),
            ("i32 main() { string s = (3.1415).ToString(); return (i32) s.Length; }", 6),
            ("i32 main() { string s = \"hello\".ToString(); return (i32) s.Length; }", 5),
            ("i32 main() { string s = 'a'.ToString(); return (i32) s.Length; }", 1)
        ])
    def test_valid_to_string_calls_and_string_length_access(self, source, expected_value):
        res = self.compile_and_run_main(source)
        assert res == expected_value
    
    @pytest.mark.parametrize("source, expected_value",[
            ("i32 main() { i32[] arr = new i32[4]; return (i32) arr.Length; }", 4),
            ("i32 main() { i32[] arr = new i32[0]; return (i32) arr.Length; }", 0),
            ("i32 main() { bool[] arr = new bool[5]; return (i32) arr.Length; }", 5),
            ("i32 main() { string[] arr = new string[100]; return (i32) arr.Length; }", 100),
            ("""class A{}
             i32 main() { A[] arr = new A[10]; return (i32) arr.Length; }""", 10),
        ])
    def test_valid_array_length_field_access(self, source, expected_value):
        res = self.compile_and_run_main(source)
        assert res == expected_value

class TestCodeGeneratorArrayOperations(CodeGenTestCase):
    """Test array operations and indexing"""

    @pytest.mark.parametrize("source, expected_result",[
            ("""
            i32 main() {
                i32[] arr = new i32[10];
                arr[0] = 42;
                arr[5] = 2;
                i32 x = arr[5];
                return x;
            }
            """, 2),
            ("""
            i32 main() {
                i32[] arr = new i32[3];
                return arr[1];
            }
            """, 0),
            ("""
            i32[][] matrix = new i32[3][];
            i32 main() {
                matrix[0] = new i32[3];
                matrix[0][0] = 1;
                i32 x = matrix[0][0];
                return x;
            }
            """, 1)
        ])
    def test_valid_array_indexing(self, source, expected_result):
        """Test valid array indexing operations"""
        module = self.generate_module(source)
        ir_code = self.get_function_ir(module)
        assert "getelementptr" in ir_code
        assert "store" in ir_code
        assert "load" in ir_code
        result = self.compile_and_run_main(source)
        assert result == expected_result

    @pytest.mark.parametrize("source, expected_result",[
            ("""
            class C
            {
                i32[] arr = new i32[5];
            }
            i32 main() {
                C obj = new C();
                obj.arr[0] = 123;
                return obj.arr[0];
            }
            """, 123),
            ("""
            class C
            {
                i32[] arr = new i32[5];
            }
            i32 main() {
                C obj = new C();
                obj.arr[1] = 123;
                return obj.arr[0];
            }
            """, 0),
            ("""
            class C
            {
                i32[][] matrix = new i32[2][];
            }
            i32 main() {
                C obj = new C();
                obj.matrix[0] = new i32[1];
                obj.matrix[1] = new i32[2];
                obj.matrix[0][0] = 1;
                obj.matrix[1][1] = 2;
                return obj.matrix[1][1];
            }
            """, 2),
            ("""
            class C
            {
                i32[][] matrix = new i32[2][];
            }
            i32 main() {
                C obj = new C();
                obj.matrix[0] = new i32[1];
                obj.matrix[1] = new i32[2];
                obj.matrix[0][0] = 1;
                obj.matrix[1][1] = 2;
                return obj.matrix[1][0];
            }
            """, 0)
        ])
    def test_valid_field_array_indexing(self, source, expected_result):
        """Test valid array indexing operations"""
        module = self.generate_module(source)
        ir_code = self.get_function_ir(module)
        assert "getelementptr" in ir_code
        assert "store" in ir_code
        assert "load" in ir_code
        result = self.compile_and_run_main(source)
        assert result == expected_result

class TestCodeGeneratorOperators(CodeGenTestCase):
    """Test operator type checking"""

    @pytest.mark.parametrize("source, expected_result, operation", [
            ("i32 main() { return 1 + 2;}", 3, "add"),
            ("i32 main() { return 3 - 4;}", -1, "sub"),
            ("i32 main() { return 5 * 6;}", 30, "mul"),
            ("i32 main() { return 8 / 2;}", 4, "div"),
            ("i32 main() { return 10 % 3;}", 1, "srem")
        ])
    def test_valid_arithmetic_operators(self, source, expected_result, operation):
        """Test valid arithmetic operators"""
        module = self.generate_module(source)
        ir_code = self.get_function_ir(module)
        assert operation in ir_code
        res = self.compile_and_run_main(source)
        assert res == expected_result

    @pytest.mark.parametrize("source, expected_result",[
            ("i32 main() { return 1 < 2;}", True),
            ("i32 main() { return 3 > 4;}", False),
            ("i32 main() { return 5 <= 6;}", True),
            ("i32 main() { return 7 >= 8;}", False),
            ("i32 main() { return 9 == 10;}", False),
            ("i32 main() { return 11 != 12;}", True)
        ])
    def test_valid_comparison_operators(self, source, expected_result):
        """Test valid comparison operators"""
        module = self.generate_module(source)
        ir_code = self.get_function_ir(module)
        assert "icmp" in ir_code
        res = self.compile_and_run_main(source)
        assert res == int(expected_result)

    @pytest.mark.parametrize("source, expected_result, operation",[
            ("i32 main() { return true and false;}", False, "and"),
            ("i32 main() { return true or false;}", True, "or"),
            ("i32 main() { return not true;}", False, "xor")
        ])
    def test_valid_logical_operators(self, source, expected_result, operation):
        """Test valid logical operators"""
        module = self.generate_module(source)
        ir_code = self.get_function_ir(module)
        assert operation in ir_code
        res = self.compile_and_run_main(source)
        assert res == int(expected_result)

class TestCodeGeneratorControlFlow(CodeGenTestCase):
    """Test type checking in control flow statements"""

    @pytest.mark.parametrize("source",[
            """
            i32 main(){
                i32 x = 0;
                if (true)
                    x = 2;
                return x;
            }
            """,
            """
            i32 main(){
                i32 x = 0;
                if (1 < 2)
                    x = 2;
                return x;
            }
            """,
            """
            i32 main(){
                i32 x = 0;
                if (not false)
                    x = 2;
                return x;
            }
            """])
    def test_valid_if_conditions(self, source):
        """Test valid if statement conditions"""
        module = self.generate_module(source)
        ir_code = self.get_function_ir(module)
        assert "br i1" in ir_code
        res = self.compile_and_run_main(source)
        assert res == 2

    @pytest.mark.parametrize("source, excepted_result",[
            ("""
            i32 main(){
                i32 x = 1;
                while (x < 10) 
                    x++;
                return x;
            }""", 10),
            ("""
            i32 main(){
                i32 i = 30;
                while (i > 10)
                    i = i - 3;
                return i;
            }
            """, 9),
            ("""
            i32 main(){
                i32 i = 0;
                i32 j = 0;
                while (true)
                {
                    if (i == 3)
                        break;
                    i++;
                    j = j + 3;
                }
                return j;
            }
            """, 9)])
    def test_valid_while_conditions(self, source, excepted_result):
        """Test valid while loop conditions"""
        module = self.generate_module(source)
        ir_code = self.get_function_ir(module)
        assert "br i1" in ir_code
        res = self.compile_and_run_main(source)
        assert res == excepted_result

    @pytest.mark.parametrize("source, excepted_result",[
            ("""
            i32 main(){
                i32 x;
                for (i32 i = 0; i < 10; i++)
                    x = i*2;
                return x;
            }""",18),
            ("""
            i32 main(){
                i32 y = 0;
                for (i32 j = 10; j > 0; j--)
                    y = j;
                return y;
            }""",1),
            ("""
            i32 main() {
                for (;;){return 3;}
            }""",3)
            ])
    def test_valid_for_components(self, source, excepted_result):
        """Test valid for loop components"""
        module = self.generate_module(source)
        ir_code = self.get_function_ir(module)
        assert "br i1" in ir_code
        res = self.compile_and_run_main(source)
        assert res == excepted_result

class TestCodeGeneratorImplicitConversions(CodeGenTestCase):
    """Test implicit type conversion rules"""

    def test_valid_integer_promotions(self):
        """Test valid integer type promotions"""
        source = """
        i8 small = (i8)42;
        i16 medium = small;  // i8 -> i16
        i32 large = medium;  // i16 -> i32
        i64 huge = large;    // i32 -> i64
        """
        module = self.generate_module(source)
        ir_code = self.get_function_ir(module, FUNC_POPULATE_GLOBALS)
        assert "sext" in ir_code

    def test_valid_float_promotions(self):
        """Test valid float type promotions"""
        source = """
        f32 single = 3.14;
        f64 double = single;  // f32 -> f64
        """
        module = self.generate_module(source)
        ir_code = self.get_function_ir(module, FUNC_POPULATE_GLOBALS)
        assert "fpext" in ir_code

    @pytest.mark.parametrize("source",[
            "f32 float32 = (i8) 123;    // i8 -> f32",
            "f32 another = (i16) 123;    // i16 -> f32",
            "f64 float64 = (i32) 123;    // i32 -> f64"
        ])
    def test_valid_integer_to_float_conversions(self, source):
        """Test valid integer to float conversions"""
        module = self.generate_module(source)
        ir_code = self.get_function_ir(module, FUNC_POPULATE_GLOBALS)
        assert "sitofp" in ir_code

class TestCodeGeneratorTypeCasting(CodeGenTestCase):
    """Test explicit type casting operations"""

    def test_valid_numeric_down_casts(self):
        """Test valid numeric down casting"""
        source = """
        i64 large = 42;
        i32 medium = (i32)large;  // i64 -> i32
        i16 small = (i16)medium;  // i32 -> i16
        i8 tiny = (i8)small;      // i16 -> i8
        """
        module = self.generate_module(source)
        ir_code = self.get_function_ir(module, FUNC_POPULATE_GLOBALS)
        assert "trunc" in ir_code

    @pytest.mark.parametrize("source",[
            """
            f64 double = 3.14; 
            i32 int32 = (i32)double;  // f64 -> i32
            """,
            """
            f32 single = 2.718;
            i16 int16 = (i16)single;  // f32 -> i16
            """])
    def test_valid_float_to_integer_casts(self, source):
        """Test valid float to integer casts"""
        module = self.generate_module(source)
        ir_code = self.get_function_ir(module, FUNC_POPULATE_GLOBALS)
        assert "fptosi" in ir_code

class TestCodeGeneratorUnaryOperations(CodeGenTestCase):
    """Test type checking of unary operations"""

    @pytest.mark.parametrize("source, expected_op, expected_result",(
            ("i32 main(){ return -42;}", "sub", -42),
            ("i32 main(){ return -(1 + 2);}", "sub", -3),
            ("i32 main(){ return (i32) -3.14;}", "fneg", -3),
            ("i32 main(){ return (i32) -(2.0 * 3.0);}"," fneg", -6)
        ))
    def test_valid_numeric_negation(self, source, expected_op, expected_result):
        """Test valid numeric negation"""
        module = self.generate_module(source)
        ir_code = self.get_function_ir(module)
        assert expected_op in ir_code
        res = self.compile_and_run_main(source)
        assert res == expected_result

    @pytest.mark.parametrize("var_decl",[
                    "bool a = not true;",
                    "bool b = not (1 < 2);",
                    "bool c = not (true and false);",
                    "bool d = not not true;"])
    def test_valid_logical_not(self, var_decl):
        """Test valid logical not operations"""
        module = self.generate_module(var_decl)
        ir_code = self.get_function_ir(module, FUNC_POPULATE_GLOBALS)
        assert "xor" in ir_code

    @pytest.mark.parametrize("source, expected_result",[
                ("i32 main(){ i32 x = 0; return x++;}", 0),
                ("i32 main(){ i32 x = 0; return ++x;}", 1),
                ("i32 main(){ i32 x = 0; return x--;}", 0),
                ("i32 main(){ i32 x = 0; return --x;}", -1),
                ("i32 main(){ i32 x = 0; i32 y = x++; return x;}", 1),
                ("i32 main(){ i32 x = 0; i32 z = ++x; return x;}", 1)
            ])
    def test_valid_increment_decrement(self, source, expected_result):
        """Test valid increment/decrement operations"""
        res = self.compile_and_run_main(source)
        assert res == expected_result

class TestRuntimeExecution(CodeGenTestCase):
    """Test cases that verify correct execution results at runtime"""
    
    @pytest.mark.parametrize("source, expected",[
            ("""i32 main() {
                return 1 + 2;
            }""", 3),
            ("""i32 main() {
                return 5 - 2;
            }""", 3),
            ("""i32 main() {
                return 3 * 4;
            }""", 12),
            ("""i32 main() {
                return 10 / 2;
            }""", 5),
            ("""i32 main() {
                return 10 % 3;
            }""", 1)
        ])
    def test_arithmetic_operations(self, source, expected):
        """Test basic arithmetic operations with runtime verification"""
        result = self.compile_and_run_main(source)
        assert result == expected
    
    @pytest.mark.parametrize("source, expected",[
            ("""i32 main() {
                i32 x = 42;
                return x;
            }""", 42),
            ("""i32 main() {
                i32 x = 10;
                i32 y = 20;
                return x + y;
            }""", 30),
            ("""i32 main() {
                i32 x = 5;
                x = 10;
                return x;
            }""", 10)
        ])
    def test_variable_declarations(self, source, expected):
        """Test variable declarations with runtime verification"""  
        result = self.compile_and_run_main(source)
        assert result == expected
    
    @pytest.mark.parametrize("source, expected",[
            ("""i32 main() {
                if (true) {
                    return 42;
                }
                return 0;
            }""", 42),
            ("""i32 main() {
                if (false) {
                    return 42;
                }
                return 0;
            }""", 0),
            ("""i32 main() {
                if (10 > 5) {
                    return 1;
                } else {
                    return 0;
                }
            }""", 1),
            ("""i32 main() {
                if (3 > 5) {
                    return 1;
                } else {
                    return 0;
                }
            }""", 0)
        ])
    def test_condition_statements(self, source, expected):
        """Test if statements with runtime verification"""
        result = self.compile_and_run_main(source)
        assert result == expected
    
    @pytest.mark.parametrize("source, expected",[
            ("""i32 main() {
                i32 sum = 0;
                for (i32 i = 1; i <= 5; i = i + 1) {
                    sum = sum + i;
                }
                return sum;
            }""", 15),  # 1+2+3+4+5 = 15
            ("""i32 main() {
                i32 i = 0;
                i32 sum = 0;
                while (i < 5) {
                    sum = sum + i;
                    i = i + 1;
                }
                return sum;
            }""", 10)  # 0+1+2+3+4 = 10
        ])
    def test_loop_statements(self, source, expected):
        """Test loop statements with runtime verification"""
        result = self.compile_and_run_main(source)
        assert result == expected
    
    @pytest.mark.parametrize("source, expected",[
            ("""
            i32 add(i32 a, i32 b) {
                return a + b;
            }
            
            i32 main() {
                return add(5, 7);
            }
            """, 12),
            ("""
            i32 factorial(i32 n) {
                if (n <= 1) {
                    return 1;
                }
                return n * factorial(n - 1);
            }
            
            i32 main() {
                return factorial(5);
            }
            """, 120)  # 5! = 120
        ])
    def test_function_calls(self, source, expected):
        """Test function calls with runtime verification"""
        result = self.compile_and_run_main(source)
        assert result == expected
    
    @pytest.mark.parametrize("source, expected",[
            ("""i32 main() {
                i8 a = (i8)127;
                i32 b = a;
                return b;
            }""", 127),
            ("""i32 main() {
                i32 a = 300;
                i8 b = (i8)a;
                i32 c = b;
                return c;
            }""", 44),  # 300 % 256 = 44 (truncation)
            ("""i32 main() {
                f32 a = 3.75;
                i32 b = (i32)a;
                return b;
            }""", 3)  # float to int truncates
        ])
    def test_type_conversions(self, source, expected):
        """Test type conversions with runtime verification"""
        result = self.compile_and_run_main(source)
        assert result == expected
    
    @pytest.mark.parametrize("source, expected",[
            ("""i32 main() {
                return (5 + 3) * 2 - 4;
            }""", 12),
            ("""i32 main() {
                return 10 / (5 - 3) + 7;
            }""", 12),
            ("""i32 main() {
                i32 a = 5;
                i32 b = 3;
                i32 c = 2;
                return a * b + c * (a - b);
            }""", 19)  # 5*3 + 2*(5-3) = 15 + 4 = 19
        ])
    def test_complex_expressions(self, source, expected):
        """Test complex expressions with runtime verification"""
        result = self.compile_and_run_main(source)
        assert result == expected
    
    @pytest.mark.parametrize("source, expected",[
            ("""i32 main() {
                return true and true;
            }""", 1),
            ("""i32 main() {
                return true and false;
            }""", 0),
            ("""i32 main() {
                return true or false;
            }""", 1),
            ("""i32 main() {
                return false or false;
            }""", 0),
            ("""i32 main() {
                return not false;
            }""", 1),
            ("""i32 main() {
                return not true;
            }""", 0),
            ("""i32 main() {
                return (5 > 3) and (10 < 20);
            }""", 1)
        ])
    def test_boolean_logic(self, source, expected):
        """Test boolean logic with runtime verification"""
        result = self.compile_and_run_main(source)
        assert result == expected
    
    @pytest.mark.parametrize("source, expected",[
            ("""
             i32 x = 5;
             bool inc_x(){++x; return true;}
             i32 main() {
                if (true or inc_x()) {
                    return x;
                }
                return 0;
            }""", 5),  # x should not be modified because of short-circuit
            ("""i32 x = 5;
                bool inc_x(){++x; return true;}
                i32 main() {
                if (false and inc_x()) {
                    return 0;
                }
                return x;
            }""", 5)  # x should not be modified because of short-circuit
        ])
    def test_logical_short_circuit(self, source, expected):
        """Test logical short-circuit behavior"""
        result = self.compile_and_run_main(source)
        assert result == expected

    @pytest.mark.parametrize("source, expected",[
            ("""i32 main() {
                char a = 'A';
                return a;
            }""", 65),  # ASCII value of 'A'
            ("""i32 main() {
                char a = 'A';
                char b = 'a';
                return b - a;
            }""", 32)  # Difference between 'a' and 'A' in ASCII
        ])
    def test_char_operations(self, source, expected):
        """Test character operations with runtime verification"""
        result = self.compile_and_run_main(source)
        assert result == expected
                
    @pytest.mark.parametrize("source, expected",[
            ("""i32 main() {
                i32 x = 5;
                x++;
                return x;
            }""", 6),
            ("""i32 main() {
                i32 x = 5;
                return x++;
            }""", 5),  # Return value before increment
            ("""i32 main() {
                i32 x = 5;
                return ++x;
            }""", 6),  # Return value after increment
            ("""i32 main() {
                i32 x = 5;
                x--;
                return x;
            }""", 4),
            ("""i32 main() {
                i32 x = 5;
                return --x;
            }""", 4),  # Return value after decrement
            ("""i32 main() {
                i32 x = 5;
                return x--;
            }""", 5)  # Return value before decrement
        ])
    def test_increment_decrement(self, source, expected):
        """Test increment/decrement operations with runtime verification"""
        
        result = self.compile_and_run_main(source)
        assert result == expected

class TestCodeGeneratorNestedLoops(CodeGenTestCase):
    """Test nested loops: both for–for and while–while combinations."""

    def test_nested_for_loops(self):
        source = """
        i32 main(){
            i32 sum = 0;
            for (i32 i = 1; i <= 3; i = i + 1) {
                for (i32 j = 1; j <= 3; j = j + 1) {
                    sum = sum + i * j;
                }
            }
            return sum;
        }
        """
        # Expected: (1*1 + 1*2 + 1*3) + (2*1 + 2*2 + 2*3) + (3*1 + 3*2 + 3*3) = 36
        expected = 36
        result = self.compile_and_run_main(source)
        assert result == expected

    def test_nested_while_loops(self):
        source = """
        i32 main(){
            i32 i = 1;
            i32 sum = 0;
            while (i <= 3) {
                i32 j = 1;
                while (j <= 3) {
                    sum = sum + i * j;
                    j = j + 1;
                }
                i = i + 1;
            }
            return sum;
        }
        """
        expected = 36
        result = self.compile_and_run_main(source)
        assert result == expected


class TestCodeGeneratorContinueBreak(CodeGenTestCase):
    """Test loops using continue and break statements."""

    def test_for_loop_with_continue(self):
        # Sum only odd numbers from 1 to 10 (skipping even numbers)
        source = """
        i32 main(){
            i32 sum = 0;
            for (i32 i = 1; i <= 10; i = i + 1) {
                if (i % 2 == 0)
                    continue;
                sum = sum + i;
            }
            return sum;
        }
        """
        # 1 + 3 + 5 + 7 + 9 = 25
        expected = 25
        result = self.compile_and_run_main(source)
        assert result == expected

    def test_while_loop_with_continue(self):
        # Sum only odd numbers using a while loop with continue
        source = """
        i32 main(){
            i32 i = 1;
            i32 sum = 0;
            while (i <= 10) {
                if (i % 2 == 0) {
                    i = i + 1;
                    continue;
                }
                sum = sum + i;
                i = i + 1;
            }
            return sum;
        }
        """
        expected = 25
        result = self.compile_and_run_main(source)
        assert result == expected

    def test_for_loop_with_break(self):
        # Break out of the loop when i equals 5
        source = """
        i32 main(){
            i32 sum = 0;
            for (i32 i = 1; i <= 10; i = i + 1) {
                if (i == 5)
                    break;
                sum = sum + i;
            }
            return sum;
        }
        """
        # Sum of 1+2+3+4 = 10
        expected = 10
        result = self.compile_and_run_main(source)
        assert result == expected

    def test_while_loop_with_break(self):
        # Break the while loop when counter reaches 7
        source = """
        i32 main(){
            i32 i = 1;
            i32 sum = 0;
            while (i <= 10) {
                if (i == 7)
                    break;
                sum = sum + i;
                i = i + 1;
            }
            return sum;
        }
        """
        # Sum of 1+2+3+4+5+6 = 21
        expected = 21
        result = self.compile_and_run_main(source)
        assert result == expected


class TestCodeGeneratorClassFieldAccess(CodeGenTestCase):
    """Test that class methods properly access and update fields."""

    def test_counter_class(self):
        source = """
        class Counter {
            i32 value = 0;
            void inc() {
                this.value = this.value + 1;
            }
            i32 get() {
                return this.value;
            }
        }
        i32 main(){
            Counter c = new Counter();
            c.inc();
            c.inc();
            c.inc();
            return c.get();
        }
        """
        expected = 3
        result = self.compile_and_run_main(source)
        assert result == expected


class TestCodeGeneratorArrayOfObjects(CodeGenTestCase):
    """Test arrays containing objects and invoking their methods."""

    def test_array_of_objects(self):
        source = """
        class Dummy {
            i32 x = 0;
            void setX(i32 val) {
                this.x = val;
            }
            i32 getX() {
                return this.x;
            }
        }
        i32 main(){
            Dummy[] arr = new Dummy[3];
            arr[0] = new Dummy();
            arr[1] = new Dummy();
            arr[2] = new Dummy();
            arr[0].setX(10);
            arr[1].setX(20);
            arr[2].setX(30);
            return arr[0].getX() + arr[1].getX() + arr[2].getX();
        }
        """
        expected = 60
        result = self.compile_and_run_main(source)
        assert result == expected


class TestCodeGeneratorRecursionAdvanced(CodeGenTestCase):
    """Test recursive function calls using Fibonacci as an example."""

    def test_fibonacci(self):
        source = """
        i32 fib(i32 n) {
            if (n <= 1)
                return n;
            return fib(n - 1) + fib(n - 2);
        }
        i32 main(){
            return fib(6);
        }
        """
        # Fibonacci sequence: 0, 1, 1, 2, 3, 5, 8 so fib(6) = 8
        expected = 8
        result = self.compile_and_run_main(source)
        assert result == expected


class TestCodeGeneratorTernaryOperators(CodeGenTestCase):
    """Test simple and nested ternary (conditional) operators."""

    def test_simple_ternary(self):
        source = """
        i32 main(){
            i32 a = 10;
            i32 b = 20;
            i32 max = a > b ? a : b;
            i32 min = a < b ? a : b;
            return max - min;
        }
        """
        # Expected: 20 - 10 = 10
        expected = 10
        result = self.compile_and_run_main(source)
        assert result == expected

    def test_nested_ternary(self):
        source = """
        i32 main(){
            i32 a = 5;
            i32 result = a == 5 ? (a == 6 ? 100 : 50) : 0;
            return result;
        }
        """
        expected = 50
        result = self.compile_and_run_main(source)
        assert result == expected


class TestCodeGeneratorMixedTypeExpressions(CodeGenTestCase):
    """Test expressions combining integer and float types with explicit casts."""

    def test_mixed_int_float(self):
        source = """
        i32 main(){
            i32 a = 3;
            f32 b = (f32)a;
            f32 c = b * 1.5;
            i32 d = (i32)c;
            return d;
        }
        """
        # 3 * 1.5 = 4.5 which truncates to 4
        expected = 4
        result = self.compile_and_run_main(source)
        assert result == expected


class TestCodeGeneratorEdgeCases(CodeGenTestCase):
    """Test edge cases such as loops that never execute and zero-length arrays."""

    def test_empty_for_loop(self):
        source = """
        i32 main(){
            i32 sum = 0;
            for (i32 i = 0; i < 0; i = i + 1)
                sum = sum + i;
            return sum;
        }
        """
        expected = 0
        result = self.compile_and_run_main(source)
        assert result == expected

    def test_zero_length_array(self):
        source = """
        i32 main(){
            i32[] arr = new i32[0];
            return 42;
        }
        """
        expected = 42
        result = self.compile_and_run_main(source)
        assert result == expected
        
class TestCodeGeneratorGCScope(CodeGenTestCase):
    """Tests that the GC scopes are opened and all properly closed"""

    def test_scope_management_code_after_return(self):
        source = """
        i32 f()
        //enter scope for params
        {
            //enter scope
            i32 x;
            { //enter scope
                i32 y;
                { //enter scope
                    i32 z = 0;
                    { //enter scope
                        //leave 4 scopes
                        return 1;
                    }// leave 1 scope
                }// leave 1 scope
            }// leave 1 scope
        }// leave 1 scope
        i32 main(){
            return f();
        }
        """
        expected = 1
        result = self.compile_and_run_main(source)
        assert result == expected
        #count the number of enter/leave scopes
        ir_code = self.get_function_ir(self.generate_module(source), "f")
        assert ir_code.count(f'call void @{FUNC_GC_ENTER_SCOPE}') == 5
        assert f'call void @{FUNC_GC_LEAVE_SCOPE}(i64 5)' in ir_code
        
    @pytest.mark.parametrize("source, scope_enter_count, scope_leave_counts",[
        ("""
        bool f()//enter param scope
        {
            //enter body scope
            return false; //leave twice
        }
        """, 2, [2]),
        ("""
        f32 f()//enter param scope
        {
            //enter body scope
            if (1 == 1) //enter if scope
                return 0.0; //leave 3 scopes
            return 1.0; //leave 2 scopes
        }
        """, 3, [2,3]),
        ("""
        bool f()//enter param scope
        {
            //enter body scope
            if (true){ //enter if scope
                for (;;) //enter for init scope
                    //enter for body scope
                    while (true) //enter while scope
                        return true; //leave 6 scopes
                        //leave 
            }
            else{ //enter else scope
                return false; //leave 3 scopes
            }
            return false; //leave 2 scopes
        }
        """, 7, [2, 3, 6]),
        ])
    def test_enter_as_many_scopes_as_we_leave(self, source, scope_enter_count, scope_leave_counts):
        main = """
        i32 main(){
            return 0;
        }
        """
        mod = self.generate_module(source)
        ir_code = self.get_function_ir(mod, 'f')
        assert ir_code.count(f'call void @{FUNC_GC_ENTER_SCOPE}') == scope_enter_count
        for leave_count in scope_leave_counts:
            assert f'call void @{FUNC_GC_LEAVE_SCOPE}(i64 {leave_count})' in ir_code

class TestCodeGeneratorLoopWithoutBraces(CodeGenTestCase):
    """Test for-loops written without braces for a single statement body."""

    def test_single_statement_for_loop(self):
        source = "i32 main() { i32 sum = 0; for (i32 j = 0; j < 5; j++) sum = sum + j; return sum; }"
        # Expected: 0+1+2+3+4 = 10
        expected = 10
        result = self.compile_and_run_main(source)
        assert result == expected


class TestCodeGeneratorComplexProgram(CodeGenTestCase):
    """Combine classes, loops, and recursion into a single complex program."""

    def test_complex_program(self):
        source = """
        class Accumulator {
            i32 sum = 0;
            void add(i32 x) {
                this.sum = this.sum + x;
            }
            i32 get() {
                return this.sum;
            }
        }
        i32 factorial(i32 n) {
            if (n <= 1)
                return 1;
            return n * factorial(n - 1);
        }
        i32 main(){
            Accumulator acc = new Accumulator();
            for (i32 i = 1; i <= 4; i = i + 1)
                acc.add(i);
            i32 s = acc.get();
            return factorial(s);
        }
        """
        # Sum from 1 to 4 = 10; 10! = 3628800
        sum_tot = sum(range(1,5))
        expected = math.factorial(sum_tot)
        result = self.compile_and_run_main(source)
        assert result == expected


class TestCodeGeneratorVariableScope(CodeGenTestCase):
    """Test variable scoping rules and shadowing in nested blocks."""

    def test_loop_variable_scope(self):
        source = """
        i32 main(){
            i32 sum = 0;
            for (i32 i = 0; i < 3; i = i + 1) {
                i32 temp = i;
                sum = sum + temp;
            }
            return sum;
        }
        """
        # Expected: 0 + 1 + 2 = 3
        expected = 3
        result = self.compile_and_run_main(source)
        assert result == expected


class TestCodeGeneratorComplexMethodChaining(CodeGenTestCase):
    """Test method chaining in classes with multiple operations."""

    def test_complex_method_chaining(self):
        source = """
        class Builder {
            i32 value = 0;
            
            Builder add(i32 x) {
                this.value = this.value + x;
                return this;
            }
            Builder mul(i32 x) {
                this.value = this.value * x;
                return this;
            }
        }
        i32 main(){
            Builder b = new Builder();
            b.add(2).mul(3).add(4);
            return b.value;
        }
        """
        # Calculation: ((0+2)*3)+4 = 10
        expected = 10
        result = self.compile_and_run_main(source)
        assert result == expected


class TestCodeGeneratorOperatorPrecedence(CodeGenTestCase):
    """Test that arithmetic operator precedence is correctly implemented."""

    def test_operator_precedence(self):
        source = """
        i32 main(){
            i32 a = 5 + 3 * 2 - 4 / 2;
            return a;
        }
        """
        # 5 + (3*2)=11, 4/2=2, 11-2=9
        expected = 9
        result = self.compile_and_run_main(source)
        assert result == expected


class TestCodeGeneratorMultipleStatements(CodeGenTestCase):
    """Test multiple statements written on a single line."""

    def test_multiple_statements_on_one_line(self):
        source = "i32 main() { i32 a = 10; i32 b = 20; return a + b; }"
        expected = 30
        result = self.compile_and_run_main(source)
        assert result == expected


class TestCodeGeneratorLargeLoop(CodeGenTestCase):
    """Test a larger loop to sum a series of numbers."""

    def test_large_loop_sum(self):
        source = """
        i32 main(){
            i32 sum = 0;
            for (i32 i = 1; i < 100; i = i + 1)
                sum = sum + i;
            return sum;
        }
        """
        expected = sum(range(1,100))
        result = self.compile_and_run_main(source)
        assert result == expected


class TestCodeGeneratorComments(CodeGenTestCase):
    """Test that both single-line and multi-line comments are correctly ignored."""

    def test_comments_handling(self):
        source = """
        i32 main(){
            // This is a single line comment
            /* This is a multi-line comment */
            i32 x = 10; // Comment after code
            return x;
        }
        """
        expected = 10
        result = self.compile_and_run_main(source)
        assert result == expected

class DebugSymbolTestCase:
    """Base class for debug symbol tests"""
    
    def setup_method(self):
        self.generator = CodeGen()
    
    def compile_to_llvm_ir(self, source, filename='/tmp/test.cs'):
        """Helper to compile source to LLVM IR with debug symbols enabled"""
        with TemporaryDirectory() as tmpdir:
            outfile = str(Path(tmpdir, 'outfile.ll'))
            compile_opts = CompilationOptions(add_debug_symbols=True)
            outfile = self.generator.compile_module(
                Path(filename),
                StringIO(source),
                emit_format=OutputFormat.IntermediateRepresentation,
                output_file=outfile,
                llvm_version=LLVM_Version.v15,
                compiler_opts=compile_opts
            )
            with open(outfile, 'rt') as ir:
                return ir.read()
    
    def assert_debug_info_present(self, ir_code):
        """Check that basic debug info sections are present"""
        assert "!llvm.dbg.cu" in ir_code, "Debug compilation unit missing"
        assert "DICompileUnit" in ir_code, "DICompileUnit missing"
        assert "!DIFile" in ir_code, "DIFile missing"
    
    def assert_local_variable_debug_info(self, ir_code, var_name):
        """Check if debug info for a specific variable exists"""
        var_pattern = re.compile(r"!DILocalVariable\(.*name\s*:\s*\"" + var_name + r"\"")
        assert var_pattern.search(ir_code), f"Debug info for variable '{var_name}' not found"
    
    def assert_global_variable_debug_info(self, ir_code, var_name):
        """Check if debug info for a specific variable exists"""
        var_pattern = re.compile(r"!DIGlobalVariable\(.*name\s*:\s*\"" + var_name + r"\"")
        assert var_pattern.search(ir_code), f"Debug info for variable '{var_name}' not found"
    
    def assert_function_debug_info(self, ir_code, func_name):
        """Check if debug info for a specific function exists"""
        func_pattern = re.compile(r"!DISubprogram\(.*name\s*:\s*\"" + func_name + r"\"")
        assert func_pattern.search(ir_code), f"Debug info for function '{func_name}' not found"
    
    def assert_debug_location(self, ir_code, line_num):
        """Check if debug info for a specific line number exists"""
        loc_pattern = re.compile(r"!DILocation\(line:\s*" + str(line_num))
        assert loc_pattern.search(ir_code), f"Debug location for line {line_num} not found"
    
    def assert_type_debug_info(self, ir_code, type_name):
        """Check if debug info for a specific type exists"""
        type_pattern = re.compile(r"!DIBasicType\(.*name\s*:\s*\"" + type_name + r"\"")
        assert type_pattern.search(ir_code), f"Debug info for type '{type_name}' not found"
    
    def assert_class_debug_info(self, ir_code, class_name):
        """Check if debug info for a specific class exists"""
        class_pattern = re.compile(r"!DICompositeType\(.*name\s*:\s*\"" + class_name + r"\"")
        assert class_pattern.search(ir_code), f"Debug info for class '{class_name}' not found"


class TestBasicDebugSymbols(DebugSymbolTestCase):
    """Test basic debug symbols generation"""

    def test_debug_info_present(self):
        """Test that basic debug info sections are present"""
        source = "i32 x = 42;"
        ir_code = self.compile_to_llvm_ir(source)
        self.assert_debug_info_present(ir_code)
    
    def test_file_info_present(self):
        """Test that source file information is correctly included"""
        source = "i32 x = 42;"
        filename = "/path/to/test_file.cs"
        ir_code = self.compile_to_llvm_ir(source, filename)
        
        # Check for file path in debug info
        file_pattern = re.compile(r"!DIFile\(.*filename\s*:\s*\"[^\"]*test_file.cs\"")
        assert file_pattern.search(ir_code), "Source file info not found in debug info"

    @pytest.mark.parametrize("var_type, var_name, value", [
        ("i32", "intVar", "42"),
        ("f64", "doubleVar", "3.14159"),
        ("bool", "boolVar", "true"),
        ("char", "charVar", "'a'"),
        ("string", "stringVar", "\"hello world\"")
    ])
    def test_variable_debug_info(self, var_type, var_name, value):
        """Test debug info for different types of variable declarations"""
        source = f"i32 main(){{ {var_type} {var_name} = {value}; return 0;}}"
        ir_code = self.compile_to_llvm_ir(source)
        
        self.assert_local_variable_debug_info(ir_code, var_name)
        if var_type != "string":  # Basic types should have type info
            self.assert_type_debug_info(ir_code, var_type)


class TestFunctionDebugSymbols(DebugSymbolTestCase):
    """Test debug symbols for functions"""

    def test_function_declaration_debug_info(self):
        """Test debug info for function declarations"""
        source = """
        i32 addNumbers(i32 a, i32 b) {
            return a + b;
        }
        """
        ir_code = self.compile_to_llvm_ir(source)
        
        self.assert_function_debug_info(ir_code, "addNumbers")
        self.assert_local_variable_debug_info(ir_code, "a")
        self.assert_local_variable_debug_info(ir_code, "b")
    
    def test_empty_function_debug_info(self):
        """Test debug info for empty function"""
        source = """
        void emptyFunc() {
            // Empty function
        }
        """
        ir_code = self.compile_to_llvm_ir(source)
        
        self.assert_function_debug_info(ir_code, "emptyFunc")
    
    def test_recursive_function_debug_info(self):
        """Test debug info for recursive function"""
        source = """
        i32 factorial(i32 n) {
            if (n <= 1) {
                return 1;
            }
            return n * factorial(n - 1);
        }
        """
        ir_code = self.compile_to_llvm_ir(source)
        
        self.assert_function_debug_info(ir_code, "factorial")
        self.assert_local_variable_debug_info(ir_code, "n")
    
    def test_nested_function_calls_debug_info(self):
        """Test debug info for nested function calls"""
        source = """
        i32 add(i32 a, i32 b) {
            return a + b;
        }
        
        i32 multiply(i32 a, i32 b) {
            return a * b;
        }
        
        i32 compute(i32 x, i32 y) {
            return multiply(add(x, 1), add(y, 2));
        }
        """
        ir_code = self.compile_to_llvm_ir(source)
        
        self.assert_function_debug_info(ir_code, "add")
        self.assert_function_debug_info(ir_code, "multiply")
        self.assert_function_debug_info(ir_code, "compute")


class TestControlFlowDebugSymbols(DebugSymbolTestCase):
    """Test debug symbols for control flow structures"""

    def test_if_else_debug_info(self):
        """Test debug info for if-else statements"""
        source = """
        i32 max(i32 a, i32 b) {
            if (a > b) {
                return a;
            } else {
                return b;
            }
        }
        """
        ir_code = self.compile_to_llvm_ir(source)
        
        self.assert_function_debug_info(ir_code, "max")
        # Check for debug locations at the appropriate lines
        self.assert_debug_location(ir_code, 3)  # if condition
        self.assert_debug_location(ir_code, 4)  # return a
        self.assert_debug_location(ir_code, 6)  # return b
    
    def test_for_loop_debug_info(self):
        """Test debug info for for loops"""
        source = """
        i32 sumRange(i32 n) {
            i32 sum = 0;
            for (i32 i = 1; i <= n; i = i + 1) {
                sum = sum + i;
            }
            return sum;
        }
        """
        ir_code = self.compile_to_llvm_ir(source)
        
        self.assert_function_debug_info(ir_code, "sumRange")
        self.assert_local_variable_debug_info(ir_code, "sum")
        self.assert_local_variable_debug_info(ir_code, "i")
        # Check for debug locations
        self.assert_debug_location(ir_code, 3)  # sum initialization
        self.assert_debug_location(ir_code, 4)  # for loop
        self.assert_debug_location(ir_code, 5)  # sum = sum + i
    
    def test_while_loop_debug_info(self):
        """Test debug info for while loops"""
        source = """
        i32 countDown(i32 start) {
            i32 count = 0;
            while (start > 0) {
                start = start - 1;
                count = count + 1;
            }
            return count;
        }
        """
        ir_code = self.compile_to_llvm_ir(source)
        
        self.assert_function_debug_info(ir_code, "countDown")
        self.assert_local_variable_debug_info(ir_code, "count")
        # Check for debug locations
        self.assert_debug_location(ir_code, 3)  # count initialization
        self.assert_debug_location(ir_code, 4)  # while condition
        self.assert_debug_location(ir_code, 5)  # start = start - 1
    
    def test_nested_control_flow_debug_info(self):
        """Test debug info for nested control structures"""
        source = """
        i32 complexFunction(i32 n) {
            i32 result = 0;
            
            for (i32 i = 0; i < n; i = i + 1) {
                if (i % 2 == 0) {
                    result = result + i;
                } else {
                    while (i > 0 && i % 3 != 0) {
                        i = i - 1;
                        result = result + 1;
                    }
                }
            }
            
            return result;
        }
        """
        ir_code = self.compile_to_llvm_ir(source)
        
        self.assert_function_debug_info(ir_code, "complexFunction")
        self.assert_local_variable_debug_info(ir_code, "result")
        self.assert_local_variable_debug_info(ir_code, "i")


class TestClassDebugSymbols(DebugSymbolTestCase):
    """Test debug symbols for classes and methods"""

    def test_class_debug_info(self):
        """Test debug info for class declaration"""
        source = """
        class Rectangle {
            i32 width;
            i32 height;
        }
        Rectangle r = new Rectangle();
        """
        ir_code = self.compile_to_llvm_ir(source)
        
        self.assert_class_debug_info(ir_code, "Rectangle")
    
    def test_class_fields_debug_info(self):
        """Test debug info for class fields"""
        source = """
        class Person {
            string name;
            i32 age;
            bool isStudent;
        }
        Person p = new Person();
        """
        ir_code = self.compile_to_llvm_ir(source)
        
        self.assert_class_debug_info(ir_code, "Person")
        
        # Check for field debug info within class scope
        field_pattern = re.compile(r"!DIDerivedType\(tag: DW_TAG_member, name: \"(name|age|isStudent)\"")
        matches = field_pattern.findall(ir_code)
        
        assert "name" in matches, "Debug info for field 'name' not found"
        assert "age" in matches, "Debug info for field 'age' not found"
        assert "isStudent" in matches, "Debug info for field 'isStudent' not found"
    
    def test_class_methods_debug_info(self):
        """Test debug info for class methods"""
        source = """
        class Calculator {
            i32 add(i32 a, i32 b) {
                return a + b;
            }
            
            i32 subtract(i32 a, i32 b) {
                return a - b;
            }
        }
        Calculator c = new Calculator();
        """
        ir_code = self.compile_to_llvm_ir(source)
        
        self.assert_class_debug_info(ir_code, "Calculator")
        self.assert_function_debug_info(ir_code, "__Calculator.__add")
        self.assert_function_debug_info(ir_code, "__Calculator.__subtract")
    
    def test_class_instance_debug_info(self):
        """Test debug info for class instantiation and method calls"""
        source = """
        class Counter {
            i32 value = 0;
            
            void increment() {
                this.value = this.value + 1;
            }
            
            i32 getValue() {
                return this.value;
            }
        }
        
        i32 main() {
            Counter c = new Counter();
            c.increment();
            return c.getValue();
        }
        """
        ir_code = self.compile_to_llvm_ir(source)
        
        self.assert_class_debug_info(ir_code, "Counter")
        self.assert_function_debug_info(ir_code, "__Counter.__increment")
        self.assert_function_debug_info(ir_code, "__Counter.__getValue")
        self.assert_function_debug_info(ir_code, "main")
        
        # Check for variable 'c' in main function
        self.assert_local_variable_debug_info(ir_code, "c")


class TestArrayDebugSymbols(DebugSymbolTestCase):
    """Test debug symbols for arrays"""

    def test_array_declaration_debug_info(self):
        """Test debug info for array declarations"""
        source = """
        i32 main() {
            i32[] numbers = new i32[10];
            return 0;
        }
        """
        ir_code = self.compile_to_llvm_ir(source)
        
        self.assert_function_debug_info(ir_code, "main")
        self.assert_local_variable_debug_info(ir_code, "numbers")
    
    def test_multidimensional_array_debug_info(self):
        """Test debug info for multidimensional arrays"""
        source = """
        i32 main() {
            i32[][] matrix = new i32[3][];
            for (i32 i = 0; i < 3; i = i + 1) {
                matrix[i] = new i32[4];
            }
            return 0;
        }
        """
        ir_code = self.compile_to_llvm_ir(source)
        
        self.assert_function_debug_info(ir_code, "main")
        self.assert_local_variable_debug_info(ir_code, "matrix")
        self.assert_local_variable_debug_info(ir_code, "i")
    
    def test_array_access_debug_info(self):
        """Test debug info for array access operations"""
        source = """
        i32 sumArray(i32[] arr) {
            i32 sum = 0;
            for (i32 i = 0; i < arr.Length; i = i + 1) {
                sum = sum + arr[i];
            }
            return sum;
        }
        """
        ir_code = self.compile_to_llvm_ir(source)
        
        self.assert_function_debug_info(ir_code, "sumArray")
        self.assert_local_variable_debug_info(ir_code, "arr")
        self.assert_local_variable_debug_info(ir_code, "sum")
        self.assert_local_variable_debug_info(ir_code, "i")


class TestComplexDebugSymbols(DebugSymbolTestCase):
    """Test debug symbols for complex code patterns"""

    def test_variable_scoping_debug_info(self):
        """Test debug info for variables in different scopes"""
        source = """
        i32 calculateScoped(i32 value) {
            i32 result = 0;
            
            // Outer scope
            {
                i32 temp = value * 2;
                result = temp;
                
                // Inner scope
                {
                    i32 temp = value + 10;  // Shadows outer temp
                    result = result + temp;
                }
            }
            
            return result;
        }
        """
        ir_code = self.compile_to_llvm_ir(source)
        
        self.assert_function_debug_info(ir_code, "calculateScoped")
        self.assert_local_variable_debug_info(ir_code, "result")
        
        # Both instances of 'temp' should have debug info, potentially with different DILocalVariable entries
        # This is just a basic check - might need refinement based on how scoping is implemented
        temp_vars = re.findall(r"!DILocalVariable\(.*name\s*:\s*\"temp\"", ir_code)
        assert len(temp_vars) >= 1, "Debug info for 'temp' variable(s) not found"
    
    def test_complex_expression_debug_info(self):
        """Test debug info for complex expressions"""
        source = """
        i32 evaluate() {
            i32 a = 5;
            i32 b = 10;
            i32 c = 15;
            
            i32 result = a + b * c / (a + 1) - b;
            
            return result;
        }
        """
        ir_code = self.compile_to_llvm_ir(source)
        
        self.assert_function_debug_info(ir_code, "evaluate")
        self.assert_local_variable_debug_info(ir_code, "a")
        self.assert_local_variable_debug_info(ir_code, "b")
        self.assert_local_variable_debug_info(ir_code, "c")
        self.assert_local_variable_debug_info(ir_code, "result")
    
    def test_method_chaining_debug_info(self):
        """Test debug info for method chaining"""
        source = """
        class Builder {
            i32 value = 0;
            
            Builder add(i32 x) {
                this.value = this.value + x;
                return this;
            }
            
            Builder multiply(i32 x) {
                this.value = this.value * x;
                return this;
            }
            
            i32 getValue() {
                return this.value;
            }
        }
        
        i32 main() {
            Builder b = new Builder();
            i32 result = b.add(5).multiply(2).add(3).getValue();
            return result;
        }
        """
        ir_code = self.compile_to_llvm_ir(source)
        
        self.assert_class_debug_info(ir_code, "Builder")
        self.assert_function_debug_info(ir_code, "__Builder.__add")
        self.assert_function_debug_info(ir_code, "__Builder.__multiply")
        self.assert_function_debug_info(ir_code, "__Builder.__getValue")
        self.assert_function_debug_info(ir_code, "main")
        self.assert_local_variable_debug_info(ir_code, "result")


class TestEdgeCaseDebugSymbols(DebugSymbolTestCase):
    """Test debug symbols for edge cases"""

    def test_empty_main_debug_info(self):
        """Test debug info for empty main function"""
        source = """
        i32 main() {
            return 0;
        }
        """
        ir_code = self.compile_to_llvm_ir(source)
        
        self.assert_function_debug_info(ir_code, "main")
        self.assert_debug_location(ir_code, 3)  # return statement
    
    def test_one_line_function_debug_info(self):
        """Test debug info for one-line function"""
        source = "i32 getValue() { return 42; }"
        ir_code = self.compile_to_llvm_ir(source)
        
        self.assert_function_debug_info(ir_code, "getValue")
        # Line number might be 1, depending on how lines are counted
        self.assert_debug_location(ir_code, 1)
    
    def test_unused_variables_debug_info(self):
        """Test debug info for unused variables"""
        source = """
        void unusedVars() {
            i32 unused1 = 10;
            string unused2 = "hello";
            bool unused3 = true;
        }
        """
        ir_code = self.compile_to_llvm_ir(source)
        
        self.assert_function_debug_info(ir_code, "unusedVars")
        self.assert_local_variable_debug_info(ir_code, "unused1")
        self.assert_local_variable_debug_info(ir_code, "unused2")
        self.assert_local_variable_debug_info(ir_code, "unused3")
    
    def test_shadowing_variable_debug_info(self):
        """Test debug info for shadowing variables"""
        source = """
        i32 shadowTest() {
            i32 x = 10;
            
            {
                i32 x = 20;  // Shadows outer x
                x = x + 5;
            }
            
            return x;  // Should be 10
        }
        """
        ir_code = self.compile_to_llvm_ir(source)
        
        self.assert_function_debug_info(ir_code, "shadowTest")
        
        # Both instances of 'x' should have debug info
        x_vars = re.findall(r"!DILocalVariable\(.*name\s*:\s*\"x\"", ir_code)
        assert len(x_vars) >= 1, "Debug info for 'x' variable(s) not found"


class TestLargeSourceDebugSymbols(DebugSymbolTestCase):
    """Test debug symbols with larger source files"""
    
    def test_large_function_debug_info(self):
        """Test debug info for a function with many statements"""
        # Create a large function with many statements
        statements = ["i32 x{0} = {0};".format(i) for i in range(1, 101)]
        function_body = "\n        ".join(statements)
        
        source = f"""
        void largeFunction() {{
        {function_body}
        }}
        """
        
        ir_code = self.compile_to_llvm_ir(source)
        
        self.assert_function_debug_info(ir_code, "largeFunction")
        
        # Check a sample of variables
        self.assert_local_variable_debug_info(ir_code, "x1")
        self.assert_local_variable_debug_info(ir_code, "x50")
        self.assert_local_variable_debug_info(ir_code, "x100")
    
    def test_many_functions_debug_info(self):
        """Test debug info with many functions in one file"""
        # Create many small functions
        functions = []
        for i in range(1, 21):
            functions.append(f"""
        i32 func{i}() {{
            return {i};
        }}
        """)
        
        source = "".join(functions)
        ir_code = self.compile_to_llvm_ir(source)
        
        # Check a sample of functions
        self.assert_function_debug_info(ir_code, "func1")
        self.assert_function_debug_info(ir_code, "func10")
        self.assert_function_debug_info(ir_code, "func20")
    
    def test_many_classes_debug_info(self):
        """Test debug info with many classes in one file"""
        # Create many small classes
        classes = []
        for i in range(1, 11):
            classes.append(f"""
        class Class{i} {{
            i32 field{i};
            i32 method{i}() {{
                return this.field{i};
            }}
        }}
        """)
        
        source = "".join(classes)
        ir_code = self.compile_to_llvm_ir(source)
        
        # Check a sample of classes and their methods
        self.assert_class_debug_info(ir_code, "Class1")
        self.assert_function_debug_info(ir_code, "__Class1.__method1")
        self.assert_class_debug_info(ir_code, "Class10")
        self.assert_function_debug_info(ir_code, "__Class10.__method10")


class TestCustomTypes(DebugSymbolTestCase):
    """Test debug symbols for custom types in the language"""

    def test_class_type_debug_info(self):
        """Test debug info for variables of custom class types"""
        source = """
        class Point {
            i32 x;
            i32 y;
            
            void setCoords(i32 newX, i32 newY) {
                this.x = newX;
                this.y = newY;
            }
        }
        
        void usePoint() {
            Point p = new Point();
            p.setCoords(10, 20);
        }
        """
        ir_code = self.compile_to_llvm_ir(source)
        
        self.assert_class_debug_info(ir_code, "Point")
        self.assert_function_debug_info(ir_code, "__Point.__setCoords")
        
        # Check for variable 'p' in usePoint function
        self.assert_local_variable_debug_info(ir_code, "p")
        
        # There should be a DICompositeType for Point and p should reference it
        point_type = re.search(r"!DICompositeType\(.*name\s*:\s*\"Point\".*", ir_code)
        assert point_type, "Point composite type not found"
    
    def test_array_type_debug_info(self):
        """Test debug info for array types"""
        source = """
        void useArrays() {
            i32[] intArray = new i32[5];
            string[] stringArray = new string[3];
        }
        """
        ir_code = self.compile_to_llvm_ir(source)
        
        self.assert_function_debug_info(ir_code, "useArrays")
        self.assert_local_variable_debug_info(ir_code, "intArray")
        self.assert_local_variable_debug_info(ir_code, "stringArray")
        
        # There should be array type DICompositeTypes
        array_types = re.findall(r"!DICompositeType\(tag: DW_TAG_array_type", ir_code)
        assert len(array_types) >= 1, "Array composite types not found"


class TestErrorHandling(DebugSymbolTestCase):
    """Test debug symbols with potential error scenarios"""
    
    def test_unicode_characters_debug_info(self):
        """Test debug info with non-ASCII characters"""
        source = """
        i32 unicode() {
            string euroSymbol = "€";
            string emoji = "😊";
            string chineseText = "你好";
            return 0;
        }
        """
        ir_code = self.compile_to_llvm_ir(source)
        
        self.assert_function_debug_info(ir_code, "unicode")
        self.assert_local_variable_debug_info(ir_code, "euroSymbol")
        self.assert_local_variable_debug_info(ir_code, "emoji")
        self.assert_local_variable_debug_info(ir_code, "chineseText")
    
    def test_source_with_line_directives(self):
        """Test debug info when source has line directives"""
        source = """
        // This should be line 2
        #line 100
        i32 lineDirective() {
            i32 x = 42;
            return x;
        }
        """
        # Note: Your compiler might not support #line directives,
        # but this test checks how debug info handles them if they exist
        ir_code = self.compile_to_llvm_ir(source)
        
        self.assert_function_debug_info(ir_code, "lineDirective")
        
        # Check if line numbers are affected by the directive
        # This is implementation-dependent, but we can check if line info exists
        self.assert_debug_location(ir_code, 100)
