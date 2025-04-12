from argparse import ArgumentParser, ArgumentError, Namespace
from pathlib import Path
from llvm_transpiler import CodeGen, OutputFormat, LLVM_Version
from typing import Union
from os import environ
from warnings import filterwarnings
import sys
#avoid including full traceback in the exception messages
sys.tracebacklimit = -1

try:
    LLVM_VERSION = LLVM_Version(int(environ.get("LLVM_VERSION", "15")))
except:
    raise ValueError(f"Unable to use LLVM version '{environ.get("LLVM_VERSION", "15")}', it's not a valid version. Valid versions are 15, 16, 17, 18 or 19")

def compile_file(filename: Path, output: str, is_library: bool, optimization_level: Union[int, str],
                 use_warnings: bool, debug_symbols:bool, emit: OutputFormat):
    if filename == Path(output):
        raise FileExistsError("Cannot use the same file for input and output!")
    codegen = CodeGen(use_warnings, debug_symbols)
    clang_flags= [] 
    if debug_symbols:
        clang_flags.append('-g')
    clang_flags.append(f'-O{optimization_level}')
    with open(filename, 'rt') as fileIO:
        codegen.compile_module(filename, fileIO,
                               output_file=output,
                               emit_format=emit,
                               is_library=is_library,
                               llvm_version=LLVM_VERSION,
                               clang_flags=clang_flags)

def file_check(filepath:str) -> Path:
    path = Path(filepath)
    if not path.exists():
        raise FileNotFoundError(f"Unable to find file {filepath}")
    if not path.is_file():
        raise IOError(f"{filepath} must be a file!")
    assert path.suffix.lower() == '.psc'
    return path.resolve()

def opt_level(val:str):
    if val == 's':
        return 's'
    elif val in ['0', '1', '2', '3']:
        return int(val)
    raise ArgumentError(None, "Optimization level should be 0, 1, 2, 3 or s")

def setup_warnings(args:Namespace):
    #TODO here use filterwarnings function to filter out most warnings or allow others
    pass

def setup_argparse(parser:ArgumentParser):
    parser.add_argument("input", type=file_check, help="Input .psc source file")
    parser.add_argument("-o", "--output", type=str, default="a.out", help="Output file name")
    parser.add_argument("--lib", action="store_true", help="Compile as a library (omit main function, and GC) (Unstable for now, use at your own risk!)")
    parser.add_argument("-O", type=opt_level, choices=[*range(0, 4),'s'], default=0, help="Optimization level (0-3) or optimize for size -Os", dest="O")
    parser.add_argument("-g", action='store_true', dest='debug_symbols', default=False, help="Add debug symbols (Currently not available)")
    parser.add_argument("-w", "--warnings", action="store_true", default=False, help="Enable warnings (only some available for now)")
    parser.add_argument("--emit", type=OutputFormat, choices=["ir", "bc", 'asm', "obj", "exe"], default="exe",
                        help="""Select output type (default exe):
                        ir : builds to LLVM Intermediate Representation and outputs a human readable .ll file
                        bc : builds to LLVM Intermediate Representation and outputs a machine readable bitcode .bc file
                        asm: builds to assembly representation for the current architecture
                        obj: builds to an object file for the current architecture
                        exe: builds to an executable elf""")

def main():    
    parser = ArgumentParser(description="P# Compiler for .psc files")
    setup_argparse(parser)
    args = parser.parse_args() 
       
    compile_file(args.input, args.output, args.lib, args.O, args.warnings, args.debug_symbols, args.emit)
    
if __name__ == "__main__":
    main()
