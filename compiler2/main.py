from argparse import ArgumentParser, ArgumentError, Namespace
from subprocess import Popen, PIPE
from pathlib import Path
from tempfile import TemporaryDirectory
from llvm_transpiler import CodeGen
from typing import Union
from os import environ
from shutil import move
from warnings import filterwarnings
from tempfile import TemporaryDirectory
import sys
#avoid including full traceback in the exception messages
# sys.tracebacklimit = -1

LLVM_VERSION = environ.get("LLVM_VERSION", "")
assert LLVM_VERSION in ("", "-15", "-16", "-17", "-18", "-19"), "The only currently supported llvm versions are 15 to 19"

LLC = 'llc' + LLVM_VERSION
LLVM_LINK = 'llvm-link' + LLVM_VERSION
LLVM_DIS = 'llvm-dis' + LLVM_VERSION
CLANG = 'clang' + LLVM_VERSION

def compile_file(filename: Path, output: str, is_library: bool, optimization_level: Union[int, str],
                 use_warnings: bool, debug_symbols:bool, emit: str):
    if filename == Path(output):
        raise FileExistsError("Cannot use the same file for input and output!")
    with filename.open('r') as fileIO, TemporaryDirectory() as tmpdir:
        codegen = CodeGen(optimization_level, use_warnings, debug_symbols)
        module_location = codegen.compile_module(filename, fileIO,
                                                 output_dir=tmpdir, is_library=is_library,
                                                 llvm_version=LLVM_VERSION)
        llc_flags = ['-relocation-model=pic']
        clang_flags= [] 
        if debug_symbols:
            llc_flags.append('--emit-call-site-info')
            clang_flags.append('-g')
        
        if optimization_level == 's':
            opt_flags = [f'-O2']
        else:
            opt_flags = [f'-O{optimization_level}']
        
        if emit == "bc":
            bc_file = output if output.endswith(".bc") else output + ".bc"
            move(module_location, str(Path(bc_file).resolve()))
        
        elif emit == "ir":
            ll_file = output if output.endswith(".ll") else output + ".ll"
            proc = Popen([LLVM_DIS, '-o', ll_file, str(module_location.resolve().absolute())])
            proc.wait()
        
        elif emit == "asm":
            llc_flags.append('-filetype=asm')
            asm_file = output if output.endswith(".s") else output + ".s"
            proc = Popen([LLC, "-o", asm_file, str(module_location.resolve().absolute()),
                          *llc_flags,*opt_flags])
            proc.wait()
        
        elif emit == "obj":
            llc_flags.append("-filetype=obj")
            obj_file = output if output.endswith(".o") else output + ".o"
            proc = Popen([LLC, "-o", obj_file, str(module_location.resolve().absolute()),
                          *llc_flags,*opt_flags])
            proc.wait()
            
        elif emit == 'exe':
            exe_file = output or "a.out"
            o_to_exe_proc = Popen([CLANG, "-o", exe_file, module_location, *clang_flags, *opt_flags])
            o_to_exe_proc.wait()
        
        else:
            raise ArgumentError(None, f"Unknown format to emit to '{emit}'")

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

def main():    
    parser = ArgumentParser(description="P# Compiler for .psc files")
    parser.add_argument("input", type=file_check, help="Input .psc source file")
    parser.add_argument("-o", "--output", type=str, default="a.out", help="Output file name")
    parser.add_argument("--lib", action="store_true", help="Compile as a library (omit main function, and GC) (Unstable for now, use at your own risk!)")
    parser.add_argument("-O", type=opt_level, choices=[*range(0, 4),'s'], default=0, help="Optimization level (0-3) or optimize for size -Os", dest="O")
    parser.add_argument("-g", action='store_true', dest='debug_symbols', default=False, help="Add debug symbols (Currently not available)")
    parser.add_argument("-w", "--warnings", action="store_true", default=False, help="Enable warnings (only some available for now)")
    parser.add_argument("--emit", type=str, choices=["ir", "bc", 'asm', "obj", "exe"], default="exe",
                        help="""Select output type (default exe):
                        ir : builds to LLVM Intermediate Representation and outputs a human readable .ll file
                        bc : builds to LLVM Intermediate Representation and outputs a machine readable bitcode .bc file
                        asm: builds to assembly representation for the current architecture
                        obj: builds to an object file for the current architecture
                        exe: builds to an executable elf""")
    
    args = parser.parse_args()    
    compile_file(args.input, args.output, args.lib, args.O, args.warnings, args.debug_symbols, args.emit)
    
if __name__ == "__main__":
    main()
