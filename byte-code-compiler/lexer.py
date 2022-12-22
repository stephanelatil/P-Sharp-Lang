from pygments.lexer import RegexLexer
from pygments.token import *
import pygments

class PS_Lexer(RegexLexer):
    name = 'P_Sharp'
    aliases = ['P#', 'PS']
    filenames = ['*.psc']

    _identifier = r'[_a-zA-Z]\w*'

    tokens = {
        'root': [
            # Comments
            (r'//.*$', Comment.Singleline),                             
            (r'/[*]([^*]|([*][^/]))*[*]+/', Comment.Multiline),

            # String
            (r'\$?"(\\\\|\\[^\\]|[^"\\n])*["\n]', String),            
            
            # Keywords
            (r'if',Keyword.Control.If),
            (r'else',Keyword.Control.Else),
            (r'return',Keyword.Control.Return),
            (r'when', Keyword.Control.When),
            (r'for',Keyword.Control.For),
            (r'while',Keyword.Control.While),
            (r'continue',Keyword.Control.Continue),
            (r'break',Keyword.Control.Break),
            (r'public', Keyword.Access.Public),
            (r'private', Keyword.Access.Private),
            (r'static', Keyword.Access.Static),
            (r'const', Keyword.Access.Const),
            (r'unsigned', Keyword.Type.Mod_Unsigned),
            (r'ref', Keyword.Type.ArgRef),
            (r'class', Keyword.Object.Class),
            (r'enum', Keyword.Object.Enum),
            (r'null', Keyword.Object.Null),
            (r'and', Operator.Binary.Bool_And),
            (r'or', Operator.Binary.Bool_Or),
            (r'not', Operator.Unary.Not),
            
            # type
            (r'void', Keyword.Type.Void),
            (r'int_16', Keyword.Type.Int16),
            (r'int_32', Keyword.Type.Int32),
            (r'int_64', Keyword.Type.Int64),
            (r'string', Keyword.Type.String),
            (r'float_32', Keyword.Type.Float_32),
            (r'float_64', Keyword.Type.Float_64),
            (r'char', Keyword.Type.Char),
            (r'bool', Keyword.Type.Boolean),
            
            # Numbers
            (r"'(.|\\[\da-fA-F][\da-fA-F])'", Number.Char),
            (r'0x[\da-fA-F_]+', Number.Hex),
            (r'[1-9][\d_]*', Number.Int),
            (r'0', Number.Int),
            (r'(?:0|[1-9]\d*)(?:\.\d+)?(?:[eE][+\-]?\d+)?', Number.Float),

            # Punctuation
            (r'\(', Punctuation.OpenParen),
            (r'\)', Punctuation.CloseParen),
            (r'\[', Punctuation.OpenBracket),
            (r'\]', Punctuation.CloseBracket),
            (r'{', Punctuation.OpenBrace),
            (r'}', Punctuation.CloseBrace),

            # Operators
            (r'--', Operator.Unary.Dec),
            (r'\+\+', Operator.Unary.Inc),
            (r'==', Operator.Binary.Bool_Eq),
            (r'!=', Operator.Binary.Bool_Neq),
            (r'>=', Operator.Binary.Bool_Geq),
            (r'<=', Operator.Binary.Bool_Leq),
            (r'>', Operator.Binary.Bool_Gt),
            (r'<', Operator.Binary.Bool_Lt),
            (r':=', Operator.Binary.Copy),
            (r'\+=', Operator.Binary.PlusEq),
            (r'-=', Operator.Binary.MinusEq),
            (r'\*=', Operator.Binary.TimesEq),
            (r'/=', Operator.Binary.DivEq),
            (r'&=', Operator.Binary.AndEq),
            (r'\|=', Operator.Binary.OrEq),
            (r'\^=', Operator.Binary.XorEq),
            (r'<<=', Operator.Binary.ShlEq),
            (r'>>=', Operator.Binary.ShrEq),
            (r'=', Operator.Binary.Affectation),
            (r'\+', Operator.Binary.Plus),
            (r'-', Operator.Minus),
            (r'\*', Operator.Binary.Times),
            (r'/', Operator.Binary.Div),
            (r'%', Operator.Binary.Mod),
            (r'&', Operator.Binary.And),
            (r'\|', Operator.Binary.Or),
            (r'\^', Operator.Binary.Xor),
            (r'<<', Operator.Binary.Shl),
            (r'>>', Operator.Binary.Shr),
            (r';', Punctuation.EoL),
            (r'\?', Punctuation.TernaryConditional),
            (r':', Punctuation.TernarySeparator),
            (r'[^\S]+', Whitespace),

            # Identifier
            (r'[a-zA-Z_][a-zA-Z_\d]*', Name.ID),
            (r'.', Error)
        ]
    }

class Lexeme:
    CurrLine = 1
    CurrLineStartOffset = 0

    def __init__(self, unprocessed_token) -> None:
        assert(len(unprocessed_token) == 3)
        self.token_type = unprocessed_token[1]
        self.value = unprocessed_token[2]
        self.line_no = Lexeme.CurrLine
        self.col = 1 + unprocessed_token[0] - Lexeme.CurrLineStartOffset
        if '\n' in self.value:
            Lexeme.CurrLine += self.value.count('\n')
            Lexeme.CurrLineStartOffset = unprocessed_token[0] + self.value.rfind('\n') + 1

    def __str__(self) -> str:
        return f"Line: {self.line_no:02} col: {self.col:02} | {repr(self.value)}{' '*(20-len(repr(self.value)))}| {self.token_type}"

def lex(path:str):
    tokens = []
    for t in PS_Lexer().get_tokens_unprocessed(open(path, 'r').read()):
        tokens.append(Lexeme(t))
    return tokens

from sys import argv
print('\n'.join([str(x) for x in lex(argv[1])]))