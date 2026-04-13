# parser.py  –  Lumen parser (PLY yacc)
# Extensions over previous version:
#   • struct definition and literal
#   • class definition (with extends), new, self
#   • pointer / reference declarations  (int* p = &x;  int& r = x;)
#   • parameter passing modes  (ref / out / const)
#   • type aliases  (type Mag = float;)
#   • switch / case / default
#   • try / catch / finally  +  throw
#   • return statement as a full statement
#   • const declarations
#   • error recovery: skip to next SEMI on bad token
#   • lineno stored on every node
#
# FIXES applied:
#   1. p_unit: each alternative on its own line (PLY docstring requirement)
#   2. 'IN' removed from manual tokens list in lexer (duplicate token fix)
#   3. p_return / p_func_def: removed redundant return_stmt non-terminal
#      to eliminate reduce/reduce conflict
#   4. %prec IFX added to braceless and braced if-without-else rules
#      to resolve dangling-else shift/reduce conflict
#   5. AMP added to precedence table with %prec LOWER_THAN_AMP on
#      type->type AMP rule to resolve type reference shift/reduce conflict

import ply.yacc as yacc
from lexer import tokens, lexer
from ast_nodes import *


# ─── Operator precedence ──────────────────────────────────────────────────────
precedence = (
    ('left',     'OR'),
    ('left',     'AND'),
    ('right',    'NOT'),
    ('nonassoc', 'EQ', 'NEQ', 'LT', 'GT', 'LE', 'GE'),
    ('left',     'PLUS', 'MINUS'),
    ('left',     'TIMES', 'DIVIDE'),
    ('right',    'UMINUS', 'UDEREF', 'UADDR'),   # unary prefix
    ('left',     'DOT', 'ARROW'),
    ('nonassoc', 'IFX'),            # bare if with no else
    ('nonassoc', 'ELSE'),           # else binds tighter than bare IFX
    ('nonassoc', 'LOWER_THAN_AMP'), # sentinel: sits just below AMP
    ('nonassoc', 'AMP'),            # resolves type& vs address-of conflict
)


# ─── Helpers ──────────────────────────────────────────────────────────────────
def _ln(p, pos=1):
    """Return lineno from PLY production item."""
    try:
        return p.lineno(pos)
    except Exception:
        return None


# ─── Program ──────────────────────────────────────────────────────────────────
def p_program(p):
    '''program : statements'''
    p[0] = Program(p[1])


def p_statements(p):
    '''statements : statements statement
                  | empty'''
    p[0] = (p[1] + [p[2]]) if len(p) == 3 else []


def p_empty(p):
    '''empty :'''
    pass


# ─── Types ────────────────────────────────────────────────────────────────────
def p_type_primitive(p):
    '''type : INT
            | FLOAT
            | BOOL_TYPE
            | STRING_TYPE
            | VOID
            | ID'''
    p[0] = p[1].lower() if p[1] not in ('void',) else p[1]


def p_type_pointer(p):
    '''type : type TIMES'''
    p[0] = p[1] + '*'


def p_type_ref(p):
    '''type : type AMP %prec LOWER_THAN_AMP'''
    p[0] = p[1] + '&'


# ─── Type alias ───────────────────────────────────────────────────────────────
def p_type_alias(p):
    '''statement : TYPE ID ASSIGN type SEMI'''
    p[0] = TypeAlias(p[2], p[4], lineno=_ln(p))


# ─── Const declaration ────────────────────────────────────────────────────────
def p_const_decl(p):
    '''statement : CONST type ID ASSIGN expression SEMI'''
    p[0] = ConstDecl(p[2], p[3], p[5], lineno=_ln(p))


# ─── Struct definition ────────────────────────────────────────────────────────
def p_struct_def(p):
    '''statement : STRUCT ID LBRACE struct_fields RBRACE'''
    p[0] = StructDef(p[2], p[4], lineno=_ln(p))


def p_struct_fields(p):
    '''struct_fields : struct_fields struct_field
                     | empty'''
    p[0] = (p[1] + [p[2]]) if len(p) == 3 else []


def p_struct_field(p):
    '''struct_field : type ID SEMI'''
    p[0] = (p[1], p[2])


# ─── Class definition ─────────────────────────────────────────────────────────
def p_class_def(p):
    '''statement : CLASS ID LBRACE class_members RBRACE
                 | CLASS ID EXTENDS ID LBRACE class_members RBRACE'''
    if len(p) == 6:
        fields, methods = p[4]
        p[0] = ClassDef(p[2], None, fields, methods, lineno=_ln(p))
    else:
        fields, methods = p[6]
        p[0] = ClassDef(p[2], p[4], fields, methods, lineno=_ln(p))


def p_class_members(p):
    '''class_members : class_members class_member
                     | empty'''
    if len(p) == 3:
        fields, methods = p[1]
        f2, m2 = p[2]
        p[0] = (fields + f2, methods + m2)
    else:
        p[0] = ([], [])


def p_class_member_field(p):
    '''class_member : type ID SEMI'''
    p[0] = ([(p[1], p[2])], [])


def p_class_member_method(p):
    '''class_member : func_def_inner'''
    p[0] = ([], [p[1]])


def p_func_def_inner(p):
    '''func_def_inner : DEF ID LPAREN param_list_opt RPAREN LBRACE statements RBRACE'''
    p[0] = FuncDef(p[2], p[4], p[7], None, lineno=_ln(p))


# ─── Pointer / reference declarations ────────────────────────────────────────
def p_pointer_decl(p):
    '''statement : type TIMES ID SEMI
                 | type TIMES ID ASSIGN expression SEMI'''
    if len(p) == 5:
        p[0] = PointerDecl(p[1], p[3], lineno=_ln(p))
    else:
        p[0] = PointerDecl(p[1], p[3], p[5], lineno=_ln(p))


def p_ref_decl(p):
    '''statement : type AMP ID ASSIGN expression SEMI'''
    p[0] = ReferenceDecl(p[1], p[3], p[5], lineno=_ln(p))


def p_deref_assign(p):
    '''statement : TIMES ID ASSIGN expression SEMI'''
    p[0] = DerefAssign(p[2], p[4], lineno=_ln(p))


# ─── Variable declarations ────────────────────────────────────────────────────
def p_declaration(p):
    '''statement : type ID SEMI
                 | type ID ASSIGN expression SEMI'''
    if len(p) == 4:
        p[0] = VarDecl(p[1], p[2], lineno=_ln(p))
    else:
        p[0] = VarDecl(p[1], p[2], p[4], lineno=_ln(p))


def p_array_decl(p):
    '''statement : type LBRACKET RBRACKET ID ASSIGN LBRACKET arg_list_opt RBRACKET SEMI'''
    p[0] = ArrayDecl(p[1], p[4], p[7] or [], lineno=_ln(p))


# ─── Assignment ───────────────────────────────────────────────────────────────
def p_assignment(p):
    '''statement : ID ASSIGN expression SEMI'''
    p[0] = Assignment(p[1], p[3], lineno=_ln(p))


# ─── If / else ────────────────────────────────────────────────────────────────
def p_if_braced(p):
    '''statement : IF LPAREN expression RPAREN LBRACE statements RBRACE %prec IFX
                 | IF LPAREN expression RPAREN LBRACE statements RBRACE ELSE LBRACE statements RBRACE'''
    if len(p) == 8:
        p[0] = IfStmt(p[3], p[6], lineno=_ln(p))
    else:
        p[0] = IfStmt(p[3], p[6], p[10], lineno=_ln(p))


def p_if_braceless(p):
    '''statement : IF LPAREN expression RPAREN simple_statement %prec IFX
                 | IF LPAREN expression RPAREN simple_statement ELSE simple_statement'''
    if len(p) == 6:
        p[0] = IfStmt(p[3], [p[5]], lineno=_ln(p))
    else:
        p[0] = IfStmt(p[3], [p[5]], [p[7]], lineno=_ln(p))


def p_simple_statement(p):
    '''simple_statement : CONTINUE SEMI
                        | BREAK SEMI
                        | RETURN expression SEMI
                        | ID ASSIGN expression SEMI
                        | PRINT LPAREN print_args_opt RPAREN SEMI
                        | call SEMI'''
    if p[1] == 'continue':    p[0] = ContinueStmt(lineno=_ln(p))
    elif p[1] == 'break':     p[0] = BreakStmt(lineno=_ln(p))
    elif p[1] == 'return':    p[0] = ReturnStmt(p[2], lineno=_ln(p))
    elif p[2] == '=':         p[0] = Assignment(p[1], p[3], lineno=_ln(p))
    elif p[1] == 'print':     p[0] = PrintStmt(p[3], lineno=_ln(p))
    else:                     p[0] = p[1]


# ─── Switch / case ────────────────────────────────────────────────────────────
def p_switch(p):
    '''statement : SWITCH LPAREN expression RPAREN LBRACE case_list RBRACE
                 | SWITCH LPAREN expression RPAREN LBRACE case_list DEFAULT COLON LBRACE statements RBRACE RBRACE'''
    if len(p) == 8:
        p[0] = SwitchStmt(p[3], p[6], lineno=_ln(p))
    else:
        p[0] = SwitchStmt(p[3], p[6], p[10], lineno=_ln(p))


def p_case_list(p):
    '''case_list : case_list case_item
                 | empty'''
    p[0] = (p[1] + [p[2]]) if len(p) == 3 else []


def p_case_item(p):
    '''case_item : CASE expression COLON LBRACE statements RBRACE'''
    p[0] = (p[2], p[5])


# ─── While ────────────────────────────────────────────────────────────────────
def p_while(p):
    '''statement : WHILE LPAREN expression RPAREN LBRACE statements RBRACE'''
    p[0] = WhileStmt(p[3], p[6], lineno=_ln(p))


# ─── For ──────────────────────────────────────────────────────────────────────
def p_for(p):
    '''statement : FOR LPAREN ID IN expression RPAREN LBRACE statements RBRACE'''
    p[0] = ForStmt(p[3], p[5], p[8], lineno=_ln(p))


# ─── Continue / Break / Return ────────────────────────────────────────────────
def p_continue(p):
    '''statement : CONTINUE SEMI'''
    p[0] = ContinueStmt(lineno=_ln(p))


def p_break(p):
    '''statement : BREAK SEMI'''
    p[0] = BreakStmt(lineno=_ln(p))


def p_return_stmt(p):
    '''statement : RETURN expression SEMI
                 | RETURN SEMI'''
    expr = p[2] if len(p) == 4 else None
    p[0] = ReturnStmt(expr, lineno=_ln(p))


# ─── Try / catch / finally ────────────────────────────────────────────────────
def p_try(p):
    '''statement : TRY LBRACE statements RBRACE CATCH LPAREN ID RPAREN LBRACE statements RBRACE
                 | TRY LBRACE statements RBRACE CATCH LPAREN ID RPAREN LBRACE statements RBRACE FINALLY LBRACE statements RBRACE'''
    if len(p) == 12:
        p[0] = TryStmt(p[3], p[7], p[10], lineno=_ln(p))
    else:
        p[0] = TryStmt(p[3], p[7], p[10], p[14], lineno=_ln(p))


def p_throw(p):
    '''statement : THROW expression SEMI'''
    p[0] = ThrowStmt(p[2], lineno=_ln(p))


# ─── Function definition ──────────────────────────────────────────────────────
def p_func_def(p):
    '''statement : DEF ID LPAREN param_list_opt RPAREN LBRACE statements RBRACE'''
    p[0] = FuncDef(p[2], p[4], p[7], None, lineno=_ln(p))


def p_param_list_opt(p):
    '''param_list_opt : param_list
                      | '''
    p[0] = p[1] if len(p) == 2 else []


def p_param_list(p):
    '''param_list : param COMMA param_list
                  | param'''
    p[0] = [p[1]] + p[3] if len(p) == 4 else [p[1]]


def p_param(p):
    '''param : type ID
             | REF type ID
             | OUT type ID
             | CONST type ID'''
    if len(p) == 3:
        p[0] = Param(p[2], p[1], 'val', lineno=_ln(p))
    else:
        mode = {'ref': 'ref', 'out': 'out', 'const': 'const'}[p[1]]
        p[0] = Param(p[3], p[2], mode, lineno=_ln(p))


def p_param_bare_id(p):
    '''param : ID'''
    p[0] = Param(p[1], 'unknown', 'val', lineno=_ln(p))


# ─── Function call ────────────────────────────────────────────────────────────
def p_func_call_stmt(p):
    '''statement : call SEMI'''
    p[0] = p[1]


def p_call(p):
    '''call : ID LPAREN arg_list_opt RPAREN'''
    p[0] = Call(p[1], p[3], lineno=_ln(p))


def p_arg_list_opt(p):
    '''arg_list_opt : arg_list
                    | '''
    p[0] = p[1] if len(p) == 2 else []


def p_arg_list(p):
    '''arg_list : expression COMMA arg_list
                | expression'''
    p[0] = [p[1]] + p[3] if len(p) == 4 else [p[1]]


# ─── Print / Input ────────────────────────────────────────────────────────────
def p_print(p):
    '''statement : PRINT LPAREN print_args_opt RPAREN SEMI'''
    p[0] = PrintStmt(p[3], lineno=_ln(p))


def p_print_args_opt(p):
    '''print_args_opt : print_args
                      | '''
    p[0] = p[1] if len(p) == 2 else []


def p_print_args(p):
    '''print_args : expression COMMA print_args
                  | expression'''
    p[0] = [p[1]] + p[3] if len(p) == 4 else [p[1]]


def p_input_stmt(p):
    '''statement : INPUT LPAREN ID RPAREN SEMI'''
    p[0] = InputStmt(p[3], lineno=_ln(p))


# ─── Astronomy ────────────────────────────────────────────────────────────────
def p_load_dataset(p):
    '''statement : DATASET ID ASSIGN LOAD LPAREN STRING RPAREN SEMI'''
    p[0] = LoadDataset(p[2], p[6], lineno=_ln(p))


def p_filter(p):
    '''statement : FILTER ID WHERE expression SEMI'''
    p[0] = FilterStmt(p[2], p[4], lineno=_ln(p))


# ─── Expressions ──────────────────────────────────────────────────────────────
def p_binop(p):
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
    p[0] = BinOp(p[1], p[2], p[3], lineno=_ln(p))


def p_not(p):
    '''expression : NOT expression'''
    p[0] = UnaryOp('not', p[2], lineno=_ln(p))


def p_uminus(p):
    '''expression : MINUS expression %prec UMINUS'''
    p[0] = UnaryOp('-', p[2], lineno=_ln(p))


def p_address_of(p):
    '''expression : AMP ID %prec UADDR'''
    p[0] = AddressOf(p[2], lineno=_ln(p))


def p_deref_expr(p):
    '''expression : TIMES expression %prec UDEREF'''
    p[0] = Deref(p[2], lineno=_ln(p))


def p_group(p):
    '''expression : LPAREN expression RPAREN'''
    p[0] = p[2]


def p_number(p):
    '''expression : NUMBER'''
    p[0] = Number(p[1], lineno=_ln(p))


def p_string(p):
    '''expression : STRING'''
    p[0] = StringLit(p[1], lineno=_ln(p))


def p_bool(p):
    '''expression : TRUE
                  | FALSE'''
    p[0] = BoolLit(p[1] == 'true', lineno=_ln(p))


def p_id(p):
    '''expression : ID'''
    p[0] = Var(p[1], lineno=_ln(p))


def p_self(p):
    '''expression : SELF'''
    p[0] = SelfExpr(lineno=_ln(p))


def p_unit_expr(p):
    '''expression : NUMBER unit
                  | NUMBER unit unit'''
    unit_str = p[2] + (' ' + p[3] if len(p) == 4 else '')
    p[0] = UnitExpr(p[1], unit_str, lineno=_ln(p))


def p_array_access(p):
    '''expression : ID LBRACKET expression RBRACKET'''
    p[0] = ArrayAccess(p[1], p[3], lineno=_ln(p))


def p_member_access(p):
    '''expression : expression DOT ID
                  | expression ARROW ID'''
    p[0] = MemberAccess(p[1], p[3], lineno=_ln(p))


def p_call_expr(p):
    '''expression : call'''
    p[0] = p[1]


def p_new_expr(p):
    '''expression : NEW ID LPAREN arg_list_opt RPAREN'''
    p[0] = NewExpr(p[2], p[4], lineno=_ln(p))


def p_struct_lit(p):
    '''expression : ID LBRACE struct_field_inits RBRACE'''
    p[0] = StructLit(p[1], p[3], lineno=_ln(p))


def p_struct_field_inits(p):
    '''struct_field_inits : struct_field_inits COMMA struct_field_init
                          | struct_field_init'''
    p[0] = p[1] + [p[3]] if len(p) == 4 else [p[1]]


def p_struct_field_init(p):
    '''struct_field_init : ID COLON expression'''
    p[0] = (p[1], p[3])


# ─── Units ────────────────────────────────────────────────────────────────────
# Each alternative MUST be on its own line in PLY docstrings.
def p_unit(p):
    '''unit : UNIT_KM
            | UNIT_S
            | UNIT_DEG
            | UNIT_ARCSEC
            | UNIT_PC
            | UNIT_JY
            | UNIT_MAG
            | UNIT_AU
            | UNIT_LY'''
    p[0] = p[1].lower()


# ─── Error recovery ───────────────────────────────────────────────────────────
_syntax_errors = []


def p_error(p):
    if p:
        msg = (f"Syntax error: unexpected token '{p.value}' "
               f"(type {p.type}) at line {p.lineno}")
        print(f"  \u2718  {msg}")
        _syntax_errors.append(msg)
        # Skip tokens until we find a statement boundary
        while True:
            tok = parser.token()
            if tok is None or tok.type in ('SEMI', 'RBRACE'):
                break
        parser.restart()
    else:
        msg = "Syntax error: unexpected end of file"
        print(f"  \u2718  {msg}")
        _syntax_errors.append(msg)


def get_syntax_errors():
    return list(_syntax_errors)


def clear_syntax_errors():
    _syntax_errors.clear()


# ─── Build parser ─────────────────────────────────────────────────────────────
parser = yacc.yacc()
