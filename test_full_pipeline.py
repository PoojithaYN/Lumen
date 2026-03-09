# test_full_pipeline.py
from lexer import lexer
from parser import parser
from semantic import analyze
from ir import ast_to_ir
from codegen import generate_python

import sys
import traceback

def run_pipeline(file_path):
    print(f"\n===== Starting full pipeline for: {file_path} =====\n")
    
    # Step 1: Read source
    print("1. Reading Lumen source code...")
    try:
        with open(file_path, 'r') as f:
            data = f.read()
        print("   → Source code loaded successfully.")
        print("   First few lines:\n" + "\n".join(data.splitlines()[:5]) + "\n...")
    except Exception as e:
        print(f"   ERROR reading file: {e}")
        return

    # Step 2: Lexing (optional – but good to see tokens)
    print("2. Running lexer...")
    lexer.input(data)
    print("   Tokens produced:")
    token_list = []
    while True:
        tok = lexer.token()
        if not tok:
            break
        token_list.append(f"{tok.type:12} {tok.value}")
    if token_list:
        print("\n".join(token_list[:15]) + "\n   ... (showing first 15 tokens)")
    else:
        print("   No tokens produced (empty file?)")

    # Step 3: Parsing → AST
    print("\n3. Running parser...")
    try:
        ast = parser.parse(data, lexer=lexer)
        if ast:
            print("   → Parsing successful! AST root created.")
            print("   Program has", len(ast.statements), "statements.")
        else:
            print("   Parsing returned None – likely syntax error.")
            return
    except Exception as e:
        print(f"   Parser crashed: {e}")
        traceback.print_exc()
        return

    # Step 4: Semantic analysis
    print("\n4. Running semantic analysis...")
    try:
        analyze(ast)
        print("   → Semantic checks passed! No errors detected.")
    except Exception as e:
        print(f"   Semantic error: {e}")
        return

    # Step 5: IR generation
    print("\n5. Generating Intermediate Representation (IR)...")
    ir = ast_to_ir(ast)
    print("   IR instructions generated:", len(ir))
    print("   IR dump:")
    for i, instr in enumerate(ir, 1):
        print(f"     {i:2d}. {instr}")

    # Step 6: Code generation
    print("\n6. Generating Python code...")
    py_code = generate_python(ir)
    print("   Generated Python code (full):\n")
    print("-" * 60)
    print(py_code)
    print("-" * 60)

    # Step 7: Execution
    print("\n7. Executing generated Python code...")
    try:
        print("   → Execution output starts here:")
        print("   " + "-" * 50)
        exec(py_code, globals())  # using globals() so prints go to console
        print("   " + "-" * 50)
        print("   → Execution finished successfully.")
    except Exception as e:
        print("   Execution failed:")
        traceback.print_exc()

if __name__ == "__main__":
    if len(sys.argv) > 1:
        run_pipeline(sys.argv[1])
    else:
        print("Usage: python test_full_pipeline.py <path_to_lumen_file>")
        print("Example: python test_full_pipeline.py samples/unit_handling.lumen")
