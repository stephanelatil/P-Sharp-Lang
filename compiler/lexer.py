import ply.lex as lex
from ply.yacc import NullLogger

class Location:
    """Track the location of a token in the code"""

    def __init__(self, lineno, col) -> None:
        self.line = int(lineno)
        self.col = int(col)

    def __str__(self) -> str:
        return f"Line {self.line} " +\
            f"and column {self.col}"

    def __repr__(self) -> str:
        return '"'+str(self)+'"'
    
    def __eq__(self, __value: object) -> bool:
        if not isinstance(__value, Location):
            return False
        return self.line == __value.line and self.col == __value.col

class LexerError(SyntaxError):
    def __init__(self, *args: object, location:Location=None, token=None) -> None:
        super().__init__(*args)
        self.location = location
        self.token = token
        
    def __str__(self) -> str:
        return super().__str__() + \
               f"\nLocation: {self.location} on string {repr(self.token[:6])}..."

class PS_Lexer:
    reserved = {
        'if': 'Keyword_Control_If',
        'else': 'Keyword_Control_Else',
        'return': 'Keyword_Control_Return',
        'for': 'Keyword_Control_For',
        'while': 'Keyword_Control_While',
        'continue': 'Keyword_Control_Continue',
        'break': 'Keyword_Control_Break',
        'assert': 'Keyword_Control_Assert',
#        'public': 'Keyword_Access_Public',   # Will be implemented later
#        'private': 'Keyword_Access_Private', # Will be implemented later
#        'static': 'Keyword_Access_Static',   # Will be implemented later
#        'readonly': 'Keyword_Access_Const',     # Will be added later when declare+define can be done on a single line
#        'from': 'Keyword_Import_From',       # Will be implemented later
#        'import': 'Keyword_Import_Import',   # Will be implemented later
#        'as': 'Keyword_Import_As',
        'unsigned': 'Keyword_Type_Mod_Unsigned',
#        'ref': 'Keyword_Type_ArgRef',        # Will be implemented later
        'class': 'Keyword_Object_Class',
        'this': 'Keyword_Object_This',
#        'abstract': 'Keyword_Access_Abstract',       # Will be implemented later
#        'override': 'Keyword_Access_Override',       # Will be implemented later
#        'enum': 'Keyword_Object_Enum',       # Will be implemented later
#        'override': 'Keyword_Object_Enum',       # Will be implemented later
#        'operator': 'Keyword_Object_Enum',       # Will be implemented later
        'null': 'Keyword_Object_Null',
        'true': 'Keyword_Object_True',
        'false': 'Keyword_Object_False',
        'new': 'Keyword_Object_New',
        'and': 'Operator_Binary_Bool_And',
        'or': 'Operator_Binary_Bool_Or',
        'not': 'Operator_Unary_Not',
        'void': 'Keyword_Type_Void',
        'i8': 'Keyword_Type_Int8',
        'i16': 'Keyword_Type_Int16',
        'i32': 'Keyword_Type_Int32',
        'i64': 'Keyword_Type_Int64',
        'string': 'Keyword_Type_String',
        'f32': 'Keyword_Type_Float_32',
        'f64': 'Keyword_Type_Float_64',
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
        'Operator_Logic_Not',
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
        self.lineno = 0
        self.lexpos = 0
        self.code = ""
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
        t.value = t.value[1:-1]
        return t
    
    def t_Number_Float(self,t):
        r'((?:(([1-9][\d_]*)(\.\d[\d_]*)|0\.)([eE][+\-]?\d[\d_]*))|(?:([1-9][\d_]*)([eE][+\-]?\d[\d_]*))|(?:([0-9][\d_]*)(\.\d[\d_]*)))\b'
        setattr(t, 'len', len(t.value))
        t.value = float(t.value)
        return t

    def t_Number_Int(self,t):
        r'\b(0|[1-9][\d_]*)([^\d_])?'
        setattr(t, 'len', len(t.value))
        if t.value[-1] not in range(10):
            t.value = t.value[:-1]
            t.lexer.skip(-1)
        t.value = int(t.value.replace('_', ''))
        return t

    def t_Number_Char(self,t):
        r"'(.{1}|\\x[\da-fA-F][\da-fA-F]|\\.)'" # single char or char hex escaped ex: '\x00' for null char or single escaped char 
        setattr(t, 'len', len(t.value))
        t.value = t.value.strip("'")
        if len(t.value) == 1:
            t.value = ord(t.value)
        elif t.value[:2] == '\\x':
            t.value = int(t.value[1:], 16)
        elif len(t.value) == 2:
            c = bytes(s, "ascii").decode("unicode_escape")
            if len(c) != 1:
                raise SyntaxError(f"Invalid escape sequence '{c}'")
            t.value = ord(c)
        if isinstance(t.value, str):
            raise SyntaxError(f"Unable to parse char: {repr(t.value)}")
        if t.value > 255 or t.value < 0:
            raise SyntaxError("Invalid character, must have a value between 0 and 255 (inclusive)")
        return t

    def t_Number_Hex(self,t):
        r'\b0x[\da-fA-F_]+\b'
        setattr(t, 'len', len(t.value))
        t.value = int(t.value[2:].replace('_', ''), 16)
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

    def t_Operator_Binary_Shl(self, t):
        r'<<'
        return t

    def t_Operator_Binary_Shr(self, t):
        r'>>'
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
    

    def t_Operator_Binary_Bool_Gt(self,t):
        r'>'
        return t

    def t_Operator_Binary_Bool_Lt(self,t):
        r'<'
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

    def t_Operator_Logic_Not(self, t):
        r'!'
        return t

    def t_newline(self,t):
        r'\n\r?'
        t.lexer.lineno += 1

    def t_Whitespace(self,t):
        r'[^\S]+'
        pass
        #Discard whitespace

    def t_reserved_prefix(self,t):
        r'\bPS_GC__[a-zA-Z_\d]*\b'
        line = str(t.lineno)
        col = t.lexpos - self.code.rfind('\n', 0, t.lexpos)
        raise LexerError("Identifiers cannot contain the prefix 'PS_GC__' which is reserved for internal use",
                         location=Location(line, col), token=t.value)

    def t_ID(self, t):
        r'\b[a-zA-Z_][a-zA-Z_\d]*\b'
        if t.value.startswith("__"):
            line = str(t.lineno)
            col = t.lexpos - self.code.rfind('\n', 0, t.lexpos)
            raise LexerError("Identifiers starting with double underscores are reserved",
                             location=Location(line, col), token=t.value)
        t.type = self.reserved.get(t.value, 'ID')    # Check for reserved words
        return t

    def t_error(self,t):
        line = str(t.lineno)
        col = t.lexpos - self.code.rfind('\n', 0, t.lexpos)

        raise LexerError("Illegal character", location=Location(line, col), token=t.value)

    def t_eof(self,t):
        return None

    # Build the lexer
    def build(self, **kwargs):
        self.lexer = lex.lex(module=self, errorlog=NullLogger(), **kwargs)

    def lexCode(self, code):
        self.code = code
        self.lexer.input(code)
        while True:
            token = self.token()
            if not token:
                break
            yield token

    def input(self, code, **kwargs):
        self.code = code
        self.lexer.input(code, **kwargs)

    def token(self):
        tok = self.lexer.token()
        self.lexpos = self.lexer.lexpos
        self.lineno = self.code.count("\n", 0, self.lexpos)+1
        
        line = self.lineno
        if self.code.rfind('\n', 0, self.lexpos) >= 0:
            col = self.lexpos - self.code.rfind('\n', 0, self.lexpos)-1
        else:
            col = self.lexpos
        if tok is not None:
            # offset correctly to point to first char of token
            col += 1 - len(tok.value) if isinstance(tok.value, str) else tok.len
            #add location info
            setattr(tok, "location", Location(line, col))
            setattr(tok, "location_end", Location(
                line, col+len(tok.value) if isinstance(tok.value, str) else tok.len))
            setattr(tok, "lineno", line)
        return tok

tokens = PS_Lexer.tokens