# lexer.py  –  Lumen lexical analyser
# New tokens: struct, class, extends, new, self, switch, case, default,
#             try, catch, finally, throw, const, type, ref, out,
#             TIMES (for pointer), AMP (for address-of / reference),
#             ARROW (for pointer member access)

import ply.lex as lex

# ─── Token list ───────────────────────────────────────────────────────────────
# Only non-reserved tokens go here manually.
# All reserved-word tokens are added automatically from reserved.values() below.
tokens = [
    'ID', 'NUMBER', 'STRING',
    'PLUS', 'MINUS', 'TIMES', 'DIVIDE',
    'EQ', 'NEQ', 'LT', 'GT', 'LE', 'GE',
    'DOT', 'ARROW',
    'LPAREN', 'RPAREN', 'LBRACE', 'RBRACE',
    'SEMI', 'ASSIGN', 'COMMA', 'COLON',
    'LBRACKET', 'RBRACKET',
    'AMP',       # & (address-of / reference param)
    # NOTE: 'IN' and all other reserved-word tokens are NOT listed here;
    # they are added via  tokens += list(set(reserved.values()))  below.
]

# ─── Reserved words ───────────────────────────────────────────────────────────
reserved = {
    # primitive types
    'int':      'INT',
    'float':    'FLOAT',
    'bool':     'BOOL_TYPE',
    'string':   'STRING_TYPE',
    'void':     'VOID',
    # control flow
    'if':       'IF',
    'else':     'ELSE',
    'for':      'FOR',
    'while':    'WHILE',
    'switch':   'SWITCH',
    'case':     'CASE',
    'default':  'DEFAULT',
    'break':    'BREAK',
    'continue': 'CONTINUE',
    'return':   'RETURN',
    # functions / OO
    'def':      'DEF',
    'class':    'CLASS',
    'extends':  'EXTENDS',
    'new':      'NEW',
    'self':     'SELF',
    # struct / type
    'struct':   'STRUCT',
    'type':     'TYPE',
    'const':    'CONST',
    # parameter modes
    'ref':      'REF',
    'out':      'OUT',
    # exceptions
    'try':      'TRY',
    'catch':    'CATCH',
    'finally':  'FINALLY',
    'throw':    'THROW',
    # I/O
    'print':    'PRINT',
    'input':    'INPUT',
    # astronomy
    'dataset':  'DATASET',
    'load':     'LOAD',
    'filter':   'FILTER',
    'where':    'WHERE',
    # logical
    'and':      'AND',
    'or':       'OR',
    'not':      'NOT',
    'true':     'TRUE',
    'false':    'FALSE',
    # loop helper
    'in':       'IN',
    # units
    'km':       'UNIT_KM',
    's':        'UNIT_S',
    'deg':      'UNIT_DEG',
    'arcsec':   'UNIT_ARCSEC',
    'pc':       'UNIT_PC',
    'Jy':       'UNIT_JY',
    'mag':      'UNIT_MAG',
    'au':       'UNIT_AU',
    'ly':       'UNIT_LY',
}

# Add all reserved-word token names exactly once (set deduplicates)
tokens += list(set(reserved.values()))


# ─── Simple token rules ───────────────────────────────────────────────────────
t_PLUS      = r'\+'
t_MINUS     = r'-'
t_TIMES     = r'\*'
t_DIVIDE    = r'/'
t_EQ        = r'=='
t_NEQ       = r'!='
t_LE        = r'<='
t_GE        = r'>='
t_LT        = r'<'
t_GT        = r'>'
t_ARROW     = r'->'
t_LPAREN    = r'\('
t_RPAREN    = r'\)'
t_LBRACE    = r'\{'
t_RBRACE    = r'\}'
t_SEMI      = r';'
t_ASSIGN    = r'='
t_COMMA     = r','
t_COLON     = r':'
t_LBRACKET  = r'\['
t_RBRACKET  = r'\]'
t_DOT       = r'\.'
t_AMP       = r'&'


# ─── Complex token rules ──────────────────────────────────────────────────────
def t_NUMBER(t):
    r'\d+(\.\d*)?|\.\d+'
    t.value = float(t.value)
    return t


def t_STRING(t):
    r'"[^"]*"'
    t.value = t.value[1:-1]   # strip surrounding quotes
    return t


def t_ID(t):
    r'[a-zA-Z_][a-zA-Z0-9_]*'
    t.type = reserved.get(t.value, 'ID')
    return t


def t_COMMENT(t):
    r'\#[^\n]*'
    pass   # discard comments


def t_newline(t):
    r'\n+'
    t.lexer.lineno += len(t.value)


t_ignore = ' \t\r'


def t_error(t):
    line = t.lexer.lineno
    print(f"  \u2718  Lexical error: illegal character '{t.value[0]}' at line {line}")
    t.lexer.skip(1)


# ─── Build lexer ──────────────────────────────────────────────────────────────
lexer = lex.lex()


# ─── CLI test harness ─────────────────────────────────────────────────────────
if __name__ == "__main__":
    import sys
    src = open(sys.argv[1]).read() if len(sys.argv) > 1 else 'int x = 5;'
    lexer.input(src)
    print(f"{'TYPE':<14}  {'VALUE':<20}  LINE")
    print("\u2500" * 44)
    for tok in lexer:
        print(f"{tok.type:<14}  {str(tok.value):<20}  {tok.lineno}")
