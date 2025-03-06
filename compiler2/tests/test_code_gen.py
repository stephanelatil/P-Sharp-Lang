from unittest import TestCase
from io import StringIO
from typing import List, Type
from llvm_transpiler import CodeGen
from llvmlite import ir
from llvmlite.binding import Target, parse_assembly, create_mcjit_compiler, ModuleRef
from constants import ENTRYPOINT_FUNCTION_NAME
import ctypes

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

class CodeGenTestCase(TestCase):    
    def setUp(self):
        self.generator = CodeGen()
        self._engine = create_execution_engine()

    def generate_module(self, source: str) -> ModuleRef:
        """Helper method to generate LLVM IR from source code"""
        gen = CodeGen()
        return gen.compile_module('test.cs', StringIO(source))
    
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
        return self.run_function(ENTRYPOINT_FUNCTION_NAME, main_proto)
    
    def run_function(self, func_name:str, func_prototype_ctypes:List[Type], *args):
        """Runs a function compiled in the engine using ctypes and returns the result"""
        func_ptr = self._engine.get_function_address(func_name)

        # Run the function via ctypes
        cfunc = ctypes.CFUNCTYPE(*func_prototype_ctypes)(func_ptr)
        return cfunc(*args)

class TestCodeGeneratorBasicDeclarations(CodeGenTestCase):
    """Test basic variable and function declarations"""

    def test_valid_primitive_global_literal_declarations(self):
        """Test valid primitive type declarations"""
        test_cases = [
            ("i32 x = 42;", "x"),
            ("f64 pi = 3.14159;", "pi"),
            # "string msg = \"hello\";", #TODO strings not defined yet
            ("bool flag = true;", "flag"),
            ("char c = 'a';", "c")
        ]

        for source, var_name in test_cases:
            with self.subTest(source=source):
                module = self.generate_module(source)
                global_ir = str(module)
                main_ir = self.get_function_ir(module)
                self.assertIn(f"@{var_name} = external global", global_ir)
                self.assertIn("store", main_ir)


    def test_valid_primitive_literal_declarations(self):
        """Test valid primitive type declarations"""
        test_cases = [
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
        ]

        for source, expected_result in test_cases:
            with self.subTest(source=source):
                ret_val = self.compile_and_run_main(source)
                self.assertEqual(ret_val, expected_result)

    def test_valid_array_declarations(self):
        """Test valid array declarations"""
        test_cases = [
            # ("i32[] arr = new i32[10];", "@__PS_AllocateValueArray"),
            ("string[] arr = new string[5];", "@__PS_AllocateRefArray"),
            ("bool[] arr = new bool[3];", "@__PS_AllocateValueArray"),
            ("i32[][] arr = new i32[3][];", "@__PS_AllocateRefArray")
        ]

        for source, alloc_func in test_cases:
            with self.subTest(source=source):
                module = self.generate_module(source)
                main_code = self.get_function_ir(module)
                global_code = str(module)
                # assert array var is globally known
                self.assertIn("@arr = global { i64, [0 x", global_code)
                # assert value is initialized in main func
                self.assertIn(f"call ptr {alloc_func}", main_code)

class TestCodeGeneratorFunctionDeclarations(CodeGenTestCase):
    """Test function declarations and return types"""

    def test_valid_void_functions(self):
        """Test valid void function declarations"""
        test_cases = [
            ("""
            void empty() {
            }
            """, "empty", (None,),tuple()),
            ("""
            void printInt(i32 int) {
                // Empty function with parameter
            }
            ""","printInt", (None,ctypes.c_int32), (1,))
        ]

        for (source, f_name, proto, args) in test_cases:
            with self.subTest(source=source.strip()):
                module = self.generate_module(source)
                ir_code = self.get_function_ir(module)
                self.assertIn("define void", ir_code)
                #checks returns None
                self.compile_ir(module)
                self.assertEqual(None, self.run_function(f_name, proto, *args))
                

    def test_valid_return_type_functions(self):
        """Test valid functions with return values"""
        test_cases = [
            ("""
            i32 add(i32 a, i32 b) {
                return a + b;
            }
            """, "add",
            (ctypes.c_uint32, ctypes.c_uint32, ctypes.c_uint32),
            ((2,3),5)),
            ("""
            f32 mul(f32 a, f32 b) {
                return a * b;
            }
            """, "mul",
            (ctypes.c_float, ctypes.c_float, ctypes.c_float),
            ((2,3),6))
        ]

        for (source, f_name, proto, (args,res)) in test_cases:
            with self.subTest(source=source.strip()):
                module = self.generate_module(source)
                ir_code = self.get_function_ir(module)
                self.assertIn("define", ir_code)
                self.assertIn("ret", ir_code)
                #checks returns correct result
                self.compile_ir(module)
                self.assertEqual(res, self.run_function(f_name, proto, *args))


class TestCodeGeneratorClassDeclarations(CodeGenTestCase):
    """Test class declarations and member access"""

    def test_valid_simple_class(self):
        """Test valid simple class declaration"""
        source = """
        class Point {
            i32 x;
            i32 y;
        }
        """
        module = self.generate_module(source)
        ir_code = self.get_function_ir(module)
        self.assertIn("%Point", ir_code)
        self.assertIn("i32", ir_code)

    def test_valid_class_with_methods(self):
        """Test valid class with method declarations"""
        source = """
        class Rectangle {
            i32 width;
            i32 height;

            i32 getArea() {
                return this.width * this.height;
            }

            void setSize(i32 w, i32 h) {
                this.width = w;
                this.height = h;
            }
        }
        """
        module = self.generate_module(source)
        ir_code = self.get_function_ir(module)
        self.assertIn("%Rectangle", ir_code)
        self.assertIn("define i32", ir_code)
        self.assertIn("define void", ir_code)

class TestCodeGeneratorMethodCalls(CodeGenTestCase):
    """Test method calls and method chaining"""

    def test_valid_simple_method_calls(self):
        """Test valid simple method calls"""
        source = """
        class Calculator {
            i32 add(i32 a, i32 b) {
                return a + b;
            }
        }

        Calculator calc = new Calculator();
        i32 result = calc.add(5, 3);
        """
        module = self.generate_module(source)
        ir_code = self.get_function_ir(module)
        self.assertIn("call", ir_code)
        self.assertIn("i32", ir_code)

    def test_valid_method_chaining(self):
        """Test valid method chaining"""
        source = """
        class StringBuilder {
            string value;

            StringBuilder append(string text) {
                this.value = this.value + text;
                return this;
            }

            string ToString() {
                return this.value;
            }
        }

        StringBuilder builder = new StringBuilder();
        string result = builder.append("Hello").append(" ").append("World").ToString();
        """
        module = self.generate_module(source)
        ir_code = self.get_function_ir(module)
        self.assertIn("call", ir_code)
        self.assertIn("string", ir_code)

class TestCodeGeneratorArrayOperations(CodeGenTestCase):
    """Test array operations and indexing"""

    def test_valid_array_indexing(self):
        """Test valid array indexing operations"""
        test_cases = [
            ("""
            i32 main() {
                i32[] arr = new i32[10];
                arr[0] = 42;
                i32 x = arr[5];
                return x;
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
            """,1)
        ]

        for source, expected_result in test_cases:
            with self.subTest(source=source.strip()):
                module = self.generate_module(source)
                ir_code = self.get_function_ir(module)
                self.assertIn("getelementptr", ir_code)
                self.assertIn("store", ir_code)
                self.assertIn("load", ir_code)
                result = self.run_function('main', [ctypes.c_int32])
                self.assertEqual(result, expected_result)

class TestCodeGeneratorOperators(CodeGenTestCase):
    """Test operator type checking"""

    def test_valid_arithmetic_operators(self):
        """Test valid arithmetic operators"""
        test_cases = [
            "i32 a = 1 + 2;",
            "i32 b = 3 - 4;",
            "i32 c = 5 * 6;",
            "i32 d = 8 / 2;",
            "i32 e = 10 % 3;"
        ]
        for source in test_cases:
            with self.subTest(source=source):
                module = self.generate_module(source)
                ir_code = self.get_function_ir(module)
                self.assertIn("add", ir_code)
                self.assertIn("sub", ir_code)
                self.assertIn("mul", ir_code)
                self.assertIn("sdiv", ir_code)
                self.assertIn("srem", ir_code)

    def test_valid_comparison_operators(self):
        """Test valid comparison operators"""
        test_cases = [
            "bool a = 1 < 2;",
            "bool b = 3 > 4;",
            "bool c = 5 <= 6;",
            "bool d = 7 >= 8;",
            "bool e = 9 == 10;",
            "bool f = 11 != 12;"
        ]
        for source in test_cases:
            with self.subTest(source=source):
                module = self.generate_module(source)
                ir_code = self.get_function_ir(module)
                self.assertIn("icmp", ir_code)

    def test_valid_logical_operators(self):
        """Test valid logical operators"""
        test_cases = [
            "bool a = true and false;",
            "bool b = true or false;",
            "bool c = not true;"
        ]
        for source in test_cases:
            with self.subTest(source=source):
                module = self.generate_module(source)
                ir_code = self.get_function_ir(module)
                self.assertIn("and", ir_code)
                self.assertIn("or", ir_code)
                self.assertIn("xor", ir_code)

class TestCodeGeneratorControlFlow(CodeGenTestCase):
    """Test type checking in control flow statements"""

    def test_valid_if_conditions(self):
        """Test valid if statement conditions"""
        test_cases = [
            """
            if (true) {
                i32 x = 1;
            }
            """,
            """
            if (1 < 2) {
                i32 y = 2;
            }
            """,
            """
            if (not false) {
                i32 z = 3;
            }"""]
        for source in test_cases:
            with self.subTest(source=source):
                module = self.generate_module(source)
                ir_code = self.get_function_ir(module)
                self.assertIn("br i1", ir_code)

    def test_valid_while_conditions(self):
        """Test valid while loop conditions"""
        source = """
            while (true) {
                i32 x = 1;
            }
            i32 i = 0;
            while (i < 10) {
                i = i + 1;
            }
        """
        module = self.generate_module(source)
        ir_code = self.get_function_ir(module)
        self.assertIn("br i1", ir_code)

    def test_valid_for_components(self):
        """Test valid for loop components"""
        source = """
            for (i32 i = 0; i < 10; i = i + 1) {
                i32 x = i;
            }
            for (i32 j = 10; j > 0; j = j - 1) {
                i32 y = j;
            }
            for (;;){}
        """
        module = self.generate_module(source)
        ir_code = self.get_function_ir(module)
        self.assertIn("br i1", ir_code)

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
        ir_code = self.get_function_ir(module)
        self.assertIn("sext", ir_code)

    def test_valid_float_promotions(self):
        """Test valid float type promotions"""
        source = """
        f32 single = 3.14;
        f64 double = single;  // f32 -> f64
        """
        module = self.generate_module(source)
        ir_code = self.get_function_ir(module)
        self.assertIn("fpext", ir_code)

    def test_valid_integer_to_float_conversions(self):
        """Test valid integer to float conversions"""
        test_cases = [
            "f32 float32 = (i8) 123;    // i8 -> f32",
            "f32 another = (i16) 123;    // i16 -> f32",
            "f64 float64 = (i32) 123;    // i32 -> f64"
        ]
        for source in test_cases:
            with self.subTest(source=source):
                module = self.generate_module(source)
                ir_code = self.get_function_ir(module)
                self.assertIn("sitofp", ir_code)

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
        ir_code = self.get_function_ir(module)
        self.assertIn("trunc", ir_code)

    def test_valid_float_to_integer_casts(self):
        """Test valid float to integer casts"""
        test_cases = [
            """
            f64 double = 3.14; 
            i32 int32 = (i32)double;  // f64 -> i32
            """,
            """
            f32 single = 2.718;
            i16 int16 = (i16)single;  // f32 -> i16
            """]
        for source in test_cases:
            with self.subTest(source=source):
                module = self.generate_module(source)
                ir_code = self.get_function_ir(module)
                self.assertIn("fptosi", ir_code)

class TestCodeGeneratorUnaryOperations(CodeGenTestCase):
    """Test type checking of unary operations"""

    def test_valid_numeric_negation(self):
        """Test valid numeric negation"""
        test_cases = (
            "i32 a = -42;",
            "f64 b = -3.14;",
            "i32 c = -(1 + 2);",
            "f32 d = -(2.0 * 3.0);"
        )
        for var_decl in test_cases:
            with self.subTest(source=var_decl):
                module = self.generate_module(var_decl)
                ir_code = self.get_function_ir(module)
                self.assertIn("neg", ir_code)

    def test_valid_logical_not(self):
        """Test valid logical not operations"""
        test_cases = ("bool a = not true;",
                      "bool b = not (1 < 2);",
                      "bool c = not (true and false);",
                      "bool d = not not true;")
        for var_decl in test_cases:
            with self.subTest(source=var_decl):
                module = self.generate_module(var_decl)
                ir_code = self.get_function_ir(module)
                self.assertIn("xor", ir_code)

    def test_valid_increment_decrement(self):
        """Test valid increment/decrement operations"""
        test_cases = ("i32 x = 0; x++;",
                      "i32 x = 0; ++x;",
                      "i32 x = 0; x--;",
                      "i32 x = 0; --x;",
                      "i32 x = 0; i32 y = x++;",
                      "i32 x = 0; i32 z = ++x;")
        for source in test_cases:
            with self.subTest(source=source):
                module = self.generate_module(source)
                ir_code = self.get_function_ir(module)
                self.assertIn("add", ir_code)
                self.assertIn("sub", ir_code)

class TestRuntimeExecution(CodeGenTestCase):
    """Test cases that verify correct execution results at runtime"""
    
    def test_arithmetic_operations(self):
        """Test basic arithmetic operations with runtime verification"""
        test_cases = [
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
        ]
        
        for source, expected in test_cases:
            with self.subTest(source=source):
                result = self.compile_and_run_main(source)
                self.assertEqual(result, expected)
    
    def test_variable_declarations(self):
        """Test variable declarations with runtime verification"""
        test_cases = [
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
        ]
        
        for source, expected in test_cases:
            with self.subTest(source=source):
                result = self.compile_and_run_main(source)
                self.assertEqual(result, expected)
    
    def test_condition_statements(self):
        """Test if statements with runtime verification"""
        test_cases = [
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
        ]
        
        for source, expected in test_cases:
            with self.subTest(source=source):
                result = self.compile_and_run_main(source)
                self.assertEqual(result, expected)
    
    def test_loop_statements(self):
        """Test loop statements with runtime verification"""
        test_cases = [
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
        ]
        
        for source, expected in test_cases:
            with self.subTest(source=source):
                result = self.compile_and_run_main(source)
                self.assertEqual(result, expected)
    
    def test_function_calls(self):
        """Test function calls with runtime verification"""
        test_cases = [
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
        ]
        
        for source, expected in test_cases:
            with self.subTest(source=source):
                result = self.compile_and_run_main(source)
                self.assertEqual(result, expected)
    
    def test_type_conversions(self):
        """Test type conversions with runtime verification"""
        test_cases = [
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
        ]
        
        for source, expected in test_cases:
            with self.subTest(source=source):
                result = self.compile_and_run_main(source)
                self.assertEqual(result, expected)
    
    def test_complex_expressions(self):
        """Test complex expressions with runtime verification"""
        test_cases = [
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
        ]
        
        for source, expected in test_cases:
            with self.subTest(source=source):
                result = self.compile_and_run_main(source)
                self.assertEqual(result, expected)
    
    def test_boolean_logic(self):
        """Test boolean logic with runtime verification"""
        test_cases = [
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
        ]
        
        for source, expected in test_cases:
            with self.subTest(source=source):
                result = self.compile_and_run_main(source)
                self.assertEqual(result, expected)
    
    def test_logical_short_circuit(self):
        """Test logical short-circuit behavior"""
        test_cases = [
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
        ]
        
        for source, expected in test_cases:
            with self.subTest(source=source):
                result = self.compile_and_run_main(source)
                self.assertEqual(result, expected)

    def test_char_operations(self):
        """Test character operations with runtime verification"""
        test_cases = [
            ("""i32 main() {
                char a = 'A';
                return a;
            }""", 65),  # ASCII value of 'A'
            ("""i32 main() {
                char a = 'A';
                char b = 'a';
                return b - a;
            }""", 32)  # Difference between 'a' and 'A' in ASCII
        ]
        
        for source, expected in test_cases:
            with self.subTest(source=source):
                result = self.compile_and_run_main(source)
                self.assertEqual(result, expected)
                
    def test_increment_decrement(self):
        """Test increment/decrement operations with runtime verification"""
        test_cases = [
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
        ]
        
        for source, expected in test_cases:
            with self.subTest(source=source):
                result = self.compile_and_run_main(source)
                self.assertEqual(result, expected)
