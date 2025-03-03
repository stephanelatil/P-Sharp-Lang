from unittest import TestCase
from io import StringIO
from lexer import Lexer, LexemeType, LexerError, Position, CharacterStream

class TestPosition(TestCase):
    """
    Test suite for the Position class which tracks line numbers, columns, and indices
    in source code.
    """

    def setUp(self) -> None:
        """Initialize a fresh Position instance before each test."""
        self.position = Position()

    def test_position_initializes_with_default_values(self) -> None:
        """Test that Position initializes with expected default values (line 1, column 1, index 0)."""
        self.assertEqual(self.position.line, 1)
        self.assertEqual(self.position.column, 1)
        self.assertEqual(self.position.index, 0)

    def test_position_advances_correctly_with_normal_characters(self) -> None:
        """Test that Position advances correctly with regular characters."""
        # Advance through a normal character
        self.position.advance('a')
        self.assertEqual(self.position.line, 1)
        self.assertEqual(self.position.column, 2)
        self.assertEqual(self.position.index, 1)

    def test_position_handles_newline_characters_correctly(self) -> None:
        """Test that Position correctly updates when encountering newline characters."""
        # First advance some regular characters
        for _ in range(3):
            self.position.advance('a')

        # Then hit a newline
        self.position.advance('\n')

        self.assertEqual(self.position.line, 2)  # Line should increment
        self.assertEqual(self.position.column, 1)  # Column should reset
        self.assertEqual(self.position.index, 4)  # Index should still increment

    def test_position_copy_creates_independent_instance(self) -> None:
        """Test that Position.copy() creates a completely independent copy."""
        # Advance the original position
        self.position.advance('a')
        self.position.advance('b')

        # Create a copy
        copied_position = self.position.copy()

        # Verify copy has same values
        self.assertEqual(copied_position.line, self.position.line)
        self.assertEqual(copied_position.column, self.position.column)
        self.assertEqual(copied_position.index, self.position.index)

        # Modify original and verify copy remains unchanged
        self.position.advance('c')
        self.assertNotEqual(copied_position.column, self.position.column)
        self.assertNotEqual(copied_position.index, self.position.index)

    def test_position_arithmetic_addition_works_correctly(self) -> None:
        """Test that Position addition creates correct new position."""
        # Start position (1,1,0)
        result = self.position + 5

        # New position should be offset by 5 columns
        self.assertEqual(result.line, 1)
        self.assertEqual(result.column, 6)
        self.assertEqual(result.index, 5)

        # Original position should be unchanged
        self.assertEqual(self.position.line, 1)
        self.assertEqual(self.position.column, 1)
        self.assertEqual(self.position.index, 0)


class TestCharacterStream(TestCase):
    """
    Test suite for the CharacterStream class which handles reading and buffering
    characters from an input stream.
    """

    def setUp(self) -> None:
        """Initialize a fresh CharacterStream instance before each test."""
        self.create_stream("")

    def create_stream(self, content: str) -> None:
        """Helper method to create a new stream with given content."""
        self.stream = CharacterStream(StringIO(content), 'test.cs')

    def test_empty_stream_returns_none_on_peek(self) -> None:
        """Test that peeking an empty stream returns None."""
        self.assertIsNone(self.stream.peek())
        self.assertTrue(self.stream.eof)

    def test_stream_handles_single_character_correctly(self) -> None:
        """Test reading a single character from the stream."""
        self.create_stream("a")

        # Peek should show 'a' but not advance
        self.assertEqual(self.stream.peek(), "a")
        self.assertEqual(self.stream.position().column, 1)

        # Advance should return 'a' and move position
        self.assertEqual(self.stream.advance(), "a")
        self.assertEqual(self.stream.position().column, 2)

    def test_stream_handles_multiple_characters_correctly(self) -> None:
        """Test reading multiple characters from the stream."""
        self.create_stream("abc")

        # Read each character and verify position
        self.assertEqual(self.stream.advance(), "a")
        self.assertEqual(self.stream.position().column, 2)

        self.assertEqual(self.stream.advance(), "b")
        self.assertEqual(self.stream.position().column, 3)

        self.assertEqual(self.stream.advance(), "c")
        self.assertEqual(self.stream.position().column, 4)

    def test_stream_peek_with_different_lookahead_amounts(self) -> None:
        """Test peeking ahead multiple characters in the stream."""
        self.create_stream("abcd")

        # Peek at different positions without advancing
        self.assertEqual(self.stream.peek(0), "a")
        self.assertEqual(self.stream.peek(1), "b")
        self.assertEqual(self.stream.peek(2), "c")
        self.assertEqual(self.stream.peek(3), "d")

        # Position should not have changed
        self.assertEqual(self.stream.position().column, 1)

    def test_stream_handles_newlines_correctly(self) -> None:
        """Test that stream correctly handles newline characters."""
        self.create_stream("a\nb\nc")

        # Read through newlines and verify position
        self.assertEqual(self.stream.advance(), "a")
        self.assertEqual(self.stream.position().line, 1)
        self.assertEqual(self.stream.position().column, 2)

        self.assertEqual(self.stream.advance(), "\n")
        self.assertEqual(self.stream.position().line, 2)
        self.assertEqual(self.stream.position().column, 1)

        self.assertEqual(self.stream.advance(), "b")
        self.assertEqual(self.stream.position().line, 2)
        self.assertEqual(self.stream.position().column, 2)

    def test_stream_raises_eof_error_on_advance_past_end(self) -> None:
        """Test that advancing past the end of stream raises EOFError."""
        self.create_stream("a")

        # Read the only character
        self.stream.advance()

        # Attempting to read past end should raise EOFError
        with self.assertRaises(EOFError):
            self.stream.advance()

    def test_stream_eof_flag_sets_correctly(self) -> None:
        """Test that EOF flag is set correctly when reaching end of stream."""
        self.create_stream("a")

        # Initially EOF should be False
        self.assertFalse(self.stream.eof)

        # Read content
        self.stream.peek()
        self.assertFalse(self.stream.eof)
        # Read past the end of content
        self.stream.peek(1)
        self.assertTrue(self.stream.eof)
        # Read past the end of content
        self.stream.peek(100)
        self.assertTrue(self.stream.eof)

    def test_stream_position_tracking_with_mixed_content(self) -> None:
        """Test position tracking with mix of characters, newlines, and multiple peeks."""
        self.create_stream("abc\ndef\nghi")

        # Track position through mixed content
        self.assertEqual(self.stream.advance(), "a")  # (1,2)
        self.assertEqual(self.stream.advance(), "b")  # (1,3)
        self.assertEqual(self.stream.advance(), "c")  # (1,4)
        self.assertEqual(self.stream.advance(), "\n") # (2,1)
        self.assertEqual(self.stream.advance(), "d")  # (2,2)

        pos = self.stream.position()
        self.assertEqual(pos.line, 2)
        self.assertEqual(pos.column, 2)
        self.assertEqual(pos.index, 5)

    def test_stream_buffer_management(self) -> None:
        """Test that the stream's buffer is managed correctly with mixed peek and advance operations."""
        self.create_stream("abcdef")

        # Peek ahead several characters
        self.assertEqual(self.stream.peek(3), "d")

        # Buffer should contain 4 characters now
        self.assertEqual(len(self.stream.buffer), 4)

        # Advance and verify buffer shrinks
        self.stream.advance()  # 'a'
        self.stream.advance()  # 'b'
        self.assertEqual(len(self.stream.buffer), 2)

        # Peek again should refill buffer
        self.assertEqual(self.stream.peek(2), "e")
        self.assertEqual(len(self.stream.buffer), 3)

class LexerTests(TestCase):
    def setUp(self) -> None:
        return super().setUp()

    def tearDown(self) -> None:
        return super().tearDown()

    def test_block_comments_with_many_or_few_chars_and_unicode_chars(self):
        blocks = ["/*ThisIsAComment*/",
                "/*\r\n\r\n*/",
                "/*Comment with \t various whitespaces\ntest\ttest\t\n\t\n\r\r test \n\n*/",
                "/*\n*/",
                "/*¡£©¶œβюॴ௴ඕ*/"]
        for block_comment in blocks:
            with self.subTest(block_comment=block_comment):
                lexer = Lexer('test.ps', StringIO(block_comment))
                lexemes = list(lexer.lex(include_comments=True))
                self.assertEqual(len(lexemes), 1)
                self.assertEqual(lexemes[0].type, LexemeType.COMMENT_MULTILINE)

    def test_line_comments_with_various_content(self) -> None:
        """Test single-line comments with different content."""
        comments = [
            "// Simple comment\n",
            "// Simple comment without newline",
            "// Comment with symbols !@#$%^&*()\n",
            "// Comment with numbers 12345\n",
            "// Unicode content ¡£©¶œβ\n"
        ]
        for comment in comments:
            with self.subTest(comment=comment):
                lexer = Lexer('test.ps', StringIO(comment))
                lexemes = list(lexer.lex(include_comments=True))
                self.assertEqual(len(lexemes), 1)
                self.assertEqual(lexemes[0].type, LexemeType.COMMENT_SINGLELINE)

    def test_numeric_literals_integers(self) -> None:
        """Test various forms of integer literals."""
        test_cases = {
            "42": (LexemeType.NUMBER_INT, "42"),
            "0": (LexemeType.NUMBER_INT, "0"),
            "123_456": (LexemeType.NUMBER_INT, "123456"),
            "0xFF": (LexemeType.NUMBER_HEX, "0xFF"),
            "0xDEAD_BEEF": (LexemeType.NUMBER_HEX, "0xDEADBEEF")
        }
        for input_str, expected in test_cases.items():
            with self.subTest(input_str=input_str, expected=expected):
                lexer = Lexer('test.ps', StringIO(input_str))
                lexemes = list(lexer.lex())
                self.assertEqual(len(lexemes), 1)  # Number
                self.assertEqual(lexemes[0].type, expected[0])
                self.assertEqual(lexemes[0].value, expected[1])

    def test_numeric_literals_floats(self) -> None:
        """Test various forms of floating-point literals."""
        test_cases = {
            "3.14": (LexemeType.NUMBER_FLOAT, "3.14"),
            "0.0": (LexemeType.NUMBER_FLOAT, "0.0"),
            "1e10": (LexemeType.NUMBER_FLOAT, "1e10"),
            "1e+10": (LexemeType.NUMBER_FLOAT, "1e10"),
            "1.5e-10": (LexemeType.NUMBER_FLOAT, "1.5e-10"),
            "1_234.567_89": (LexemeType.NUMBER_FLOAT, "1234.56789"),
            "1.": (LexemeType.NUMBER_FLOAT, "1."), # Allows unterminated period
            "1__2_______3": (LexemeType.NUMBER_INT, "123") # Any number of underscores
        }
        for input_str, expected in test_cases.items():
            with self.subTest(input_str=input_str, expected=expected):
                lexer = Lexer('test.ps', StringIO(input_str))
                lexemes = list(lexer.lex())
                self.assertEqual(len(lexemes), 1)  # Float
                self.assertEqual(lexemes[0].type, expected[0])
                self.assertEqual(lexemes[0].value, expected[1])

    def test_invalid_numeric_literals(self) -> None:
        """Test that invalid numeric literals raise appropriate errors."""
        invalid_numbers = [
            "0x",      # Incomplete hex
            "0xG",     # Invalid hex digit
            "1e",      # Incomplete exponent
            "1e+",     # Incomplete exponent
            "1e1.5",   # Non-int exponent
            "1e1.",   # exponent with terminating period
            "1.5.2",   # Non-int exponent
        ]
        for num in invalid_numbers:
            with self.subTest(num=num):
                with self.assertRaises(LexerError):
                    lexer = Lexer('test.ps', StringIO(num))
                    list(lexer.lex())

    def test_string_literals_with_escapes(self) -> None:
        """Test string literals with various escape sequences."""
        test_cases = {
            '"Simple string"': '"Simple string"',
            '"String with \\"quotes\\""': '"String with \\"quotes\\""',
            '"String with \\n\\t\\r"': '"String with \\n\\t\\r"',
            '"Unicode string ¡£©¶œβ"': '"Unicode string ¡£©¶œβ"',
            '"Strings\\0 with escape sequences \\\\ \\\" \\\' \\n\\r\\f\\b\\x50"':
            '"Strings\\0 with escape sequences \\\\ \\\" \\\' \\n\\r\\f\\b\\x50"'
        }
        for input_str, expected in test_cases.items():
            with self.subTest(input_str=input_str, excepted=expected):
                lexer = Lexer('test.ps', StringIO(input_str))
                lexemes = list(lexer.lex())
                self.assertEqual(len(lexemes), 1)  # String
                self.assertEqual(lexemes[0].type, LexemeType.STRING_LITERAL)
                self.assertEqual(lexemes[0].value, expected)

    def test_character_literals(self) -> None:
        """Test character literals including escape sequences."""
        test_cases = {
            "'a'": LexemeType.NUMBER_CHAR,
            "'\\n'": LexemeType.NUMBER_CHAR,
            "'\\t'": LexemeType.NUMBER_CHAR,
            "'\\''": LexemeType.NUMBER_CHAR,
            "'\\\\'": LexemeType.NUMBER_CHAR,
            "'\\x41'": LexemeType.NUMBER_CHAR  # Hex escape
        }
        for input_str, expected_type in test_cases.items():
            with self.subTest(input_str=input_str, expected_type=expected_type):
                lexer = Lexer('test.ps', StringIO(input_str))
                lexemes = list(lexer.lex())
                self.assertEqual(len(lexemes), 1)  # Char
                self.assertEqual(lexemes[0].type, expected_type)
                self.assertEqual(lexemes[0].value, input_str)

    def test_invalid_character_literals(self) -> None:
        """Test that invalid character literals raise appropriate errors."""
        invalid_chars = [
            "'",       # Unterminated and empty
            "''",      # Empty
            "'ab'",    # Too long
            "'\\x'",   # Incomplete hex escape
            "'\\x0'",  # Incomplete hex escape
            "'\\xGG'"  # Invalid hex digits
            "'\\'",    # Empty escape sequence
            "'\\",     # Unterminated empty escape sequence
            "'\\n"     # Unterminated escape sequence
        ]
        for char in invalid_chars:
            with self.subTest(char=char):
                with self.assertRaises(LexerError):
                    lexer = Lexer('test.ps', StringIO(char))
                    list(lexer.lex())

    def test_operators_and_punctuation(self) -> None:
        """Test all operators and punctuation marks."""
        operators = {
            "+": LexemeType.OPERATOR_BINARY_PLUS,
            "+=": LexemeType.OPERATOR_BINARY_PLUSEQ,
            "-": LexemeType.OPERATOR_BINARY_MINUS,
            "-=": LexemeType.OPERATOR_BINARY_MINUSEQ,
            "*": LexemeType.OPERATOR_BINARY_TIMES,
            "*=": LexemeType.OPERATOR_BINARY_TIMESEQ,
            "/": LexemeType.OPERATOR_BINARY_DIV,
            "/=": LexemeType.OPERATOR_BINARY_DIVEQ,
            "&": LexemeType.OPERATOR_BINARY_AND,
            "&=": LexemeType.OPERATOR_BINARY_ANDEQ,
            "|": LexemeType.OPERATOR_BINARY_OR,
            "|=": LexemeType.OPERATOR_BINARY_OREQ,
            "^": LexemeType.OPERATOR_BINARY_XOR,
            "^=": LexemeType.OPERATOR_BINARY_XOREQ,
            "<<": LexemeType.OPERATOR_BINARY_SHL,
            "<<=": LexemeType.OPERATOR_BINARY_SHLEQ,
            ">>": LexemeType.OPERATOR_BINARY_SHR,
            ">>=": LexemeType.OPERATOR_BINARY_SHREQ
        }
        for op, expected_type in operators.items():
            with self.subTest(operator=op, expected_type=expected_type):
                lexer = Lexer('test.ps', StringIO(op))
                lexemes = list(lexer.lex())
                self.assertEqual(len(lexemes), 1)  # Operator
                self.assertEqual(lexemes[0].type, expected_type)
                self.assertEqual(lexemes[0].value, op)

        with self.assertRaises(LexerError):
            lexer = Lexer('test.ps', StringIO("@"))
            val = list(lexer.lex())

    def test_keywords(self) -> None:
        """Test all language keywords."""
        keywords = {
            "if": LexemeType.KEYWORD_CONTROL_IF,
            "else": LexemeType.KEYWORD_CONTROL_ELSE,
            "while": LexemeType.KEYWORD_CONTROL_WHILE,
            "for": LexemeType.KEYWORD_CONTROL_FOR,
            "return": LexemeType.KEYWORD_CONTROL_RETURN,
            "class": LexemeType.KEYWORD_OBJECT_CLASS,
            "null": LexemeType.KEYWORD_OBJECT_NULL,
            "true": LexemeType.KEYWORD_OBJECT_TRUE,
            "false": LexemeType.KEYWORD_OBJECT_FALSE
        }
        for keyword, expected_type in keywords.items():
            with self.subTest(keyword=keyword, expected_type=expected_type):
                lexer = Lexer('test.ps', StringIO(keyword))
                lexemes = list(lexer.lex())
                self.assertEqual(len(lexemes), 1)  # Keyword
                self.assertEqual(lexemes[0].type, expected_type)
                self.assertEqual(lexemes[0].value, keyword)

    def test_discard(self) -> None:
        """Test all language keywords."""
        test_case = {
            "_": [LexemeType.DISCARD],
            "_ = a()": [LexemeType.DISCARD, LexemeType.OPERATOR_BINARY_ASSIGN,
                        LexemeType.IDENTIFIER, LexemeType.PUNCTUATION_OPENPAREN,
                        LexemeType.PUNCTUATION_CLOSEPAREN],
            "f(_)": [LexemeType.IDENTIFIER, LexemeType.PUNCTUATION_OPENPAREN,
                     LexemeType.DISCARD ,LexemeType.PUNCTUATION_CLOSEPAREN],
            "_a": [LexemeType.IDENTIFIER]
        }
        for source, expected_types in test_case.items():
            with self.subTest(keyword=source, expected_type=expected_types):
                lexer = Lexer('test.ps', StringIO(source))
                lexemes = list(lexer.lex())
                self.assertEqual(len(lexemes), len(expected_types))  # Keyword
                self.assertListEqual([l.type for l in lexemes], expected_types)

    def test_identifiers(self) -> None:
        """Test valid and invalid identifier patterns."""
        valid_ids = [
            "identifier",
            "camelCase",
            "PascalCase",
            "snake_case",
            "_underscore",
            "with123numbers",
            "α_unicode",  # If Unicode identifiers are supported
            "contains___many__underscores______"
            "_" #single underscore for discard
        ]
        for identifier in valid_ids:
            with self.subTest(identifier=identifier):
                lexer = Lexer('test.ps', StringIO(identifier))
                lexemes = list(lexer.lex())
                self.assertEqual(len(lexemes), 1)  # Identifier
                self.assertEqual(lexemes[0].type, LexemeType.IDENTIFIER)
                self.assertEqual(lexemes[0].value, identifier)

    def test_invalid_identifiers(self) -> None:
        """Test that invalid identifiers raise appropriate errors."""
        invalid_ids = [
            "123identifier",    # Cannot start with number
            "__reserved",      # Cannot start with double underscore
        ]
        for identifier in invalid_ids:
            with self.subTest(identifier=identifier):
                with self.assertRaises(LexerError):
                    lexer = Lexer('test.ps', StringIO(identifier))
                    vals = list(lexer.lex())

    def test_invalid_string_literals(self) -> None:
        """Test that invalid string literals raise appropriate errors."""
        invalid_strings = [
            '"Unterminated string',           # Missing closing quote
            '"String with invalid \\escape"',   # Invalid escape sequence
            '"\n"',                           # Raw newline in string
            '"\\',                           # Raw newline in string
            '"\\x1"',                           # Raw newline in string
            '"String\vwith\\invalid\\controls"', # Invalid control characters
            '"'                               # Empty unterminated string
        ]
        for string_expr in invalid_strings:
            with self.subTest(string_expr=string_expr):
                with self.assertRaises(LexerError):
                    lexer = Lexer('test.ps', StringIO(string_expr))
                    val = list(lexer.lex())

    def test_partial_line_comments(self) -> None:
        """Test comments that occupy only part of a line with code before/after."""
        test_cases = [
            # Code before comment
            ("x = 42; // This is a comment\n",
             [LexemeType.IDENTIFIER, LexemeType.OPERATOR_BINARY_ASSIGN,
              LexemeType.NUMBER_INT, LexemeType.PUNCTUATION_SEMICOLON],
             [LexemeType.IDENTIFIER, LexemeType.OPERATOR_BINARY_ASSIGN,
              LexemeType.NUMBER_INT, LexemeType.PUNCTUATION_SEMICOLON,
              LexemeType.COMMENT_SINGLELINE]),

            # Code after comment on next line
            ("// First line comment\nx = 42;",
             [LexemeType.IDENTIFIER, LexemeType.OPERATOR_BINARY_ASSIGN,
              LexemeType.NUMBER_INT, LexemeType.PUNCTUATION_SEMICOLON],
             [LexemeType.COMMENT_SINGLELINE,
              LexemeType.IDENTIFIER, LexemeType.OPERATOR_BINARY_ASSIGN,
              LexemeType.NUMBER_INT, LexemeType.PUNCTUATION_SEMICOLON]),

            # Multiple comments and code segments
            ("x = 42; // First comment\ny = 73; // Second comment\n",
             [LexemeType.IDENTIFIER, LexemeType.OPERATOR_BINARY_ASSIGN,
              LexemeType.NUMBER_INT, LexemeType.PUNCTUATION_SEMICOLON,
              LexemeType.IDENTIFIER, LexemeType.OPERATOR_BINARY_ASSIGN,
              LexemeType.NUMBER_INT, LexemeType.PUNCTUATION_SEMICOLON],
             [LexemeType.IDENTIFIER, LexemeType.OPERATOR_BINARY_ASSIGN,
              LexemeType.NUMBER_INT, LexemeType.PUNCTUATION_SEMICOLON,
              LexemeType.COMMENT_SINGLELINE,
              LexemeType.IDENTIFIER, LexemeType.OPERATOR_BINARY_ASSIGN,
              LexemeType.NUMBER_INT, LexemeType.PUNCTUATION_SEMICOLON,
              LexemeType.COMMENT_SINGLELINE])
        ]

        for input_str, expected_types, expected_types_with_comments in test_cases:
            with self.subTest(input_str=input_str, expected_types=expected_types,
                              expected_types_with_comments=expected_types_with_comments):
                # Test without comments
                lexer = Lexer('test.ps', StringIO(input_str))
                lexemes = list(lexer.lex())
                actual_types = [lexeme.type for lexeme in lexemes]
                self.assertEqual(actual_types, expected_types)

                # Test with comments included
                lexer = Lexer('test.ps', StringIO(input_str))
                lexemes = list(lexer.lex(include_comments=True))
                actual_types = [lexeme.type for lexeme in lexemes]
                self.assertEqual(actual_types, expected_types_with_comments)

    def test_mixed_comments_types(self) -> None:
        """Test mixing of block and line comments in various configurations."""
        test_cases = [
            # Block comment followed by line comment
            ("/* Block comment */ // Line comment\n",
             [LexemeType.COMMENT_MULTILINE, LexemeType.COMMENT_SINGLELINE]),

            # Line comment inside block comment (should be part of block comment)
            ("/* Block contains\n // nested line comment\n */", [LexemeType.COMMENT_MULTILINE]),

            # Code with mixed comment types
            ("x = 42; /* block */ y = 73; // line\n",
             [LexemeType.IDENTIFIER, LexemeType.OPERATOR_BINARY_ASSIGN,
              LexemeType.NUMBER_INT, LexemeType.PUNCTUATION_SEMICOLON,
              LexemeType.COMMENT_MULTILINE,
              LexemeType.IDENTIFIER, LexemeType.OPERATOR_BINARY_ASSIGN,
              LexemeType.NUMBER_INT, LexemeType.PUNCTUATION_SEMICOLON,
              LexemeType.COMMENT_SINGLELINE]),

            # Complex mixing
            ("/* Start block\n" +
             "// Nested line\n" +
             "*/ // End line\n" +
             "x = 42; // Final line",
             [LexemeType.COMMENT_MULTILINE, LexemeType.COMMENT_SINGLELINE,
              LexemeType.IDENTIFIER, LexemeType.OPERATOR_BINARY_ASSIGN,
              LexemeType.NUMBER_INT, LexemeType.PUNCTUATION_SEMICOLON,
              LexemeType.COMMENT_SINGLELINE])
        ]
        for input_str, expected_types in test_cases:
            with self.subTest(input_str=input_str):
                lexer = Lexer('test.ps', StringIO(input_str))
                lexemes = list(lexer.lex(include_comments=True))
                actual_types = [lexeme.type for lexeme in lexemes]
                self.assertEqual(actual_types, expected_types)

    def test_invalid_block_comments(self) -> None:
        """Test invalid block comment formations."""
        invalid_comments = [
            "/* Unterminated block comment",
            "/*/",  # unterminated
        ]
        for comment in invalid_comments:
            with self.subTest(source=comment):
                with self.assertRaises(LexerError):
                    lexer = Lexer('test.ps', StringIO(comment))
                    val = list(lexer.lex())

    def test_complex_expressions(self) -> None:
        """Test lexing of complex expressions with multiple token types."""
        expressions = [
            ("x = 42 + y;", [LexemeType.IDENTIFIER, LexemeType.OPERATOR_BINARY_ASSIGN,
                            LexemeType.NUMBER_INT, LexemeType.OPERATOR_BINARY_PLUS,
                            LexemeType.IDENTIFIER, LexemeType.PUNCTUATION_SEMICOLON]),
            ("if (x <= 10) { return true; }", [LexemeType.KEYWORD_CONTROL_IF,
                                              LexemeType.PUNCTUATION_OPENPAREN,
                                              LexemeType.IDENTIFIER,
                                              LexemeType.OPERATOR_BINARY_BOOL_LEQ,
                                              LexemeType.NUMBER_INT,
                                              LexemeType.PUNCTUATION_CLOSEPAREN,
                                              LexemeType.PUNCTUATION_OPENBRACE,
                                              LexemeType.KEYWORD_CONTROL_RETURN,
                                              LexemeType.KEYWORD_OBJECT_TRUE,
                                              LexemeType.PUNCTUATION_SEMICOLON,
                                              LexemeType.PUNCTUATION_CLOSEBRACE])
        ]
        for expr, expected_types in expressions:
            with self.subTest(expr=expr, expected_types=expected_types):
                lexer = Lexer('test.ps', StringIO(expr))
                lexemes = list(lexer.lex())
                actual_types = [lexeme.type for lexeme in lexemes]  # Exclude EOF
                self.assertListEqual(actual_types, expected_types)

    def test_unary_operators_simple(self):
        test_cases = [("--", (LexemeType.OPERATOR_UNARY_DECREMENT,)),
                      ("++", (LexemeType.OPERATOR_UNARY_INCREMENT,)),
                      ("not", (LexemeType.OPERATOR_UNARY_BOOL_NOT,)),
                      ("!", (LexemeType.OPERATOR_UNARY_LOGIC_NOT,)),
                      ("x+++1", (LexemeType.IDENTIFIER,LexemeType.OPERATOR_UNARY_INCREMENT,
                                 LexemeType.OPERATOR_BINARY_PLUS, LexemeType.NUMBER_INT)),
                      ("-x---1", (LexemeType.OPERATOR_BINARY_MINUS, LexemeType.IDENTIFIER,
                                  LexemeType.OPERATOR_UNARY_DECREMENT,LexemeType.OPERATOR_BINARY_MINUS,
                                  LexemeType.NUMBER_INT)),]

        for expr, expected_ops in test_cases:
            with self.subTest(expr=expr, expected_ops=expected_ops):
                lexer = Lexer('test.ps', StringIO(expr))
                lexemes = tuple(lexeme.type for lexeme in lexer.lex())
                self.assertTupleEqual(lexemes, expected_ops)