import os, sys
from argparse import ArgumentParser
from lexer import PS_Lexer
from parser_tree import parser, MultiParsingException, ParsingError
from typing_tree import p_to_t_tree, MultiTypingException
from typing_to_cfg import Context, typing_to_cfg
from interpreter.interpreter import Env

def validate_path(path:str):
    assert(isinstance(path, str))
    if not os.path.exists(path) or not os.path.isfile(path):
        raise IOError(f"Given path ({path}) must point to an existing FILE!")

def parse_args():
    args = ArgumentParser()
    
    args.add_argument("--print-tokens", required=False, default=False, action='store_true', dest='print_tokens',
                        help="Prints the list of tokens found in order, one per line (Warning: Very verbose)")
    args.add_argument("--reconstruct", required=False, default=False, action='store_true', dest='print_reconstructed_code',
                      help="Prints the code reconstructed from the token list (Removes white space and comments)")
    args.add_argument("--print-ast", required=False, default=False, action='store_true', dest='print_ast',
                      help="Prints the abstract syntax tree as a string JSON object")
    args.add_argument("--print-att", required=False, default=False, action='store_true', dest='print_att',
                      help="Prints the abstract typing tree as a string JSON object")
    args.add_argument("-i", '--interpret', required=False, default=False, action='store_true', dest='interpret',
                      help="Interprets the code directly instead of compiling it.")
    args.add_argument('-C','--compile-to', required=False, choices=['L', 'P', 'T', 'B', 'M'], dest='stage', default='M',
                      help="Compiles until the given stage: L=Lexer, P=Parser, T=Typing, B=ByteCode (LLVM IR), M=Machine Code (default)")
    args.add_argument("filepath", metavar='FILE', help="The code file to pass to the compiler")

    return args.parse_args()

if __name__ != '__main__':
    exit(0)

args = parse_args()
code = ""
with open(args.filepath, 'r') as f:
    code = f.read()

if args.print_tokens:
    l = PS_Lexer()
    print("Printing tokens:")
    for tok in l.lexCode(code):
        print('\t'+str(tok), flush=False)
    print('\n', flush=True)

if args.print_reconstructed_code:
    l = PS_Lexer()
    print("Printing reconstructed code:")
    for tok in l.lexCode(code):
        if tok.type == 'Number_Char':
            print(f"'{tok.value}'", end=" ", flush=False)
        elif tok.type == 'Literal_String':
            print(f'"{tok.value}"', end=" ", flush=False)
        else:
            print(tok.value, end=" ", flush=False)
    print('\n', flush=True)

if args.stage == 'L': #Lex only
    exit(0)

try:
    p = parser.parse(code, tracking=True, lexer=PS_Lexer())
except MultiParsingException as e:
    print(e, file=sys.stderr)
    exit(len(e.exceptions))
except ParsingError as e:
    print(e, file=sys.stderr)
    exit(1)
    
if args.print_ast:
    print(p)

if args.stage == 'P': #Parse only
    exit(0)
    
try:
    t = p_to_t_tree(p)
except MultiTypingException as e:
    print(e, file=sys.stderr)
    exit(len(e.exceptions))
    
if args.print_att:
    print(t)

if args.stage == 'T': #Typing only
    exit(0)

start, context = typing_to_cfg(t)
if args.interpret:
    Env(start, context).run()
    print('\n', end='', flush=True)
    exit(0)

if args.stage == 'R': #RTL only
    exit(0)

if args.stage == 'E': #ERTL only
    exit(0)

if args.stage == 'L': #LTL only
    exit(0)

if args.stage == 'B':  # Compiled all the way to byte code
    exit(0)
