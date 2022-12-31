import os
from argparse import ArgumentParser

from lexer import PS_Lexer
from parser_tree import parser

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
                        help="Prints the abstract syntax tree on a single line")
    args.add_argument('-C','--compile-to', required=False, choices=['L', 'P', 'T', 'R', 'E', 'L', 'B'],dest='stage',
                      help="Compiles until the given stage: L=Lexer, P=Parser, T=Typing, R=RTL, E=ERTL, L=LTL, B=ByteCode (default)")
    args.add_argument("filepath", metavar='FILE', required=True, help="The code file to pass to the compiler")

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
        print('\t'+tok, flush=False)
    print('\n', flush=True)

if args.print_reconstructed_code:
    l = PS_Lexer()
    print("Printing reconstructed code:")
    for tok in l.lexCode(code):
        print(tok.value, end=" ", flush=False)
    print('\n', flush=True)

if args.stage == 'L': #Lex only
    exit(0)

p = parser.parse(code, tracking=True, lexer=PS_Lexer())
if args.print_ast:
    print(p)

if args.stage == 'P': #Parse only
    exit(0)

if args.stage == 'T': #Typing only
    exit(0)

if args.stage == 'R': #RTL only
    exit(0)

if args.stage == 'E': #ERTL only
    exit(0)

if args.stage == 'L': #LTL only
    exit(0)

if args.stage == 'B':  # Compiled all the way to byte code
    exit(0)
