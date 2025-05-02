import pytest
from io import StringIO
from lexer import Lexer, LexemeType, LexerError, Position, CharacterStream

class TestPosition:
    """
    Test suite for the Position class which tracks line numbers, columns, and indices
    in source code.
    """

    def setup_method(self) -> None:
        """Initialize a fresh Position instance before each test."""
        self.position = Position()

    def test_position_initializes_with_default_values(self) -> None:
        """Test that Position initializes with expected default values (line 1, column 1, index 0)."""
        assert self.position.line == 1
        assert self.position.column == 1
        assert self.position.index == 0

    def test_position_advances_correctly_with_normal_characters(self) -> None:
        """Test that Position advances correctly with regular characters."""
        # Advance through a normal character
        self.position.advance('a')
        assert self.position.line == 1
        assert self.position.column == 2
        assert self.position.index == 1

    def test_position_handles_newline_characters_correctly(self) -> None:
        """Test that Position correctly updates when encountering newline characters."""
        # First advance some regular characters
        for _ in range(3):
            self.position.advance('a')

        # Then hit a newline
        self.position.advance('\n')

        assert self.position.line == 2# Line should increment
        assert self.position.column == 1# Column should reset
        assert self.position.index == 4# Index should still increment

    def test_position_copy_creates_independent_instance(self) -> None:
        """Test that Position.copy() creates a completely independent copy."""
        # Advance the original position
        self.position.advance('a')
        self.position.advance('b')

        # Create a copy
        copied_position = self.position.copy()

        # Verify copy has same values
        assert copied_position.line == self.position.line
        assert copied_position.column == self.position.column
        assert copied_position.index == self.position.index

        # Modify original and verify copy remains unchanged
        self.position.advance('c')
        assert copied_position.column != self.position.column
        assert copied_position.index != self.position.index

    def test_position_arithmetic_addition_works_correctly(self) -> None:
        """Test that Position addition creates correct new position."""
        # Start position (1,1,0)
        result = self.position + 5

        # New position should be offset by 5 columns
        assert result.line == 1
        assert result.column == 6
        assert result.index == 5

        # Original position should be unchanged
        assert self.position.line == 1
        assert self.position.column == 1
        assert self.position.index == 0


class TestCharacterStream:
    """
    Test suite for the CharacterStream class which handles reading and buffering
    characters from an input stream.
    """

    def setup_method(self) -> None:
        """Initialize a fresh CharacterStream instance before each test."""
        self.create_stream("")

    def create_stream(self, content: str) -> None:
        """Helper method to create a new stream with given content."""
        self.stream = CharacterStream(StringIO(content), 'test.cs')

    def test_empty_stream_returns_none_on_peek(self) -> None:
        """Test that peeking an empty stream returns None."""
        assert self.stream.peek() is None
        assert self.stream.eof

    def test_stream_handles_single_character_correctly(self) -> None:
        """Test reading a single character from the stream."""
        self.create_stream("a")

        # Peek should show 'a' but not advance
        assert self.stream.peek() == "a"
        assert self.stream.position().column == 1

        # Advance should return 'a' and move position
        assert self.stream.advance() == "a"
        assert self.stream.position().column == 2

    def test_stream_handles_multiple_characters_correctly(self) -> None:
        """Test reading multiple characters from the stream."""
        self.create_stream("abc")

        # Read each character and verify position
        assert self.stream.advance() == "a"
        assert self.stream.position().column == 2

        assert self.stream.advance() == "b"
        assert self.stream.position().column == 3

        assert self.stream.advance() == "c"
        assert self.stream.position().column == 4

    def test_stream_peek_with_different_lookahead_amounts(self) -> None:
        """Test peeking ahead multiple characters in the stream."""
        self.create_stream("abcd")

        # Peek at different positions without advancing
        assert self.stream.peek(0) == "a"
        assert self.stream.peek(1) == "b"
        assert self.stream.peek(2) == "c"
        assert self.stream.peek(3) == "d"

        # Position should not have changed
        assert self.stream.position().column == 1

    def test_stream_handles_newlines_correctly(self) -> None:
        """Test that stream correctly handles newline characters."""
        self.create_stream("a\nb\nc")

        # Read through newlines and verify position
        assert self.stream.advance() == "a"
        assert self.stream.position().line == 1
        assert self.stream.position().column == 2

        assert self.stream.advance() == "\n"
        assert self.stream.position().line == 2
        assert self.stream.position().column == 1

        assert self.stream.advance() == "b"
        assert self.stream.position().line == 2
        assert self.stream.position().column == 2

    def test_stream_raises_eof_error_on_advance_past_end(self) -> None:
        """Test that advancing past the end of stream raises EOFError."""
        self.create_stream("a")

        # Read the only character
        self.stream.advance()

        # Attempting to read past end should raise EOFError
        with pytest.raises(EOFError):
            self.stream.advance()

    def test_stream_eof_flag_sets_correctly(self) -> None:
        """Test that EOF flag is set correctly when reaching end of stream."""
        self.create_stream("a")

        # Initially EOF should be False
        assert not self.stream.eof

        # Read content
        self.stream.peek()
        assert not self.stream.eof
        # Read past the end of content
        self.stream.peek(1)
        assert self.stream.eof
        # Read past the end of content
        self.stream.peek(100)
        assert self.stream.eof

    def test_stream_position_tracking_with_mixed_content(self) -> None:
        """Test position tracking with mix of characters, newlines, and multiple peeks."""
        self.create_stream("abc\ndef\nghi")

        # Track position through mixed content
        assert self.stream.advance() == "a"# (1,2)
        assert self.stream.advance() == "b"# (1,3)
        assert self.stream.advance() == "c"# (1,4)
        assert self.stream.advance() == "\n"# (2,1)
        assert self.stream.advance() == "d"# (2,2)

        pos = self.stream.position()
        assert pos.line == 2
        assert pos.column == 2
        assert pos.index == 5

    def test_stream_buffer_management(self) -> None:
        """Test that the stream's buffer is managed correctly with mixed peek and advance operations."""
        self.create_stream("abcdef")

        # Peek ahead several characters
        assert self.stream.peek(3) == "d"

        # Buffer should contain 4 characters now
        assert len(self.stream.buffer) == 4

        # Advance and verify buffer shrinks
        self.stream.advance()  # 'a'
        self.stream.advance()  # 'b'
        assert len(self.stream.buffer) == 2

        # Peek again should refill buffer
        assert self.stream.peek(2) == "e"
        assert len(self.stream.buffer) == 3

class TestLexer:
    @pytest.mark.parametrize("block_comment", ["/*ThisIsAComment*/",
                "/*\r\n\r\n*/",
                "/*Comment with \t various whitespaces\ntest\ttest\t\n\t\n\r\r test \n\n*/",
                "/*\n*/",
                "/*¡£©¶œβюॴ௴ඕ*/"])
    def test_block_comments_with_many_or_few_chars_and_unicode_chars(self, block_comment):
        lexer = Lexer('test.ps', StringIO(block_comment))
        lexemes = list(lexer.lex(include_comments=True))
        assert len(lexemes) == 1
        assert lexemes[0].type == LexemeType.COMMENT_MULTILINE

    @pytest.mark.parametrize("comment",[
            "// Simple comment\n",
            "// Simple comment without newline",
            "// Comment with symbols !@#$%^&*()\n",
            "// Comment with numbers 12345\n",
            "// Unicode content ¡£©¶œβ\n"
        ])
    def test_line_comments_with_various_content(self, comment) -> None:
        """Test single-line comments with different content."""
        lexer = Lexer('test.ps', StringIO(comment))
        lexemes = list(lexer.lex(include_comments=True))
        assert len(lexemes) == 1
        assert lexemes[0].type == LexemeType.COMMENT_SINGLELINE

    @pytest.mark.parametrize("input_str, expected_type, expected_val",[
            ("42", LexemeType.NUMBER_INT, "42"),
            ("0", LexemeType.NUMBER_INT, "0"),
            ("123_456", LexemeType.NUMBER_INT, "123456"),
            ("0xFF", LexemeType.NUMBER_HEX, "0xFF"),
            ("0xDEAD_BEEF", LexemeType.NUMBER_HEX, "0xDEADBEEF")
        ])
    def test_numeric_literals_integers(self, input_str, expected_type, expected_val) -> None:
        """Test various forms of integer literals."""
        lexer = Lexer('test.ps', StringIO(input_str))
        lexemes = list(lexer.lex())
        assert len(lexemes) == 1# Number
        assert lexemes[0].type == expected_type
        assert lexemes[0].value == expected_val

    @pytest.mark.parametrize("input_str, expected_type, expected_val",[
            ("3.14", LexemeType.NUMBER_FLOAT, "3.14"),
            ("0.0", LexemeType.NUMBER_FLOAT, "0.0"),
            ("1e10", LexemeType.NUMBER_FLOAT, "1e10"),
            ("1e+10", LexemeType.NUMBER_FLOAT, "1e10"),
            ("1.5e-10", LexemeType.NUMBER_FLOAT, "1.5e-10"),
            ("1_234.567_89", LexemeType.NUMBER_FLOAT, "1234.56789"),
            ("1.", LexemeType.NUMBER_FLOAT, "1."), # Allows unterminated period
            ("1__2_______3", LexemeType.NUMBER_INT, "123") # Any number of underscores
            ])
    def test_numeric_literals_floats(self, input_str, expected_type, expected_val) -> None:
        """Test various forms of floating-point literals."""
        lexer = Lexer('test.ps', StringIO(input_str))
        lexemes = list(lexer.lex())
        assert len(lexemes) == 1# Float
        assert lexemes[0].type == expected_type
        assert lexemes[0].value == expected_val

    @pytest.mark.parametrize("num",[
            "0x",      # Incomplete hex
            "0xG",     # Invalid hex digit
            "1e",      # Incomplete exponent
            "1e+",     # Incomplete exponent
            "1e1.5",   # Non-int exponent
            "1e1.",   # exponent with terminating period
            "1.5.2",   # Non-int exponent
        ])
    def test_invalid_numeric_literals(self, num) -> None:
        """Test that invalid numeric literals raise appropriate errors."""
        with pytest.raises(LexerError):
            lexer = Lexer('test.ps', StringIO(num))
            list(lexer.lex())

    @pytest.mark.parametrize("input_str, expected",[
            ('"Simple string"', '"Simple string"'),
            ('"String with \\"quotes\\""', '"String with \"quotes\""'),
            ('"String with \\n\\t\\r"', '"String with \n\t\r"'),
            ('"Unicode string ¡£©¶œβ"', '"Unicode string ¡£©¶œβ"'),
            ('"Strings\\0 with escape sequences \\\\ \\\" \\\' \\n\\r\\f\\b\\x50"',
            '"Strings\0 with escape sequences \\ \" \' \n\r\f\b\x50"')
            ])
    def test_string_literals_with_escapes(self, input_str, expected) -> None:
        """Test string literals with various escape sequences."""
        lexer = Lexer('test.ps', StringIO(input_str))
        lexemes = list(lexer.lex())
        assert len(lexemes) == 1# String
        assert lexemes[0].type == LexemeType.STRING_LITERAL
        assert lexemes[0].value == expected

    @pytest.mark.parametrize("input_str, expected_type, expected_char",[
            ("'a'", LexemeType.NUMBER_CHAR, "'a'"),
            ("'\\n'", LexemeType.NUMBER_CHAR, "'\n'"),
            ("'\\t'", LexemeType.NUMBER_CHAR, "'\t'"),
            ("'\\''", LexemeType.NUMBER_CHAR, "'''"),
            ("'\\\\'", LexemeType.NUMBER_CHAR, "'\\'"),
            ("'\\x41'", LexemeType.NUMBER_CHAR, "'\x41'") # Hex escape
            ])
    def test_character_literals(self, input_str, expected_type, expected_char) -> None:
        """Test character literals including escape sequences."""
        lexer = Lexer('test.ps', StringIO(input_str))
        lexemes = list(lexer.lex())
        assert len(lexemes) == 1# Char
        assert lexemes[0].type == expected_type
        assert lexemes[0].value == expected_char

    @pytest.mark.parametrize("char",[
            "'",       # Unterminated and empty
            "''",      # Empty
            "'ab'",    # Too long
            "'\\x'",   # Incomplete hex escape
            "'\\x0'",  # Incomplete hex escape
            "'\\xGG'"  # Invalid hex digits
            "'\\'",    # Empty escape sequence
            "'\\",     # Unterminated empty escape sequence
            "'\\n"     # Unterminated escape sequence
        ])
    def test_invalid_character_literals(self, char) -> None:
        """Test that invalid character literals raise appropriate errors."""
        with pytest.raises(LexerError):
            lexer = Lexer('test.ps', StringIO(char))
            list(lexer.lex())

    @pytest.mark.parametrize("op, expected_type",[
            ("+", LexemeType.OPERATOR_BINARY_PLUS),
            ("+=", LexemeType.OPERATOR_BINARY_PLUSEQ),
            ("-", LexemeType.OPERATOR_BINARY_MINUS),
            ("-=", LexemeType.OPERATOR_BINARY_MINUSEQ),
            ("*", LexemeType.OPERATOR_BINARY_TIMES),
            ("*=", LexemeType.OPERATOR_BINARY_TIMESEQ),
            ("/", LexemeType.OPERATOR_BINARY_DIV),
            ("/=", LexemeType.OPERATOR_BINARY_DIVEQ),
            ("&", LexemeType.OPERATOR_BINARY_AND),
            ("&=", LexemeType.OPERATOR_BINARY_ANDEQ),
            ("|", LexemeType.OPERATOR_BINARY_OR),
            ("|=", LexemeType.OPERATOR_BINARY_OREQ),
            ("^", LexemeType.OPERATOR_BINARY_XOR),
            ("^=", LexemeType.OPERATOR_BINARY_XOREQ),
            ("<<", LexemeType.OPERATOR_BINARY_SHL),
            ("<<=", LexemeType.OPERATOR_BINARY_SHLEQ),
            (">>", LexemeType.OPERATOR_BINARY_SHR),
            (">>=", LexemeType.OPERATOR_BINARY_SHREQ)
        ])
    def test_operators_and_punctuation(self, op, expected_type) -> None:
        """Test all operators and punctuation marks."""
        lexer = Lexer('test.ps', StringIO(op))
        lexemes = list(lexer.lex())
        assert len(lexemes) == 1# Operator
        assert lexemes[0].type == expected_type
        assert lexemes[0].value == op

    def test_invalid_punctuation(self) -> None:
        with pytest.raises(LexerError):
            lexer = Lexer('test.ps', StringIO("@"))
            val = list(lexer.lex())

    @pytest.mark.parametrize("keyword, expected_type",[
            ("if", LexemeType.KEYWORD_CONTROL_IF),
            ("else", LexemeType.KEYWORD_CONTROL_ELSE),
            ("while", LexemeType.KEYWORD_CONTROL_WHILE),
            ("for", LexemeType.KEYWORD_CONTROL_FOR),
            ("return", LexemeType.KEYWORD_CONTROL_RETURN),
            ("class", LexemeType.KEYWORD_OBJECT_CLASS),
            ("null", LexemeType.KEYWORD_OBJECT_NULL),
            ("true", LexemeType.KEYWORD_OBJECT_TRUE),
            ("false", LexemeType.KEYWORD_OBJECT_FALSE)
        ])
    def test_keywords(self, keyword, expected_type) -> None:
        """Test all language keywords."""
        lexer = Lexer('test.ps', StringIO(keyword))
        lexemes = list(lexer.lex())
        assert len(lexemes) == 1# Keyword
        assert lexemes[0].type == expected_type
        assert lexemes[0].value == keyword

    @pytest.mark.parametrize("source, expected_types",[
            ("_", [LexemeType.DISCARD]),
            ("_ = a()", [LexemeType.DISCARD, LexemeType.OPERATOR_BINARY_ASSIGN, LexemeType.IDENTIFIER, LexemeType.PUNCTUATION_OPENPAREN, LexemeType.PUNCTUATION_CLOSEPAREN]),
            ("f(_)", [LexemeType.IDENTIFIER, LexemeType.PUNCTUATION_OPENPAREN, LexemeType.DISCARD ,LexemeType.PUNCTUATION_CLOSEPAREN]),
            ("_a", [LexemeType.IDENTIFIER])
            ])
    def test_discard(self, source, expected_types) -> None:
        """Test all language keywords."""
        lexer = Lexer('test.ps', StringIO(source))
        lexemes = list(lexer.lex())
        assert len(lexemes) == len(expected_types)# Keyword
        assert [l.type for l in lexemes] == expected_types

    @pytest.mark.parametrize("identifier",[
            "identifier",
            "camelCase",
            "PascalCase",
            "snake_case",
            "_underscore",
            "with123numbers",
            "α_unicode",  # If Unicode identifiers are supported
            "contains___many__underscores______"
            "_" #single underscore for discard
        ])
    def test_identifiers(self, identifier) -> None:
        """Test valid and invalid identifier patterns."""
        lexer = Lexer('test.ps', StringIO(identifier))
        lexemes = list(lexer.lex())
        assert len(lexemes) == 1# Identifier
        assert lexemes[0].type == LexemeType.IDENTIFIER
        assert lexemes[0].value == identifier

    @pytest.mark.parametrize("identifier",[
            "123identifier",    # Cannot start with number
            "__reserved",      # Cannot start with double underscore
        ])
    def test_invalid_identifiers(self, identifier) -> None:
        """Test that invalid identifiers raise appropriate errors."""
        with pytest.raises(LexerError):
            lexer = Lexer('test.ps', StringIO(identifier))
            vals = list(lexer.lex())

    @pytest.mark.parametrize("string_expr",[
            '"Unterminated string',           # Missing closing quote
            '"String with invalid \\escape"',   # Invalid escape sequence
            '"\n"',                           # Raw newline in string
            '"\\',                           # Raw newline in string
            '"\\x1"',                           # Raw newline in string
            '"String\vwith\\invalid\\controls"', # Invalid control characters
            '"'                               # Empty unterminated string
        ])
    def test_invalid_string_literals(self, string_expr) -> None:
        """Test that invalid string literals raise appropriate errors."""
        with pytest.raises(LexerError):
            lexer = Lexer('test.ps', StringIO(string_expr))
            val = list(lexer.lex())

    @pytest.mark.parametrize("input_str, expected_types, expected_types_with_comments",[
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
        ])
    def test_partial_line_comments(self, input_str, expected_types, expected_types_with_comments) -> None:
        """Test comments that occupy only part of a line with code before/after."""
        # Test without comments
        lexer = Lexer('test.ps', StringIO(input_str))
        lexemes = list(lexer.lex())
        actual_types = [lexeme.type for lexeme in lexemes]
        assert actual_types == expected_types

        # Test with comments included
        lexer = Lexer('test.ps', StringIO(input_str))
        lexemes = list(lexer.lex(include_comments=True))
        actual_types = [lexeme.type for lexeme in lexemes]
        assert actual_types == expected_types_with_comments

    @pytest.mark.parametrize("input_str, expected_types",[
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
        ])
    def test_mixed_comments_types(self, input_str, expected_types) -> None:
        """Test mixing of block and line comments in various configurations."""
        lexer = Lexer('test.ps', StringIO(input_str))
        lexemes = list(lexer.lex(include_comments=True))
        actual_types = [lexeme.type for lexeme in lexemes]
        assert actual_types == expected_types

    @pytest.mark.parametrize("comment",[
            "/* Unterminated block comment",
            "/*/",  # unterminated
        ])
    def test_invalid_block_comments(self, comment) -> None:
        """Test invalid block comment formations."""
        with pytest.raises(LexerError):
            lexer = Lexer('test.ps', StringIO(comment))
            val = list(lexer.lex())

    @pytest.mark.parametrize("expr, expected_types",[
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
        ])
    def test_complex_expressions(self, expr, expected_types) -> None:
        """Test lexing of complex expressions with multiple token types."""
        lexer = Lexer('test.ps', StringIO(expr))
        lexemes = list(lexer.lex())
        actual_types = [lexeme.type for lexeme in lexemes]  # Exclude EOF
        assert actual_types == expected_types

    @pytest.mark.parametrize("expr, expected_ops",[("--", (LexemeType.OPERATOR_UNARY_DECREMENT,)),
                      ("++", (LexemeType.OPERATOR_UNARY_INCREMENT,)),
                      ("not", (LexemeType.OPERATOR_UNARY_BOOL_NOT,)),
                      ("!", (LexemeType.OPERATOR_UNARY_LOGIC_NOT,)),
                      ("x+++1", (LexemeType.IDENTIFIER,LexemeType.OPERATOR_UNARY_INCREMENT,
                                 LexemeType.OPERATOR_BINARY_PLUS, LexemeType.NUMBER_INT)),
                      ("-x---1", (LexemeType.OPERATOR_BINARY_MINUS, LexemeType.IDENTIFIER,
                                  LexemeType.OPERATOR_UNARY_DECREMENT,LexemeType.OPERATOR_BINARY_MINUS,
                                  LexemeType.NUMBER_INT)),])
    def test_unary_operators_simple(self, expr, expected_ops):
        lexer = Lexer('test.ps', StringIO(expr))
        lexemes = tuple(lexeme.type for lexeme in lexer.lex())
        assert lexemes == expected_ops

        # Add these tests to the TestLexer class

    @pytest.mark.parametrize("namespace_declaration, expected_lexemes", [
        # Valid namespace declarations
        ("namespace Test;", [
            (LexemeType.KEYWORD_CONTROL_NAMESPACE, "namespace"),
            (LexemeType.IDENTIFIER, "Test"),
            (LexemeType.PUNCTUATION_SEMICOLON, ";")
        ]),
        ("namespace MyApp.Entities;", [
            (LexemeType.KEYWORD_CONTROL_NAMESPACE, "namespace"),
            (LexemeType.IDENTIFIER, "MyApp"),
            (LexemeType.OPERATOR_DOT, "."),
            (LexemeType.IDENTIFIER, "Entities"),
            (LexemeType.PUNCTUATION_SEMICOLON, ";")
        ]),
        ("namespace A.B.C.D;", [
            (LexemeType.KEYWORD_CONTROL_NAMESPACE, "namespace"),
            (LexemeType.IDENTIFIER, "A"),
            (LexemeType.OPERATOR_DOT, "."),
            (LexemeType.IDENTIFIER, "B"),
            (LexemeType.OPERATOR_DOT, "."),
            (LexemeType.IDENTIFIER, "C"),
            (LexemeType.OPERATOR_DOT, "."),
            (LexemeType.IDENTIFIER, "D"),
            (LexemeType.PUNCTUATION_SEMICOLON, ";")
        ]),
        # With underscores and numbers (valid identifiers)
        ("namespace Data_2023.Core_v1;", [
            (LexemeType.KEYWORD_CONTROL_NAMESPACE, "namespace"),
            (LexemeType.IDENTIFIER, "Data_2023"),
            (LexemeType.OPERATOR_DOT, "."),
            (LexemeType.IDENTIFIER, "Core_v1"),
            (LexemeType.PUNCTUATION_SEMICOLON, ";")
        ]),
    ])
    def test_valid_namespace_declaration(self, namespace_declaration, expected_lexemes):
        """Test valid namespace declarations at the top of the file."""
        lexer = Lexer('test.ps', StringIO(namespace_declaration))
        lexemes = list(lexer.lex())
        
        assert len(lexemes) == len(expected_lexemes)
        for idx, (expected_type, expected_val) in enumerate(expected_lexemes):
            assert lexemes[idx].type == expected_type
            assert lexemes[idx].value == expected_val