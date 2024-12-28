from unittest import TestCase
from io import StringIO
from lexer import Lexer, LexemeType, LexerError

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
        for block in blocks:
            lexer = Lexer('test.ps', StringIO(block))
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
            "'\\x41'": LexemeType.NUMBER_CHAR  # Hex escape
        }
        for input_str, expected_type in test_cases.items():
            lexer = Lexer('test.ps', StringIO(input_str))
            lexemes = list(lexer.lex())
            self.assertEqual(len(lexemes), 1)  # Char
            self.assertEqual(lexemes[0].type, expected_type)
            self.assertEqual(lexemes[0].value, input_str)

    def test_invalid_character_literals(self) -> None:
        """Test that invalid character literals raise appropriate errors."""
        invalid_chars = [
            "'",       # Unterminated
            "''",      # Empty
            "'ab'",    # Too long
            "'\\x'",   # Incomplete hex escape
            "'\\x0'",  # Incomplete hex escape
            "'\\xGG'"  # Invalid hex digits
        ]
        for char in invalid_chars:
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
            lexer = Lexer('test.ps', StringIO(op))
            lexemes = list(lexer.lex())
            self.assertEqual(len(lexemes), 1)  # Operator
            self.assertEqual(lexemes[0].type, expected_type)
            self.assertEqual(lexemes[0].value, op)

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
            lexer = Lexer('test.ps', StringIO(keyword))
            lexemes = list(lexer.lex())
            self.assertEqual(len(lexemes), 1)  # Keyword
            self.assertEqual(lexemes[0].type, expected_type)
            self.assertEqual(lexemes[0].value, keyword)

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
        for id in valid_ids:
            lexer = Lexer('test.ps', StringIO(id))
            lexemes = list(lexer.lex())
            self.assertEqual(len(lexemes), 1)  # Identifier
            self.assertEqual(lexemes[0].type, LexemeType.IDENTIFIER)
            self.assertEqual(lexemes[0].value, id)

    def test_invalid_identifiers(self) -> None:
        """Test that invalid identifiers raise appropriate errors."""
        invalid_ids = [
            "123identifier",    # Cannot start with number
            "PS_GC__name",     # Cannot start with PS_GC__
            "__reserved",      # Cannot start with double underscore
        ]
        for id in invalid_ids:
            with self.assertRaises(LexerError):
                lexer = Lexer('test.ps', StringIO(id))
                vals = list(lexer.lex())

    def test_invalid_string_literals(self) -> None:
        """Test that invalid string literals raise appropriate errors."""
        invalid_strings = [
            '"Unterminated string',           # Missing closing quote
            '"String with invalid \\escape"',   # Invalid escape sequence
            '"\n"',                           # Raw newline in string
            '"String\vwith\\invalid\\controls"', # Invalid control characters
            '"'                               # Empty unterminated string
        ]
        for string in invalid_strings:
            with self.assertRaises(LexerError):
                lexer = Lexer('test.ps', StringIO(string))
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
            lexer = Lexer('test.ps', StringIO(expr))
            lexemes = list(lexer.lex())
            actual_types = [lexeme.type for lexeme in lexemes]  # Exclude EOF
            self.assertEqual(actual_types, expected_types)
