# lexer.py  -  Lumen lexical analyser
#
# FIXES applied:
#   1. 'IN' removed from manual tokens list. It only appears via
#      reserved.values() now. Having it in both caused the PLY warning
#      "Token 'IN' multiply defined" which corrupted the parse table
#      and caused the first while-loop in long programs to be dropped.
#   2. 'mag', 'pc', 's' removed from reserved so they are treated as
#      plain identifiers. This fixes crashes when variables are named
#      app_mag, dist_pc, passed, etc.

import ply.lex as lex

# Pure punctuation / literal tokens only.
# DO NOT add any keyword token here - keywords come from reserved.values().
tokens = [
    'ID', 'NUMBER', 'STRING',
    'PLUS', 'MINUS', 'TIMES', 'DIVIDE',
    'EQ', 'NEQ', 'LT', 'GT', 'LE', 'GE',
    'DOT', 'ARROW',
    'LPAREN', 'RPAREN', 'LBRACE', 'RBRACE',
    'SEMI', 'ASSIGN', 'COMMA', 'COLON',
    'LBRACKET', 'RBRACKET',
    'AMP',
]

reserved = {
    # primitive types
    'int':    'INT',
    'float':  'FLOAT',
    'bool':   'BOOL_TYPE',
    'string': 'STRING_TYPE',
    'void':   'VOID',
    # control flow
    'if':       'IF',
    'else':     'ELSE',
    'for':      'FOR',
    'while':    'WHILE',
    'in':       'IN',
    'switch':   'SWITCH',
    'case':     'CASE',
    'default':  'DEFAULT',
    'break':    'BREAK',
    'continue': 'CONTINUE',
    'return':   'RETURN',
    # functions / OO
    'def':     'DEF',
    'class':   'CLASS',
    'extends': 'EXTENDS',
    'new':     'NEW',
    'self':    'SELF',
    # struct / types
    'struct': 'STRUCT',
    'type':   'TYPE',
    'const':  'CONST',
    # parameter modes
    'ref': 'REF',
    'out': 'OUT',
    # exceptions
    'try':     'TRY',
    'catch':   'CATCH',
    'finally': 'FINALLY',
    'throw':   'THROW',
    # I/O
    'print': 'PRINT',
    'input': 'INPUT',
    # astronomy
    'dataset': 'DATASET',
    'load':    'LOAD',
    'filter':  'FILTER',
    'where':   'WHERE',
    # logical
    'and': 'AND',
    'or':  'OR',
    'not': 'NOT',
    # boolean literals
    'true':  'TRUE',
    'false': 'FALSE',
    # units - only ones safe from variable name clashes
    # 'mag','pc','s' deliberately excluded
    'km':     'UNIT_KM',
    'deg':    'UNIT_DEG',
    'arcsec': 'UNIT_ARCSEC',
    'Jy':     'UNIT_JY',
    'au':     'UNIT_AU',
    'ly':     'UNIT_LY',
}

# Extend tokens with all reserved-word token types (deduplicated).
# This is the only place reserved tokens enter the list.
tokens += list(set(reserved.values()))

# ── Token rules ───────────────────────────────────────────────────────────────
# Multi-char operators first (PLY tries longer strings before shorter ones
# when rules are strings, but being explicit is safer).
t_EQ       = r'=='
t_NEQ      = r'!='
t_LE       = r'<='
t_GE       = r'>='
t_ARROW    = r'->'
t_LT       = r'<'
t_GT       = r'>'
t_PLUS     = r'\+'
t_MINUS    = r'-'
t_TIMES    = r'\*'
t_DIVIDE   = r'/'
t_LPAREN   = r'\('
t_RPAREN   = r'\)'
t_LBRACE   = r'\{'
t_RBRACE   = r'\}'
t_SEMI     = r';'
t_ASSIGN   = r'='
t_COMMA    = r','
t_COLON    = r':'
t_LBRACKET = r'\['
t_RBRACKET = r'\]'
t_DOT      = r'\.'
t_AMP      = r'&'

def t_NUMBER(t):
    r'\d+(\.\d*)?|\.\d+'
    t.value = float(t.value)
    return t

def t_STRING(t):
    r'"[^"]*"'
    t.value = t.value[1:-1]
    return t

def t_ID(t):
    r'[a-zA-Z_][a-zA-Z0-9_]*'
    t.type = reserved.get(t.value, 'ID')
    return t

def t_COMMENT(t):
    r'\#[^\n]*'
    pass

def t_newline(t):
    r'\n+'
    t.lexer.lineno += len(t.value)

t_ignore = ' \t\r'

def t_error(t):
    print(f"  Lexical error: illegal character '{t.value[0]}' at line {t.lexer.lineno}")
    t.lexer.skip(1)

lexer = lex.lex(optimize=False)

if __name__ == "__main__":
    import sys
    src = open(sys.argv[1]).read() if len(sys.argv) > 1 else 'int x = 5;'
    lexer.input(src)
    print(f"{'TYPE':<16}  {'VALUE':<24}  LINE")
    print("-" * 50)
    for tok in lexer:
        print(f"{tok.type:<16}  {str(tok.value):<24}  {tok.lineno}")
