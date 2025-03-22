from argparse import ArgumentParser, ArgumentError
from subprocess import Popen, PIPE
from pathlib import Path
from tempfile import TemporaryDirectory
from llvm_transpiler import CodeGen
from os import environ

LLC_LOCATION=environ.get('LLC_LOCATION', 'llc')
CLANG_LOCATION=environ.get('CLANG_LOCATION', 'clang')

def compile_file(filename: Path, output: str, is_library: bool, speed_opt: int, size_opt: int,
                 use_warnings: bool, debug_symbols:bool, emit: str):
    with filename.open('r') as fileIO:
        codegen = CodeGen(speed_opt, size_opt, use_warnings)
        module_ref = codegen.compile_module(filename.name, fileIO, is_library)
        llc_flags = ['-relocation-model=pic']
        clang_flags= [] 
        if debug_symbols:
            llc_flags.append('-g')
            clang_flags.append('-g')
        
        opt_flags = [f'-O{speed_opt}']
        
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
                bc_to_o_proc = Popen([LLC_LOCATION, "-o", obj_filename, '-']+ llc_flags,
                                    stdin=PIPE)
                bc_to_o_proc.communicate(module_ref.as_bitcode())
                o_to_exe_proc = Popen([CLANG_LOCATION, "-o", exe_file, obj_filename]+clang_flags)
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

def main():    
    parser = ArgumentParser(description="P# Compiler for .psc files")
    parser.add_argument("input", type=file_check, help="Input .psc source file")
    parser.add_argument("-o", "--output", type=str, default="a.out", help="Output file name")
    parser.add_argument("--lib", action="store_true", help="Compile as a library (omit main function, and GC) (Unstable, use at our own risk!)")
    parser.add_argument("-O", type=int, choices=range(0, 4), default=0, help="Optimization level (0-3)")
    parser.add_argument("-Os", type=int, choices=range(0, 3), default=0, help="Size optimization level (0-2)")
    parser.add_argument("-g", action='store_true', dest='debug_symbols', default=False, help="Add debug symbols (Currently not enabled)")
    parser.add_argument("-w", "--warnings", action="store_true", default=False, help="Enable warnings (only some available for now)")
    parser.add_argument("--emit", type=str, choices=["ir", "bc", 'asm', "obj", "exe"], default="exe", help="Select output type")
    
    args = parser.parse_args()
    compile_file(args.input, args.output, args.lib, args.O, args.Os, args.warnings, args.debug_symbols, args.emit)
    
if __name__ == "__main__":
    main()
