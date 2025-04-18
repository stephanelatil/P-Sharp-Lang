from argparse import ArgumentParser, ArgumentError
from subprocess import Popen, PIPE
from pathlib import Path
from tempfile import TemporaryDirectory
from llvm_transpiler import CodeGen
from typing import Union
from os import environ
import sys
#avoid including full traceback in the exception messages
sys.tracebacklimit = -1

LLC_LOCATION=environ.get('LLC_LOCATION', 'llc')
CLANG_LOCATION=environ.get('CLANG_LOCATION', 'clang')

def compile_file(filename: Path, output: str, is_library: bool, optimization_level: Union[int, str],
                 use_warnings: bool, debug_symbols:bool, emit: str):
    if filename == Path(output):
        raise FileExistsError("Cannot use the same file for input and output!")
    with filename.open('r') as fileIO:
        codegen = CodeGen(optimization_level, use_warnings)
        module_ref = codegen.compile_module(filename, fileIO, is_library)
        llc_flags = ['-relocation-model=pic']
        clang_flags= [] 
        if debug_symbols:
            llc_flags.append('--emit-call-site-info')
            # llc_flags.append('--debug-entry-values')
            clang_flags.append('-g')
        
        if optimization_level == 's':
            opt_flags = [f'-O2']
        else:
            opt_flags = [f'-O{optimization_level}']
        
        if emit == "ir":
            ll_file = output if output.endswith(".ll") else output + ".ll"
            with open(ll_file, 'w') as out:
                out.write(str(module_ref))
        
        elif emit == "bc":
            bc_file = output if output.endswith(".bc") else output + ".bc"
            with open(bc_file, "wb") as f:
                f.write(module_ref.as_bitcode())
        
        elif emit == "asm":
            llc_flags.append('-filetype=asm')
            asm_file = output if output.endswith(".s") else output + ".s"
            proc = Popen([LLC_LOCATION, "-o", asm_file, '-'] + llc_flags + opt_flags,
                    stdin=PIPE)
            proc.communicate(module_ref.as_bitcode())
        
        elif emit == "obj":
            llc_flags.append("-filetype=obj")
            obj_file = output if output.endswith(".o") else output + ".o"
            proc = Popen([LLC_LOCATION, "-o", obj_file, '-'] + llc_flags + opt_flags,
                    stdin=PIPE)
            proc.communicate(module_ref.as_bitcode())
            
        elif emit == 'exe':
            llc_flags.append("-filetype=obj")
            exe_file = output if output.endswith("") else output + ""
            with TemporaryDirectory() as tmpdir:
                obj_filename = str(Path(tmpdir, 'built_obj.o'))
                bc_to_o_proc = Popen([LLC_LOCATION, "-o", obj_filename, '-', *llc_flags, *opt_flags],
                                    stdin=PIPE)
                bc_to_o_proc.communicate(module_ref.as_bitcode())
                o_to_exe_proc = Popen([CLANG_LOCATION, "-o", exe_file, obj_filename, *clang_flags, *opt_flags])
                o_to_exe_proc.communicate()
        
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
