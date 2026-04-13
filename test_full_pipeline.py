#!/usr/bin/env python3
# test_full_pipeline.py  –  Lumen end-to-end compiler driver
#
# Stages:
#  1  Source reading
#  2  Lexical analysis
#  3  Parsing → AST
#  4  AST visualisation
#  5  Semantic analysis (types, units, scopes, line numbers)
#  6  IR generation
#  7  Quadruples
#  8  IR Optimisation  (7 passes, loop-safe)
#  9  SSA display
# 10  Control-flow graph
# 11  Activation records
# 12  Python code generation
# 13  Execution

import sys, traceback

from lexer     import lexer
from parser    import parser, get_syntax_errors, clear_syntax_errors
from semantic  import analyze, SemanticWarning
from ir        import (ast_to_ir, optimise, to_quadruples, print_quadruples,
                       build_cfg, print_cfg, to_ssa_display, build_activation_records)
from codegen   import generate_python
from ast_viz   import visualise_ast

BAR = "═" * 65

def section(n, title):
    print(f"\n╔{BAR}╗")
    print(f"║  {n}  ·  {title:<57}║")
    print(f"╚{BAR}╝")


def run_pipeline(file_path):
    print(f"\n{'━'*67}")
    print(f"  ✦  Lumen Compiler  ✦   {file_path}")
    print(f"{'━'*67}")

    # ── 1. Read source ────────────────────────────────────────────────────────
    section("1 / 13", "Reading Source")
    try:
        with open(file_path) as f:
            source = f.read()
        lines = source.splitlines()
        print(f"  {len(lines)} line(s) loaded.")
        for i, ln in enumerate(lines, 1):
            print(f"  {i:4d} │ {ln}")
    except FileNotFoundError:
        print(f"  ✘  File not found: {file_path}"); return

    # ── 2. Lexical analysis ───────────────────────────────────────────────────
    section("2 / 13", "Lexical Analysis")
    lexer.input(source)
    toks = list(lexer)
    print(f"  {len(toks)} token(s).")
    print(f"  {'TYPE':<16}  {'VALUE':<22}  LINE")
    print(f"  {'─'*16}  {'─'*22}  {'─'*4}")
    for tok in toks[:25]:
        print(f"  {tok.type:<16}  {str(tok.value):<22}  {tok.lineno}")
    if len(toks) > 25:
        print(f"  ... ({len(toks)-25} more tokens)")

    # ── 3. Parsing ────────────────────────────────────────────────────────────
    section("3 / 13", "Parsing → AST")
    clear_syntax_errors()
    try:
        ast = parser.parse(source, lexer=lexer)
    except Exception as exc:
        print(f"  ✘  Parser crashed:\n{traceback.format_exc()}"); return

    syntax_errs = get_syntax_errors()
    if syntax_errs:
        print(f"  {len(syntax_errs)} syntax error(s) (recovered and continued):")
        for e in syntax_errs:
            print(f"    ✘  {e}")

    if not ast:
        print("  ✘  Parser returned None."); return
    print(f"  ✔  AST built — {len(ast.statements)} top-level statement(s).")

    # ── 4. AST visualisation ──────────────────────────────────────────────────
    section("4 / 13", "AST Visualisation")
    print(visualise_ast(ast, title=file_path.split('/')[-1]))

    # ── 5. Semantic analysis ──────────────────────────────────────────────────
    section("5 / 13", "Semantic Analysis")
    SemanticWarning.reset()
    try:
        analyze(ast)
        ws = SemanticWarning.all_warnings()
        print(f"\n  ✔  Semantic OK.  {len(ws)} warning(s) issued.")
    except Exception as exc:
        print(f"\n  ✘  Semantic error: {exc}")
        for w in SemanticWarning.all_warnings():
            print(f"  ⚠  {w}")
        return

    # ── 6. IR generation ──────────────────────────────────────────────────────
    section("6 / 13", "IR Generation")
    ir = ast_to_ir(ast)
    print(f"  {len(ir)} IR instruction(s).")
    for i, instr in enumerate(ir, 1):
        print(f"  {i:3d}.  {instr}")

    # ── 7. Quadruples ─────────────────────────────────────────────────────────
    section("7 / 13", "Quadruples  (op, arg1, arg2, result)")
    quads = to_quadruples(ir)
    print_quadruples(quads)

    # ── 8. IR Optimisation ────────────────────────────────────────────────────
    section("8 / 13", "IR Optimisation  (7 passes, loop-safe)")
    ir_opt, opt_log = optimise(ir, report=True)
    print(f"\n  IR: {len(ir)} → {len(ir_opt)} instruction(s).")
    for i, instr in enumerate(ir_opt, 1):
        print(f"  {i:3d}.  {instr}")

    # ── 9. SSA display ────────────────────────────────────────────────────────
    section("9 / 13", "Static Single Assignment  (display)")
    print()
    print(to_ssa_display(ir_opt))

    # ── 10. Control-flow graph ────────────────────────────────────────────────
    section("10 / 13", "Control-Flow Graph")
    cfg = build_cfg(ir_opt)
    print_cfg(cfg)

    # ── 11. Activation records ────────────────────────────────────────────────
    section("11 / 13", "Activation Records  (stack frame layout)")
    ars = build_activation_records(ir_opt)
    if ars:
        for name, ar in ars.items():
            print(ar.describe())
            print()
    else:
        print("  (no functions defined in this program)")

    # ── 12. Code generation ───────────────────────────────────────────────────
    section("12 / 13", "Python Code Generation")
    py_code = generate_python(ir_opt)
    print()
    print("  ┌─ Generated Python " + "─" * 46)
    for i, line in enumerate(py_code.splitlines(), 1):
        print(f"  │ {i:3d}  {line}")
    print("  └" + "─" * 65)

    # ── 13. Execution ─────────────────────────────────────────────────────────
    section("13 / 13", "Execution")
    print()
    try:
        exec(py_code, {})
        print()
        print("  ✔  Execution finished successfully.")
    except Exception:
        print()
        print("  ✘  Runtime error:")
        traceback.print_exc()


if __name__ == "__main__":
    if len(sys.argv) < 2:
        print("Usage:  python test_full_pipeline.py <file.lumen>")
        sys.exit(1)
    run_pipeline(sys.argv[1])
