# lexer.py
import ply.lex as lex

tokens = [
    'ID', 'NUMBER', 'STRING',
    'PLUS', 'MINUS', 'TIMES', 'DIVIDE',
    'EQ', 'NEQ', 'LT', 'GT', 'LE', 'GE',
    'AND', 'OR', 'NOT',
    'LPAREN', 'RPAREN', 'LBRACE', 'RBRACE',
    'SEMI', 'ASSIGN', 'COMMA',
    'IN',
]

reserved = {
    'int': 'INT', 'float': 'FLOAT', 'bool': 'BOOL_TYPE', 'string': 'STRING_TYPE',
    'if': 'IF', 'else': 'ELSE', 'for': 'FOR', 'while': 'WHILE',
    'def': 'DEF', 'return': 'RETURN',
    'print': 'PRINT', 'input': 'INPUT',
    'dataset': 'DATASET', 'load': 'LOAD', 'filter': 'FILTER', 'where': 'WHERE',
    'coord': 'COORD', 'ra_dec': 'RA_DEC',
    'and': 'AND', 'or': 'OR', 'not': 'NOT',
    'true': 'TRUE', 'false': 'FALSE',
    # Astronomy units
    'km': 'UNIT_KM', 's': 'UNIT_S', 'deg': 'UNIT_DEG', 'arcsec': 'UNIT_ARCSEC',
    'pc': 'UNIT_PC', 'Jy': 'UNIT_JY', 'mag': 'UNIT_MAG'
}

tokens += list(reserved.values())

t_PLUS    = r'\+'
t_MINUS   = r'-'
t_TIMES   = r'\*'
t_DIVIDE  = r'/'
t_EQ      = r'=='
t_NEQ     = r'!='
t_LT      = r'<'
t_GT      = r'>'
t_LE      = r'<='
t_GE      = r'>='
t_LPAREN  = r'\('
t_RPAREN  = r'\)'
t_LBRACE  = r'\{'
t_RBRACE  = r'\}'
t_SEMI    = r';'
t_ASSIGN  = r'='
t_COMMA   = r','

def t_NUMBER(t):
    r'\d+(\.\d*)?|\.\d+'
    t.value = float(t.value)
    return t

def t_STRING(t):
    r'"[^"]*"'
    t.value = t.value[1:-1]  # remove quotes
    return t

def t_ID(t):
    r'[a-zA-Z_][a-zA-Z0-9_]*'
    t.type = reserved.get(t.value, 'ID')
    return t

t_ignore = ' \t\n\r'

def t_COMMENT(t):
    r'\#.*'
    pass

def t_error(t):
    print(f"Illegal character '{t.value[0]}' at line {t.lineno}")
    t.lexer.skip(1)

lexer = lex.lex()


if __name__ == "__main__":
    import sys
    
    if len(sys.argv) > 1:
        filename = sys.argv[1]
        try:
            with open(filename, 'r') as f:
                code = f.read()
            print(f"\nTokenizing file: {filename}\n")
        except FileNotFoundError:
            print(f"File not found: {filename}")
            sys.exit(1)
    else:
        code = """
float dist = 4.2 pc;
print(dist);
        """
        print("Tokenizing hardcoded sample...\n")

    lexer.input(code)
    while True:
        tok = lexer.token()
        if not tok:
            break
        print(f"{tok.type:12}  {tok.value}")
