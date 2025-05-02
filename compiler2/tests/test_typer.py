import pytest
from io import StringIO
from lexer import Position, Lexeme
from parser import (PProgram, PType, PArrayType, PVariableDeclaration,
                    PExpression, PMethodCall, PCast, PClass, PClassField,
                    PBinaryOperation, PUnaryOperation, PIfStatement,
                    PWhileStatement, PForStatement, PTernaryOperation)
from typer import (Typer, TypeClass, ReferenceTyp, ArrayTyp, ValueTyp,
                  UnknownTypeError, TypingError, TypingConversionError,
                  SymbolNotFoundError, SymbolRedefinitionError, IRCompatibleTyp)

class TestTypeConversions:
    """Test type conversion logic and compatibility checks"""
    def setup_method(self):
        self.typer = Typer('test.ps', StringIO(''))

    def parse_and_type(self, source: str) -> PProgram:
        """Helper method to parse and type check source code"""
        self.typer = Typer('test.ps', StringIO(source))
        return self.typer.type_program()

    @pytest.mark.parametrize("type_",[
            PType("i8", Position.default),
            PType("i16", Position.default),
            PType("i32", Position.default),
            PType("i64", Position.default),
            PType("u8", Position.default),
            PType("u16", Position.default),
            PType("u32", Position.default),
            PType("u64", Position.default),
            PType("f16", Position.default),
            PType("f32", Position.default),
            PType("f64", Position.default),
            PType("char", Position.default)
        ])
    def test_numeric_type_detection(self, type_):
        """Test detection of numeric types"""
        assert self.typer.is_numeric_type(self.typer._type_ptype(type_))

    @pytest.mark.parametrize("type_",[
            PType("string", Position.default),
            PType("void", Position.default),
            PArrayType(PType("i32", Position.default), Position.default)
        ])
    def test_non_numeric_type_detection(self, type_):
        """Test detection of non-numeric types"""
        assert not  \
            self.typer.is_numeric_type(self.typer._type_ptype(type_))

    @pytest.mark.parametrize("from_type, to_type, expected",[
            # Same type conversions
            ("i32", "i32", True),
            ("f32", "f32", True),
            
            # Char int conversions
            ("char", "i32", True),
            ("char", "i8", False), # Char is equivalent to u8. Need explicit cast to convert
            ("char", "u8", True),
            
            # Integer width conversions
            ("i8", "i16", True),
            ("i16", "i32", True),
            ("i32", "i64", True),
            ("i16", "i8", False),  # No narrowing

            # Unsigned to signed conversions
            ("u8", "i16", True),   # Fits with extra sign bit
            ("u16", "i32", True),
            ("u8", "i8", False),   # Need extra bit for sign
            
            #signed to unsigned
            ("bool", "u8", True),
            ("i8", "u16", False), #signed to unsigned needs explicit task
            ("i16", "u64", False),
            ("i32", "u64", False),

            # Float width conversions
            ("f16", "f32", True),
            ("f32", "f64", True),
            ("f64", "f32", False), # No narrowing

            # Integer to float conversions
            ("i8", "f16", True),   # Small integers to f16
            ("i8", "f32", True),
            ("i8", "f64", True),
            ("i16", "f32", True),  # Larger integers need bigger float
            ("i32", "f64", True),
            ("i64", "f64", True),

            # Float to integer requires explicit cast
            ("f32", "i32", False),
            ("f64", "i64", False),
            
            #non numerics This should never happen but test anyways
            ("void", "i8", False),
            ("string", "i32", False)
        ])
    def test_numeric_conversions(self, from_type, to_type, expected):
        """Test numeric type conversion rules"""
        actual = self.typer.can_convert_numeric(
            self.typer.known_types[from_type],
            self.typer.known_types[to_type]
        )
        assert actual == expected

    @pytest.mark.parametrize("type1, type2, expected",[
            # Same array types
            (PArrayType(PType("i32", Position.default), Position.default), PArrayType(PType("i32", Position.default), Position.default), True),
            (PArrayType(PType("string", Position.default), Position.default), PArrayType(PType("string", Position.default), Position.default), True),

            # Different array types
            (PArrayType(PType("i32", Position.default), Position.default), PArrayType(PType("i64", Position.default), Position.default), False),
            (PArrayType(PType("i32", Position.default), Position.default), PArrayType(PType("f32", Position.default), Position.default), False),

            # Nested arrays
            (PArrayType(PArrayType(PType("i32", Position.default), Position.default), Position.default),
                PArrayType(PArrayType(PType("i32", Position.default), Position.default), Position.default), True),
            (PArrayType(PType("i32", Position.default), Position.default), 
                PArrayType(PArrayType(PType("i32", Position.default), Position.default), Position.default), False),

            # Array of custom types
            (PArrayType(PType("MyClass", Position.default), Position.default), PArrayType(PType("MyClass", Position.default), Position.default), True),
            (PArrayType(PType("MyClass", Position.default), Position.default), PArrayType(PType("OtherClass", Position.default), Position.default), False)
        ])
    def test_array_type_compatibility(self, type1, type2, expected):
        """Test array type compatibility checks"""
        self.typer.known_types["MyClass"] = ReferenceTyp("MyClass", methods={}, fields=[])
        self.typer.known_types["OtherClass"] = ReferenceTyp("OtherClass", methods={}, fields=[])
        
        actual = self.typer.check_types_match(
            self.typer._type_ptype(type1),
            self.typer._type_ptype(type2)
        )
        assert actual == expected

    @pytest.mark.parametrize("type1, type2, expected",[
            # Same type cases
            ("i32", "i32", "i32"),
            ("f32", "f32", "f32"),

            # Integer width promotion
            ("i8", "i16", "i16"),
            ("i16", "i32", "i32"),
            ("i32", "i64", "i64"),

            # Unsigned/signed mixing
            ("u8", "i8", "i16"),
            ("u16", "i16", "i32"),
            ("u32", "i32", "i64"),
            ("u64", "i32", "i64"),
            
            # Unsigned
            ("u8", "u8", "u8"),
            ("u8", "u16", "u16"),
            ("u16", "u32", "u32"),
            ("u64", "u32", "u64"),

            # Float mixing
            ("f16", "f32", "f32"),
            ("f32", "f64", "f64"),

            # Integer to float mixing
            ("i8", "f16", "f16"),    # Small int can use f16
            ("i8", "f32", "f32"),
            ("i8", "f64", "f64"),
            ("i16", "f32", "f32"),   # Larger ints need bigger floats
            ("i32", "f32", "f32"),
            ("i64", "f64", "f64"),
            
            # Boolean and Integer mixing
            ("bool", "i8", "i8"),
            ("bool", "i16", "i16"),
            ("bool", "i32", "i32"),
            ("bool", "i64", "i64"),
            ("bool", "u8", "u8"),
            ("bool", "u16", "u16"),
            ("bool", "u32", "u32"),
            ("bool", "u64", "u64"),
        ])
    def test_common_numeric_types(self, type1, type2, expected):
        """Test finding common type for numeric operations"""
        result = self.typer.get_common_type(
            self.typer.known_types[type1],
            self.typer.known_types[type2]
        )
        assert result == self.typer.known_types[expected]

    @pytest.mark.parametrize("to_type, from_type, expected",[
            # Char to 8-bit integers
            ("char", "i8", False), #chars are unsigned
            ("char", "u8", True),

            # 8-bit integers to char
            ("i8", "char", False), #char is equivalent to u8
            ("u8", "char", True),

            # Invalid conversions
            ("char", "i16", True),
            ("char", "f32", True),
            ("i16", "char", False)  #fits should be ok
        ])
    def test_character_conversion_rules(self, to_type, from_type, expected):
        """Test character conversion rules with 8-bit integers"""
        actual = self.typer.check_types_match(
            self.typer.known_types[from_type],
            self.typer.known_types[to_type])
        assert actual == expected

class TestTypeInfoHandling:
    """Test TypeInfo handling and type classification"""
    def setup_method(self):
        self.typer = Typer('test.ps', StringIO(''))

    def parse_and_type(self, source: str) -> PProgram:
        """Helper method to parse and type check source code"""
        self.typer = Typer('test.ps', StringIO(source))
        return self.typer.type_program()

    @pytest.mark.parametrize("type_name, expected_class, expected_width, expected_signed",[
            ("i8", TypeClass.INTEGER, 8, True),
            ("u8", TypeClass.INTEGER, 8, False),
            ("f32", TypeClass.FLOAT, 32, True),
            ("bool", TypeClass.BOOLEAN, 1, False),
            ("char", TypeClass.INTEGER, 8, False),
            ("string", TypeClass.STRING, 0, True),
            ("void", TypeClass.VOID, 0, True)
        ])
    def test_builtin_type_info(self, type_name, expected_class, expected_width, expected_signed):
        """Test TypeInfo for built-in types"""
        info = self.typer.get_type_info(self.typer.known_types[type_name])
        assert info.type_class == expected_class
        assert info.bit_width == expected_width
        assert info.is_signed == expected_signed
        assert info.is_builtin

    @pytest.mark.parametrize("var_decl",[
            "i32[] x;",
            "string[] x;",
            "MyClass[] x;",
            "i32[][] x;"
        ])
    def test_array_type_info(self, var_decl):
        """Test TypeInfo for array types"""
        self.typer = Typer('text.cs', StringIO(var_decl))
        self.typer.known_types["MyClass"] = ReferenceTyp("MyClass", methods={}, fields=[])
        ast = self.typer.type_program()
        assert isinstance(ast.statements[0], PVariableDeclaration)
        assert isinstance(ast.statements[0].var_type, PArrayType)
        typ_ = self.typer._type_ptype(ast.statements[0].var_type)
        info = self.typer.get_type_info(typ_)
        assert info.type_class == TypeClass.ARRAY
        assert info.bit_width == 0
        assert info.is_builtin

    @pytest.mark.parametrize("class_name",["MyClass", "AnotherClass", "DataHolder"])
    def test_custom_class_type_info(self, class_name):
        """Test TypeInfo for custom class types"""
        # Add some custom classes
        self.typer.known_types[class_name] = ReferenceTyp(class_name, methods={}, fields=[])

        info = self.typer.get_type_info(self.typer.known_types[class_name])
        assert info.type_class == TypeClass.CLASS
        assert info.bit_width == 0
        assert not info.is_builtin

class TestErrorHandling:
    """Test error handling in typer"""
    def setup_method(self):
        self.typer = Typer('test.ps', StringIO(''))

    def parse_and_type(self, source: str) -> PProgram:
        """Helper method to parse and type check source code"""
        self.typer = Typer('test.ps', StringIO(source))
        return self.typer.type_program()

    @pytest.mark.parametrize("type_name",[
            "UnknownType",
            "NonExistentClass",
            "Invalid[]"
        ])
    def test_unknown_type_error(self, type_name):
        """Test UnknownTypeError is raised for unknown types"""
        with pytest.raises(UnknownTypeError):
            self.typer._type_ptype(PType(type_name, Position.default))

    def test_typing_conversion_error(self):
        """Test TypingConversionError is raised for invalid conversions"""
        # Example: Try to convert string to int
        with pytest.raises(TypingConversionError):
            from parser import PVariableDeclaration, PLiteral
            var_decl = PVariableDeclaration(
                "x",
                PType("i32", Position.default),
                PLiteral("invalid", "string", Lexeme.default),
                Lexeme.default
            )
            self.typer._type_variable_declaration(var_decl)

    def test_typing_error(self):
        """Test TypingError is raised for invalid typing scenarios"""
        with pytest.raises(AssertionError):
            # Try to type an invalid node type
            class InvalidNode(PProgram):
                pass
            self.typer._type_statement(InvalidNode([], Lexeme.default))

class TestTyperBasicDeclarations:
    """Test basic variable and function declarations"""
    def setup_method(self):
        self.typer = Typer('test.ps', StringIO(''))

    def parse_and_type(self, source: str) -> PProgram:
        """Helper method to parse and type check source code"""
        self.typer = Typer('test.ps', StringIO(source))
        return self.typer.type_program()

    @pytest.mark.parametrize("source",[
            "i32 x = 42;",
            "f64 pi = 3.14159;",
            "string msg = \"hello\";",
            "string empty = null;",
            "bool flag = true;",
            "char c = 'a';"
        ])
    def test_valid_primitive_literal_declarations(self, source):
        """Test valid primitive type declarations"""
        self.parse_and_type(source)

    @pytest.mark.parametrize("source",[
            "_ = 1;",
            "_ = 'a';",
            """void f() {}
            _ = f();""",
        ])
    def test_valid_discard(self, source):
        """Test valid primitive type declarations"""
        self.parse_and_type(source)

    @pytest.mark.parametrize("source",[
            """bool a;
               a = false;""",
            """f32[] a;
               a = new f32[3];""",
            """i32 a;
               a = 'a';""",
        ])
    def test_valid_assignment(self, source):
        """Test valid primitive type declarations"""
        self.parse_and_type(source)

    @pytest.mark.parametrize("source",[
            """i32 a;
               a = "hello";""",
            """bool a;
               a = 'c';""",
            """f64 a;
               a = new f32[2];""",
        ])
    def test_invalid_assignment(self, source):
        """Test valid primitive type declarations"""
        with pytest.raises(TypingConversionError):
            self.parse_and_type(source)

    @pytest.mark.parametrize("source, expected_error",[
            ("i32 x = \"string\";", TypingConversionError),
            ("string s = 42;", TypingConversionError),
            ("bool b = 1;", TypingConversionError),
            ("UnknownType x = 42;", UnknownTypeError)
        ])
    def test_invalid_primitive_declarations(self, source, expected_error):
        """Test invalid primitive type declarations"""
        with pytest.raises(expected_error):
            self.parse_and_type(source)

    @pytest.mark.parametrize("source, expected_type",[
            ("i32[] numbers = new i32[10];", ArrayTyp(ValueTyp('i32'))),
            ("string[] names = new string[5];", ArrayTyp(ReferenceTyp('string'))),
            ("bool[] flags = new bool[3];", ArrayTyp(ValueTyp('bool'))),
            ("i32[][] matrix = new i32[3][];", ArrayTyp(ArrayTyp(ValueTyp('i32'))))
        ])
    def test_valid_array_declarations(self, source, expected_type):
        """Test valid array declarations"""
        prog = self.parse_and_type(source)
        var_decl = prog.statements[0]
        assert isinstance(var_decl, PVariableDeclaration)
        assert isinstance(var_decl.initial_value, PExpression)
        assert isinstance(var_decl.initial_value.expr_type, ArrayTyp)
        assert var_decl.initial_value.expr_type == expected_type

    @pytest.mark.parametrize("source, expected_error",[
            ("i32[] arr = new f32[10];", TypingConversionError),
            ("string[] arr = new i32[5];", TypingConversionError),
            ("i32[] arr = new i32[5][];", TypingConversionError),
            ("i32[][] arr = new i32[5];", TypingConversionError),
            ("UnknownType[] arr = new UnknownType[5];", UnknownTypeError),
            ("i32[] arr = new i32[2.5];", TypingError)
        ])
    def test_invalid_array_declarations(self, source, expected_error):
        """Test invalid array declarations"""
        with pytest.raises(expected_error):
            self.parse_and_type(source)

class TestTyperFunctionCall:
    """Test function declarations and return types"""
    def setup_method(self):
        self.typer = Typer('test.ps', StringIO(''))

    def parse_and_type(self, source: str) -> PProgram:
        """Helper method to parse and type check source code"""
        self.typer = Typer('test.ps', StringIO(source))
        return self.typer.type_program()
    
    @pytest.mark.parametrize("source",[
        """ 
        void f() {}
        f();
        """,
        """ 
        void f() {
            return;
        }
        f();
        """,
        """ 
        i32 f() {
            return 1;
        }
        f();
        """,
        """ 
        i32 max(i32 a, i32 b) {
            return a > b ? a : b;
        }
        max (1,3);
        """,
        ])
    def test_simple_call(self, source):
        self.parse_and_type(source)
    
    @pytest.mark.parametrize("source",[
        """ 
        i64 f() {
            return true;
        }
        f();
        """,
        """ 
        void f(f64 x1, i64 x2) {}
        f(2,3);
        """,
        ])
    def test_call_with_implicit_casting(self, source):
        self.parse_and_type(source)
                
    @pytest.mark.parametrize("source, expected_error",[
            ("""
             i32 f(i32 x) { return x; }
             f(3.1415);
             """
             ,TypingConversionError),
            ("""
             i32 max(i32 x, i32 y) { return x; }
             max(5);
             """
             ,TypingError),
            ("""
             i32 max(i32 x, i32 y) { return x; }
             max(1,2,3);
             """
             ,TypingError),
            ("""
             i32 max = 3;
             max(1,2,3);
             """
             ,TypingError)
        ])
    def test_invalid_function_calls(self, source, expected_error):
        with pytest.raises(expected_error):
            self.parse_and_type(source)

class TestTyperFunctionDeclarations:
    """Test function declarations and return types"""
    def setup_method(self):
        self.typer = Typer('test.ps', StringIO(''))

    def parse_and_type(self, source: str) -> PProgram:
        """Helper method to parse and type check source code"""
        self.typer = Typer('test.ps', StringIO(source))
        return self.typer.type_program()

    @pytest.mark.parametrize("source",[
            """
            void empty() {
            }
            """,
            """
            void printMessage(string msg) {
                // Empty function with parameter
            }
            """
        ])
    def test_valid_void_functions(self, source):
        """Test valid void function declarations"""
        self.parse_and_type(source)

    @pytest.mark.parametrize("source",[
            """
            i32 add(i32 a, i32 b) {
                return a + b;
            }
            """,
            """
            i32 ReturnTrue() {
                return true;
            }
            """,
            """
            string greet(string name) {
                return "Hello " + name;
            }
            """
        ])
    def test_valid_return_type_functions(self, source):
        """Test valid functions with return values"""
        self.parse_and_type(source)

    @pytest.mark.parametrize("source, expected_error",[
            ("""
            i32 wrong() {
                return "string";
            }
            """,TypingConversionError),
            ("""
            bool getBool() {
                return 42;
            }
            """,TypingConversionError)
        ])
    def test_invalid_return_types(self, source, expected_error):
        """Test functions with invalid return types"""
        with pytest.raises(expected_error):
            self.parse_and_type(source)

class TestTyperClassDeclarations:
    """Test class declarations and member access"""
    def setup_method(self):
        self.typer = Typer('test.ps', StringIO(''))

    def parse_and_type(self, source: str) -> PProgram:
        """Helper method to parse and type check source code"""
        self.typer = Typer('test.ps', StringIO(source))
        return self.typer.type_program()

    def test_valid_simple_class(self):
        """Test valid simple class declaration"""
        source = """
        class Point {
            i32 x;
            i32 y;
        }
        """
        self.parse_and_type(source)
        assert 'Point' in self.typer.known_types
        typ = self.typer.known_types['Point']
        assert isinstance(typ, ReferenceTyp)
        assert not isinstance(typ, ArrayTyp)
        assert typ.is_reference_type
        assert len(typ.methods) == 0
        assert len(typ.fields) == 2
        assert isinstance(typ.fields[0], PClassField)
        assert isinstance(typ.fields[1], PClassField)
        assert typ.fields[0].var_type.type_string == "i32"
        assert typ.fields[1].var_type.type_string == "i32"

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
        prog = self.parse_and_type(source)
        class_decl = prog.statements[0]
        assert isinstance(class_decl, PClass)
        assert len(class_decl.fields) == 2
        assert len(class_decl.methods) == 2
        assert class_decl.name in self.typer.known_types

    @pytest.mark.parametrize("source",[
            """
            class Invalid {
                UnknownType x;
            }
            """,
            """
            class TypeMismatch {
                i32 x = "string";
            }
            """,
            """
            class UnknownField {
                i32 x;
            }
            _ = new UnknownField().y;
            """
        ])
    def test_invalid_class_property_types(self, source):
        """Test class with invalid property types"""
        with pytest.raises((UnknownTypeError, TypingConversionError, TypingError)):
            self.parse_and_type(source)

    @pytest.mark.parametrize("source",[
            """
            void DoThis(){
                _  = this;
            }
            """,
            """
            if (false)
                _ = this;
            """
        ])
    def test_invalid_this_location(self, source):
        """Test class with invalid property types"""
        with pytest.raises(TypingError):
            self.parse_and_type(source)

class TestTyperMethodCalls:
    """Test method calls and method chaining"""
    def setup_method(self):
        self.typer = Typer('test.ps', StringIO(''))

    def parse_and_type(self, source: str) -> PProgram:
        """Helper method to parse and type check source code"""
        self.typer = Typer('test.ps', StringIO(source))
        return self.typer.type_program()

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
        prog = self.parse_and_type(source)
        last = prog.statements[-1]
        assert isinstance(last, PVariableDeclaration)
        assert last.initial_value is not None
        assert last.initial_value is not None
        method_call = last.initial_value
        assert isinstance(method_call, PMethodCall)
        assert len(method_call.arguments) == 2
        assert method_call.expr_type is not None
        assert method_call.expr_type is not None
        assert method_call.object.expr_type == self.typer.known_types['Calculator']
        assert method_call.expr_type == self.typer.known_types['i32']
        
    @pytest.mark.parametrize("source",[
            "string s = true.ToString();",
            "string s = (123).ToString();",
            "string s = (3.1415).ToString();",
            "string s = \"hello\".ToString();",
            "string s = 'a'.ToString();"
        ])
    def test_valid_to_string_calls(self, source):
        prog = self.parse_and_type(source)
        var_decl = prog.statements[0]
        assert isinstance(var_decl, PVariableDeclaration)
        assert var_decl.initial_value is not None
        method_call = var_decl.initial_value
        assert isinstance(method_call, PMethodCall)
        assert len(method_call.arguments) == 0
        assert method_call.method_name.name == 'ToString'
        assert method_call.expr_type is not None
        assert method_call.expr_type == self.typer.known_types['string']

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
        prog = self.parse_and_type(source)
        last = prog.statements[-1]
        assert isinstance(last, PVariableDeclaration)
        assert last.initial_value is not None
        assert last.initial_value is not None
        method_call = last.initial_value
        #go up the call tree
        for _ in range(4):
            assert isinstance(method_call, PMethodCall)
            assert method_call.expr_type is not None
            assert method_call.expr_type is not None
            assert method_call.object.expr_type == self.typer.known_types['StringBuilder']
            method_call = method_call.object

    @pytest.mark.parametrize("source",[
            """
            class Calculator {
                i32 add(i32 a, i32 b) {
                    return a + b;
                }
            }

            Calculator calc = new Calculator();
            i32 result = calc.add("5", 3);
            """,
            """
            class Test {
                void method() {}
            }

            Test t = new Test();
            t.unknownMethod();
            """,
            """
            class Test {
                void method() {}
            }

            Test t = new Test();
            t.method(123);
            """
        ])
    def test_invalid_method_calls(self, source):
        """Test invalid method calls"""
        with pytest.raises((TypingError, TypingConversionError)):
            self.parse_and_type(source)

class TestTyperArrayOperations:
    """Test array operations and indexing"""
    def setup_method(self):
        self.typer = Typer('test.ps', StringIO(''))

    def parse_and_type(self, source: str) -> PProgram:
        """Helper method to parse and type check source code"""
        self.typer = Typer('test.ps', StringIO(source))
        return self.typer.type_program()

    @pytest.mark.parametrize("source",[
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
            """])
    def test_valid_array_indexing(self, source):
        """Test valid array indexing operations"""
        self.parse_and_type(source)

    @pytest.mark.parametrize("source, expected_error",[
            ("""
            i32[] arr = new i32[10];
            arr["string"] = 42;
            """, TypingError),

            ("""
            i32[] arr = new i32[10];
            bool x = arr[0];
            """, TypingConversionError),

            ("""
            i32 not_arr = 123;
            _ = not_arr[0];
            """, TypingError)
        ])
    def test_invalid_array_indexing(self, source, expected_error):
        """Test invalid array indexing operations"""
        with pytest.raises(expected_error):
            self.parse_and_type(source)

class TestTyperOperators:
    """Test operator type checking"""
    def setup_method(self):
        self.typer = Typer('test.ps', StringIO(''))

    def parse_and_type(self, source: str) -> PProgram:
        """Helper method to parse and type check source code"""
        self.typer = Typer('test.ps', StringIO(source))
        return self.typer.type_program()

    @pytest.mark.parametrize("source",[
            "i32 a = true + 2;",
            "i32 b = 3 - 4;",
            "i32 c = 5 * 6;",
            "i32 d = 8 / 2;",
            "i32 e = 10 % 3;",
            "i32 f = 23 & 7;",
            "i32 g = 8 | 1;"
        ])
    def test_valid_arithmetic_operators(self, source):
        """Test valid arithmetic operators"""
        prog = self.parse_and_type(source)
        var_decl = prog.statements[0]
        assert isinstance(var_decl, PVariableDeclaration)
        assert var_decl.initial_value is not None
        assert var_decl.initial_value is not None
        assert var_decl.initial_value.expr_type == self.typer.known_types['i32']

    @pytest.mark.parametrize("source",[
            "i32 a = true ? 1 : 2;",
            "i32 b = false ? 1 : 2;",
            "i32 b = 1 == 1 ? 1 : 2;",
            "i32 b = 1 == 1 ? ('a' == 'b' ? 2 : 3) : 4;",
        ])
    def test_valid_ternary_operators(self, source):
        """Test valid arithmetic operators"""
        prog = self.parse_and_type(source)
        var_decl = prog.statements[0]
        assert isinstance(var_decl, PVariableDeclaration)
        assert var_decl.initial_value is not None
        assert var_decl.initial_value is not None
        tern = var_decl.initial_value
        assert isinstance(tern, PTernaryOperation)
        assert tern.condition.expr_type == self.typer.known_types['bool']
        assert tern.true_value.expr_type == self.typer.known_types['i32']
        assert tern.false_value.expr_type == self.typer.known_types['i32']


    @pytest.mark.parametrize("source, expected_error",[
            ("i32 x = 'a' ? 1 : 2;", TypingError),
            ("string x = false ? false : null;", TypingError),
            ("i32 x = true ? 1.23 : 123;", TypingConversionError)
        ])
    def test_invalid_ternary(self, source, expected_error):
        """Test invalid operator usage"""
        with pytest.raises(expected_error):
            self.parse_and_type(source)

    @pytest.mark.parametrize("source",[
            "bool a = 1 < 2;",
            "bool b = 3 > 4;",
            "bool c = 5 <= 6;",
            "bool d = 7 >= 8;",
            "bool e = 9 == 10;",
            "bool f = 11 != 12;",
            'bool g = "abc" <= "def";'
            'bool h = new i32[0] == new i32[0];'
        ])
    def test_valid_comparison_operators(self, source):
        """Test valid comparison operators"""
        prog = self.parse_and_type(source)
        var_decl = prog.statements[0]
        assert isinstance(var_decl, PVariableDeclaration)
        assert var_decl.initial_value is not None
        assert var_decl.initial_value is not None
        assert not isinstance(var_decl.initial_value, PCast)
        assert var_decl.initial_value.expr_type == self.typer.known_types['bool']

    @pytest.mark.parametrize("source",[
            "bool a = true and false;",
            "bool b = true or false;",
            "bool c = not true;"
        ])
    def test_valid_logical_operators(self, source):
        """Test valid logical operators"""
        prog = self.parse_and_type(source)
        var_decl = prog.statements[0]
        assert isinstance(var_decl, PVariableDeclaration)
        assert var_decl.initial_value is not None
        assert var_decl.initial_value is not None
        assert var_decl.initial_value.expr_type == self.typer.known_types['bool']
        if isinstance(var_decl.initial_value, PBinaryOperation):
            assert var_decl.initial_value.left.expr_type == self.typer.known_types['bool']
            assert var_decl.initial_value.right.expr_type == self.typer.known_types['bool']
        else:
            assert isinstance(var_decl.initial_value, PUnaryOperation)
            assert var_decl.initial_value.operand.expr_type == self.typer.known_types['bool']


    @pytest.mark.parametrize("source, expected_error",[
            ("i32 x = \"string\" + 42;", TypingError),

            ("bool x = 1 + true;", TypingConversionError),

            ("string s = \"hello\" - \"world\";", TypingError)
        ])
    def test_invalid_operators(self, source, expected_error):
        """Test invalid operator usage"""
        with pytest.raises(expected_error):
            self.parse_and_type(source)

class TestTyperControlFlow:
    """Test type checking in control flow statements"""
    def setup_method(self):
        self.typer = Typer('test.ps', StringIO(''))

    def parse_and_type(self, source: str) -> PProgram:
        """Helper method to parse and type check source code"""
        self.typer = Typer('test.ps', StringIO(source))
        return self.typer.type_program()

    @pytest.mark.parametrize("source",[
            """
            if (true) {
                i32 x = 1;
            }
            """,
            """
            if (1 < 2) {
                _ = 2;
            }
            """,
            """
            if (not false)
                i32 z = 3;"""])
    def test_valid_if_conditions(self, source):
        """Test valid if statement conditions"""
        prog = self.parse_and_type(source)
        if_statement = prog.statements[0]
        assert isinstance(if_statement, PIfStatement)
        assert if_statement.condition.expr_type == self.typer.known_types['bool']
            

    @pytest.mark.parametrize("source",["""
            while (true) {
                i32 x = 1;
            }
            """,
            """
            i32 i = 0;
            while (i < 10) {
                i = i + 1;
            }
            """,
            """
            while (true) {
                break;
            }
            """,
            """
            i32 i = 0;
            while (true) {
                if ( i < 10){
                    i++;
                    continue;
                }
                break;
            }
            """
        ])
    def test_valid_while_conditions(self, source):
        """Test valid while loop conditions"""
        prog = self.parse_and_type(source)
        for statement in prog.statements:
            if isinstance(statement, PVariableDeclaration):
                break
            assert isinstance(statement, PWhileStatement)
            assert statement.condition.expr_type == self.typer.known_types['bool']

    @pytest.mark.parametrize("source",["""
            for (i32 i = 0; i < 10; i = i + 1) {
                i32 x = i;
            }""",
            """
            for (i32 j = 10; j > 0; j = j - 1) {
                i32 y = j;
            }""",
            """
            for (;;){}
            """
        ])
    def test_valid_for_components(self, source):
        """Test valid for loop components"""
        prog = self.parse_and_type(source)
        statement = prog.statements[0]
        assert isinstance(statement, PForStatement)
        assert statement.condition.expr_type == self.typer.known_types['bool']

    @pytest.mark.parametrize("source, expected_error",[
            ("""
                if (42) {
                    i32 x = 1;
                }
            """, TypingConversionError),
            ("""
                while ("string") {
                    i32 x = 1;
                }
            """, TypingConversionError),
            ("""
                for (string s = "start"; s < 10; s = s + 1) {
                    i32 x = 1;
                }
            """, TypingError),
            ("""
                for (i32 i = 0; i++;) {
                    i32 x = 1;
                }
            """, TypingConversionError)
        ])
    def test_invalid_control_flow_conditions(self, source, expected_error):
        """Test invalid conditions in control flow statements"""
        with pytest.raises(expected_error):
            self.parse_and_type(source)

class TestTyperImplicitConversions:
    """Test implicit type conversion rules"""
    def setup_method(self):
        self.typer = Typer('test.ps', StringIO(''))

    def parse_and_type(self, source: str) -> PProgram:
        """Helper method to parse and type check source code"""
        self.typer = Typer('test.ps', StringIO(source))
        return self.typer.type_program()

    def test_valid_integer_promotions(self):
        """Test valid integer type promotions"""
        source = """
        i8 small = (i8)42;
        i16 medium = small;  // i8 -> i16
        i32 large = medium;  // i16 -> i32
        i64 huge = large;    // i32 -> i64
        """
        prog = self.parse_and_type(source)
        for statement in prog.statements:
            assert isinstance(statement, PVariableDeclaration)
            assert statement.initial_value is not None
            assert isinstance(statement.initial_value.expr_type, ValueTyp)
            assert self.typer.can_convert_numeric(statement.initial_value.expr_type,
                                                  self.typer.known_types[statement.var_type.type_string])

    def test_valid_float_promotions(self):
        """Test valid float type promotions"""
        source = """
        f32 single = 3.14;
        f64 double = single;  // f32 -> f64
        """
        prog = self.parse_and_type(source)
        for statement in prog.statements:
            assert isinstance(statement, PVariableDeclaration)
            assert statement.initial_value is not None
            assert isinstance(statement.initial_value.expr_type, ValueTyp)
            assert self.typer.can_convert_numeric(statement.initial_value.expr_type,
                                                      self.typer.known_types[statement.var_type.type_string])

    @pytest.mark.parametrize("source",[
            "f32 float32 = (i8) 123;    // i8 -> f32",
            "f32 another = (i16) 123;    // i16 -> f32",
            "f64 float64 = (i32) 123;    // i32 -> f64"
        ])
    def test_valid_integer_to_float_conversions(self, source):
        """Test valid integer to float conversions"""
        self.parse_and_type(source)

class TestTyperTypeCasting:
    """Test explicit type casting operations"""
    def setup_method(self):
        self.typer = Typer('test.ps', StringIO(''))

    def parse_and_type(self, source: str) -> PProgram:
        """Helper method to parse and type check source code"""
        self.typer = Typer('test.ps', StringIO(source))
        return self.typer.type_program()

    @pytest.mark.parametrize("source",[
        "i64 large = 42;",
        "i32 medium = (i32)((i64)12345);  // i64 -> i32",
        "i16 small = (i16)123;  // i32 -> i16",
        "i8 tiny = (i8)1;      // i16 -> i8"
        ])
    def test_valid_numeric_down_casts(self, source):
        """Test valid numeric down casting"""
        self.parse_and_type(source)
                
    @pytest.mark.parametrize("source",[
        "i64 large = 42;",
        "f64 large = 42;",
        "f32 large = 42;",
        ])
    def test_implicit_casts(self, source):
        self.parse_and_type(source)

    @pytest.mark.parametrize("source",[
        """class Test{}
        Test t = (Test) null;"""
        ])
    def test_valid_null_cast(self, source):
        """Test valid numeric down casting"""
        self.parse_and_type(source)

    @pytest.mark.parametrize("source",[
        "f64 double = 3.14; i32 int32 = (i32)double;  // f64 -> i32",
        "f32 single = 2.718; i16 int16 = (i16)single;  // f32 -> i16"
        ])
    def test_valid_float_to_integer_casts(self, source):
        """Test valid float to integer casts"""
        self.parse_and_type(source)

    @pytest.mark.parametrize("source",[
        "_ = (bool) 3.14;",
        "_ = (bool) ((f16) 12.34); ",
        "_ = (bool) 'a';", 
        "_ = (bool) \"hello\";",
        "_ = (bool) null;",
        "_ = (i32) false;",
        ])
    def test_valid_cast_to_bool(self, source):
        """Test valid float to integer casts"""
        self.parse_and_type(source)

    @pytest.mark.parametrize("source, expected_error",[
            ("""
            string str = "42";
            i32 num = (i32)str;  // Can't cast string to int
            """, TypingError),
            ("""
            i32 num = 123;  
            _ = (string) num;    // Can't cast to string
            """, TypingError),
            ("""
            bool[] flag = new bool[1];
            f64 double = (f64)flag;  // Can't cast array to float
            """, TypingError),
            ("""
            i32 value = (i32) null;  // Can't cast null to value type
            """, TypingError)
        ])
    def test_invalid_casts(self, source, expected_error):
        """Test invalid type casts"""
        with pytest.raises(expected_error):
            self.parse_and_type(source)

class TestTyperUnaryOperations:
    """Test type checking of unary operations"""
    def setup_method(self):
        self.typer = Typer('test.ps', StringIO(''))

    def parse_and_type(self, source: str) -> PProgram:
        """Helper method to parse and type check source code"""
        self.typer = Typer('test.ps', StringIO(source))
        return self.typer.type_program()

    @pytest.mark.parametrize("source, expected_type",(
            ("i32 a = -42;",'i32'),
            ("f32 b = -3.14;",'f32'),
            ("i32 c = -(1 + 2);",'i32'),
            ("f32 d = -(2.0 * 3.0);",'f32')
        ))
    def test_valid_numeric_negation(self, source, expected_type):
        """Test valid numeric negation"""
        program = self.parse_and_type(source)
        assert len(program.statements) > 0
        var_decl = program.statements[0]
        assert isinstance(var_decl, PVariableDeclaration)
        assert isinstance(var_decl.initial_value, PUnaryOperation)
        assert var_decl.initial_value.expr_type == self.typer.known_types[expected_type]
        assert var_decl.initial_value.operand.expr_type == self.typer.known_types[expected_type]

    @pytest.mark.parametrize("source",("bool a = not true;",
                      "bool b = not (1 < 2);",
                      "bool c = not (true and false);",
                      "bool d = not not true;"))
    def test_valid_logical_not(self, source):
        """Test valid logical not operations"""
        program = self.parse_and_type(source)
        assert len(program.statements) > 0
        var_decl = program.statements[0]
        assert isinstance(var_decl, PVariableDeclaration)
        assert isinstance(var_decl.initial_value, PUnaryOperation)
        assert var_decl.initial_value.expr_type == self.typer.known_types['bool']
        assert var_decl.initial_value.operand.expr_type == self.typer.known_types['bool']

    @pytest.mark.parametrize("source",("i32 x = 0; x++;",
                      "i32 x = 0; ++x;",
                      "i32 x = 0; x--;",
                      "i32 x = 0; --x;"))
    def test_valid_increment_decrement(self, source):
        """Test valid increment/decrement operations"""
        program = self.parse_and_type(source)
        assert len(program.statements) > 1
        incr = program.statements[1]
        assert isinstance(incr, PUnaryOperation)
        assert incr.expr_type == self.typer.known_types['i32']
        assert incr.operand.expr_type == self.typer.known_types['i32']

    @pytest.mark.parametrize("source",("i32 x = 0; i32 y = x++;",
                      "i32 x = 0; i32 z = ++x;"))
    def test_valid_expression_from_increment(self, source):
        program = self.parse_and_type(source)
        assert len(program.statements) > 1
        incr = program.statements[1]
        assert isinstance(incr, PVariableDeclaration)
        assert isinstance(incr.initial_value, PUnaryOperation)
        assert incr.initial_value.expr_type == self.typer.known_types['i32']
        assert incr.initial_value.operand.expr_type == self.typer.known_types['i32']

    @pytest.mark.parametrize("source, expected_error",[
            ("""
                string s = "hello";
                -s;  // Can't negate string
            """, TypingError),

            ("""
                i32[] x;
                x++;  // Can't increment array
            """, TypingError),

            ("""
                bool b = true;
                b++;  // Can't increment boolean
            """, TypingError)
        ])
    def test_invalid_unary_operations(self, source, expected_error):
        """Test invalid unary operations"""
        with pytest.raises(expected_error):
            prog = self.parse_and_type(source)

class TestTyperScopeRules:
    """Test scope rules and variable shadowing"""
    def setup_method(self):
        self.typer = Typer('test.ps', StringIO(''))

    def parse_and_type(self, source: str) -> PProgram:
        """Helper method to parse and type check source code"""
        self.typer = Typer('test.ps', StringIO(source))
        return self.typer.type_program()

    def test_valid_variable_shadowing(self):
        """Test valid variable shadowing"""
        source = """
            i32 x = 1;
            {
                i32 y = x + 1;  // Uses inner x
            }
            i32 z = x + 1;  // Uses outer x
        """
        self.parse_and_type(source)

    def test_valid_function_parameter_shadowing(self):
        """Test valid parameter shadowing"""
        source = """
        void process(i32 x) {
            i32 z = x + 1;  // Uses parameter x
        }
        """
        self.parse_and_type(source)

    @pytest.mark.parametrize("source, expected_error",[
            ("""
            {
                i32 x = 1;
            }
            i32 y = x;  // x not in scope
            """, SymbolNotFoundError),
            ("""
            void test1() {
                i32 x = 1;
            }
            void test2() {
                i32 y = x;  // x not in scope
            }
            """, SymbolNotFoundError),
            ("""
             i32 x = 1;
             i64 x = 2; // redefinition
            """, SymbolRedefinitionError),
            ("""
            i32 x = 1;
            {
                i32 x = 2; // Attempt to shadow existing var
            }
            """, SymbolRedefinitionError)
        ])
    def test_invalid_scope_access(self, source, expected_error):
        """Test invalid scope access"""
        with pytest.raises(expected_error):
            self.parse_and_type(source)

class TestTyperUsageWarnings:
    def setup_method(self):
        self.typer = Typer('test.ps', StringIO(''))

    def parse_and_type(self, source: str) -> PProgram:
        self.typer = Typer('test.ps', StringIO(source))
        return self.typer.type_program()

    def test_unused_variable_warning(self):
        source = "i32 x;"
        self.parse_and_type(source)
        assert len(self.typer.warnings) == 1
        assert "Variable 'x' is declared but never read" in str(self.typer.warnings[0])

    def test_unused_function_warning(self):
        source = "void unusedFunc() {}"
        self.parse_and_type(source)
        assert len(self.typer.warnings) == 1
        assert "Function 'unusedFunc' is declared but never called" in str(self.typer.warnings[0])

    def test_unused_class_property_warning(self):
        source = """
        class Test {
            i32 unusedProp;
        }
        """
        self.parse_and_type(source)
        assert len(self.typer.warnings) == 1
        assert "Class property 'unusedProp' is never assigned" in str(self.typer.warnings[0])

    def test_unused_class_method_warning(self):
        source = """
        class Test {
            void unusedMethod() {}
        }
        """
        self.parse_and_type(source)
        assert len(self.typer.warnings) == 1
        assert "Method 'unusedMethod' is declared but never called" in str(self.typer.warnings[0])

class TestTyperFunctionReturnPaths:
    """Test that the typer correctly checks return paths in functions."""

    def setup_method(self):
        self.typer = Typer('test.ps', StringIO(''))

    def parse_and_type(self, source: str) -> PProgram:
        """Helper method to parse and type check source code."""
        self.typer = Typer('test.ps', StringIO(source))
        return self.typer.type_program()

    @pytest.mark.parametrize("source, description",[
            (
                "i32 valid1() { return 42; }",
                "Single return statement"
            ),
            (
                "string valid2() { return \"hello\"; }",
                "Single return statement with string"
            ),
            (
                "bool valid3() { return true; }",
                "Single return statement with boolean"
            )
        ])
    def test_valid_single_return(self, source, description):
        """Test functions with a single return statement."""
        self.parse_and_type(source.strip())

    @pytest.mark.parametrize("source, description",[
            (
                """
                i32 valid1(bool b) {
                    if (b)
                        return 1;
                    else
                        return 0;
                }
                """,
                "If-else with returns in both branches"
            ),
            (
                """
                string valid2(bool b) {
                    if (b) {
                        return "true";
                    }
                    return "false";
                }
                """,
                "If with return, and return after if"
            ),
            (
                """
                i32 valid3(i32 x) {
                    if (x > 0) {
                        return x;
                    } else if (x < 0) {
                        return -x;
                    } else {
                        return 0;
                    }
                }
                """,
                "Multiple if-else branches with returns"
            )
        ])
    def test_valid_if_else_return(self, source, description):
        """Test functions with returns in all if-else branches."""
        self.parse_and_type(source.strip())

    @pytest.mark.parametrize("source, description",[
            (
                """
                i32 valid1() {
                    while (true) {
                        return 5;
                    }
                }
                """,
                "Infinite loop with return"
            ),
            (
                """
                i32 valid2(i32 x) {
                    for (i32 i = 0; i < x; i++) {
                        if (i == 5) {
                            return i;
                        }
                    }
                    return -1;
                }
                """,
                "For loop with return inside and after"
            ),
            (
                """
                i32 valid3(i32 x) {
                    while (x > 0) {
                        if (x == 5) {
                            return x;
                        }
                        x--;
                    }
                    return 0;
                }
                """,
                "While loop with return inside and after"
            )
        ])
    def test_valid_loop_return(self, source, description):
        """Test functions with returns inside loops."""
        self.parse_and_type(source.strip())

    @pytest.mark.parametrize("source, description",[
            (
                """
                void valid1() {
                    // No return needed
                }
                """,
                "Void function with no return"
            ),
            (
                """
                void valid2(bool b) {
                    if (b) {
                        return;
                    }
                    // No return needed in else branch
                }
                """,
                "Void function with optional return"
            ),
            (
                """
                void valid3() {
                    while (true) {
                        return;
                    }
                }
                """,
                "Void function with return in infinite loop"
            )
        ])
    def test_valid_void_functions(self, source, description):
        """Test void functions, which do not require explicit returns."""
        self.parse_and_type(source.strip())

    @pytest.mark.parametrize("source, description, expected_error",[
            (
                "i32 invalid1() { }",
                "Missing return statement",
                TypingError
            ),
            (
                """class A {i32 invalid1() {} }""",
                "Missing return statement in method",
                TypingError
            ),
            (
                """
                i32 invalid2(bool b) {
                    if (b) {
                        return 1;
                    }
                    // No return if b is false
                }
                """,
                "Missing return in else path",
                TypingError
            ),
            (
                """
                i32 invalid3(i32 x) {
                    while (x > 0) {
                        if (x == 5) {
                            return x;
                        }
                        x--;
                    }
                    // No return if loop exits
                }
                """,
                "Missing return after loop",
                TypingError
            ),
            (
                """
                i32 invalid4(bool b) {
                    if (b) {
                        return 1;
                    } else if (!b) {
                        // No return here
                    } else {
                        return 0;
                    }
                }
                """,
                "Missing return in nested if-else",
                TypingError
            )
        ])
    def test_invalid_missing_return(self, source, description, expected_error):
        """Test functions with missing return statements."""
        with pytest.raises(expected_error):
            self.parse_and_type(source.strip())

    @pytest.mark.parametrize("source, description, expected_error",[
            (
                """
                void invalid1() {
                    return 42;
                }
                """,
                "Void function returning a value",
                TypingConversionError
            ),
            (
                """
                void invalid2(bool b) {
                    if (b) {
                        return "string";
                    }
                }
                """,
                "Void function returning a string",
                TypingConversionError
            )
        ])
    def test_invalid_void_with_return_value(self, source, description, expected_error):
        """Test void functions that incorrectly return a value."""
        with pytest.raises(expected_error):
            self.parse_and_type(source.strip())

    @pytest.mark.parametrize("source, expected_error",[
                ("""
                i32 invalid1(bool b) {
                    if (b) {
                        return 1;
                    }
                    // No return if b is false
                }
                """,
                TypingError
            ),
            (
                """
                string invalid2(i32 x) {
                    if (x > 0) {
                        return "positive";
                    } else if (x < 0) {
                        return "negative";
                    }
                    // No return if x == 0
                }
                """,
                TypingError
            )
        ])
    def test_invalid_non_void_missing_return(self, source, expected_error):
        """Test non-void functions that are missing a return statement."""
        with pytest.raises(expected_error):
            self.parse_and_type(source.strip())
