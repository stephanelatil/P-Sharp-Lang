from unittest import TestCase
from lexer import PS_Lexer, LexerError
from parser_tree import parser, ParsingError
from typing_tree import MultiTypingException, p_to_t_tree, CustomType, Type

class TestLexer(TestCase):
    def setUp(self) -> None:
        self.lexer = PS_Lexer()
        return super().setUp()
    
    def tearDown(self) -> None:
        return super().tearDown()
    
    def test_bad_ident1_1(self):
        with open(r".\test_files\lexing\bad\testfile-bad_ident1-1.psc", 'r') as f:
            code = f.read()
        with self.assertRaises(LexerError) as ex:
            tokens = list(self.lexer.lexCode(code))
        self.assertEqual(ex.exception.location.line,2)
        self.assertEqual(ex.exception.location.col,7)
        self.assertEqual(ex.exception.token[0], "A")

    def test_bad_ident2_1(self):
        with open(r".\test_files\lexing\bad\testfile-bad_ident2-1.psc", 'r') as f:
            code = f.read()
        with self.assertRaises(LexerError) as ex:
            tokens = list(self.lexer.lexCode(code))
        self.assertEqual(ex.exception.location.line, 1)
        self.assertEqual(ex.exception.location.col, 8)
        self.assertEqual(ex.exception.token[0], "'")

    def test_assign_1(self):
        with open(r".\test_files\lexing\good\testfile-assign-1.psc", 'r') as f:
            code = f.read()
        tokens = list(self.lexer.lexCode(code))
        self.assertEqual(len(tokens), 18)

    def test_bool_1(self):
        with open(r".\test_files\lexing\good\testfile-bool-1.psc", 'r') as f:
            code = f.read()
        tokens = list(self.lexer.lexCode(code))
        self.assertEqual(len(tokens), 42)

    def test_instr_decl1_1(self):
        with open(r".\test_files\lexing\good\testfile-instr_decl1-1.psc", 'r') as f:
            code = f.read()
        tokens = list(self.lexer.lexCode(code))
        self.assertEqual(len(tokens), 10)

    def test_instr_expr_1(self):
        with open(r".\test_files\lexing\good\testfile-instr_expr-1.psc", 'r') as f:
            code = f.read()
        tokens = list(self.lexer.lexCode(code))
        self.assertEqual(len(tokens), 7)

    def test_lexing2_1(self):
        with open(r".\test_files\lexing\good\testfile-lexing2-1.psc", 'r') as f:
            code = f.read()
        tokens = list(self.lexer.lexCode(code))
        self.assertEqual(len(tokens), 12)

    def test_lexing3_1(self):
        with open(r".\test_files\lexing\good\testfile-lexing3-1.psc", 'r') as f:
            code = f.read()
        tokens = list(self.lexer.lexCode(code))
        self.assertEqual(len(tokens), 12)

    def test_lexing4_1(self):
        with open(r".\test_files\lexing\good\testfile-lexing4-1.psc", 'r') as f:
            code = f.read()
        tokens = list(self.lexer.lexCode(code))
        self.assertEqual(len(tokens), 12)

    def test_lexing5_1(self):
        with open(r".\test_files\lexing\good\testfile-lexing5-1.psc", 'r') as f:
            code = f.read()
        tokens = list(self.lexer.lexCode(code))
        self.assertEqual(len(tokens), 16)

    def test_lexing6_1(self):
        with open(r".\test_files\lexing\good\testfile-lexing6-1.psc", 'r') as f:
            code = f.read()
        tokens = list(self.lexer.lexCode(code))
        self.assertEqual(len(tokens), 16)

    def test_parameters1_1(self):
        with open(r".\test_files\lexing\good\testfile-parameters1-1.psc", 'r') as f:
            code = f.read()
        tokens = list(self.lexer.lexCode(code))
        self.assertEqual(len(tokens), 7)

    def test_parameters2_1(self):
        with open(r".\test_files\lexing\good\testfile-parameters2-1.psc", 'r') as f:
            code = f.read()
        tokens = list(self.lexer.lexCode(code))
        self.assertEqual(len(tokens), 9)

    def test_return1_1(self):
        with open(r".\test_files\lexing\good\testfile-return1-1.psc", 'r') as f:
            code = f.read()
        tokens = list(self.lexer.lexCode(code))
        self.assertEqual(len(tokens), 6)

    def test_var2_1(self):
        with open(r".\test_files\lexing\good\testfile-var2-1.psc", 'r') as f:
            code = f.read()
        tokens = list(self.lexer.lexCode(code))
        self.assertEqual(len(tokens), 7)

    def test_char(self):
        with open(r".\test_files\lexing\good\testfile-char.psc", 'r') as f:
            code = f.read()
        tokens = list(self.lexer.lexCode(code))
        self.assertEqual(len(tokens), 24)


class TestParsing(TestCase):
    def setUp(self) -> None:
        return super().setUp()
    
    def tearDown(self) -> None:
        return super().tearDown()
    
    def test_block1_1(self):
        with open(r".\test_files\parsing\bad\testfile-block1-1.psc", 'r') as f:
            code = f.read()
        with self.assertRaises(ParsingError) as ex:
            p = parser.parse(code, tracking=True, lexer=PS_Lexer())

    def test_block2_1(self):
        with open(r".\test_files\parsing\bad\testfile-block2-1.psc", 'r') as f:
            code = f.read()
        with self.assertRaises(ParsingError) as ex:
            p = parser.parse(code, tracking=True, lexer=PS_Lexer())
        ex = ex.exception      

    def test_expr3_1(self):
        with open(r".\test_files\parsing\bad\testfile-expr3-1.psc", 'r') as f:
            code = f.read()
        with self.assertRaises(ParsingError) as ex:
            p = parser.parse(code, tracking=True, lexer=PS_Lexer())
        ex = ex.exception
        

    def test_expr4_1(self):
        with open(r".\test_files\parsing\bad\testfile-expr4-1.psc", 'r') as f:
            code = f.read()
        with self.assertRaises(ParsingError) as ex:
            p = parser.parse(code, tracking=True, lexer=PS_Lexer())
        ex = ex.exception
        

    def test_expr6_1(self):
        with open(r".\test_files\parsing\bad\testfile-expr6-1.psc", 'r') as f:
            code = f.read()
        with self.assertRaises(ParsingError) as ex:
            p = parser.parse(code, tracking=True, lexer=PS_Lexer())
        ex = ex.exception
        

    def test_expr7_1(self):
        with open(r".\test_files\parsing\bad\testfile-expr7-1.psc", 'r') as f:
            code = f.read()
        with self.assertRaises(ParsingError) as ex:
            p = parser.parse(code, tracking=True, lexer=PS_Lexer())
        ex = ex.exception

    def test_this(self):
        with open(r".\test_files\parsing\bad\testfile-this.psc", 'r') as f:
            code = f.read()
        with self.assertRaises(ParsingError) as ex:
            p = parser.parse(code, tracking=True, lexer=PS_Lexer())
        ex = ex.exception
        

    def test_if1_1(self):
        with open(r".\test_files\parsing\bad\testfile-if1-1.psc", 'r') as f:
            code = f.read()
        with self.assertRaises(ParsingError) as ex:
            p = parser.parse(code, tracking=True, lexer=PS_Lexer())
        ex = ex.exception
        

    def test_if2_1(self):
        with open(r".\test_files\parsing\bad\testfile-if2-1.psc", 'r') as f:
            code = f.read()
        with self.assertRaises(ParsingError) as ex:
            p = parser.parse(code, tracking=True, lexer=PS_Lexer())
        ex = ex.exception
        

    def test_if3_1(self):
        with open(r".\test_files\parsing\bad\testfile-if3-1.psc", 'r') as f:
            code = f.read()
        with self.assertRaises(ParsingError) as ex:
            p = parser.parse(code, tracking=True, lexer=PS_Lexer())

    def test_if_else_1(self):
        with open(r".\test_files\parsing\bad\testfile-if_else-1.psc", 'r') as f:
            code = f.read()
        with self.assertRaises(ParsingError) as ex:
            p = parser.parse(code, tracking=True, lexer=PS_Lexer())

    def test_instr_decl1_1(self):
        with open(r".\test_files\parsing\bad\testfile-instr_decl1-1.psc", 'r') as f:
            code = f.read()
        with self.assertRaises(ParsingError) as ex:
            p = parser.parse(code, tracking=True, lexer=PS_Lexer())

    def test_instr_expr_1(self):
        with open(r".\test_files\parsing\bad\testfile-instr_expr-1.psc", 'r') as f:
            code = f.read()
        with self.assertRaises(ParsingError) as ex:
            p = parser.parse(code, tracking=True, lexer=PS_Lexer())

    def test_lexing2_1(self):
        with open(r".\test_files\parsing\bad\testfile-lexing2-1.psc", 'r') as f:
            code = f.read()
        with self.assertRaises(ParsingError) as ex:
            p = parser.parse(code, tracking=True, lexer=PS_Lexer())

    def test_lexing3_1(self):
        with open(r".\test_files\parsing\bad\testfile-lexing3-1.psc", 'r') as f:
            code = f.read()
        with self.assertRaises(ParsingError) as ex:
            p = parser.parse(code, tracking=True, lexer=PS_Lexer())

    def test_lexing4_1(self):
        with open(r".\test_files\parsing\bad\testfile-lexing4-1.psc", 'r') as f:
            code = f.read()
        with self.assertRaises(ParsingError) as ex:
            p = parser.parse(code, tracking=True, lexer=PS_Lexer())

    def test_lexing5_1(self):
        with open(r".\test_files\parsing\bad\testfile-lexing5-1.psc", 'r') as f:
            code = f.read()
        with self.assertRaises(ParsingError) as ex:
            p = parser.parse(code, tracking=True, lexer=PS_Lexer())

    def test_lexing6_1(self):
        with open(r".\test_files\parsing\bad\testfile-lexing6-1.psc", 'r') as f:
            code = f.read()
        with self.assertRaises(ParsingError) as ex:
            p = parser.parse(code, tracking=True, lexer=PS_Lexer())

    def test_parameters1_1(self):
        with open(r".\test_files\parsing\bad\testfile-parameters1-1.psc", 'r') as f:
            code = f.read()
        with self.assertRaises(ParsingError) as ex:
            p = parser.parse(code, tracking=True, lexer=PS_Lexer())

    def test_parameters2_1(self):
        with open(r".\test_files\parsing\bad\testfile-parameters2-1.psc", 'r') as f:
            code = f.read()
        with self.assertRaises(ParsingError) as ex:
            p = parser.parse(code, tracking=True, lexer=PS_Lexer())

    def test_return1_1(self):
        with open(r".\test_files\parsing\bad\testfile-return1-1.psc", 'r') as f:
            code = f.read()
        with self.assertRaises(ParsingError) as ex:
            self.assertEqual(parser.parse(code, tracking=True, lexer=PS_Lexer()), None)

    def test_unclosed_comment_1(self):
        with open(r".\test_files\parsing\bad\testfile-unclosed_comment-1.psc", 'r') as f:
            code = f.read()
        with self.assertRaises(ParsingError) as ex:
            p = parser.parse(code, tracking=True, lexer=PS_Lexer())

    def test_var2_1(self):
        with open(r".\test_files\parsing\bad\testfile-var2-1.psc", 'r') as f:
            code = f.read()
        with self.assertRaises(ParsingError) as ex:
            p = parser.parse(code, tracking=True, lexer=PS_Lexer())

    def test_assign_1(self):
        with open(r".\test_files\parsing\good\testfile-assign-1.psc", 'r') as f:
            code = f.read()
        p = parser.parse(code, tracking=True, lexer=PS_Lexer())
        

    def test_bool_1(self):
        with open(r".\test_files\parsing\good\testfile-bool-1.psc", 'r') as f:
            code = f.read()
        p = parser.parse(code, tracking=True, lexer=PS_Lexer())
        

    def test_assign_float(self):
        with open(r".\test_files\parsing\good\testfile-assign-float.psc", 'r') as f:
            code = f.read()
        p = parser.parse(code, tracking=True, lexer=PS_Lexer())

    def test_assign_string(self):
        with open(r".\test_files\parsing\good\testfile-assign-string.psc", 'r') as f:
            code = f.read()
        p = parser.parse(code, tracking=True, lexer=PS_Lexer())

    def test_assign_array(self):
        with open(r".\test_files\parsing\good\testfile-assign-array.psc", 'r') as f:
            code = f.read()
        p = parser.parse(code, tracking=True, lexer=PS_Lexer())

    def test_char(self):
        with open(r".\test_files\parsing\good\testfile-function-def.psc", 'r') as f:
            code = f.read()
        p = parser.parse(code, tracking=True, lexer=PS_Lexer())

    def test_builtins(self):
        with open(r".\test_files\parsing\good\testfile-builtins.psc", 'r') as f:
            code = f.read()
        p = parser.parse(code, tracking=True, lexer=PS_Lexer())

    def test_class_methods(self):
        with open(r".\test_files\parsing\good\testfile-class-methods.psc", 'r') as f:
            code = f.read()
        p = parser.parse(code, tracking=True, lexer=PS_Lexer())

    def test_function_chaining(self):
        with open(r".\test_files\parsing\good\testfile-function-chaining.psc", 'r') as f:
            code = f.read()
        p = parser.parse(code, tracking=True, lexer=PS_Lexer())

    def test_if(self):
        with open(r".\test_files\parsing\good\testfile-if.psc", 'r') as f:
            code = f.read()
        p = parser.parse(code, tracking=True, lexer=PS_Lexer())

    def test_while(self):
        with open(r".\test_files\parsing\good\testfile-while.psc", 'r') as f:
            code = f.read()
        p = parser.parse(code, tracking=True, lexer=PS_Lexer())

    def test_for(self):
        with open(r".\test_files\parsing\good\testfile-for.psc", 'r') as f:
            code = f.read()
        p = parser.parse(code, tracking=True, lexer=PS_Lexer())

    def test_foreach(self):
        with open(r".\test_files\parsing\good\testfile-foreach.psc", 'r') as f:
            code = f.read()
        p = parser.parse(code, tracking=True, lexer=PS_Lexer())
 
    def test_break(self):
        with open(r".\test_files\parsing\good\testfile-break.psc", 'r') as f:
            code = f.read()
        p = parser.parse(code, tracking=True, lexer=PS_Lexer())


class TestTyping(TestCase):
    def setUp(self) -> None:
        return super().setUp()

    def tearDown(self) -> None:
        CustomType.known_types.clear()
        return super().tearDown()
            
    def test_arith_1(self):
        with open(r".\test_files\typing\bad\testfile-arith-1.psc", 'r') as f:
            code = f.read()
        p = parser.parse(code, tracking=True, lexer=PS_Lexer())
        with self.assertRaises(MultiTypingException) as ex:
            t = p_to_t_tree(p)

    def test_arith_2(self):
        with open(r".\test_files\typing\bad\testfile-arith-2.psc", 'r') as f:
            code = f.read()
        p = parser.parse(code, tracking=True, lexer=PS_Lexer())
        with self.assertRaises(MultiTypingException) as ex:
            t = p_to_t_tree(p)

    def test_arith_3(self):
        with open(r".\test_files\typing\bad\testfile-arith-3.psc", 'r') as f:
            code = f.read()
        p = parser.parse(code, tracking=True, lexer=PS_Lexer())
        with self.assertRaises(MultiTypingException) as ex:
            t = p_to_t_tree(p)

    def test_arrow_1(self):
        with open(r".\test_files\typing\bad\testfile-arrow-1.psc", 'r') as f:
            code = f.read()
        p = parser.parse(code, tracking=True, lexer=PS_Lexer())
        with self.assertRaises(MultiTypingException) as ex:
            t = p_to_t_tree(p)

    def test_arrow_2(self):
        with open(r".\test_files\typing\bad\testfile-arrow-2.psc", 'r') as f:
            code = f.read()
        p = parser.parse(code, tracking=True, lexer=PS_Lexer())
        with self.assertRaises(MultiTypingException) as ex:
            t = p_to_t_tree(p)

    def test_arrow_3(self):
        with open(r".\test_files\typing\bad\testfile-arrow-3.psc", 'r') as f:
            code = f.read()
        p = parser.parse(code, tracking=True, lexer=PS_Lexer())
        with self.assertRaises(MultiTypingException) as ex:
            t = p_to_t_tree(p)

    def test_arrow_4(self):
        with open(r".\test_files\typing\bad\testfile-arrow-4.psc", 'r') as f:
            code = f.read()
        p = parser.parse(code, tracking=True, lexer=PS_Lexer())
        with self.assertRaises(MultiTypingException) as ex:
            t = p_to_t_tree(p)

    def test_unique(self):
        with open(r".\test_files\typing\bad\testfile-unique-1.psc", 'r') as f:
            code = f.read()
        p = parser.parse(code, tracking=True, lexer=PS_Lexer())
        with self.assertRaises(MultiTypingException) as ex:
            t = p_to_t_tree(p)

    def test_call_1(self):
        with open(r".\test_files\typing\bad\testfile-call-1.psc", 'r') as f:
            code = f.read()
        p = parser.parse(code, tracking=True, lexer=PS_Lexer())
        with self.assertRaises(MultiTypingException) as ex:
            t = p_to_t_tree(p)
    
    def test_call_2(self):
        with open(r".\test_files\typing\bad\testfile-call-2.psc", 'r') as f:
            code = f.read()
        p = parser.parse(code, tracking=True, lexer=PS_Lexer())
        with self.assertRaises(MultiTypingException) as ex:
            t = p_to_t_tree(p)

    def test_call_3(self):
        with open(r".\test_files\typing\bad\testfile-call-3.psc", 'r') as f:
            code = f.read()
        p = parser.parse(code, tracking=True, lexer=PS_Lexer())
        with self.assertRaises(MultiTypingException) as ex:
            t = p_to_t_tree(p)

    def test_redef_1(self):
        with open(r".\test_files\typing\bad\testfile-redef-1.psc", 'r') as f:
            code = f.read()
        p = parser.parse(code, tracking=True, lexer=PS_Lexer())
        with self.assertRaises(MultiTypingException) as ex:
            t = p_to_t_tree(p)

    def test_redef_2(self):
        with open(r".\test_files\typing\bad\testfile-redef-2.psc", 'r') as f:
            code = f.read()
        p = parser.parse(code, tracking=True, lexer=PS_Lexer())
        with self.assertRaises(MultiTypingException) as ex:
            t = p_to_t_tree(p)

    def test_redef_4(self):
        with open(r".\test_files\typing\bad\testfile-redef-4.psc", 'r') as f:
            code = f.read()
        p = parser.parse(code, tracking=True, lexer=PS_Lexer())
        with self.assertRaises(MultiTypingException) as ex:
            t = p_to_t_tree(p)

    def test_redef_5(self):
        with open(r".\test_files\typing\bad\testfile-redef-5.psc", 'r') as f:
            code = f.read()
        p = parser.parse(code, tracking=True, lexer=PS_Lexer())
        with self.assertRaises(MultiTypingException) as ex:
            t = p_to_t_tree(p)

    def test_redef_6(self):
        with open(r".\test_files\typing\bad\testfile-redef-6.psc", 'r') as f:
            code = f.read()
        p = parser.parse(code, tracking=True, lexer=PS_Lexer())
        with self.assertRaises(MultiTypingException) as ex:
            t = p_to_t_tree(p)

    def test_redef_7(self):
        with open(r".\test_files\typing\bad\testfile-redef-7.psc", 'r') as f:
            code = f.read()
        p = parser.parse(code, tracking=True, lexer=PS_Lexer())
        with self.assertRaises(MultiTypingException) as ex:
            t = p_to_t_tree(p)

    def test_redef_8(self):
        with open(r".\test_files\typing\bad\testfile-redef-8.psc", 'r') as f:
            code = f.read()
        p = parser.parse(code, tracking=True, lexer=PS_Lexer())
        with self.assertRaises(MultiTypingException) as ex:
            t = p_to_t_tree(p)

    def test_scope_1(self):
        with open(r".\test_files\typing\bad\testfile-scope-1.psc", 'r') as f:
            code = f.read()
        p = parser.parse(code, tracking=True, lexer=PS_Lexer())
        with self.assertRaises(MultiTypingException) as ex:
            t = p_to_t_tree(p)

    def test_scope_2(self):
        with open(r".\test_files\typing\bad\testfile-scope-2.psc", 'r') as f:
            code = f.read()
        p = parser.parse(code, tracking=True, lexer=PS_Lexer())
        with self.assertRaises(MultiTypingException) as ex:
            t = p_to_t_tree(p)

    def test_unary_minus_1(self):
        with open(r".\test_files\typing\bad\testfile-unary_minus-1.psc", 'r') as f:
            code = f.read()
        p = parser.parse(code, tracking=True, lexer=PS_Lexer())
        with self.assertRaises(MultiTypingException) as ex:
            t = p_to_t_tree(p)

    def test_undef_field_1(self):
        with open(r".\test_files\typing\bad\testfile-undef_field-1.psc", 'r') as f:
            code = f.read()
        p = parser.parse(code, tracking=True, lexer=PS_Lexer())
        with self.assertRaises(MultiTypingException) as ex:
            t = p_to_t_tree(p)

    def test_undef_fun_1(self):
        with open(r".\test_files\typing\bad\testfile-undef_fun-1.psc", 'r') as f:
            code = f.read()
        p = parser.parse(code, tracking=True, lexer=PS_Lexer())
        with self.assertRaises(MultiTypingException) as ex:
            t = p_to_t_tree(p)

    def test_undef_var_1(self):
        with open(r".\test_files\typing\bad\testfile-undef_var-1.psc", 'r') as f:
            code = f.read()
        p = parser.parse(code, tracking=True, lexer=PS_Lexer())
        with self.assertRaises(MultiTypingException) as ex:
            t = p_to_t_tree(p)

    def test_undef_var_2(self):
        with open(r".\test_files\typing\bad\testfile-undef_var-2.psc", 'r') as f:
            code = f.read()
        p = parser.parse(code, tracking=True, lexer=PS_Lexer())
        with self.assertRaises(MultiTypingException) as ex:
            t = p_to_t_tree(p)

    def test_undef_var_3(self):
        with open(r".\test_files\typing\bad\testfile-undef_var-3.psc", 'r') as f:
            code = f.read()
        p = parser.parse(code, tracking=True, lexer=PS_Lexer())
        with self.assertRaises(MultiTypingException) as ex:
            t = p_to_t_tree(p)

    def test_empty_file(self):
        with open(r".\test_files\typing\good\testfile-empty-file.psc", 'r') as f:
            code = f.read()
        p = parser.parse(code, tracking=True, lexer=PS_Lexer())
        t = p_to_t_tree(p)
        self.assertEqual(len(t.classDecl), 0)
        self.assertEqual(len(t.statements), 0)
        self.assertEqual(len(t.funcDecl), 0)
        self.assertEqual(len(t.varDecl), 0)
        self.assertEqual(len(CustomType.known_types), 15,
                          "There should just be the 15 built-in types defined.")
        self.assertEqual(len(t._known_vars), 1,
                          "There should just be print function defined.")

    def test_dot_on_return(self):
        with open(r".\test_files\typing\good\testfile-dot-on-return.psc", 'r') as f:
            code = f.read()
        p = parser.parse(code, tracking=True, lexer=PS_Lexer())
        t = p_to_t_tree(p)
        self.assertEqual(len(t.funcDecl), 2)
        self.assertEqual(len(t.funcDecl[1].body.statements), 1)

    def test_implicit_casting(self):
        with open(r".\test_files\typing\good\testfile-implicit-casting.psc", 'r') as f:
            code = f.read()
        p = parser.parse(code, tracking=True, lexer=PS_Lexer())
        t = p_to_t_tree(p)
        self.assertEqual(len(t.funcDecl), 1)

    def test_constructor(self):
        with open(r".\test_files\typing\good\testfile-constructor.psc", 'r') as f:
            code = f.read()
        p = parser.parse(code, tracking=True, lexer=PS_Lexer())
        t = p_to_t_tree(p)

    def test_null(self):
        with open(r".\test_files\typing\good\testfile-null.psc", 'r') as f:
            code = f.read()
        p = parser.parse(code, tracking=True, lexer=PS_Lexer())
        t = p_to_t_tree(p)
