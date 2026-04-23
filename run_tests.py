
# run_tests.py  -  Lumen batch test runner

# Runs all .lumen files in a folder, shows pass/fail, timing, output only.
#
# Usage:
#   python run_tests.py samples/
#   python run_tests.py samples/ --verbose
#   python run_tests.py samples/ --filter test2
#   python run_tests.py samples/test01.lumen
#   python run_tests.py samples/ --stop-on-fail

import sys
import os
import time
import traceback
import argparse
import io
import contextlib

from lexer    import lexer
from parser   import parser, get_syntax_errors, clear_syntax_errors
from semantic import analyze, SemanticWarning
from ir       import ast_to_ir, optimise
from codegen  import generate_python

# ── ANSI colours ──────────────────────────────────────────────────────────────
def _supports_colour():
    return hasattr(sys.stdout, 'isatty') and sys.stdout.isatty()

if _supports_colour():
    GREEN  = "\033[92m"
    RED    = "\033[91m"
    YELLOW = "\033[93m"
    CYAN   = "\033[96m"
    BOLD   = "\033[1m"
    DIM    = "\033[2m"
    RESET  = "\033[0m"
else:
    GREEN = RED = YELLOW = CYAN = BOLD = DIM = RESET = ""

# ── Result record ─────────────────────────────────────────────────────────────
class TestResult:
    def __init__(self, name, path):
        self.name          = name
        self.path          = path
        self.passed        = False
        self.error_phase   = None
        self.error_msg     = ""
        self.output        = ""
        self.elapsed_ms    = 0.0
        self.syntax_errors = []
        self.warnings      = []


# ── Single-file pipeline ──────────────────────────────────────────────────────
def run_one(path):
    """Run the full Lumen pipeline on one file. Returns a TestResult."""
    name   = os.path.basename(path)
    result = TestResult(name, path)
    t0     = time.perf_counter()

    try:
        # 1. Read
        with open(path) as f:
            source = f.read()

        # 2. Lex  (consume tokens just to check for lex errors)
        lexer.input(source)
        _ = list(lexer)

        # 3. Parse
        # CRITICAL: reset lineno before parsing.
        # Stage 2 consumed all tokens, leaving the lexer's lineno at the
        # end of the file. Reusing it without resetting causes the parser
        # to see wrong line numbers, silently drop statements, and report
        # variables as undefined even when they are clearly declared.
        clear_syntax_errors()
        lexer.lineno = 1
        ast = parser.parse(source, lexer=lexer)
        result.syntax_errors = get_syntax_errors()

        if not ast:
            result.error_phase = 'parse'
            result.error_msg   = "Parser returned None"
            result.elapsed_ms  = (time.perf_counter() - t0) * 1000
            return result

        # 4. Semantic
        SemanticWarning.reset()
        try:
            analyze(ast)
            result.warnings = SemanticWarning.all_warnings()
        except Exception as exc:
            result.error_phase = 'semantic'
            result.error_msg   = str(exc)
            result.warnings    = SemanticWarning.all_warnings()
            result.elapsed_ms  = (time.perf_counter() - t0) * 1000
            return result

        # 5. IR + optimise
        ir        = ast_to_ir(ast)
        ir_opt, _ = optimise(ir, report=False)

        # 6. Codegen
        py_code = generate_python(ir_opt)

        # 7. Execute and capture stdout
        buf = io.StringIO()
        try:
            with contextlib.redirect_stdout(buf):
                exec(py_code, {})
            result.output = buf.getvalue()
            result.passed = True
        except Exception as exc:
            result.output      = buf.getvalue()
            result.error_phase = 'exec'
            result.error_msg   = f"{type(exc).__name__}: {exc}"

    except FileNotFoundError:
        result.error_phase = 'io'
        result.error_msg   = f"File not found: {path}"
    except Exception as exc:
        result.error_phase = 'pipeline'
        result.error_msg   = traceback.format_exc()

    result.elapsed_ms = (time.perf_counter() - t0) * 1000
    return result


# ── Pretty print a single result ──────────────────────────────────────────────
def print_result(r, verbose=False, index=1, total=1):
    status  = f"{GREEN}PASS{RESET}" if r.passed else f"{RED}FAIL{RESET}"
    timing  = f"{r.elapsed_ms:6.1f} ms"
    print(f"  {BOLD}[{index:>3}/{total}]{RESET}  "
          f"{status}  "
          f"{CYAN}{r.name:<32}{RESET}  "
          f"{DIM}{timing}{RESET}")

    # Program output (capped at 40 lines unless --verbose)
    if r.output:
        lines = r.output.rstrip().splitlines()
        cap   = len(lines) if verbose else min(len(lines), 40)
        for line in lines[:cap]:
            print(f"         {DIM}|{RESET} {line}")
        if not verbose and len(lines) > 40:
            print(f"         {DIM}| ... ({len(lines)-40} more lines){RESET}")

    # Error detail
    if not r.passed:
        print(f"         {RED}! phase : {r.error_phase}{RESET}")
        for line in r.error_msg.splitlines()[:8]:
            print(f"         {RED}! {line}{RESET}")

    # Syntax errors
    if r.syntax_errors:
        for e in r.syntax_errors:
            print(f"         {YELLOW}~ syntax: {e}{RESET}")

    # Warnings (verbose only)
    if verbose and r.warnings:
        for w in r.warnings:
            print(f"         {YELLOW}~ warn  : {w}{RESET}")

    print()


# ── Summary ───────────────────────────────────────────────────────────────────
def print_summary(results, total_ms):
    passed = sum(1 for r in results if r.passed)
    failed = len(results) - passed
    pct    = 100 * passed // len(results) if results else 0

    bar_len = 40
    filled  = bar_len * passed // len(results) if results else 0
    bar     = (f"{GREEN}{'█' * filled}{RESET}"
               f"{RED}{'░' * (bar_len - filled)}{RESET}")

    print("─" * 68)
    print(f"  {BOLD}Results{RESET}   {bar}  {pct}%")
    print(f"  {GREEN}Passed : {passed}{RESET}   "
          f"{RED}Failed : {failed}{RESET}   "
          f"Total : {len(results)}")
    if results:
        print(f"  Wall time : {total_ms:.1f} ms   "
              f"Avg/test : {total_ms/len(results):.1f} ms")
    print("─" * 68)

    if failed:
        print(f"\n  {RED}{BOLD}Failed tests:{RESET}")
        for r in results:
            if not r.passed:
                print(f"    {RED}x  {r.name:<32}  "
                      f"[{r.error_phase}] {r.error_msg[:60]}{RESET}")
    print()


# ── Collect test files ────────────────────────────────────────────────────────
def collect_files(folder, name_filter=None):
    if os.path.isfile(folder) and folder.endswith('.lumen'):
        return [folder]
    if not os.path.isdir(folder):
        print(f"  ERROR: '{folder}' is not a directory or .lumen file")
        sys.exit(1)

    files = sorted(
        os.path.join(folder, f)
        for f in os.listdir(folder)
        if f.endswith('.lumen')
    )

    if name_filter:
        files = [f for f in files
                 if name_filter.lower() in os.path.basename(f).lower()]

    if not files:
        print(f"  No .lumen files found in '{folder}'"
              + (f" matching '{name_filter}'" if name_filter else ""))
        sys.exit(0)

    return files


# ── Entry point ───────────────────────────────────────────────────────────────
def main():
    ap = argparse.ArgumentParser(
        description="Lumen batch test runner",
        formatter_class=argparse.RawTextHelpFormatter,
        epilog=(
            "Examples:\n"
            "  python run_tests.py samples/\n"
            "  python run_tests.py samples/ --verbose\n"
            "  python run_tests.py samples/ --filter test2\n"
            "  python run_tests.py samples/test01.lumen\n"
        )
    )
    ap.add_argument("folder",
                    help="Folder of .lumen files, or a single .lumen file")
    ap.add_argument("--verbose", "-v", action="store_true",
                    help="Show all output lines and warnings")
    ap.add_argument("--filter", "-f", default=None,
                    help="Only run files whose name contains this string")
    ap.add_argument("--stop-on-fail", "-x", action="store_true",
                    help="Stop after the first failing test")
    args = ap.parse_args()

    files = collect_files(args.folder, args.filter)

    print()
    print(f"{BOLD}  Lumen Test Runner{RESET}   "
          f"{CYAN}{len(files)} file(s){RESET}   "
          f"folder: {args.folder}")
    if args.filter:
        print(f"  Filter: '{args.filter}'")
    print("─" * 68)
    print()

    results  = []
    wall_t0  = time.perf_counter()

    for idx, path in enumerate(files, 1):
        r = run_one(path)
        results.append(r)
        print_result(r, verbose=args.verbose, index=idx, total=len(files))
        if args.stop_on_fail and not r.passed:
            print(f"  {RED}Stopping on first failure (--stop-on-fail){RESET}\n")
            break

    total_ms = (time.perf_counter() - wall_t0) * 1000
    print_summary(results, total_ms)

    sys.exit(0 if all(r.passed for r in results) else 1)


if __name__ == "__main__":
    main()
