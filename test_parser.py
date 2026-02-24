# test_parser.py
from parser import parser
from lexer import lexer
from ast_nodes import Node
import sys

def print_ast(node, indent=0):
    if not isinstance(node, list):
        node = [node]
    for n in node:
        if n is None:
            continue
        print("  " * indent + repr(n))
        for child in vars(n).values():
            if isinstance(child, (list, Node)):
                print_ast(child, indent + 1)

if __name__ == "__main__":
    if len(sys.argv) > 1:
        with open(sys.argv[1], 'r') as f:
            data = f.read()
        print(f"\nParsing: {sys.argv[1]}\n")
    else:
        data = """
float dist = 4.2 pc;
if (dist > 3 pc) {
    print("Far away");
}
        """
        print("Parsing hardcoded sample...\n")

    ast = parser.parse(data, lexer=lexer)
    if ast:
        print("AST:")
        print_ast(ast.statements)
    else:
        print("Parsing failed.")
