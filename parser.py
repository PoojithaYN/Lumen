# parser.py
import ply.yacc as yacc

from lexer import tokens, lexer
from ast_nodes import (
    Program, VarDecl, Assignment, IfStmt, WhileStmt, ForStmt, FuncDef, Call,
    ContinueStmt, BreakStmt, PrintStmt, LoadDataset, FilterStmt, CoordDecl,
    BinOp, UnaryOp, Number, StringLit, BoolLit, Var, UnitExpr, RaDec,
    ArrayDecl, ArrayAccess, MemberAccess, InputStmt
)

# Precedence and associativity
precedence = (
    ('left', 'OR', 'AND'),
    ('right', 'NOT'),
    ('nonassoc', 'EQ', 'NEQ', 'LT', 'GT', 'LE', 'GE'),
    ('left', 'PLUS', 'MINUS'),
    ('left', 'TIMES', 'DIVIDE'),
)

# ─── Program ──────────────────────────────────────────────────────────────────

def p_program(p):
    '''program : statements'''
    p[0] = Program(p[1])

def p_statements(p):
    '''statements : statements statement
                  | empty'''
    if len(p) == 3:
        p[0] = p[1] + [p[2]]
    else:
        p[0] = []

def p_empty(p):
    '''empty :'''
    pass

# ─── Types ────────────────────────────────────────────────────────────────────

def p_type(p):
    '''type : INT
            | FLOAT
            | BOOL_TYPE
            | STRING_TYPE'''
    p[0] = p[1].lower()

# ─── Declarations ─────────────────────────────────────────────────────────────

def p_declaration(p):
    '''statement : type ID SEMI
                 | type ID ASSIGN expression SEMI'''
    if len(p) == 4:
        p[0] = VarDecl(p[1], p[2])
    else:
        p[0] = VarDecl(p[1], p[2], p[4])

def p_array_decl(p):
    '''statement : type LBRACKET RBRACKET ID ASSIGN LBRACKET arg_list_opt RBRACKET SEMI'''
    p[0] = ArrayDecl(p[1], p[4], p[7] if p[7] else [])

# ─── Assignment ───────────────────────────────────────────────────────────────

def p_assignment(p):
    '''statement : ID ASSIGN expression SEMI'''
    p[0] = Assignment(p[1], p[3])

# ─── If statement (braced and braceless) ──────────────────────────────────────

def p_if_braced(p):
    '''statement : IF LPAREN expression RPAREN LBRACE statements RBRACE
                 | IF LPAREN expression RPAREN LBRACE statements RBRACE ELSE LBRACE statements RBRACE'''
    if len(p) == 8:
        p[0] = IfStmt(p[3], p[6])
    else:
        p[0] = IfStmt(p[3], p[6], p[10])

def p_if_braceless(p):
    '''statement : IF LPAREN expression RPAREN simple_statement
                 | IF LPAREN expression RPAREN simple_statement ELSE simple_statement'''
    if len(p) == 6:
        p[0] = IfStmt(p[3], [p[5]])
    else:
        p[0] = IfStmt(p[3], [p[5]], [p[7]])

# simple_statement covers the one-liner body forms (no braces needed)
def p_simple_statement(p):
    '''simple_statement : CONTINUE SEMI
                        | BREAK SEMI
                        | RETURN expression SEMI
                        | ID ASSIGN expression SEMI
                        | PRINT LPAREN print_args_opt RPAREN SEMI
                        | call SEMI'''
    if p[1] == 'continue':
        p[0] = ContinueStmt()
    elif p[1] == 'break':
        p[0] = BreakStmt()
    elif p[1] == 'return':
        from ast_nodes import ReturnStmt
        p[0] = ReturnStmt(p[2]) if hasattr(__import__('ast_nodes'), 'ReturnStmt') else p[2]
    elif p[2] == '=':
        p[0] = Assignment(p[1], p[3])
    elif p[1] == 'print':
        p[0] = PrintStmt(p[3])
    else:
        p[0] = p[1]  # call

# ─── While ────────────────────────────────────────────────────────────────────

def p_while(p):
    '''statement : WHILE LPAREN expression RPAREN LBRACE statements RBRACE'''
    p[0] = WhileStmt(p[3], p[6])

# ─── For ──────────────────────────────────────────────────────────────────────

def p_for(p):
    '''statement : FOR LPAREN ID IN expression RPAREN LBRACE statements RBRACE'''
    p[0] = ForStmt(p[3], p[5], p[8])

# ─── Continue / Break ─────────────────────────────────────────────────────────

def p_continue(p):
    '''statement : CONTINUE SEMI'''
    p[0] = ContinueStmt()

def p_break(p):
    '''statement : BREAK SEMI'''
    p[0] = BreakStmt()

# ─── Function definition ──────────────────────────────────────────────────────

def p_func_def(p):
    '''statement : DEF ID LPAREN param_list_opt RPAREN LBRACE statements RBRACE
                 | DEF ID LPAREN param_list_opt RPAREN LBRACE statements return_stmt RBRACE'''
    ret = p[8] if len(p) == 10 else None
    p[0] = FuncDef(p[2], p[4], p[7], ret)

def p_return(p):
    '''return_stmt : RETURN expression SEMI'''
    p[0] = p[2]

def p_param_list_opt(p):
    '''param_list_opt : param_list
                      | '''
    p[0] = p[1] if len(p) == 2 else []

def p_param_list(p):
    '''param_list : ID COMMA param_list
                  | ID'''
    if len(p) == 4:
        p[0] = [p[1]] + p[3]
    else:
        p[0] = [p[1]]

# ─── Function call ────────────────────────────────────────────────────────────

def p_func_call_stmt(p):
    '''statement : call SEMI'''
    p[0] = p[1]

def p_call(p):
    '''call : ID LPAREN arg_list_opt RPAREN'''
    p[0] = Call(p[1], p[3])

def p_arg_list_opt(p):
    '''arg_list_opt : arg_list
                    | '''
    p[0] = p[1] if len(p) == 2 else []

def p_arg_list(p):
    '''arg_list : expression COMMA arg_list
                | expression'''
    if len(p) == 4:
        p[0] = [p[1]] + p[3]
    else:
        p[0] = [p[1]]

# ─── Print ────────────────────────────────────────────────────────────────────

def p_print(p):
    '''statement : PRINT LPAREN print_args_opt RPAREN SEMI'''
    p[0] = PrintStmt(p[3])

def p_print_args_opt(p):
    '''print_args_opt : print_args
                      | '''
    p[0] = p[1] if len(p) == 2 else []

def p_print_args(p):
    '''print_args : expression COMMA print_args
                  | expression'''
    if len(p) == 4:
        p[0] = [p[1]] + p[3]
    else:
        p[0] = [p[1]]

# ─── Input ────────────────────────────────────────────────────────────────────

def p_input_stmt(p):
    '''statement : INPUT LPAREN ID RPAREN SEMI'''
    p[0] = InputStmt(p[3])

# ─── Astronomy ────────────────────────────────────────────────────────────────

def p_load_dataset(p):
    '''statement : DATASET ID ASSIGN LOAD LPAREN STRING RPAREN SEMI'''
    p[0] = LoadDataset(p[2], p[6])

def p_filter(p):
    '''statement : FILTER ID WHERE expression SEMI'''
    p[0] = FilterStmt(p[2], p[4])

# ─── Expressions ──────────────────────────────────────────────────────────────

def p_expression_binop(p):
    '''expression : expression PLUS expression
                  | expression MINUS expression
                  | expression TIMES expression
                  | expression DIVIDE expression
                  | expression EQ expression
                  | expression NEQ expression
                  | expression LT expression
                  | expression GT expression
                  | expression LE expression
                  | expression GE expression
                  | expression AND expression
                  | expression OR expression'''
    p[0] = BinOp(p[1], p[2], p[3])

def p_expression_not(p):
    '''expression : NOT expression'''
    p[0] = UnaryOp('not', p[2])

def p_expression_group(p):
    '''expression : LPAREN expression RPAREN'''
    p[0] = p[2]

def p_expression_number(p):
    '''expression : NUMBER'''
    p[0] = Number(p[1])

def p_expression_string(p):
    '''expression : STRING'''
    p[0] = StringLit(p[1])

def p_expression_bool(p):
    '''expression : TRUE
                  | FALSE'''
    p[0] = BoolLit(p[1] == 'true')

def p_expression_id(p):
    '''expression : ID'''
    p[0] = Var(p[1])

def p_expression_unit(p):
    '''expression : NUMBER unit
                  | NUMBER unit unit'''
    unit_str = p[2]
    if len(p) == 4:
        unit_str += " " + p[3]
    p[0] = UnitExpr(p[1], unit_str)

def p_array_access(p):
    '''expression : ID LBRACKET expression RBRACKET'''
    p[0] = ArrayAccess(p[1], p[3])

def p_member_access(p):
    '''expression : expression DOT ID'''
    p[0] = MemberAccess(p[1], p[3])

def p_expression_call(p):
    '''expression : call'''
    p[0] = p[1]

# ─── Units ────────────────────────────────────────────────────────────────────

def p_unit(p):
    '''unit : UNIT_KM
            | UNIT_S
            | UNIT_DEG
            | UNIT_ARCSEC
            | UNIT_PC
            | UNIT_JY
            | UNIT_MAG'''
    p[0] = p[1].lower()

# ─── Error ────────────────────────────────────────────────────────────────────

def p_error(p):
    if p:
        print(f"Syntax error at token '{p.value}' (type {p.type}) on line {p.lineno}")
    else:
        print("Syntax error at EOF")

# Build parser
parser = yacc.yacc()
