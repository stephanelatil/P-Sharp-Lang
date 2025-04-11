from unittest import TestCase, main
from io import StringIO
from parser import (Parser, ParserError, NodeType, PProgram, PFunction, PBlock,
                   PVariableDeclaration, PAssignment, PBinaryOperation,
                   PUnaryOperation, PIfStatement, PWhileStatement, PForStatement,
                   PReturnStatement, PFunctionCall, PIdentifier, PLiteral,
                   PCast, PClassField, PMethodCall, PBreakStatement,
                   PContinueStatement, PAssertStatement, PTernaryOperation,
                   PClass, PDotAttribute, PExpression, PArrayIndexing,
                   PArrayInstantiation, PObjectInstantiation,
                   PDiscard, PArrayType, PType)
from lexer import Lexer, LexemeType
from operations import BinaryOperation, UnaryOperation
from typing import Any, Type

class TestParserBase(TestCase):
    """Base class for parser tests with common utilities."""

    def parse_source(self, source: str) -> PProgram:
        """Helper method to parse source code string."""
        parser = Parser(Lexer('test.ps', StringIO(source)))
        return parser.parse()

class TestParserUtilities(TestParserBase):
    """Test suite for Parser utility methods."""

    def setUp(self):
        """Initialize parser with empty input for each test."""
        self.parser = Parser(Lexer('test.ps', StringIO('')))

    def test_precedence_initialization_complete(self):
        """Test that all operators have correct precedence relationships."""
        precedence = self.parser.precedence

        # Test arithmetic precedence
        self.assertGreater(precedence[BinaryOperation.TIMES], precedence[BinaryOperation.PLUS])
        self.assertGreater(precedence[BinaryOperation.DIVIDE], precedence[BinaryOperation.MINUS])
        self.assertEqual(precedence[BinaryOperation.TIMES], precedence[BinaryOperation.MOD])
        self.assertEqual(precedence[BinaryOperation.TIMES], precedence[BinaryOperation.DIVIDE])

        # Test logical operator precedence
        self.assertGreater(precedence[BinaryOperation.BOOL_AND], precedence[BinaryOperation.BOOL_OR])
        self.assertGreater(precedence[BinaryOperation.LOGIC_AND], precedence[BinaryOperation.LOGIC_OR])

        # Test comparison operators
        self.assertEqual(precedence[BinaryOperation.BOOL_EQ], precedence[BinaryOperation.BOOL_NEQ])
        self.assertEqual(precedence[BinaryOperation.BOOL_GT], precedence[BinaryOperation.BOOL_LT])

        # Test bool comparators have lower precedence
        for op in (BinaryOperation.PLUS, BinaryOperation.MINUS, BinaryOperation.TIMES,
                   BinaryOperation.DIVIDE, BinaryOperation.LOGIC_AND, BinaryOperation.LOGIC_OR,
                   BinaryOperation.MOD, BinaryOperation.XOR):
            self.assertLess(precedence[BinaryOperation.BOOL_EQ], precedence[op])

        # Test assignments then bool and/or have lowest precedence
        self.assertEqual(precedence[BinaryOperation.ASSIGN], precedence[BinaryOperation.COPY])
        for op in BinaryOperation:
            if op in (BinaryOperation.ASSIGN, BinaryOperation.COPY):
                continue
            self.assertGreater(precedence[op], precedence[BinaryOperation.ASSIGN])
            if op in (BinaryOperation.BOOL_AND, BinaryOperation.BOOL_OR):
                continue
            self.assertGreater(precedence[op], precedence[BinaryOperation.BOOL_AND])
            self.assertGreater(precedence[op], precedence[BinaryOperation.BOOL_OR])

        # Test bitwise operators
        self.assertGreater(precedence[BinaryOperation.SHIFT_LEFT], precedence[BinaryOperation.PLUS])
        self.assertEqual(precedence[BinaryOperation.SHIFT_LEFT], precedence[BinaryOperation.SHIFT_RIGHT])

    def test_binary_ops_mapping_complete(self):
        """Test that all binary operators are correctly mapped."""
        binary_ops = self.parser.unary_binary_ops

        # Test arithmetic operators
        self.assertEqual(binary_ops[LexemeType.OPERATOR_BINARY_PLUS], BinaryOperation.PLUS)
        self.assertEqual(binary_ops[LexemeType.OPERATOR_BINARY_MINUS], BinaryOperation.MINUS)
        self.assertEqual(binary_ops[LexemeType.OPERATOR_BINARY_TIMES], BinaryOperation.TIMES)
        self.assertEqual(binary_ops[LexemeType.OPERATOR_BINARY_DIV], BinaryOperation.DIVIDE)

        # Test comparison operators
        self.assertEqual(binary_ops[LexemeType.OPERATOR_BINARY_BOOL_EQ], BinaryOperation.BOOL_EQ)
        self.assertEqual(binary_ops[LexemeType.OPERATOR_BINARY_BOOL_NEQ], BinaryOperation.BOOL_NEQ)

        # Test logical operators
        self.assertEqual(binary_ops[LexemeType.OPERATOR_BINARY_BOOL_AND], BinaryOperation.BOOL_AND)
        self.assertEqual(binary_ops[LexemeType.OPERATOR_BINARY_BOOL_OR], BinaryOperation.BOOL_OR)

        # Test bitwise operators
        self.assertEqual(binary_ops[LexemeType.OPERATOR_BINARY_AND], BinaryOperation.LOGIC_AND)
        self.assertEqual(binary_ops[LexemeType.OPERATOR_BINARY_OR], BinaryOperation.LOGIC_OR)
        self.assertEqual(binary_ops[LexemeType.OPERATOR_BINARY_XOR], BinaryOperation.XOR)

    def test_type_keywords_complete(self):
        """Test that all type keywords are recognized."""
        type_keywords = self.parser.type_keywords

        self.assertIn(LexemeType.KEYWORD_TYPE_VOID, type_keywords)
        self.assertIn(LexemeType.KEYWORD_TYPE_INT8, type_keywords)
        self.assertIn(LexemeType.KEYWORD_TYPE_INT16, type_keywords)
        self.assertIn(LexemeType.KEYWORD_TYPE_INT32, type_keywords)
        self.assertIn(LexemeType.KEYWORD_TYPE_INT64, type_keywords)
        self.assertIn(LexemeType.KEYWORD_TYPE_CHAR, type_keywords)
        self.assertIn(LexemeType.KEYWORD_TYPE_UINT8, type_keywords)
        self.assertIn(LexemeType.KEYWORD_TYPE_UINT16, type_keywords)
        self.assertIn(LexemeType.KEYWORD_TYPE_UINT32, type_keywords)
        self.assertIn(LexemeType.KEYWORD_TYPE_UINT64, type_keywords)
        self.assertIn(LexemeType.KEYWORD_TYPE_FLOAT16, type_keywords)
        self.assertIn(LexemeType.KEYWORD_TYPE_FLOAT32, type_keywords)
        self.assertIn(LexemeType.KEYWORD_TYPE_FLOAT64, type_keywords)
        self.assertIn(LexemeType.KEYWORD_TYPE_BOOLEAN, type_keywords)
        self.assertIn(LexemeType.KEYWORD_TYPE_STRING, type_keywords)

class TestParserPrimaryExpressions(TestParserBase):
    """Test suite for primary expression parsing."""

    def test_literal_values(self):
        """Test parsing of all types of literal values."""
        test_cases = [
            ("i32 x = 42;", "int", 42),
            ("f32 x = 3.14;", "float", 3.14),
            ("string x = \"hello\";", "string", "hello"),
            ("char x = 'a';", "char", ord("a")),
            ("bool x = true;", "bool", True),
            ("bool x = false;", "bool", False),
            ("MyClass x = null;", "null", None),
        ]

        for source, expected_type, expected_value in test_cases:
            with self.subTest(source=source, expected=(expected_type, expected_value)):
                program = self.parse_source(source)
                decl = program.statements[0]
                self.assertIsInstance(decl, PVariableDeclaration)
                assert isinstance(decl, PVariableDeclaration)
                self.assertIsInstance(decl.initial_value, PLiteral)
                assert isinstance(decl.initial_value, PLiteral)
                self.assertEqual(decl.initial_value.literal_type, expected_type)
                self.assertEqual(decl.initial_value.value, expected_value)

    def test_identifiers(self):
        """Test parsing of different identifier patterns."""
        test_cases = [
            "i32 simple;",
            "i32 camelCase;",
            "i32 PascalCase;",
            "i32 snake_case;",
            "i32 _leading_underscore;",
            "i32 with123numbers;",
            "i32 UPPER_CASE;",
        ]

        for source in test_cases:
            with self.subTest(source=source.replace("\n", "")):
                program = self.parse_source(source)
                decl = program.statements[0]
                self.assertIsInstance(decl, PVariableDeclaration)

    def test_grouped_expressions(self):
        """Test parsing of parenthesized expressions."""
        test_cases = [
            "i32 x = (42);",
            "i32 x = ((42));",
            "i32 x = (1 + (2 * 3));",
            "bool x = (true and (false or true));",
        ]

        for source in test_cases:
            with self.subTest(source=source.replace("\n", "")):
                program = self.parse_source(source)
                self.assertIsInstance(program.statements[0], PVariableDeclaration)

    def test_cast_expressions(self):
        """Test parsing of type cast expressions."""
        test_cases = [
            "i32 x = (i32)3.14;",
            "f32 x = (f32)42;",
            "i64 x = (i64)(42 + 3);",
            "MyClass obj = (MyClass)other;",
        ]

        for source in test_cases:
            with self.subTest(source=source.replace("\n", "")):
                program = self.parse_source(source)
                decl = program.statements[0]
                self.assertIsInstance(decl, PVariableDeclaration)
                assert isinstance(decl, PVariableDeclaration) #to remove linter warning
                self.assertIsInstance(decl.initial_value, PCast)

class TestParserOperators(TestParserBase):
    """Test suite for operator parsing."""

    def test_arithmetic_operators(self):
        """Test parsing of arithmetic operators."""
        test_cases = [
            ("i32 x = 1 + 2;", BinaryOperation.PLUS),
            ("i32 x = 3 - 4;", BinaryOperation.MINUS),
            ("i32 x = 5 * 6;", BinaryOperation.TIMES),
            ("i32 x = 8 / 2;", BinaryOperation.DIVIDE),
            ("i32 x = 10 % 3;", BinaryOperation.MOD),
        ]

        for source, expected_op in test_cases:
            with self.subTest(source=source.replace("\n", ""), expected_op=expected_op):
                program = self.parse_source(source)
                decl = program.statements[0]
                self.assertIsInstance(decl, PVariableDeclaration)
                #additional assertions to remove linter warnings
                assert isinstance(decl, PVariableDeclaration)
                self.assertIsInstance(decl.initial_value, PBinaryOperation)
                assert isinstance(decl.initial_value, PBinaryOperation)
                self.assertEqual(decl.initial_value.operation, expected_op)

    def test_comparison_operators(self):
        """Test parsing of comparison operators."""
        test_cases = [
            ("bool x = a == b;", BinaryOperation.BOOL_EQ),
            ("bool x = a != b;", BinaryOperation.BOOL_NEQ),
            ("bool x = a < b;", BinaryOperation.BOOL_LT),
            ("bool x = a <= b;", BinaryOperation.BOOL_LEQ),
            ("bool x = a > b;", BinaryOperation.BOOL_GT),
            ("bool x = a >= b;", BinaryOperation.BOOL_GEQ),
        ]

        for source, expected_op in test_cases:
            with self.subTest(source=source.replace("\n", ""), expected_op=expected_op):
                program = self.parse_source(source)
                decl = program.statements[0]
                self.assertIsInstance(decl, PVariableDeclaration)
                #additional assertions to remove linter warnings
                assert isinstance(decl, PVariableDeclaration)
                self.assertIsInstance(decl.initial_value, PBinaryOperation)
                assert isinstance(decl.initial_value, PBinaryOperation)
                self.assertEqual(decl.initial_value.operation, expected_op)

    def test_logical_operators(self):
        """Test parsing of logical operators."""
        test_cases = [
            ("bool x = a and b;", BinaryOperation.BOOL_AND),
            ("bool x = a or b;", BinaryOperation.BOOL_OR),
            ("bool x = not a;", UnaryOperation.BOOL_NOT),
        ]

        for source, expected_op in test_cases:
            with self.subTest(source=source.replace("\n", ""), expected_op=expected_op):
                program = self.parse_source(source)
                decl = program.statements[0]
                self.assertIsInstance(decl, PVariableDeclaration)
                assert isinstance(decl, PVariableDeclaration)
                if isinstance(expected_op, BinaryOperation):
                    self.assertIsInstance(decl.initial_value, PBinaryOperation)
                else:
                    self.assertIsInstance(decl.initial_value, PUnaryOperation)
                assert isinstance(decl.initial_value, (PUnaryOperation,PBinaryOperation))
                self.assertEqual(decl.initial_value.operation, expected_op)

    def test_assignment_operators(self):
        """Test parsing of compound assignment operators."""
        test_cases = [
            ("x += 5;", BinaryOperation.PLUS),
            ("x -= 5;", BinaryOperation.MINUS),
            ("x *= 5;", BinaryOperation.TIMES),
            ("x /= 5;", BinaryOperation.DIVIDE),
            ("x &= 5;", BinaryOperation.LOGIC_AND),
            ("x |= 5;", BinaryOperation.LOGIC_OR),
            ("x ^= 5;", BinaryOperation.XOR),
            ("x <<= 5;", BinaryOperation.SHIFT_LEFT),
            ("x >>= 5;", BinaryOperation.SHIFT_RIGHT)
        ]

        for source, expected_op in test_cases:
            with self.subTest(source=source, expected_op=expected_op):
                program = self.parse_source(source)
                stmt = program.statements[0]
                self.assertIsInstance(stmt, PAssignment)
                # Additional assertions to remove linter warnings
                assert isinstance(stmt, PAssignment)
                self.assertIsInstance(stmt.value, PBinaryOperation)
                # Additional assertions to remove linter warnings
                assert isinstance(stmt.value, PBinaryOperation)
                self.assertEqual(stmt.value.operation, expected_op)

    def test_assignment_operators_secondary_value(self):
        """Test parsing of compound assignment operators."""
        test_cases = [
            ("x += 5 + 2;", BinaryOperation.PLUS),
            ("x += 5 - 3;", BinaryOperation.MINUS),
            ("x += 5 * 3;", BinaryOperation.TIMES),
            ("x += 5 / 3;", BinaryOperation.DIVIDE),
            ("x += 5 & 7;", BinaryOperation.LOGIC_AND),
            ("x += 5 | 2;", BinaryOperation.LOGIC_OR),
            ("x += 5 ^ 7;", BinaryOperation.XOR),
            ("x += 5 << 3;", BinaryOperation.SHIFT_LEFT),
            ("x += 5 >> 1;", BinaryOperation.SHIFT_RIGHT)
        ]

        for source, expected_op in test_cases:
            with self.subTest(source=source, expected_op=expected_op):
                program = self.parse_source(source)
                stmt = program.statements[0]
                self.assertIsInstance(stmt, PAssignment)
                # Additional assertions to remove linter warnings
                assert isinstance(stmt, PAssignment)
                self.assertIsInstance(stmt.value, PBinaryOperation)
                # Additional assertions to remove linter warnings
                assert isinstance(stmt.value, PBinaryOperation)
                self.assertEqual(stmt.value.operation, BinaryOperation.PLUS)
                self.assertIsInstance(stmt.value.left, PIdentifier)
                self.assertIsInstance(stmt.value.right, PBinaryOperation)
                assert isinstance(stmt.value.right, PBinaryOperation)
                self.assertEqual(stmt.value.right.operation, expected_op)

    def test_bitwise_operators(self):
        """Test parsing of bitwise operators."""
        test_cases = [
            ("i32 x = a & b;", BinaryOperation.LOGIC_AND),
            ("i32 x = a | b;", BinaryOperation.LOGIC_OR),
            ("i32 x = a ^ b;", BinaryOperation.XOR),
            ("i32 x = a << 2;", BinaryOperation.SHIFT_LEFT),
            ("i32 x = a >> 2;", BinaryOperation.SHIFT_RIGHT),
        ]

        for source, expected_op in test_cases:
            with self.subTest(source=source.replace("\n", ""), expected_op=expected_op):
                program = self.parse_source(source)
                decl = program.statements[0]
                self.assertIsInstance(decl, PVariableDeclaration)
                assert isinstance(decl, PVariableDeclaration)
                self.assertIsInstance(decl.initial_value, PBinaryOperation)
                assert isinstance(decl.initial_value, PBinaryOperation)
                self.assertEqual(decl.initial_value.operation, expected_op)

    def test_operator_precedence(self):
        """Test that operators follow correct precedence rules."""
        test_cases = [
            ("i32 x = 1 + 2 * 3;", BinaryOperation.PLUS),
            ("i32 x = (1 + 2) * 3;", BinaryOperation.TIMES),
            ("bool x = a and b or c;", BinaryOperation.BOOL_OR),
            ("bool x = (a and b) or c;", BinaryOperation.BOOL_OR),
            ("i32 x = 1 << 2 + 3;", BinaryOperation.PLUS),
            ("i32 x = (1 << 2) + 3;", BinaryOperation.PLUS),
        ]

        for source, expected_root_op in test_cases:
            with self.subTest(source=source.replace("\n", ""), expected_root_op=expected_root_op):
                program = self.parse_source(source)
                decl = program.statements[0]
                self.assertIsInstance(decl, PVariableDeclaration)
                assert isinstance(decl, PVariableDeclaration)
                self.assertIsInstance(decl.initial_value, PBinaryOperation)
                assert isinstance(decl.initial_value, PBinaryOperation)
                self.assertEqual(decl.initial_value.operation, expected_root_op)

    def test_unary_operators(self):
        """Test parsing of unary operators."""
        test_cases = [
            ("i32 x = -5;", UnaryOperation.MINUS),
            ("i32 x = ++x;", UnaryOperation.PRE_INCREMENT),
            ("i32 x = --x;", UnaryOperation.PRE_DECREMENT),
            ("i32 x = x++;", UnaryOperation.POST_INCREMENT),
            ("i32 x = x--;", UnaryOperation.POST_DECREMENT),
            ("bool x = not true;", UnaryOperation.BOOL_NOT),
            ("i32 x = !5;", UnaryOperation.LOGIC_NOT),
            ("i32 x = -(-5);", UnaryOperation.MINUS),
        ]

        for source, expected_op in test_cases:
            with self.subTest(source=source.replace("\n", ""), expected_op=expected_op):
                program = self.parse_source(source)
                decl = program.statements[0]
                self.assertIsInstance(decl, PVariableDeclaration)
                assert isinstance(decl, PVariableDeclaration)
                self.assertIsInstance(decl.initial_value, PUnaryOperation)
                assert isinstance(decl.initial_value, PUnaryOperation)
                self.assertEqual(decl.initial_value.operation, expected_op)

    def test_unary_chaining(self):
        test_cases = [
            ("! not x;", UnaryOperation.LOGIC_NOT, UnaryOperation.BOOL_NOT),
            ("!!x;", UnaryOperation.LOGIC_NOT, UnaryOperation.LOGIC_NOT),
            ("not !x;", UnaryOperation.BOOL_NOT, UnaryOperation.LOGIC_NOT),
            ("!--x;", UnaryOperation.LOGIC_NOT, UnaryOperation.PRE_DECREMENT)
        ]

        for expression, unary_op1, unary_op2 in test_cases:
            with self.subTest(expression=expression,
                              unary_op1=unary_op1, unary_op2=unary_op2):
                program = self.parse_source(expression)
                expr = program.statements[0]
                self.assertIsInstance(expr, PUnaryOperation)
                assert isinstance(expr, PUnaryOperation)
                self.assertEqual(expr.operation, unary_op1)
                self.assertIsInstance(expr.operand, PUnaryOperation)
                assert isinstance(expr.operand, PUnaryOperation)
                self.assertEqual(expr.operand.operation, unary_op2)

    def test_basic_unary_operations(self):
        """Test basic unary operations with straightforward usage."""
        test_cases = [
            ("i32 x = -42;", UnaryOperation.MINUS),
            ("bool x = not true;", UnaryOperation.BOOL_NOT),
            ("i32 x = !5;", UnaryOperation.LOGIC_NOT),
            ("i32 x = !!!true;", UnaryOperation.LOGIC_NOT),
            ("i32 x = -(-(-5));", UnaryOperation.MINUS),
        ]

        for source, expected_op in test_cases:
            with self.subTest(source=source):
                program = self.parse_source(source)
                var_decl = program.statements[0]
                self.assertIsInstance(var_decl, PVariableDeclaration)
                assert isinstance(var_decl, PVariableDeclaration)
                self.assertIsInstance(var_decl.initial_value, PUnaryOperation)
                assert isinstance(var_decl.initial_value, PUnaryOperation)
                self.assertEqual(var_decl.initial_value.operation, expected_op)

    def test_unary_operations_in_control_structures(self):
        """Test unary operations within control flow statements."""
        test_cases = [
            """
            while(x++) {
                if(--y) {
                    break;
                }
            }
            """,
            """
            if(!(x++) and not(--y)) {
                process(-z);
            }
            """,
            """
            for(i32 i = 0; i < 10; i++) {
                if(!done) break;
            }
            """
        ]

        for source in test_cases:
            with self.subTest(source=source):
                program = self.parse_source(source)
                self.assertTrue(any(isinstance(stmt, (PWhileStatement, PIfStatement, PForStatement))
                                for stmt in program.statements))

    def test_unary_operations_with_arrays(self):
        """Test unary operations in array contexts."""
        test_cases = [
            ("arr[x++] = 1;", UnaryOperation.POST_INCREMENT),
            ("arr[x--] = 1;", UnaryOperation.POST_DECREMENT),
            ("arr[++x] = 1;", UnaryOperation.PRE_INCREMENT),
            ("arr[--x] = 1;", UnaryOperation.PRE_DECREMENT),
            ("arr[-x] = 1;", UnaryOperation.MINUS),
            ("arr[!x] = 1;", UnaryOperation.LOGIC_NOT),
            ("arr[not x] = 1;", UnaryOperation.BOOL_NOT),
        ]

        for source, expected_op in test_cases:
            with self.subTest(source=source):
                program = self.parse_source(source)
                stmnt = program.statements[0]
                self.assertIsInstance(stmnt, PAssignment)
                assert isinstance(stmnt, PAssignment)
                self.assertIsInstance(stmnt.target, PArrayIndexing)
                assert isinstance(stmnt.target, PArrayIndexing)
                self.assertIsInstance(stmnt.target.index, PUnaryOperation)
                assert isinstance(stmnt.target.index, PUnaryOperation)


    def test_unary_operations_with_method_calls(self):
        """Test unary operations in method call contexts."""
        test_cases = [
            """
            obj.process(x++).validate(!(--y));
            """,
            """
            obj.method1(!x).method2(--y);
            """,
            """
            getValue().process(x++);
            """
        ]

        for source in test_cases:
            with self.subTest(source=source):
                program = self.parse_source(source)
                self.assertTrue(any(isinstance(stmt, (PMethodCall, PFunctionCall))
                                for stmt in program.statements))

    def test_complex_unary_operation_combinations(self):
        """Test complex combinations of unary operations."""
        test_cases = [
            "i32 y = -(-(-x)) + !(--y) * (x++ - y--);"
            "i32 x = --x + x++;",
            "i32 y = -x + !y;"
        ]

        for source in test_cases:
            with self.subTest(source=source):
                program = self.parse_source(source)
                stmnt = program.statements[0]
                self.assertIsInstance(stmnt, PVariableDeclaration)
                assert isinstance(stmnt, PVariableDeclaration)
                self.assertIsInstance(stmnt.initial_value, PBinaryOperation)
                assert isinstance(stmnt.initial_value, PBinaryOperation)
                self.assertIsInstance(stmnt.initial_value.left, PUnaryOperation)

    def test_unary_operation_error_cases(self):
        """Test invalid unary operation combinations."""
        invalid_sources = [
            "42++;",  # Increment on literal
            "++42;",  # Pre-increment on literal
            "x+ +;",  # Invalid spacing
            "!;",     # Missing operand
            "x = ++ --;"  # Invalid sequence
        ]

        for source in invalid_sources:
            with self.subTest(source=source):
                with self.assertRaises(ParserError):
                    self.parse_source(source)

    def test_basic_discard_assignments(self):
        """Test basic discard assignment patterns to ensure core functionality works.
        """
        test_cases = [
            # Simple literal assignments
            "_ = 42;",
            "_ = \"hello\";",
            "_ = true;",
            
            # Expression assignments
            "_ = 1 + 2;",
            "_ = x * y + z;",
            "_ = (a + b) * (c - d);",
            
            # Function call assignments
            "_ = getValue();",
            "_ = calculate(x, y);",
            
            # Complex nested expressions
            "_ = getValue().process().format();",
            "_ = obj.method(func(x + y));",
            "_ = array[index + 1].field;",
        ]
        
        for source in test_cases:
            with self.subTest(source=source.replace("\n", " ").strip()):
                program = self.parse_source(source)
                
                stmt = program.statements[0]
                self.assertIsInstance(stmt, PDiscard)
                assert isinstance(stmt, PDiscard)
                self.assertEqual(stmt.node_type, NodeType.DISCARD)
                self.assertIsInstance(stmt.expression, PExpression)

    def test_discard_invalid(self):
        
        # Invalid cases that should raise ParserError
        invalid_cases = [
            # Missing assignment operator
            "_ 42;",
            # Multiple discard operators
            "_ _ = 42;",
            # Invalid assignment targets
            "x = _;",
            # Missing semicolon
            "_ = 42",
            # Empty assignment
            "_ =;",
            # Invalid expression after assignment
            "_ = ;",
        ]
        
        for source in invalid_cases:
            with self.subTest(source=source):
                with self.assertRaises(ParserError):
                    self.parse_source(source)

class TestParserControlFlow(TestParserBase):
    """Test suite for control flow statement parsing."""

    def test_if_statement_variations(self):
        """Test parsing of various if statement forms."""
        test_cases = [
            # Simple if
            """
            if (true) {
                i32 x = 1;
            }
            """,
            # If-else
            """
            if (false) {
                i32 x = 1;
            } else {
                i32 x = 2;
            }
            """,
            # Nested if
            """
            if (a) {
                if (b) {
                    i32 x = 1;
                }
            }
            """,
            # Complex condition
            """
            if (a and b or c) {
                i32 x = 1;
            }
            """
        ]

        for source in test_cases:
            with self.subTest(source=source.replace("\n", "")):
                program = self.parse_source(source)
                self.assertIsInstance(program.statements[0], PIfStatement)

    def test_while_loop_variations(self):
        """Test parsing of various while loop forms."""
        test_cases = [
            # Simple while
            """
            while (true) {
                i32 x = 1;
            }
            """,
            # Complex condition
            """
            while (i < 10 and !done) {
                i32 x = 1;
            }
            """,
            # Nested while
            """
            while (a) {
                while (b) {
                    i32 x = 1;
                }
            }
            """,
            # While with break
            """
            while (true) {
                if (x > 10) {
                    break;
                }
                x = x + 1;
            }
            """,
            # While with continue
            """
            while (x < 100) {
                x = x + 1;
                if (x % 2 == 0) {
                    continue;
                }
                doSomething();
            }
            """
        ]

        for source in test_cases:
            with self.subTest(source=source):
                program = self.parse_source(source)
                while_stmt = program.statements[0]
                self.assertIsInstance(while_stmt, PWhileStatement)
                assert isinstance(while_stmt, PWhileStatement)
                self.assertIsInstance(while_stmt.condition, PExpression)
                self.assertIsInstance(while_stmt.body, PBlock)

    def test_for_loop_variations(self):
        """Test parsing of various for loop forms."""
        test_cases = [
            # Standard for loop
            """
            for (i32 i = 0; i < 10; i = i + 1) {
                x = x + i;
            }
            """,
            # Empty components
            """
            for (;;) {
                x = x + 1;
            }
            """,
            # Missing initializer
            """
            for (; i < 10; i = i + 1) {
                x = x + 1;
            }
            """,
            # Missing condition
            """
            for (i32 i = 0;; i = i + 1) {
                x = x + 1;
            }
            """,
            # Missing increment
            """
            for (i32 i = 0; i < 10;) {
                x = x + 1;
            }
            """,
            # Complex expressions
            """
            for (i32 i = start + 5; i < end - 3; i = i + step * 2) {
                process(i);
            }
            """,
            # Nested for loops
            """
            for (i32 i = 0; i < 10; i = i + 1) {
                for (i32 j = 0; j < i; j = j + 1) {
                    matrix[i][j] = i * j;
                }
            }
            """
        ]

        for source in test_cases:
            with self.subTest(source=source):
                program = self.parse_source(source)
                for_stmt = program.statements[0]
                self.assertIsInstance(for_stmt, PForStatement)
                assert isinstance(for_stmt, PForStatement)
                self.assertIsInstance(for_stmt.body, PBlock)

    def test_break_continue_statements(self):
        """Test parsing of break and continue statements in different contexts."""
        test_cases = [
            # Break in while
            """
            while (true) {
                if (x > 10)
                    break;
            }
            """,
            # Continue in while
            """
            while (x < 100) {
                if (x % 2 == 0)
                    continue;
                process(x);
            }
            """,
            # Break in for
            """
            for (i32 i = 0; i < 10; i = i + 1) {
                if (isDone())
                    break;
            }
            """,
            # Continue in for
            """
            for (i32 i = 0; i < 10; i = i + 1) {
                if (i % 2 == 0)
                    continue;
                process(i);
            }
            """,
            # Nested loops with break/continue
            """
            while (true) {
                for (i32 i = 0; i < 10; i = i + 1) {
                    if (i == 5)
                        continue;
                    if (isDone())
                        break;
                }
                if (allDone())
                    break;
            }
            """
        ]

        for source in test_cases:
            with self.subTest(source=source):
                program = self.parse_source(source)
                loop = program.statements[0]
                self.assertIsInstance(loop, (PWhileStatement, PForStatement))
                assert isinstance(loop, (PWhileStatement, PForStatement))

    def test_assert_statement_variations(self):
        """Test parsing of assert statements with different patterns."""
        test_cases = [
            # Simple assert
            """
            assert x > 0;
            """,
            # Assert with message
            """
            assert x > 0, "x must be positive";
            """,
            # Assert with complex condition
            """
            assert x > 0 and y < 100 or z == 0;
            """,
            # Assert with function call
            """
            assert isValid(x);
            """,
            # Assert with complex expression and message
            """
            assert calculateValue() > threshold, "Value too low";
            """
        ]

        for source in test_cases:
            with self.subTest(source=source):
                program = self.parse_source(source)
                assert_stmt = program.statements[0]
                self.assertIsInstance(assert_stmt, PAssertStatement)
                assert isinstance(assert_stmt, PAssertStatement)
                self.assertIsInstance(assert_stmt.condition, PExpression)

    def test_ternary_operation_variations(self):
        """Test parsing of ternary operations in different contexts."""
        test_cases = [
            # Simple ternary
            "i32 x = condition ? 1 : 2;",
            # Nested ternary
            "i32 x = a ? b ? 1 : 2 : 3;",
            # Complex conditions
            "i32 x = (a > b and c < d) ? 1 : 2;",
            # Ternary with function calls
            "i32 x = isValid() ? getValue() : getDefault();",
            # Mixed expressions
            "i32 x = a > b ? a + b : a - b;"
        ]

        for source in test_cases:
            with self.subTest(source=source):
                program = self.parse_source(source)
                var_decl = program.statements[0]
                self.assertIsInstance(var_decl, PVariableDeclaration)
                assert isinstance(var_decl, PVariableDeclaration)
                self.assertIsInstance(var_decl.initial_value, PTernaryOperation)
                assert isinstance(var_decl.initial_value, PTernaryOperation)
                
    def test_nested_ternary(self):
        # Nested Expression
        source="i32 x = a ? c ? a : c : b;"
        with self.subTest(source="i32 x = a ? c ? a : c : b;"):
            program = self.parse_source(source)
            var_decl = program.statements[0]
            self.assertIsInstance(var_decl, PVariableDeclaration)
            assert isinstance(var_decl, PVariableDeclaration)
            self.assertIsInstance(var_decl.initial_value, PTernaryOperation)
            assert isinstance(var_decl.initial_value, PTernaryOperation)
            self.assertIsInstance(var_decl.initial_value.true_value, PTernaryOperation)
            self.assertIsInstance(var_decl.initial_value.false_value, PIdentifier)


    def test_invalid_control_structures(self):
        """Test that invalid control structure syntax raises appropriate errors."""
        invalid_sources = [
            # Missing parentheses
            "if condition { }",
            # Invalid for loop syntax
            "for i = 0; i < 10; i++ { }",
            # Missing while condition
            "while { }",
            # Invalid ternary syntax
            "i32 x = condition ? : 2;",
            # For loop with multiple initializers
            """
            for (i32 i = 0, j = 10; i < j; i = i + 1) {
                x = x + i;
            }
            """,
            # Unmatched braces
            """
            if (condition) {
                x = 1;
            """,
            # Invalid break/continue placement
            """
            i32 x = 1;
            break;
            """
        ]

        for source in invalid_sources:
            with self.subTest(source=source):
                with self.assertRaises(ParserError):
                    self.parse_source(source)

    def test_break_continue_outside_loop(self):
        """Test that break and continue statements raise errors when used outside loops."""
        invalid_cases = [
            # Top level break/continue
            "break;",
            "continue;",
            
            # In function without loop
            """
            void test() {
                break;
            }
            """,
            """
            void test() {
                continue;
            }
            """,
            
            # In if statement without loop
            """
            if (condition) {
                break;
            }
            """,
            """
            if (condition) {
                continue;
            }
            """,
            
            # In nested blocks without loop
            """
            void test() {
                if (x > 0) {
                    if (y < 0) {
                        break;
                    }
                }
            }
            """,
            """
            void test() {
                {
                    {
                        continue;
                    }
                }
            }
            """
        ]
        
        for source in invalid_cases:
            with self.subTest(source=source.replace("\n", " ").strip()):
                with self.assertRaises(ParserError) as context:
                    self.parse_source(source)
                # Verify error message mentions being outside loop
                self.assertIn("loop", str(context.exception).lower())

    def test_return_outside_function(self):
        """Test that return statements raise errors when used outside functions."""
        invalid_cases = [
            # Top level return
            "return;",
            "return 42;",
            
            # In bare blocks
            """
            {
                return;
            }
            """,
            """
            {
                return value;
            }
            """,
            
            # In if statements outside function
            """
            if (condition) {
                return;
            }
            """,
            
            # In loops outside function
            """
            while (running) {
                return result;
            }
            """,
            
            # In nested blocks outside function
            """
            {
                if (condition) {
                    while (true) {
                        return value;
                    }
                }
            }
            """
        ]
        
        for source in invalid_cases:
            with self.subTest(source=source.replace("\n", " ").strip()):
                with self.assertRaises(ParserError) as context:
                    self.parse_source(source)
                # Verify error message mentions being outside function
                self.assertIn("function", str(context.exception).lower())

    def test_valid_control_flow_contexts(self):
        """Test that break, continue, and return statements work correctly in valid contexts."""
        valid_cases = [
            # Break/continue in loops
            """
            while (true) {
                if (done) break;
                if (skip) continue;
            }
            """,
            
            # Break/continue in nested loops
            """
            for (i32 i = 0; i < 10; i = i + 1) {
                while (processing) {
                    if (error) break;
                    if (retry) continue;
                }
            }
            """,
            
            # Return in functions
            """
            i32 test() {
                return 42;
            }
            """,
            
            # Return in nested function contexts
            """
            i32 compute() {
                while (calculating) {
                    if (done) {
                        return result;
                    }
                }
                return 0;
            }
            """
        ]
        
        for source in valid_cases:
            with self.subTest(source=source.replace("\n", " ").strip()):
                # Should parse without raising exceptions
                program = self.parse_source(source)
                self.assertIsNotNone(program)

class TestParserFunctionDefinitions(TestParserBase):
    """Test suite for function definition parsing."""

    def test_function_declaration_variations(self):
        """Test parsing of various function declaration patterns."""
        test_cases = [
            # No parameters
            """
            void main() {
                return;
            }
            """,
            # Single parameter
            """
            i32 square(i32 x) {
                return x * x;
            }
            """,
            # Multiple parameters
            """
            i32 add(i32 a, i32 b) {
                return a + b;
            }
            """,
            # Complex return type
            """
            string[] getNames() {
                return names;
            }
            """,
            # Empty function body
            """
            void initialize() {
            }
            """,
            # Complex parameter types
            """
            void processArray(i32[] data, i32 length) {
                i32 i = 0;
                while (i < length) {
                    process(data[i]);
                    i = i + 1;
                }
            }
            """
        ]

        for source in test_cases:
            with self.subTest(source=source):
                program = self.parse_source(source)
                func = program.statements[0]
                self.assertIsInstance(func, PFunction)
                assert isinstance(func, PFunction)
                self.assertIsInstance(func.body, PBlock)

    def test_function_call_variations(self):
        """Test parsing of various function call patterns."""
        test_cases = [
            # No arguments
            "getZero();",
            # Single argument
            "print(42);",
            # Multiple arguments
            "add(x, y);",
            # Nested calls
            "outer(inner(x));",
            # Complex arguments
            "calculate(x + y, z * 2);",
            # Function calls as arguments
            "max(getValue(), getDefault());"
        ]

        for source in test_cases:
            with self.subTest(source=source):
                program = self.parse_source(source)
                call = program.statements[0]
                self.assertIsInstance(call, PFunctionCall)

    def test_return_statement_variations(self):
        """Test parsing of return statements with different patterns."""
        test_cases = [
            # Void return
            """
            void test() {
                return;
            }
            """,
            # Return literal
            """
            i32 test() {
                return 42;
            }
            """,
            # Return expression
            """
            i32 test() {
                return x + y;
            }
            """,
            # Return function call
            """
            i32 test() {
                return getValue();
            }
            """,
            # Return complex expression
            """
            i32 test() {
                return (a + b) * (c - d);
            }
            """
        ]

        for source in test_cases:
            with self.subTest(source=source):
                program = self.parse_source(source)
                func = program.statements[0]
                self.assertIsInstance(func, PFunction)
                assert isinstance(func, PFunction)
                # Find the return statement in the function body
                return_stmt = func.body.statements[-1]
                self.assertIsInstance(return_stmt, PReturnStatement)

class TestParserClassDefinitions(TestParserBase):
    """Test suite for class definition parsing."""

    def test_class_declaration_variations(self):
        """Test parsing of various class declaration patterns."""
        test_cases = [
            # Empty class
            """
            class Empty {
            }
            """,
            # Class with fields
            """
            class Point {
                i32 x;
                i32 y;
            }
            """,
            # Class with method
            """
            class Calculator {
                i32 add(i32 a, i32 b) {
                    return a + b;
                }
            }
            """,
            # Class with fields and methods
            """
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
        ]

        for source in test_cases:
            with self.subTest(source=source.replace("\n", "")):
                program = self.parse_source(source)
                class_def = program.statements[0]
                self.assertIsInstance(class_def, PClass)

        # Complex class with multiple methods
        source = """class Stack {
                        i32[] elements;
                        i32 size;

                        void push(i32 element) {
                            this.elements[size] = element;
                            this.size = this.size + 1;
                        }

                        i32 pop() {
                            this.size = size - 1;
                            return this.elements[size];
                        }

                        bool isEmpty() {
                            return this.size == 0;
                        }
                    }"""
        with self.subTest(source=" ".join(source.replace("\n", "").split(" "))):
            program = self.parse_source(source)
            class_def = program.statements[0]
            self.assertIsInstance(class_def, PClass)
            assert isinstance(class_def, PClass)

            #test properties
            self.assertEqual(len(class_def.fields), 2)
            for i,(typ, name) in enumerate([('i32[]', 'elements'), ("i32","size")]):
                self.assertIsInstance(class_def.fields[i], PClassField)
                self.assertEqual(typ, str(class_def.fields[i].var_type))
                self.assertEqual(name, class_def.fields[i].name)

            #test methods
            self.assertEqual(len(class_def.methods), 3)
            for i,(return_type, name) in enumerate([('void','push'), ('i32', 'pop'), ('bool', 'isEmpty')]):
                self.assertIsInstance(class_def.methods[i], PFunction)
                self.assertEqual(return_type, str(class_def.methods[i].return_type))
                self.assertEqual(name, class_def.methods[i].name)



    def test_method_call_variations(self):
        """Test parsing of various method call patterns."""
        test_cases = [
            # Simple method call
            "obj.method();",
            # Method call with arguments
            "obj.setValues(1, 2);",
            # Chained method calls
            "obj.method1().method2();",
            # Method call with expressions
            "obj.calculate(x + y, z * 2);",
            # Complex object expression
            "getObject().method();"
        ]

        for source in test_cases:
            with self.subTest(source=source):
                program = self.parse_source(source)
                stmt = program.statements[0]
                self.assertIsInstance(stmt, (PMethodCall,PFunctionCall))

    def test_invalid_class_definitions(self):
        """Test that invalid class definitions raise appropriate errors."""
        invalid_sources = [
            # Missing class name
            """
            class {
            }
            """,
            # Missing opening brace
            """
            class Test
            }
            """,
            # Invalid method declaration
            """
            class Test {
                void() {
                }
            }
            """,
            # Invalid field declaration
            """
            class Test {
                i32;
            }
            """,
            # Cannot define class if in a function or block
            """
            {
                class Test { }
            }
            """,
            """
            i32 func(){
                class Test { }
            }
            """
        ]

        for source in invalid_sources:
            with self.subTest(source=source):
                with self.assertRaises(ParserError):
                    self.parse_source(source)

    def test_class_initialization_basic(self):
        """Test basic class initialization without parameters"""
        code = "MyClass instance = new MyClass();"
        ast = self.parse_source(code)
        
        var_decl = ast.statements[0]
        self.assertIsInstance(var_decl, PVariableDeclaration)
        assert isinstance(var_decl, PVariableDeclaration)
        self.assertEqual(var_decl.name, "instance")
        self.assertIsInstance(var_decl.initial_value, PObjectInstantiation)
        assert isinstance(var_decl.initial_value, PObjectInstantiation)
        self.assertEqual(str(var_decl.initial_value.class_type), "MyClass")

    def test_array_initialization_primitive_types(self):
        """Test array initialization with different primitive types"""
        primitive_types = ["i32", "f32", "bool", "string", "char"]
        
        for type_name in primitive_types:
            code = f"{type_name}[] arr = new {type_name}[10];"
            with self.subTest(type_name=type_name, source=code):
                ast = self.parse_source(code)
                
                var_decl = ast.statements[0]
                self.assertIsInstance(var_decl, PVariableDeclaration)
                assert isinstance(var_decl, PVariableDeclaration)
                self.assertIsInstance(var_decl.var_type, PArrayType)
                assert isinstance(var_decl.var_type, PArrayType)
                self.assertEqual(var_decl.var_type.element_type.type_string, type_name)
                self.assertIsInstance(var_decl.initial_value, PArrayInstantiation)
                assert isinstance(var_decl.initial_value, PArrayInstantiation)
                self.assertIsInstance(var_decl.initial_value.element_type, PType)
                assert isinstance(var_decl.initial_value.element_type, PType)
                self.assertEqual(var_decl.initial_value.element_type.type_string, type_name)

    def test_array_initialization_custom_types(self):
        """Test array initialization with custom class types"""
        code = "MyClass[] objects = new MyClass[5];"
        ast = self.parse_source(code)
        
        var_decl = ast.statements[0]
        self.assertIsInstance(var_decl, PVariableDeclaration)
        assert isinstance(var_decl, PVariableDeclaration)
        self.assertIsInstance(var_decl.var_type, PArrayType)
        assert isinstance(var_decl.var_type, PArrayType)
        self.assertIsInstance(var_decl.var_type.element_type, PType)
        self.assertEqual(var_decl.var_type.element_type.type_string, "MyClass")
        self.assertIsInstance(var_decl.initial_value, PArrayInstantiation)
        assert isinstance(var_decl.initial_value, PArrayInstantiation)
        self.assertEqual(var_decl.initial_value.element_type.type_string, "MyClass")

    def test_array_initialization_variable_size(self):
        """Test array initialization with variable size expression"""
        code = """
        i32 size = 10;
        i64[] arr = new i64[size];
        """
        ast = self.parse_source(code)
        
        arr_decl = ast.statements[1]
        self.assertIsInstance(arr_decl, PVariableDeclaration)
        assert isinstance(arr_decl, PVariableDeclaration)
        self.assertIsInstance(arr_decl.initial_value, PArrayInstantiation)
        assert isinstance(arr_decl.initial_value, PArrayInstantiation)
        size_expr = arr_decl.initial_value.size
        self.assertIsInstance(size_expr, PIdentifier)
        assert isinstance(size_expr, PIdentifier)
        self.assertEqual(size_expr.name, "size")

    def test_array_indexing_simple(self):
        """Test basic array indexing operations"""
        code = """
        i32[] arr = new i32[5];
        arr[0] = 42;
        i32 value = arr[1];
        """
        ast = self.parse_source(code)
        
        # Test assignment to array index
        assign_stmt = ast.statements[1]
        self.assertIsInstance(assign_stmt, PAssignment)
        assert isinstance(assign_stmt, PAssignment)
        self.assertIsInstance(assign_stmt.target, PArrayIndexing)
        assert isinstance(assign_stmt.target, PArrayIndexing)
        self.assertIsInstance(assign_stmt.target.index, PLiteral)
        assert isinstance(assign_stmt.target.index, PLiteral)
        self.assertEqual(assign_stmt.target.index.value, 0)
        
        # Test reading from array index
        read_decl = ast.statements[2]
        self.assertIsInstance(read_decl, PVariableDeclaration)
        assert isinstance(read_decl, PVariableDeclaration)
        self.assertIsInstance(read_decl.initial_value, PArrayIndexing)
        assert isinstance(read_decl.initial_value, PArrayIndexing)
        self.assertIsInstance(read_decl.initial_value.index, PLiteral)
        assert isinstance(read_decl.initial_value.index, PLiteral)
        self.assertEqual(read_decl.initial_value.index.value, 1)

    def test_array_indexing_nested(self):
        """Test nested array indexing operations"""
        code = "i32[][] matrix = new i32[3][];"
        ast = self.parse_source(code)
        
        var_decl = ast.statements[0]
        self.assertIsInstance(var_decl, PVariableDeclaration)
        assert isinstance(var_decl, PVariableDeclaration)
        self.assertIsInstance(var_decl.var_type, PArrayType)
        assert isinstance(var_decl.var_type, PArrayType)
        self.assertIsInstance(var_decl.var_type.element_type, PArrayType)
        assert isinstance(var_decl.var_type.element_type, PArrayType)
        self.assertIsInstance(var_decl.var_type.element_type.element_type, PType)
        assert isinstance(var_decl.var_type.element_type.element_type, PType)
        self.assertEqual(var_decl.var_type.element_type.element_type.type_string, "i32")

    def test_array_indexing_expressions(self):
        """Test array indexing with complex expressions"""
        code = """
        i32[] arr = new i32[10];
        arr[2 + 3] = arr[1 * 2];
        """
        ast = self.parse_source(code)
        
        assign_stmt = ast.statements[1]
        self.assertIsInstance(assign_stmt, PAssignment)
        assert isinstance(assign_stmt, PAssignment)
        self.assertIsInstance(assign_stmt.target, PArrayIndexing)
        assert isinstance(assign_stmt.target, PArrayIndexing)
        self.assertIsInstance(assign_stmt.target.array, PIdentifier)
        assert isinstance(assign_stmt.target.array, PIdentifier)
        self.assertEqual(assign_stmt.target.array.name, "arr")
        self.assertIsInstance(assign_stmt.value, PArrayIndexing)
        assert isinstance(assign_stmt.value, PArrayIndexing)
        self.assertIsInstance(assign_stmt.value.array, PIdentifier)
        assert isinstance(assign_stmt.value.array, PIdentifier)
        self.assertEqual(assign_stmt.value.array.name, "arr")

    def test_array_type_single_dimension(self):
        """Test single dimension array type declarations"""
        code = """
        i32[] numbers;
        string[] words;
        MyClass[] objects;
        """
        ast = self.parse_source(code)
        
        for stmt in ast.statements:
            self.assertIsInstance(stmt, PVariableDeclaration)
            assert isinstance(stmt, PVariableDeclaration)
            self.assertIsNone(stmt.initial_value)
            self.assertIsInstance(stmt.var_type, PArrayType)
            assert isinstance(stmt.var_type, PArrayType)
            self.assertIsInstance(stmt.var_type.element_type, PType)
            assert isinstance(stmt.var_type.element_type, PType)

    def test_array_type_multiple_dimensions(self):
        """Test multi-dimensional array type declarations"""
        dimensions = range(1, 4)  # Test 1D to 3D arrays
        
        for dim in dimensions:
            with self.subTest(dimensions=dim):
                type_decl = "i32" + "[]" * dim
                code = f"{type_decl} arr;"
                ast = self.parse_source(code)
                
                var_decl = ast.statements[0]
                self.assertIsInstance(var_decl, PVariableDeclaration)
                assert isinstance(var_decl, PVariableDeclaration)
                current_type = var_decl.var_type
                
                # Verify each dimension of the array type
                for _ in range(dim):
                    self.assertIsInstance(current_type, PArrayType)
                    assert isinstance(current_type, PArrayType)
                    current_type = current_type.element_type
                
                self.assertIsInstance(current_type, PType)
                assert isinstance(current_type, PType)
                self.assertEqual(current_type.type_string, "i32")

    def test_array_type_mixed_declarations(self):
        """Test array declarations with mixed types and initializations"""
        code = """
        i32[] nums1;
        i32[] nums2 = new i32[5];
        i32[][] matrix1;
        i32[][] matrix2 = new i32[3][];
        """
        ast = self.parse_source(code)
        
        # Check uninitialized single dimension array
        self.assertIsInstance(ast.statements[0], PVariableDeclaration)
        assert isinstance(ast.statements[0], PVariableDeclaration)
        self.assertIsInstance(ast.statements[0].var_type, PArrayType)
        self.assertIsNone(ast.statements[0].initial_value)
        
        # Check initialized single dimension array
        self.assertIsInstance(ast.statements[1], PVariableDeclaration)
        assert isinstance(ast.statements[1], PVariableDeclaration)
        self.assertIsInstance(ast.statements[1].var_type, PArrayType)
        self.assertIsInstance(ast.statements[1].initial_value, PArrayInstantiation)
        
        # Check uninitialized multi-dimension array
        self.assertIsInstance(ast.statements[2], PVariableDeclaration)
        assert isinstance(ast.statements[2], PVariableDeclaration)
        self.assertIsInstance(ast.statements[2].var_type, PArrayType)
        assert isinstance(ast.statements[2].var_type, PArrayType)
        self.assertIsInstance(ast.statements[2].var_type.element_type, PArrayType)
        self.assertIsNone(ast.statements[2].initial_value)
        
        # Check initialized multi-dimension array
        self.assertIsInstance(ast.statements[3], PVariableDeclaration)
        assert isinstance(ast.statements[3], PVariableDeclaration)
        self.assertIsInstance(ast.statements[3].var_type, PArrayType)
        assert isinstance(ast.statements[3].var_type, PArrayType)
        self.assertIsInstance(ast.statements[3].var_type.element_type, PArrayType)
        self.assertIsInstance(ast.statements[3].initial_value, PArrayInstantiation)