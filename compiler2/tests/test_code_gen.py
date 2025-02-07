import unittest
from io import StringIO
from llvm_transpiler import CodeGen
from llvmlite import ir, binding
from ctypes import CFUNCTYPE

class TestCodeGeneratorBasicDeclarations(unittest.TestCase):
    """Test basic variable and function declarations"""
    def setUp(self):
        self.generator = CodeGen('??', StringIO(''))

    def generate_ir(self, source: str) -> str:
        """Helper method to generate LLVM IR from source code"""
        gen = CodeGen('test.cs', StringIO(source))
        mod = gen.compile_file_to_ir()
        return str(mod)

    def test_valid_primitive_literal_declarations(self):
        """Test valid primitive type declarations"""
        test_cases = [
            "i32 x = 42;",
            "f64 pi = 3.14159;",
            "string msg = \"hello\";",
            "bool flag = true;",
            "char c = 'a';"
        ]

        for source in test_cases:
            with self.subTest(source=source):
                ir_code = self.generate_ir(source)
                self.assertIn("global", ir_code)
                self.assertIn("store", ir_code)

    def test_valid_array_declarations(self):
        """Test valid array declarations"""
        test_cases = [
            "i32[] numbers = new i32[10];",
            "string[] names = new string[5];",
            "bool[] flags = new bool[3];",
            "i32[][] matrix = new i32[3][];"
        ]

        for source in test_cases:
            with self.subTest(source=source):
                ir_code = self.generate_ir(source)
                self.assertIn("global", ir_code)
                self.assertIn("call", ir_code)

class TestCodeGeneratorFunctionDeclarations(unittest.TestCase):
    """Test function declarations and return types"""
    def setUp(self):
        self.generator = CodeGen('??', StringIO(''))

    def generate_ir(self, source: str) -> str:
        """Helper method to generate LLVM IR from source code"""
        gen = CodeGen('test.cs', StringIO(source))
        mod = gen.compile_file_to_ir()
        return str(mod)

    def test_valid_void_functions(self):
        """Test valid void function declarations"""
        test_cases = [
            """
            void empty() {
            }
            """,
            """
            void printMessage(string msg) {
                // Empty function with parameter
            }
            """
        ]

        for source in test_cases:
            with self.subTest(source=source.strip()):
                ir_code = self.generate_ir(source)
                self.assertIn("define void", ir_code)

    def test_valid_return_type_functions(self):
        """Test valid functions with return values"""
        test_cases = [
            """
            i32 add(i32 a, i32 b) {
                return a + b;
            }
            """,
            """
            f32 mul(f32 a, f32 b) {
                return a * b;
            }
            """
        ]

        for source in test_cases:
            with self.subTest(source=source.strip()):
                ir_code = self.generate_ir(source)
                self.assertIn("define", ir_code)
                self.assertIn("ret", ir_code)

class TestCodeGeneratorClassDeclarations(unittest.TestCase):
    """Test class declarations and member access"""
    def setUp(self):
        self.generator = CodeGen('??', StringIO(''))

    def generate_ir(self, source: str) -> str:
        """Helper method to generate LLVM IR from source code"""
        gen = CodeGen('test.cs', StringIO(source))
        mod = gen.compile_file_to_ir()
        return str(mod)

    def test_valid_simple_class(self):
        """Test valid simple class declaration"""
        source = """
        class Point {
            i32 x;
            i32 y;
        }
        """
        ir_code = self.generate_ir(source)
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
        ir_code = self.generate_ir(source)
        self.assertIn("%Rectangle", ir_code)
        self.assertIn("define i32", ir_code)
        self.assertIn("define void", ir_code)

class TestCodeGeneratorMethodCalls(unittest.TestCase):
    """Test method calls and method chaining"""
    def setUp(self):
        self.generator = CodeGen('??', StringIO(''))

    def generate_ir(self, source: str) -> str:
        """Helper method to generate LLVM IR from source code"""
        gen = CodeGen('test.cs', StringIO(source))
        mod = gen.compile_file_to_ir()
        return str(mod)

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
        ir_code = self.generate_ir(source)
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
        ir_code = self.generate_ir(source)
        self.assertIn("call", ir_code)
        self.assertIn("string", ir_code)

class TestCodeGeneratorArrayOperations(unittest.TestCase):
    """Test array operations and indexing"""
    def setUp(self):
        self.generator = CodeGen('??', StringIO(''))

    def generate_ir(self, source: str) -> str:
        """Helper method to generate LLVM IR from source code"""
        gen = CodeGen('test.cs', StringIO(source))
        mod = gen.compile_file_to_ir()
        return str(mod)

    def test_valid_array_indexing(self):
        """Test valid array indexing operations"""
        test_cases = [
            """
            i32[] arr = new i32[10];
            arr[0] = 42;
            i32 x = arr[5];
            """,
            """
            i32[][] matrix = new i32[3][];
            matrix[0] = new i32[3];
            matrix[0][0] = 1;
            i32 x = matrix[1][1];
            """
        ]

        for source in test_cases:
            with self.subTest(source=source.strip()):
                ir_code = self.generate_ir(source)
                self.assertIn("getelementptr", ir_code)
                self.assertIn("store", ir_code)
                self.assertIn("load", ir_code)

class TestCodeGeneratorOperators(unittest.TestCase):
    """Test operator type checking"""
    def setUp(self):
        self.generator = CodeGen('??', StringIO(''))

    def generate_ir(self, source: str) -> str:
        """Helper method to generate LLVM IR from source code"""
        gen = CodeGen('test.cs', StringIO(source))
        mod = gen.compile_file_to_ir()
        return str(mod)

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
                ir_code = self.generate_ir(source)
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
                ir_code = self.generate_ir(source)
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
                ir_code = self.generate_ir(source)
                self.assertIn("and", ir_code)
                self.assertIn("or", ir_code)
                self.assertIn("xor", ir_code)

class TestCodeGeneratorControlFlow(unittest.TestCase):
    """Test type checking in control flow statements"""
    def setUp(self):
        self.generator = CodeGen('??', StringIO(''))

    def generate_ir(self, source: str) -> str:
        """Helper method to generate LLVM IR from source code"""
        gen = CodeGen('test.cs', StringIO(source))
        mod = gen.compile_file_to_ir()
        return str(mod)

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
                ir_code = self.generate_ir(source)
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
        ir_code = self.generate_ir(source)
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
        ir_code = self.generate_ir(source)
        self.assertIn("br i1", ir_code)

class TestCodeGeneratorImplicitConversions(unittest.TestCase):
    """Test implicit type conversion rules"""
    def setUp(self):
        self.generator = CodeGen('??', StringIO(''))

    def generate_ir(self, source: str) -> str:
        """Helper method to generate LLVM IR from source code"""
        gen = CodeGen('test.cs', StringIO(source))
        mod = gen.compile_file_to_ir()
        return str(mod)

    def test_valid_integer_promotions(self):
        """Test valid integer type promotions"""
        source = """
        i8 small = (i8)42;
        i16 medium = small;  // i8 -> i16
        i32 large = medium;  // i16 -> i32
        i64 huge = large;    // i32 -> i64
        """
        ir_code = self.generate_ir(source)
        self.assertIn("zext", ir_code)

    def test_valid_float_promotions(self):
        """Test valid float type promotions"""
        source = """
        f32 single = 3.14;
        f64 double = single;  // f32 -> f64
        """
        ir_code = self.generate_ir(source)
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
                ir_code = self.generate_ir(source)
                self.assertIn("sitofp", ir_code)

class TestCodeGeneratorTypeCasting(unittest.TestCase):
    """Test explicit type casting operations"""
    def setUp(self):
        self.generator = CodeGen('??', StringIO(''))

    def generate_ir(self, source: str) -> str:
        """Helper method to generate LLVM IR from source code"""
        gen = CodeGen('test.cs', StringIO(source))
        mod = gen.compile_file_to_ir()
        return str(mod)

    def test_valid_numeric_down_casts(self):
        """Test valid numeric down casting"""
        source = """
        i64 large = 42;
        i32 medium = (i32)large;  // i64 -> i32
        i16 small = (i16)medium;  // i32 -> i16
        i8 tiny = (i8)small;      // i16 -> i8
        """
        ir_code = self.generate_ir(source)
        self.assertIn("trunc", ir_code)

    def test_valid_float_to_integer_casts(self):
        """Test valid float to integer casts"""
        source = """
        f64 double = 3.14;
        i32 int32 = (i32)double;  // f64 -> i32
        f32 single = 2.718;
        i16 int16 = (i16)single;  // f32 -> i16
        """
        ir_code = self.generate_ir(source)
        self.assertIn("fptosi", ir_code)

class TestCodeGeneratorUnaryOperations(unittest.TestCase):
    """Test type checking of unary operations"""
    def setUp(self):
        self.generator = CodeGen('??', StringIO(''))

    def generate_ir(self, source: str) -> str:
        """Helper method to generate LLVM IR from source code"""
        gen = CodeGen('test.cs', StringIO(source))
        mod = gen.compile_file_to_ir()
        return str(mod)

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
                ir_code = self.generate_ir(var_decl)
                self.assertIn("neg", ir_code)

    def test_valid_logical_not(self):
        """Test valid logical not operations"""
        test_cases = ("bool a = not true;",
                      "bool b = not (1 < 2);",
                      "bool c = not (true and false);",
                      "bool d = not not true;")
        for var_decl in test_cases:
            with self.subTest(source=var_decl):
                ir_code = self.generate_ir(var_decl)
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
                ir_code = self.generate_ir(source)
                self.assertIn("add", ir_code)
                self.assertIn("sub", ir_code)

class TestCodeGeneratorMainFunction(unittest.TestCase):
    """Test the main function execution"""
    def setUp(self):
        self.generator = CodeGen('??', StringIO(''))

    def generate_ir(self, source: str) -> str:
        """Helper method to generate LLVM IR from source code"""
        gen = CodeGen('test.cs', StringIO(source))
        mod = gen.compile_file_to_ir()
        return str(mod)

    def test_main_function_execution(self):
        """Test the execution of the main function"""
        source = """
        void main() {
            i32 x = 42;
            print(x);
        }
        """
        ir_code = self.generate_ir(source)
        self.assertIn("define void @main()", ir_code)
        self.assertIn("call void @print(i32 42)", ir_code)

        # Compile the IR code to a shared object
        llvm_ir = ir.Module(context=binding.create_module(ir_code))
        llvm_ir.verify()
        target_machine = binding.Target.from_default_triple().create_target_machine()
        obj = target_machine.emit_object(llvm_ir)

        # Load the shared object and execute the main function
        c_func = CFUNCTYPE(None)(obj.get_symbol("main"))
        c_func()
