#!/usr/bin/env python3
# test_full_pipeline.py  -  Lumen compiler driver  (13 stages)

import sys, traceback

from lexer    import lexer
from parser   import parser, get_syntax_errors, clear_syntax_errors
from semantic import analyze, SemanticWarning
from ir       import (ast_to_ir, optimise,
                      to_quadruples, print_quadruples,
                      build_cfg, print_cfg, generate_dot,
                      to_ssa,
                      build_activation_records,
                      simulate_heap,
                      StackFrame)
from codegen  import generate_python
from ast_viz  import visualise_ast

BAR = "=" * 65

def sec(n, title):
    print(f"\n+{BAR}+")
    print(f"|  {n}  {title:<59}|")
    print(f"+{BAR}+")


def run_pipeline(file_path):
    print(f"\n{'*'*67}")
    print(f"  Lumen Compiler  |  {file_path}")
    print(f"{'*'*67}")

    # 1. Read
    sec("1/13", "Reading Source")
    try:
        with open(file_path) as f: source = f.read()
        lines = source.splitlines()
        print(f"  {len(lines)} line(s)")
        for i,ln in enumerate(lines,1):
            print(f"  {i:4d} | {ln}")
    except FileNotFoundError:
        print(f"  ERROR: file not found: {file_path}"); return

    # 2. Lex
    sec("2/13", "Lexical Analysis")
    lexer.input(source)
    toks = list(lexer)
    print(f"  {len(toks)} token(s)")
    print(f"  {'TYPE':<16}  {'VALUE':<22}  LINE")
    print(f"  {'-'*50}")
    for tok in toks[:30]:
        print(f"  {tok.type:<16}  {str(tok.value):<22}  {tok.lineno}")
    if len(toks) > 30:
        print(f"  ... ({len(toks)-30} more)")

    # 3. Parse
    sec("3/13", "Parsing -> AST")
    clear_syntax_errors()
    try:
        # IMPORTANT: reset the lexer completely before parsing.
        # Stage 2 consumed all tokens and left lineno at end-of-file.
        # If we reuse the same lexer object without resetting, line numbers
        # in the AST will be wrong (offset by the end-of-file line count)
        # and the parser's state machine will be corrupted, causing statements
        # to be silently dropped and variables to appear undefined.
        lexer.lineno = 1
        ast = parser.parse(source, lexer=lexer)
    except Exception:
        print(f"  ERROR: parser crashed\n{traceback.format_exc()}"); return

    errs = get_syntax_errors()
    if errs:
        print(f"  {len(errs)} syntax error(s) (recovered):")
        for e in errs: print(f"    {e}")

    if not ast:
        print("  ERROR: parser returned None"); return
    print(f"  OK  {len(ast.statements)} top-level statement(s)")

    # 4. AST visualisation
    sec("4/13", "AST Visualisation")
    print(visualise_ast(ast, title=file_path.split('/')[-1]))

    # 5. Semantic analysis
    sec("5/13", "Semantic Analysis")
    SemanticWarning.reset()
    try:
        analyze(ast)
        ws = SemanticWarning.all_warnings()
        print(f"\n  OK  {len(ws)} warning(s)")
    except Exception as exc:
        print(f"\n  ERROR: {exc}")
        for w in SemanticWarning.all_warnings(): print(f"  WARNING: {w}")
        return

    # 6. IR generation
    sec("6/13", "IR Generation")
    ir = ast_to_ir(ast)
    print(f"  {len(ir)} instruction(s)")
    for i,ins in enumerate(ir,1):
        print(f"  {i:3d}.  {ins}")

    # 7. Quadruples
    sec("7/13", "Quadruples  (op, arg1, arg2, result)")
    quads = to_quadruples(ir)
    print_quadruples(quads)

    # 8. Optimisation
    sec("8/13", "IR Optimisation  (7 passes, loop-safe)")
    ir_opt, opt_log = optimise(ir, report=True)
    print(f"\n  IR: {len(ir)} -> {len(ir_opt)} instruction(s)")
    for i,ins in enumerate(ir_opt,1):
        print(f"  {i:3d}.  {ins}")

    # 9. SSA
    sec("9/13", "SSA Form  (with phi-functions)")
    ssa_text, _ = to_ssa(ir_opt)
    print()
    print(ssa_text)

    # 10. CFG + DOT
    sec("10/13", "Control-Flow Graph  (with liveness)")
    blocks, entry, exit_ = build_cfg(ir_opt)
    print_cfg(blocks, entry, exit_)
    dot_file = file_path.replace('.lumen','_cfg.dot')
    generate_dot(blocks, dot_file)

    # 11. Activation records + Stack
    sec("11/13", "Activation Records + Stack Model")
    ars = build_activation_records(ir_opt)
    if ars:
        sf = StackFrame()
        for name, ar in ars.items():
            print(ar.describe())
            print()
            sf.push_frame(name, ar.params, ar.locals_)
        print("  Stack simulation:")
        print(sf.describe())
        print("\n  Stack operations log:")
        for entry_log in sf.log:
            print(f"    {entry_log}")
    else:
        print("  (no functions in this program)")

    # 12. Heap simulation
    sec("12/13", "Heap Allocation Model")
    heap = simulate_heap(ir_opt)
    if heap.allocs:
        print(heap.describe())
        print("\n  Heap log:")
        for entry_log in heap.log:
            print(f"    {entry_log}")
        print("\n  Simulating GC (marking all as live)...")
        live = set(heap.allocs.keys())
        heap.gc_mark_sweep(live)
    else:
        print("  (no heap allocations in this program)")

    # 13. Codegen + Execute
    sec("13/13", "Code Generation + Execution")
    py_code = generate_python(ir_opt)
    print("\n  Generated Python:")
    print("  " + "-"*60)
    for i,line in enumerate(py_code.splitlines(),1):
        print(f"  {i:3d}  {line}")
    print("  " + "-"*60)

    print("\n  --- Execution output ---")
    try:
        exec(py_code, {})
        print("\n  OK  Execution complete")
    except Exception:
        print("\n  ERROR during execution:")
        traceback.print_exc()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage: python test_full_pipeline.py <file.lumen>")
        sys.exit(1)
    run_pipeline(sys.argv[1])
