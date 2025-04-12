import pytest
from io import StringIO
from typing import List, Type
from tempfile import TemporaryDirectory
from llvm_transpiler import CodeGen, LLVM_Version, OutputFormat
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
        gen = CodeGen(debug_symbols=True)
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
