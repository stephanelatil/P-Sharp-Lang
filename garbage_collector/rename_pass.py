# Hacky way of enabling opaque pointers
# later versions of llvmlite will make this mandatory
import os
os.environ['LLVMLITE_ENABLE_OPAQUE_POINTERS'] = "1"
import llvmlite
llvmlite.ir_layer_typed_pointers_enabled = False
llvmlite.opaque_pointers_enabled = True

from llvmlite.binding import ModuleRef, parse_bitcode
from typing import Dict
from argparse import ArgumentParser, Namespace

def rename_functions(bc_filepath:str, name_map:Dict[str,str]) -> None:
    with open(bc_filepath, 'rb') as bc_in:
        mod:ModuleRef = parse_bitcode(bc_in.read())
    
    for func in mod.functions:
        assert func.is_function
        if func.name in name_map:
            #rename the function in the module and update references to it
            func.name = name_map[func.name]

    with open(bc_filepath, 'wb') as bc_out:
        bc_out.write(mod.as_bitcode())

def setup_args() -> Namespace:
    argument_parser = ArgumentParser(description="Used to rename functions to the correct llvm symbols according to a lookup table given as a csv.",
                               allow_abbrev=False)
    argument_parser.add_argument("bc_file", type=str,
                                 help='The path to the bit-code file to in which to rename the functions')
    argument_parser.add_argument("map_file", type=str,
                                 help='The path to the csv file that contains the key-value pairs: old_function_name,new_function_name. Note: Leading and trailing whitespace is trimmed from function names')
    
    return argument_parser.parse_args()

def read_rename_map(map_filepath:str) -> Dict[str, str]:
    name_map:Dict[str,str] = {}
    with open(map_filepath, 'r') as map_f:
        for line in map_f.readlines():
            if not "," in line:
                continue
            old_name, new_name = line.split(',', 1)
            name_map[old_name.strip()] = new_name.strip()
    return name_map

def main():
    args = setup_args()
    name_map = read_rename_map(args.map_file)
    rename_functions(args.bc_file,
                     name_map)

if __name__ == '__main__':
    main()