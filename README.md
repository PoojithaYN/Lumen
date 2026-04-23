# Lumen — A Domain-Specific Language for Astronomical Data Processing

**Lumen** is a fully implemented compiled language designed for astronomical computation. It provides clean, readable syntax for common astronomy tasks — loading catalogues, filtering objects, computing derived quantities like absolute magnitude and luminosity, and working with sky coordinates — while catching errors like unit mismatches and type conflicts at compile time.

Lumen transpiles to Python 3 and leverages `astropy`, `numpy`, and `pandas` as its runtime backend, so astronomers get professional-grade computation without writing boilerplate Python.

---

## Team

**Group 13**

| Name | Roll Number |
|---|---|
| Poojitha YN | CS23B043 |
| Lavudya Mounika | CS23B027 |
| Geddam Moukika Neha Datta | CS23B020 |

---

## Project Structure
Lumen/
├── lexer.py                - Lexical analyser (PLY lex)
├── parser.py               - Parser and grammar (PLY yacc)
├── ast_nodes.py            - AST node class definitions
├── ast_viz.py              - AST visualiser (box-drawing tree)
├── semantic.py             - Semantic analyser, symbol table, type checker
├── ir.py                   - IR generation, 7 optimisation passes,
│                           - CFG, SSA, quadruples, heap/stack model
├── codegen.py              - Python code generator
├── test_full_pipeline.py   - Single-file compiler driver (13 stages)
├── run_tests.py            - Batch test runner for all .lumen files
├── Makefile                - Build, test, clean automation
└── samples/                - Example and test .lumen programs
├── demo.lumen
├── optimisation_demo.lumen
├── test01.lumen
├── test02.lumen
│   ... (test01 through test50)
└── test50.lumen

---

## Requirements

### Python version

Python 3.8 or higher

Check your version:

```bash
python3 --version
```

### System dependencies

No C compiler or external build tools are required. Everything runs in pure Python.

---

## Installation

### Step 1 — Clone or download the project

```bash
git clone https://github.com/your-repo/lumen.git
cd lumen
```

Or simply unzip the project folder and navigate into it.

### Step 2 — Create a virtual environment (recommended)

```bash
python3 -m venv venv
```

Activate it:

```bash
# macOS / Linux
source venv/bin/activate

# Windows (Command Prompt)
venv\Scripts\activate.bat

# Windows (PowerShell)
venv\Scripts\Activate.ps1
```

### Step 3 — Install all required packages

```bash
pip install -r requirements.txt
```

If you do not have a `requirements.txt` yet, install the packages directly:

```bash
pip install ply astropy numpy pandas
```

---

## Required Packages

| Package | Version | Purpose |
|---|---|---|
| `ply` | >= 3.11 | Lexer (lex) and parser (yacc) — the compiler frontend |
| `astropy` | >= 5.0 | Astronomy units, sky coordinates in generated code |
| `numpy` | >= 1.21 | Numerical computation in generated code |
| `pandas` | >= 1.3 | Dataset loading and filtering in generated code |

All four packages are required. `ply` is needed to build and run the compiler itself. `astropy`, `numpy`, and `pandas` are imported into the Python code that Lumen generates, so they must be present at execution time.

To generate `requirements.txt`:

```bash
pip freeze > requirements.txt
```

Or create it manually with these contents:
ply>=3.11
astropy>=5.0
numpy>=1.21
pandas>=1.3

---

## Running the Compiler

### Compile and run a single Lumen file

```bash
python test_full_pipeline.py samples/demo.lumen
```

This runs all 13 stages of the compiler pipeline and prints detailed output for each stage.

### Run all test cases at once

```bash
python run_tests.py samples/
```

### Run only specific tests (filter by name)

```bash
python run_tests.py samples/ --filter test1
```

### Run with full output and warnings shown

```bash
python run_tests.py samples/ --verbose
```

### Stop on the first failing test

```bash
python run_tests.py samples/ --stop-on-fail
```

---

## The Compiler Pipeline

When you run `python test_full_pipeline.py file.lumen`, the program passes through 13 stages:

| Stage | Name | What it does |
|---|---|---|
| 1 | Reading Source | Loads the `.lumen` file and displays it with line numbers |
| 2 | Lexical Analysis | Tokenises the source into typed tokens with line numbers |
| 3 | Parsing | Builds the Abstract Syntax Tree from the token stream |
| 4 | AST Visualisation | Prints the AST as a box-drawing tree |
| 5 | Semantic Analysis | Type checking, scope analysis, unit validation |
| 6 | IR Generation | Converts AST to flat Intermediate Representation |
| 7 | Quadruples | Converts IR to classic (op, arg1, arg2, result) table |
| 8 | IR Optimisation | Runs 7 optimisation passes (see below) |
| 9 | SSA Form | Renames variables with version subscripts, inserts phi-functions |
| 10 | Control-Flow Graph | Splits IR into basic blocks with liveness analysis |
| 11 | Activation Records | Computes stack frame layout for each function |
| 12 | Heap Allocation | Simulates malloc/free for all heap-allocated objects |
| 13 | Code Generation | Emits Python 3 source and executes it |

---

## Language Features

### Variable declarations

int x = 5;
float dist = 4.2;
bool visible = true;
string name = "Sirius";
const float PI = 3.14159;
type Parsecs = float;

### Arrays

float[] magnitudes = [1.46, 0.03, 0.72];
int[]   classes    = [2, 3, 2];
print(magnitudes[0]);

### Control flow

if (x > 10) {
print("large");
} else {
print("small");
}
while (i < N) {
i = i + 1;
}
switch (code) {
case 1: { print("one"); }
case 2: { print("two"); }
}

### Functions and recursion

def factorial(int n) {
if (n <= 1) { return 1; }
return n * factorial(n - 1);
}


### Exception handling

try {
float result = safe_divide(a, b);
} catch (err) {
print("Error:", err);
} finally {
print("done");
}
throw "something went wrong";

### Structs and classes

struct Star {
float ra;
float dec;
float magnitude;
}
class Telescope {
float aperture;
def observe(float ra, float dec) {
print("Observing", ra, dec);
return 0;
}
}

### Astronomy features

Unit-aware expressions (deg, km, au, ly, arcsec, Jy)
float angle = 23.5 deg;
float baseline = 1.0 au;
Sky coordinate declaration
coord target = (83.82 deg, -5.39 deg);
Dataset loading and filtering
dataset stars = load("hipparcos.csv");
filter stars where stars.magnitude < 6.0;

---

## Optimisation Passes

All 7 passes run in `ir.py` during Stage 8 and iterate to a fixed point:

| Pass | What it does | Example |
|---|---|---|
| Constant folding | Evaluates literal expressions at compile time | `3 + 5` → `8` |
| Constant propagation | Substitutes known constant variables | `x=8; y=x+1` → `y=9` |
| Copy propagation | Eliminates redundant variable copies | `a=b; c=a` → `c=b` |
| Algebraic simplification | Applies mathematical identities | `x*1` → `x`, `x+0` → `x`, `x*0` → `0` |
| Strength reduction | Replaces expensive ops with cheaper ones | `x*2` → `x+x` |
| Common subexpression elimination | Hoists repeated sub-expressions | `PI*r*r` computed once |
| Dead code elimination | Removes temporaries that are never read | `__t3` removed if unused |

---

## Error Types Detected

| Category | Example error | Phase |
|---|---|---|
| Lexical error | Illegal character `@` | Stage 2 |
| Syntax error | Missing semicolon | Stage 3 |
| Undefined variable | `x` used before declaration | Stage 5 |
| Type mismatch | `int x = "hello"` | Stage 5 |
| Const reassignment | `N = 10` where `N` is const | Stage 5 |
| Unit mismatch | `4.2 km + 23.5 deg` | Stage 5 |
| Break outside loop | `break` at top level | Stage 5 |
| Uninitialised variable | Variable used before assignment | Stage 5 warning |
| Unused variable | Declared but never read | Stage 5 warning |
| Runtime exception | Division by zero (caught by try/catch) | Stage 13 |

---

## Writing Lumen Programs

### Rules to follow

- Every statement ends with a semicolon `;`
- Blocks use curly braces `{ }`
- Variables must be declared with a type before use
- Functions are defined with `def`
- Use `print(a, b, c)` for output — multiple arguments are separated by commas
- Comments start with `#`

### Variable naming

Avoid naming variables `mag`, `pc`, or `s` — these were astronomy unit keywords and may cause parsing issues in some versions. Use `magnitude`, `parsecs`, `seconds` instead.

### Recommended naming conventions

| Purpose | Good name | Avoid |
|---|---|---|
| Throwaway return capture | `dummy` or `_result` | (any other name — triggers unused warning) |
| Loop counter | `i`, `j`, `k`, `idx` | (fine — loop vars never trigger unused warning) |
| Distance variable | `dist`, `distance`, `dist_au` | `pc` (reserved in older versions) |
| Magnitude variable | `magnitude`, `app_mag`, `absmag` | `mag` (reserved in older versions) |

---

## Generating the CFG Diagram

Stage 10 automatically writes a `file_cfg.dot` Graphviz file next to your input file.
To render it as an image:

```bash
# Install Graphviz if not already installed
# macOS
brew install graphviz

# Ubuntu / Debian
sudo apt install graphviz

# Then render
dot -Tpng samples/demo_cfg.dot -o cfg.png
open cfg.png
```

---

## Troubleshooting

### `Token 'IN' multiply defined` warning

Delete the PLY cache files and re-run:

```bash
rm -f parsetab.py parser.out lextab.py
python test_full_pipeline.py samples/demo.lumen
```

### Variables appear undefined when they are clearly declared

The lexer's line counter was not reset between Stage 2 and Stage 3. Make sure you are using the latest `test_full_pipeline.py` which contains `lexer.lineno = 1` before the `parser.parse()` call.

### `ModuleNotFoundError: No module named 'ply'`

```bash
pip install ply
```

### `ModuleNotFoundError: No module named 'astropy'`

```bash
pip install astropy
```

### Generated code fails with `AttributeError`

Do not use `new ClassName(...)` with struct types in the current version. Structs are defined with `struct` but instantiated as plain variables with parallel arrays. The `new` keyword works for `class` definitions only.

---

## Running Tests with Make

```bash
make test          # run all test cases
make demo          # run the demo program
make optimisation  # run the optimisation demo
make clean         # remove PLY cache files
make help          # show all available targets
```

---

## License

This project was developed as part of a Compilers course assignment at IIT Tirupati.
