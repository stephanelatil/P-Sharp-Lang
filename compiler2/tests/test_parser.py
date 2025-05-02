import pytest
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

class TestParserBase:
    """Base class for parser tests with common utilities."""

    def parse_source(self, source: str) -> PProgram:
        """Helper method to parse source code string."""
        parser = Parser(Lexer('test.ps', StringIO(source)))
        return parser.parse()

class TestParserUtilities(TestParserBase):
    """Test suite for Parser utility methods."""

    def setup_method(self):
        """Initialize parser with empty input for each test."""
        self.parser = Parser(Lexer('test.ps', StringIO('')))

    def test_precedence_initialization_complete(self):
        """Test that all operators have correct precedence relationships."""
        precedence = self.parser.precedence

        # Test arithmetic precedence
        assert precedence[BinaryOperation.TIMES] > precedence[BinaryOperation.PLUS]
        assert precedence[BinaryOperation.DIVIDE] > precedence[BinaryOperation.MINUS]
        assert precedence[BinaryOperation.TIMES] == precedence[BinaryOperation.MOD]
        assert precedence[BinaryOperation.TIMES] == precedence[BinaryOperation.DIVIDE]

        # Test logical operator precedence
        assert precedence[BinaryOperation.BOOL_AND] > precedence[BinaryOperation.BOOL_OR]
        assert precedence[BinaryOperation.LOGIC_AND] > precedence[BinaryOperation.LOGIC_OR]

        # Test comparison operators
        assert precedence[BinaryOperation.BOOL_EQ] == precedence[BinaryOperation.BOOL_NEQ]
        assert precedence[BinaryOperation.BOOL_GT] == precedence[BinaryOperation.BOOL_LT]

        # Test bool comparators have lower precedence
        for op in (BinaryOperation.PLUS, BinaryOperation.MINUS, BinaryOperation.TIMES,
                   BinaryOperation.DIVIDE, BinaryOperation.LOGIC_AND, BinaryOperation.LOGIC_OR,
                   BinaryOperation.MOD, BinaryOperation.XOR):
            assert precedence[BinaryOperation.BOOL_EQ] < precedence[op]

        # Test assignments then bool and/or have lowest precedence
        assert precedence[BinaryOperation.ASSIGN] == precedence[BinaryOperation.COPY]
        for op in BinaryOperation:
            if op in (BinaryOperation.ASSIGN, BinaryOperation.COPY):
                continue
            assert precedence[op] > precedence[BinaryOperation.ASSIGN]
            if op in (BinaryOperation.BOOL_AND, BinaryOperation.BOOL_OR):
                continue
            assert precedence[op] > precedence[BinaryOperation.BOOL_AND]
            assert precedence[op] > precedence[BinaryOperation.BOOL_OR]

        # Test bitwise operators
        assert precedence[BinaryOperation.SHIFT_LEFT] > precedence[BinaryOperation.PLUS]
        assert precedence[BinaryOperation.SHIFT_LEFT] == precedence[BinaryOperation.SHIFT_RIGHT]

    def test_binary_ops_mapping_complete(self):
        """Test that all binary operators are correctly mapped."""
        binary_ops = self.parser.unary_binary_ops

        # Test arithmetic operators
        assert binary_ops[LexemeType.OPERATOR_BINARY_PLUS] == BinaryOperation.PLUS
        assert binary_ops[LexemeType.OPERATOR_BINARY_MINUS] == BinaryOperation.MINUS
        assert binary_ops[LexemeType.OPERATOR_BINARY_TIMES] == BinaryOperation.TIMES
        assert binary_ops[LexemeType.OPERATOR_BINARY_DIV] == BinaryOperation.DIVIDE

        # Test comparison operators
        assert binary_ops[LexemeType.OPERATOR_BINARY_BOOL_EQ] == BinaryOperation.BOOL_EQ
        assert binary_ops[LexemeType.OPERATOR_BINARY_BOOL_NEQ] == BinaryOperation.BOOL_NEQ

        # Test logical operators
        assert binary_ops[LexemeType.OPERATOR_BINARY_BOOL_AND] == BinaryOperation.BOOL_AND
        assert binary_ops[LexemeType.OPERATOR_BINARY_BOOL_OR] == BinaryOperation.BOOL_OR

        # Test bitwise operators
        assert binary_ops[LexemeType.OPERATOR_BINARY_AND] == BinaryOperation.LOGIC_AND
        assert binary_ops[LexemeType.OPERATOR_BINARY_OR] == BinaryOperation.LOGIC_OR
        assert binary_ops[LexemeType.OPERATOR_BINARY_XOR] == BinaryOperation.XOR

    def test_type_keywords_complete(self):
        """Test that all type keywords are recognized."""
        type_keywords = self.parser.type_keywords

        assert LexemeType.KEYWORD_TYPE_VOID in type_keywords
        assert LexemeType.KEYWORD_TYPE_INT8 in type_keywords
        assert LexemeType.KEYWORD_TYPE_INT16 in type_keywords
        assert LexemeType.KEYWORD_TYPE_INT32 in type_keywords
        assert LexemeType.KEYWORD_TYPE_INT64 in type_keywords
        assert LexemeType.KEYWORD_TYPE_CHAR in type_keywords
        assert LexemeType.KEYWORD_TYPE_UINT8 in type_keywords
        assert LexemeType.KEYWORD_TYPE_UINT16 in type_keywords
        assert LexemeType.KEYWORD_TYPE_UINT32 in type_keywords
        assert LexemeType.KEYWORD_TYPE_UINT64 in type_keywords
        assert LexemeType.KEYWORD_TYPE_FLOAT16 in type_keywords
        assert LexemeType.KEYWORD_TYPE_FLOAT32 in type_keywords
        assert LexemeType.KEYWORD_TYPE_FLOAT64 in type_keywords
        assert LexemeType.KEYWORD_TYPE_BOOLEAN in type_keywords
        assert LexemeType.KEYWORD_TYPE_STRING in type_keywords

class TestParserPrimaryExpressions(TestParserBase):
    """Test suite for primary expression parsing."""

    @pytest.mark.parametrize("source, expected_type, expected_value",[
            ("i32 x = 42;", "int", 42),
            ("f32 x = 3.14;", "float", 3.14),
            ("string x = \"hello\";", "string", "hello"),
            ("char x = 'a';", "char", ord("a")),
            ("bool x = true;", "bool", True),
            ("bool x = false;", "bool", False),
            ("MyClass x = null;", "null", None),
        ])
    def test_literal_values(self, source, expected_type, expected_value):
        """Test parsing of all types of literal values."""
        program = self.parse_source(source)
        decl = program.statements[0]
        assert isinstance(decl, PVariableDeclaration)
        assert isinstance(decl.initial_value, PLiteral)
        assert decl.initial_value.literal_type == expected_type
        assert decl.initial_value.value == expected_value

    @pytest.mark.parametrize("source",[
            "i32 simple;",
            "i32 camelCase;",
            "i32 PascalCase;",
            "i32 snake_case;",
            "i32 _leading_underscore;",
            "i32 with123numbers;",
            "i32 UPPER_CASE;",
        ])
    def test_identifiers(self, source):
        """Test parsing of different identifier patterns."""
        program = self.parse_source(source)
        decl = program.statements[0]
        assert isinstance(decl, PVariableDeclaration)

    @pytest.mark.parametrize("source",[
            "i32 x = (42);",
            "i32 x = ((42));",
            "i32 x = (1 + (2 * 3));",
            "bool x = (true and (false or true));",
        ])
    def test_grouped_expressions(self, source):
        """Test parsing of parenthesized expressions."""
        program = self.parse_source(source)
        assert isinstance(program.statements[0], PVariableDeclaration)

    @pytest.mark.parametrize("source",[
            "i32 x = (i32)3.14;",
            "f32 x = (f32)42;",
            "i64 x = (i64)(42 + 3);",
            "MyClass obj = (MyClass)other;",
        ])
    def test_cast_expressions(self, source):
        """Test parsing of type cast expressions."""
        program = self.parse_source(source)
        decl = program.statements[0]
        assert isinstance(decl, PVariableDeclaration)
        assert isinstance(decl.initial_value, PCast)

class TestParserOperators(TestParserBase):
    """Test suite for operator parsing."""

    @pytest.mark.parametrize("source, expected_op",[
            ("i32 x = 1 + 2;", BinaryOperation.PLUS),
            ("i32 x = 3 - 4;", BinaryOperation.MINUS),
            ("i32 x = 5 * 6;", BinaryOperation.TIMES),
            ("i32 x = 8 / 2;", BinaryOperation.DIVIDE),
            ("i32 x = 10 % 3;", BinaryOperation.MOD),
        ])
    def test_arithmetic_operators(self, source, expected_op):
        """Test parsing of arithmetic operators."""
        program = self.parse_source(source)
        decl = program.statements[0]
        assert isinstance(decl, PVariableDeclaration)
        #additional assertions to remove linter warnings
        assert isinstance(decl, PVariableDeclaration)
        assert isinstance(decl.initial_value, PBinaryOperation)
        assert decl.initial_value.operation == expected_op

    @pytest.mark.parametrize("source,expected_op",[
            ("bool x = a == b;", BinaryOperation.BOOL_EQ),
            ("bool x = a != b;", BinaryOperation.BOOL_NEQ),
            ("bool x = a < b;", BinaryOperation.BOOL_LT),
            ("bool x = a <= b;", BinaryOperation.BOOL_LEQ),
            ("bool x = a > b;", BinaryOperation.BOOL_GT),
            ("bool x = a >= b;", BinaryOperation.BOOL_GEQ),
        ])
    def test_comparison_operators(self,source, expected_op):
        """Test parsing of comparison operators."""
        program = self.parse_source(source)
        decl = program.statements[0]
        assert isinstance(decl, PVariableDeclaration)
        #additional assertions to remove linter warnings
        assert isinstance(decl, PVariableDeclaration)
        assert isinstance(decl.initial_value, PBinaryOperation)
        assert decl.initial_value.operation == expected_op

    @pytest.mark.parametrize("source, expected_op",[
            ("bool x = a and b;", BinaryOperation.BOOL_AND),
            ("bool x = a or b;", BinaryOperation.BOOL_OR),
            ("bool x = not a;", UnaryOperation.BOOL_NOT),
        ])
    def test_logical_operators(self, source, expected_op):
        """Test parsing of logical operators."""
        program = self.parse_source(source)
        decl = program.statements[0]
        assert isinstance(decl, PVariableDeclaration)
        if isinstance(expected_op, BinaryOperation):
            assert isinstance(decl.initial_value, PBinaryOperation)
        else:
            assert isinstance(decl.initial_value, PUnaryOperation)
        assert isinstance(decl.initial_value, (PUnaryOperation,PBinaryOperation))
        assert decl.initial_value.operation == expected_op

    @pytest.mark.parametrize("source, expected_op",[
            ("x += 5;", BinaryOperation.PLUS),
            ("x -= 5;", BinaryOperation.MINUS),
            ("x *= 5;", BinaryOperation.TIMES),
            ("x /= 5;", BinaryOperation.DIVIDE),
            ("x &= 5;", BinaryOperation.LOGIC_AND),
            ("x |= 5;", BinaryOperation.LOGIC_OR),
            ("x ^= 5;", BinaryOperation.XOR),
            ("x <<= 5;", BinaryOperation.SHIFT_LEFT),
            ("x >>= 5;", BinaryOperation.SHIFT_RIGHT)
        ])
    def test_assignment_operators(self, source, expected_op):
        """Test parsing of compound assignment operators."""
        program = self.parse_source(source)
        stmt = program.statements[0]
        assert isinstance(stmt, PAssignment)
        # Additional assertions to remove linter warnings
        assert isinstance(stmt, PAssignment)
        assert isinstance(stmt.value, PBinaryOperation)
        # Additional assertions to remove linter warnings
        assert isinstance(stmt.value, PBinaryOperation)
        assert stmt.value.operation == expected_op

    @pytest.mark.parametrize("source, expected_op", [
            ("x += 5 + 2;", BinaryOperation.PLUS),
            ("x += 5 - 3;", BinaryOperation.MINUS),
            ("x += 5 * 3;", BinaryOperation.TIMES),
            ("x += 5 / 3;", BinaryOperation.DIVIDE),
            ("x += 5 & 7;", BinaryOperation.LOGIC_AND),
            ("x += 5 | 2;", BinaryOperation.LOGIC_OR),
            ("x += 5 ^ 7;", BinaryOperation.XOR),
            ("x += 5 << 3;", BinaryOperation.SHIFT_LEFT),
            ("x += 5 >> 1;", BinaryOperation.SHIFT_RIGHT)
        ])
    def test_assignment_operators_secondary_value(self, source, expected_op):
        """Test parsing of compound assignment operators."""
        program = self.parse_source(source)
        stmt = program.statements[0]
        assert isinstance(stmt, PAssignment)
        assert isinstance(stmt.value, PBinaryOperation)
        assert stmt.value.operation == BinaryOperation.PLUS
        assert isinstance(stmt.value.left, PIdentifier)
        assert isinstance(stmt.value.right, PBinaryOperation)
        assert stmt.value.right.operation == expected_op

    @pytest.mark.parametrize("source, expected_op",[
            ("i32 x = a & b;", BinaryOperation.LOGIC_AND),
            ("i32 x = a | b;", BinaryOperation.LOGIC_OR),
            ("i32 x = a ^ b;", BinaryOperation.XOR),
            ("i32 x = a << 2;", BinaryOperation.SHIFT_LEFT),
            ("i32 x = a >> 2;", BinaryOperation.SHIFT_RIGHT),
        ])
    def test_bitwise_operators(self, source, expected_op):
        """Test parsing of bitwise operators."""
        program = self.parse_source(source)
        decl = program.statements[0]
        assert isinstance(decl, PVariableDeclaration)
        assert isinstance(decl.initial_value, PBinaryOperation)
        assert decl.initial_value.operation == expected_op

    @pytest.mark.parametrize("source, expected_op",[
            ("i32 x = 1 + 2 * 3;", BinaryOperation.PLUS),
            ("i32 x = (1 + 2) * 3;", BinaryOperation.TIMES),
            ("bool x = a and b or c;", BinaryOperation.BOOL_OR),
            ("bool x = (a and b) or c;", BinaryOperation.BOOL_OR),
            ("i32 x = 1 << 2 + 3;", BinaryOperation.PLUS),
            ("i32 x = (1 << 2) + 3;", BinaryOperation.PLUS),
        ])
    def test_operator_precedence(self, source, expected_op):
        """Test that operators follow correct precedence rules."""
        program = self.parse_source(source)
        decl = program.statements[0]
        assert isinstance(decl, PVariableDeclaration)
        assert isinstance(decl.initial_value, PBinaryOperation)
        assert decl.initial_value.operation == expected_op

    @pytest.mark.parametrize("source, expected_op",[
            ("i32 x = -5;", UnaryOperation.MINUS),
            ("i32 x = ++x;", UnaryOperation.PRE_INCREMENT),
            ("i32 x = --x;", UnaryOperation.PRE_DECREMENT),
            ("i32 x = x++;", UnaryOperation.POST_INCREMENT),
            ("i32 x = x--;", UnaryOperation.POST_DECREMENT),
            ("bool x = not true;", UnaryOperation.BOOL_NOT),
            ("i32 x = !5;", UnaryOperation.LOGIC_NOT),
            ("i32 x = -(-5);", UnaryOperation.MINUS),
        ])
    def test_unary_operators(self, source, expected_op):
        """Test parsing of unary operators."""
        program = self.parse_source(source)
        decl = program.statements[0]
        assert isinstance(decl, PVariableDeclaration)
        assert isinstance(decl.initial_value, PUnaryOperation)
        assert decl.initial_value.operation == expected_op

    @pytest.mark.parametrize("expression, unary_op1, unary_op2",[
            ("! not x;", UnaryOperation.LOGIC_NOT, UnaryOperation.BOOL_NOT),
            ("!!x;", UnaryOperation.LOGIC_NOT, UnaryOperation.LOGIC_NOT),
            ("not !x;", UnaryOperation.BOOL_NOT, UnaryOperation.LOGIC_NOT),
            ("!--x;", UnaryOperation.LOGIC_NOT, UnaryOperation.PRE_DECREMENT)
        ]
)
    def test_unary_chaining(self, expression, unary_op1, unary_op2):
        program = self.parse_source(expression)
        expr = program.statements[0]
        assert isinstance(expr, PUnaryOperation)
        assert expr.operation == unary_op1
        assert isinstance(expr.operand, PUnaryOperation)
        assert expr.operand.operation == unary_op2

    @pytest.mark.parametrize("source, expected_op",[
            ("i32 x = -42;", UnaryOperation.MINUS),
            ("bool x = not true;", UnaryOperation.BOOL_NOT),
            ("i32 x = !5;", UnaryOperation.LOGIC_NOT),
            ("i32 x = !!!true;", UnaryOperation.LOGIC_NOT),
            ("i32 x = -(-(-5));", UnaryOperation.MINUS),
        ])
    def test_basic_unary_operations(self, source, expected_op):
        """Test basic unary operations with straightforward usage."""
        program = self.parse_source(source)
        var_decl = program.statements[0]
        assert isinstance(var_decl, PVariableDeclaration)
        assert isinstance(var_decl.initial_value, PUnaryOperation)
        assert var_decl.initial_value.operation == expected_op

    @pytest.mark.parametrize("source",[
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
        ])
    def test_unary_operations_in_control_structures(self, source):
        """Test unary operations within control flow statements."""
        program = self.parse_source(source)
        assert any(isinstance(stmt, (PWhileStatement, PIfStatement, PForStatement)) \
                        for stmt in program.statements)

    @pytest.mark.parametrize("source, expected_op",[
            ("arr[x++] = 1;", UnaryOperation.POST_INCREMENT),
            ("arr[x--] = 1;", UnaryOperation.POST_DECREMENT),
            ("arr[++x] = 1;", UnaryOperation.PRE_INCREMENT),
            ("arr[--x] = 1;", UnaryOperation.PRE_DECREMENT),
            ("arr[-x] = 1;", UnaryOperation.MINUS),
            ("arr[!x] = 1;", UnaryOperation.LOGIC_NOT),
            ("arr[not x] = 1;", UnaryOperation.BOOL_NOT),
        ])
    def test_unary_operations_with_arrays(self, source, expected_op):
        """Test unary operations in array contexts."""
        program = self.parse_source(source)
        stmnt = program.statements[0]
        assert isinstance(stmnt, PAssignment)
        assert isinstance(stmnt.target, PArrayIndexing)
        assert isinstance(stmnt.target.index, PUnaryOperation)
        assert stmnt.target.index.operation == expected_op


    @pytest.mark.parametrize("source",[
            """
            obj.process(x++).validate(!(--y));
            """,
            """
            obj.method1(!x).method2(--y);
            """,
            """
            getValue().process(x++);
            """
        ])
    def test_unary_operations_with_method_calls(self, source):
        """Test unary operations in method call contexts."""
        program = self.parse_source(source)
        assert any(isinstance(stmt, (PMethodCall, PFunctionCall)) \
                        for stmt in program.statements)

    @pytest.mark.parametrize("source",[
            "i32 y = -(-(-x)) + !(--y) * (x++ - y--);"
            "i32 x = --x + x++;",
            "i32 y = -x + !y;"
        ])
    def test_complex_unary_operation_combinations(self, source):
        """Test complex combinations of unary operations."""
        program = self.parse_source(source)
        stmnt = program.statements[0]
        assert isinstance(stmnt, PVariableDeclaration)
        assert isinstance(stmnt.initial_value, PBinaryOperation)
        assert isinstance(stmnt.initial_value.left, PUnaryOperation)

    @pytest.mark.parametrize("source",[
            "42++;",  # Increment on literal
            "++42;",  # Pre-increment on literal
            "x+ +;",  # Invalid spacing
            "!;",     # Missing operand
            "x = ++ --;"  # Invalid sequence
        ])
    def test_unary_operation_error_cases(self, source):
        """Test invalid unary operation combinations."""
        with pytest.raises(ParserError):
            self.parse_source(source)

    @pytest.mark.parametrize("source",[
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
        ])
    def test_basic_discard_assignments(self, source):
        """Test basic discard assignment patterns to ensure core functionality works."""
        program = self.parse_source(source)
        
        stmt = program.statements[0]
        assert isinstance(stmt, PDiscard)
        assert stmt.node_type == NodeType.DISCARD
        assert isinstance(stmt.expression, PExpression)

    @pytest.mark.parametrize("source",[
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
        ])
    def test_discard_invalid(self, source):
        """Invalid cases that should raise ParserError"""
        with pytest.raises(ParserError):
            self.parse_source(source)

class TestParserControlFlow(TestParserBase):
    """Test suite for control flow statement parsing."""

    @pytest.mark.parametrize("source",[
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
        ])
    def test_if_statement_variations(self, source):
        """Test parsing of various if statement forms."""
        program = self.parse_source(source)
        assert isinstance(program.statements[0], PIfStatement)

    @pytest.mark.parametrize("source",[
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
        ])
    def test_while_loop_variations(self, source):
        """Test parsing of various while loop forms."""
        program = self.parse_source(source)
        while_stmt = program.statements[0]
        assert isinstance(while_stmt, PWhileStatement)
        assert isinstance(while_stmt.condition, PExpression)
        assert isinstance(while_stmt.body, PBlock)

    @pytest.mark.parametrize("source",[
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
        ])
    def test_for_loop_variations(self, source):
        """Test parsing of various for loop forms."""
        program = self.parse_source(source)
        for_stmt = program.statements[0]
        assert isinstance(for_stmt, PForStatement)
        assert isinstance(for_stmt.body, PBlock)

    @pytest.mark.parametrize("source",[
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
        ])
    def test_break_continue_statements(self, source):
        """Test parsing of break and continue statements in different contexts."""
        program = self.parse_source(source)
        loop = program.statements[0]
        assert isinstance(loop, (PWhileStatement, PForStatement))

    @pytest.mark.parametrize("source",[
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
        ])
    def test_assert_statement_variations(self, source):
        program = self.parse_source(source)
        assert_stmt = program.statements[0]
        assert isinstance(assert_stmt, PAssertStatement)
        assert isinstance(assert_stmt.condition, PExpression)

    @pytest.mark.parametrize("source",[
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
        ])
    def test_ternary_operation_variations(self, source):
        """Test parsing of ternary operations in different contexts."""
        program = self.parse_source(source)
        var_decl = program.statements[0]
        assert isinstance(var_decl, PVariableDeclaration)
        assert isinstance(var_decl.initial_value, PTernaryOperation)
                
    def test_nested_ternary(self):
        # Nested Expression
        source="i32 x = a ? c ? a : c : b;"
        program = self.parse_source(source)
        var_decl = program.statements[0]
        assert isinstance(var_decl, PVariableDeclaration)
        assert isinstance(var_decl.initial_value, PTernaryOperation)
        assert isinstance(var_decl.initial_value.true_value, PTernaryOperation)
        assert isinstance(var_decl.initial_value.false_value, PIdentifier)


    @pytest.mark.parametrize("source",[
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
        ])
    def test_invalid_control_structures(self, source):
        """Test that invalid control structure syntax raises appropriate errors."""
        with pytest.raises(ParserError):
            self.parse_source(source)

    @pytest.mark.parametrize("source",[
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
        ])
    def test_break_continue_outside_loop(self, source):
        """Test that break and continue statements raise errors when used outside loops."""
        with pytest.raises(ParserError) as context:
            self.parse_source(source)
        # Verify error message mentions being outside loop
        assert "loop" in str(context.exconly()).lower()

    @pytest.mark.parametrize("source",[
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
        ])
    def test_return_outside_function(self, source):
        """Test that return statements raise errors when used outside functions."""
        with pytest.raises(ParserError) as context:
            self.parse_source(source)
        # Verify error message mentions being outside function
        assert "function" in str(context.exconly()).lower()

    @pytest.mark.parametrize("source",[
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
        ])
    def test_valid_control_flow_contexts(self, source):
        """Test that break, continue, and return statements work correctly in valid contexts."""
        # Should parse without raising exceptions
        program = self.parse_source(source)
        assert program is not None

class TestParserFunctionDefinitions(TestParserBase):
    """Test suite for function definition parsing."""

    @pytest.mark.parametrize("source",[
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
        ])
    def test_function_declaration_variations(self, source):
        """Test parsing of various function declaration patterns."""
        program = self.parse_source(source)
        func = program.statements[0]
        assert isinstance(func, PFunction)
        assert isinstance(func.body, PBlock)

    @pytest.mark.parametrize("source",[
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
        ])
    def test_function_call_variations(self, source):
        """Test parsing of various function call patterns."""
        program = self.parse_source(source)
        call = program.statements[0]
        assert isinstance(call, PFunctionCall)

    @pytest.mark.parametrize("source",[
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
        ])
    def test_return_statement_variations(self, source):
        """Test parsing of return statements with different patterns."""
        program = self.parse_source(source)
        func = program.statements[0]
        assert isinstance(func, PFunction)
        # Find the return statement in the function body
        return_stmt = func.body.statements[-1]
        assert isinstance(return_stmt, PReturnStatement)

class TestParserClassDefinitions(TestParserBase):
    """Test suite for class definition parsing."""

    @pytest.mark.parametrize("source",[
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
        ])
    def test_class_declaration_variations(self, source):
        """Test parsing of various class declaration patterns."""
        program = self.parse_source(source)
        class_def = program.statements[0]
        assert isinstance(class_def, PClass)

    def test_multi_method_class(self):
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
        program = self.parse_source(source)
        class_def = program.statements[0]
        assert isinstance(class_def, PClass)

        #test properties
        assert len(class_def.fields) == 2
        for i,(typ, name) in enumerate([('i32[]', 'elements'), ("i32","size")]):
            assert isinstance(class_def.fields[i], PClassField)
            assert typ == str(class_def.fields[i].var_type)
            assert name == class_def.fields[i].name

        #test methods
        assert len(class_def.methods) == 3
        for i,(return_type, name) in enumerate([('void','push'), ('i32', 'pop'), ('bool', 'isEmpty')]):
            assert isinstance(class_def.methods[i], PFunction)
            assert return_type == str(class_def.methods[i].return_type)
            assert name == class_def.methods[i].name



    @pytest.mark.parametrize("source",[
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
        ])
    def test_method_call_variations(self, source):
        """Test parsing of various method call patterns."""
        program = self.parse_source(source)
        stmt = program.statements[0]
        assert isinstance(stmt, (PMethodCall,PFunctionCall))

    @pytest.mark.parametrize("source",[
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
        ])
    def test_invalid_class_definitions(self, source):
        """Test that invalid class definitions raise appropriate errors."""
        with pytest.raises(ParserError):
            self.parse_source(source)

    def test_class_initialization_basic(self):
        """Test basic class initialization without parameters"""
        code = "MyClass instance = new MyClass();"
        ast = self.parse_source(code)
        
        var_decl = ast.statements[0]
        assert isinstance(var_decl, PVariableDeclaration)
        assert var_decl.name == "instance"
        assert isinstance(var_decl.initial_value, PObjectInstantiation)
        assert str(var_decl.initial_value.class_type) == "MyClass"

    @pytest.mark.parametrize("type_name",["i32", "f32", "bool", "string", "char"])
    def test_array_initialization_primitive_types(self, type_name):
        """Test array initialization with different primitive types"""
        code = f"{type_name}[] arr = new {type_name}[10];"
        ast = self.parse_source(code)
        
        var_decl = ast.statements[0]
        assert isinstance(var_decl, PVariableDeclaration)
        assert isinstance(var_decl.var_type, PArrayType)
        assert var_decl.var_type.element_type.type_string == type_name
        assert isinstance(var_decl.initial_value, PArrayInstantiation)
        assert isinstance(var_decl.initial_value.element_type, PType)
        assert var_decl.initial_value.element_type.type_string == type_name

    def test_array_initialization_custom_types(self):
        """Test array initialization with custom class types"""
        code = "MyClass[] objects = new MyClass[5];"
        ast = self.parse_source(code)
        
        var_decl = ast.statements[0]
        assert isinstance(var_decl, PVariableDeclaration)
        assert isinstance(var_decl.var_type, PArrayType)
        assert isinstance(var_decl.var_type.element_type, PType)
        assert var_decl.var_type.element_type.type_string == "MyClass"
        assert isinstance(var_decl.initial_value, PArrayInstantiation)
        assert var_decl.initial_value.element_type.type_string == "MyClass"

    def test_array_initialization_variable_size(self):
        """Test array initialization with variable size expression"""
        code = """
        i32 size = 10;
        i64[] arr = new i64[size];
        """
        ast = self.parse_source(code)
        
        arr_decl = ast.statements[1]
        assert isinstance(arr_decl, PVariableDeclaration)
        assert isinstance(arr_decl.initial_value, PArrayInstantiation)
        size_expr = arr_decl.initial_value.size
        assert isinstance(size_expr, PIdentifier)
        assert size_expr.name == "size"

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
        assert isinstance(assign_stmt, PAssignment)
        assert isinstance(assign_stmt.target, PArrayIndexing)
        assert isinstance(assign_stmt.target.index, PLiteral)
        assert assign_stmt.target.index.value == 0
        
        # Test reading from array index
        read_decl = ast.statements[2]
        assert isinstance(read_decl, PVariableDeclaration)
        assert isinstance(read_decl.initial_value, PArrayIndexing)
        assert isinstance(read_decl.initial_value.index, PLiteral)
        assert read_decl.initial_value.index.value == 1

    def test_array_indexing_nested(self):
        """Test nested array indexing operations"""
        code = "i32[][] matrix = new i32[3][];"
        ast = self.parse_source(code)
        
        var_decl = ast.statements[0]
        assert isinstance(var_decl, PVariableDeclaration)
        assert isinstance(var_decl.var_type, PArrayType)
        assert isinstance(var_decl.var_type.element_type, PArrayType)
        assert isinstance(var_decl.var_type.element_type.element_type, PType)
        assert var_decl.var_type.element_type.element_type.type_string == "i32"

    def test_array_indexing_expressions(self):
        """Test array indexing with complex expressions"""
        code = """
        i32[] arr = new i32[10];
        arr[2 + 3] = arr[1 * 2];
        """
        ast = self.parse_source(code)
        
        assign_stmt = ast.statements[1]
        assert isinstance(assign_stmt, PAssignment)
        assert isinstance(assign_stmt.target, PArrayIndexing)
        assert isinstance(assign_stmt.target.array, PIdentifier)
        assert assign_stmt.target.array.name == "arr"
        assert isinstance(assign_stmt.value, PArrayIndexing)
        assert isinstance(assign_stmt.value.array, PIdentifier)
        assert assign_stmt.value.array.name == "arr"

    def test_array_type_single_dimension(self):
        """Test single dimension array type declarations"""
        code = """
        i32[] numbers;
        string[] words;
        MyClass[] objects;
        """
        ast = self.parse_source(code)
        
        for stmt in ast.statements:
            assert isinstance(stmt, PVariableDeclaration)
            assert stmt.initial_value is None
            assert isinstance(stmt.var_type, PArrayType)
            assert isinstance(stmt.var_type.element_type, PType)

    @pytest.mark.parametrize("dim", range(1,4))
    def test_array_type_multiple_dimensions(self, dim):
        """Test multi-dimensional array type declarations"""
        type_decl = "i32" + "[]" * dim
        code = f"{type_decl} arr;"
        ast = self.parse_source(code)
        
        var_decl = ast.statements[0]
        assert isinstance(var_decl, PVariableDeclaration)
        current_type = var_decl.var_type
        
        # Verify each dimension of the array type
        for _ in range(dim):
            assert isinstance(current_type, PArrayType)
            current_type = current_type.element_type
        
        assert isinstance(current_type, PType)
        assert current_type.type_string == "i32"

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
        assert isinstance(ast.statements[0], PVariableDeclaration)
        assert isinstance(ast.statements[0].var_type, PArrayType)
        assert ast.statements[0].initial_value is None
        
        # Check initialized single dimension array
        assert isinstance(ast.statements[1], PVariableDeclaration)
        assert isinstance(ast.statements[1].var_type, PArrayType)
        assert isinstance(ast.statements[1].initial_value, PArrayInstantiation)
        
        # Check uninitialized multi-dimension array
        assert isinstance(ast.statements[2], PVariableDeclaration)
        assert isinstance(ast.statements[2].var_type, PArrayType)
        assert isinstance(ast.statements[2].var_type.element_type, PArrayType)
        assert ast.statements[2].initial_value is None
        
        # Check initialized multi-dimension array
        assert isinstance(ast.statements[3], PVariableDeclaration)
        assert isinstance(ast.statements[3].var_type, PArrayType)
        assert isinstance(ast.statements[3].var_type.element_type, PArrayType)
        assert isinstance(ast.statements[3].initial_value, PArrayInstantiation)
        

class TestParserNamespace(TestParserBase):
    """Test suite for `namespace` declarations."""

    def test_default_namespace(self):
        """When no namespace is declared, PProgram.namespace should be 'Default'."""
        program = self.parse_source("")
        assert program.namespace_name == "Default"

    def test_valid_namespace_declaration(self):
        """A single namespace at the top should be parsed correctly."""
        src = "namespace Alpha.Beta.Gamma; i32 x = 42;"
        program = self.parse_source(src)
        assert program.namespace_name == "Alpha.Beta.Gamma"
        # also make sure parsing continues normally
        assert isinstance(program.statements[0], PVariableDeclaration)

    @pytest.mark.parametrize("src", [
        # more than one namespace
        "namespace A; namespace B;",
        # namespace not at top
        "i32 x = 1; namespace A.B;",
        # missing semicolon
        "namespace A.B.C",
        # leading dot
        "namespace .Foo.Bar;",
        # trailing dot
        "namespace Foo.Bar.;",
        # empty segment
        "namespace Foo..Bar;",
    ])
    def test_invalid_namespace_syntax(self, src):
        """These should all raise ParserError."""
        with pytest.raises(ParserError):
            self.parse_source(src)
