import ply.lex as lex

class PS_Lexer:
    reserved = {
        'if': 'Keyword_Control_If',
        'else': 'Keyword_Control_Else',
        'return': 'Keyword_Control_Return',
        'for': 'Keyword_Control_For',
        'while': 'Keyword_Control_While',
        'continue': 'Keyword_Control_Continue',
        'break': 'Keyword_Control_Break',
#        'public': 'Keyword_Access_Public',   # Will be implemented later
#        'private': 'Keyword_Access_Private', # Will be implemented later
#        'static': 'Keyword_Access_Static',   # Will be implemented later
#        'const': 'Keyword_Access_Const',     # Will be added later when declare+define can be donc on a single line
#        'from': 'Keyword_Import_From',       # Will be implemented later
#        'import': 'Keyword_Import_Import',   # Will be implemented later
#        'as': 'Keyword_Import_As',
        'unsigned': 'Keyword_Type_Mod_Unsigned',
#        'ref': 'Keyword_Type_ArgRef',        # Will be implemented later
        'class': 'Keyword_Object_Class',
        'enum': 'Keyword_Object_Enum',
        'null': 'Keyword_Object_Null',
        'true': 'Keyword_Object_True',
        'false': 'Keyword_Object_False',
        'and': 'Operator_Binary_Bool_And',
        'or': 'Operator_Binary_Bool_Or',
        'not': 'Operator_Unary_Not',
        'void': 'Keyword_Type_Void',
        'int_16': 'Keyword_Type_Int16',
        'int_32': 'Keyword_Type_Int32',
        'int_64': 'Keyword_Type_Int64',
        'string': 'Keyword_Type_String',
        'float_32': 'Keyword_Type_Float_32',
        'float_64': 'Keyword_Type_Float_64',
        'char': 'Keyword_Type_Char',
        'bool': 'Keyword_Type_Boolean',
#        'var': 'Keyword_Type_Autoassign'
    }

    tokens = [
        'Comment_Singleline',
        'Comment_Multiline',
        'Literal_String',
        'Number_Char',
        'Number_Hex',
        'Number_Int',
        'Number_Float',
        'Punctuation_OpenParen',
        'Punctuation_CloseParen',
        'Punctuation_OpenBracket',
        'Punctuation_CloseBracket',
        'Punctuation_OpenBrace',
        'Punctuation_CloseBrace',
        'Punctuation_Comma',
        'Operator_Unary_Dec',
        'Operator_Unary_Inc',
        'Operator_Binary_Bool_Eq',
        'Operator_Binary_Bool_Neq',
        'Operator_Binary_Bool_Geq',
        'Operator_Binary_Bool_Leq',
        'Operator_Binary_Bool_Gt',
        'Operator_Binary_Bool_Lt',
        'Operator_Binary_Copy',
        'Operator_Binary_PlusEq',
        'Operator_Binary_MinusEq',
        'Operator_Binary_TimesEq',
        'Operator_Binary_DivEq',
        'Operator_Binary_AndEq',
        'Operator_Binary_OrEq',
        'Operator_Binary_XorEq',
        'Operator_Binary_ShlEq',
        'Operator_Binary_ShrEq',
        'Operator_Binary_Affectation',
        'Operator_Binary_Plus',
        'Operator_Minus',
        'Operator_Binary_Times',
        'Operator_Binary_Div',
        'Operator_Binary_Mod',
        'Operator_Binary_And',
        'Operator_Binary_Or',
        'Operator_Binary_Xor',
        'Operator_Binary_Shl',
        'Operator_Binary_Shr',
        'Operator_Dot',
        'Punctuation_EoL',
        'Punctuation_TernaryConditional',
        'Punctuation_TernarySeparator',
        'Whitespace',
        'ID'
    ] + list(reserved.values())

    def __init__(self):
        self.lexer = None
        self.build()

    def t_Comment_Singleline(self,t):
        r'//.*'
        t.lexer.lineno += 1
        pass
        #Discard comment

    def t_Comment_Multiline(self,t):
        r'/[*]([^*]|([*][^/]))*[*]+/'
        t.lexer.lineno += t.value.count('\n')
        pass
        #Discard comment

    def t_Literal_String(self,t):
        r'"((?:[^\n"\\]*|\\.)*)"'
        return t

    def t_Number_Char(self,t):
        r"'(.|\\x[\da-fA-F][\da-fA-F])'" # single char or char hex escaped ex: '\00' for null char
        t.value = t.value.strip("'")
        if len(t.value) == 1:
            t.value = ord(t.value)
        elif t.value[:2] == '\\x':
            t.value = int(t.value[1:], 16)
        if isinstance(t.value, str):
            raise SyntaxError(f"Unable to parse char: {repr(t.value)}")
        if t.value > 255 or t.value < 0:
            raise SyntaxError("Invalid character, must have a value between 0 and 255 (inclusive)")
        return t

    def t_Number_Hex(self,t):
        r'0x[\da-fA-F_]+'
        t.value = int(t.value[2:].replace('_', ''), 16)
        return t

    def t_Number_Int(self,t):
        r'(0|[1-9][\d_]*)'
        t.value = int(t.value.replace('_', ''))
        return t

    def t_Number_Float(self,t):
        r'(?:0|[1-9]\d*)(?:\.\d+)?(?:[eE][+\-]?\d+)?'
        t.value = float(t.value)
        return t

    def t_Punctuation_OpenParen(self,t):
        r'\('
        return t

    def t_Punctuation_CloseParen(self,t):
        r'\)'
        return t

    def t_Punctuation_OpenBracket(self,t):
        r'\['
        return t

    def t_Punctuation_CloseBracket(self,t):
        r'\]'
        return t

    def t_Punctuation_OpenBrace(self,t):
        r'{'
        return t

    def t_Punctuation_CloseBrace(self,t):
        r'}'
        return t

    def t_Operator_Unary_Dec(self,t):
        r'--'
        return t

    def t_Operator_Unary_Inc(self,t):
        r'\+\+'
        return t

    def t_Operator_Binary_Bool_Eq(self,t):
        r'=='
        return t

    def t_Operator_Binary_Bool_Neq(self,t):
        r'!='
        return t

    def t_Operator_Binary_Bool_Geq(self,t):
        r'>='
        return t

    def t_Operator_Binary_Bool_Leq(self,t):
        r'<='
        return t

    def t_Operator_Binary_Bool_Gt(self,t):
        r'>'
        return t

    def t_Operator_Binary_Bool_Lt(self,t):
        r'<'
        return t

    def t_Operator_Binary_Copy(self,t):
        r':='
        return t

    def t_Operator_Binary_PlusEq(self,t):
        r'\+='
        return t

    def t_Operator_Binary_MinusEq(self,t):
        r'-='
        return t

    def t_Operator_Binary_TimesEq(self,t):
        r'\*='
        return t

    def t_Operator_Binary_DivEq(self,t):
        r'/='
        return t

    def t_Operator_Binary_AndEq(self,t):
        r'&='
        return t

    def t_Operator_Binary_OrEq(self,t):
        r'\|='
        return t

    def t_Operator_Binary_XorEq(self,t):
        r'\^='
        return t

    def t_Operator_Binary_ShlEq(self,t):
        r'<<='
        return t

    def t_Operator_Binary_ShrEq(self,t):
        r'>>='
        return t

    def t_Operator_Binary_Affectation(self,t):
        r'='
        return t

    def t_Operator_Binary_Plus(self,t):
        r'\+'
        return t

    def t_Operator_Minus(self,t):
        r'-'
        return t

    def t_Operator_Binary_Times(self,t):
        r'\*'
        return t

    def t_Operator_Binary_Div(self,t):
        r'/'
        return t

    def t_Operator_Binary_Mod(self,t):
        r'%'
        return t

    def t_Operator_Binary_And(self,t):
        r'&'
        return t

    def t_Operator_Binary_Or(self,t):
        r'\|'
        return t

    def t_Operator_Binary_Xor(self,t):
        r'\^'
        return t

    def t_Operator_Binary_Shl(self,t):
        r'<<'
        return t

    def t_Operator_Binary_Shr(self,t):
        r'>>'
        return t

    def t_Punctuation_EoL(self,t):
        r';'
        return t

    def t_Punctuation_TernaryConditional(self,t):
        r'\?'
        return t

    def t_Punctuation_TernarySeparator(self,t):
        r':'
        return t

    def t_Punctuation_Comma(self, t):
        r','
        return t

    def t_Operator_Dot(self, t):
        r'\.'
        return t

    def t_newline(self,t):
        r'\n+'
        t.lexer.lineno += len(t.value)

    def t_Whitespace(self,t):
        r'[^\S]+'
        pass
        #Discard whitespace

    def t_ID(self,t):
        r'[a-zA-Z_][a-zA-Z_\d]*'
        t.type = self.reserved.get(t.value, 'ID')    # Check for reserved words
        return t

    def t_error(self,t):
        line = str(t.lineno)
        col = t.lexpos - input.rfind('\n', 0, t.lexpos)

        raise SyntaxError(f"Illegal character '{t.value}' on Line "
                        + f"{' '*(5-len(line))+line} and column {' '*(5-len(col))+col}")

    def t_eof(self,t):
        return None

    # Build the lexer
    def build(self, **kwargs):
        self.lexer = lex.lex(module=self, **kwargs)

    def lexCode(self, code):
        self.lexer.input(code)
        while True:
            token = self.lexer.token()
            if not token:
                break
            yield token

    def input(self, code , **kwargs):
        self.lexer.input(code, **kwargs)

    def token(self):
        return self.lexer.token()

tokens = PS_Lexer().tokens