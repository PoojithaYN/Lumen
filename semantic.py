# semantic.py
from ast_nodes import (
    Program, VarDecl, Assignment, IfStmt, WhileStmt, ForStmt, FuncDef, Call,
    ContinueStmt, BreakStmt, PrintStmt, LoadDataset, FilterStmt, CoordDecl,
    BinOp, UnaryOp, Number, StringLit, BoolLit, Var, UnitExpr, RaDec,
    ArrayDecl, ArrayAccess, MemberAccess, InputStmt
)

class SemanticError(Exception):
    pass

class SymbolTable:
    def __init__(self):
        self.scopes = [{}]

    def enter_scope(self):
        self.scopes.append({})

    def exit_scope(self):
        if len(self.scopes) > 1:
            self.scopes.pop()

    def declare(self, name, type_name, line=None):
        current = self.scopes[-1]
        if name in current:
            raise SemanticError(f"Redeclaration of '{name}' (line {line or 'unknown'})")
        current[name] = {'type': type_name, 'initialized': False}

    def lookup(self, name, line=None):
        for scope in reversed(self.scopes):
            if name in scope:
                return scope[name]
        raise SemanticError(f"Undefined variable '{name}' (line {line or 'unknown'})")

    def mark_initialized(self, name):
        sym = self.lookup(name)
        sym['initialized'] = True

    def is_initialized(self, name):
        sym = self.lookup(name)
        return sym['initialized']

    def get_type(self, name):
        sym = self.lookup(name)
        return sym['type']


def analyze(node, symtab=None, line_num=1):
    if symtab is None:
        symtab = SymbolTable()

    print(f"Semantic: Analyzing {node.__class__.__name__}")

    if isinstance(node, Program):
        print("Semantic: Starting analysis of Program")
        for stmt in node.statements:
            analyze(stmt, symtab, line_num)
            line_num += 1

    elif isinstance(node, VarDecl):
        print(f" Semantic: Declaring '{node.name}' as '{node.type}'")
        symtab.declare(node.name, node.type)
        if node.init:
            init_type = get_type(node.init, symtab)
            #  Fix: use compatible() which now handles int/float leniency
            if not compatible(node.type, init_type):
                raise SemanticError(
                    f"Type mismatch in declaration of '{node.name}': "
                    f"expected {node.type}, got {init_type}"
                )
            symtab.mark_initialized(node.name)

    elif isinstance(node, Assignment):
        print(f" Semantic: Assignment to '{node.name}'")
        var = symtab.lookup(node.name)
        expr_type = get_type(node.expr, symtab)
        if not compatible(var['type'], expr_type):
            raise SemanticError(
                f"Type mismatch in assignment to '{node.name}': "
                f"expected {var['type']}, got {expr_type}"
            )
        symtab.mark_initialized(node.name)

    elif isinstance(node, PrintStmt):
        print(" Semantic: Print statement")
        for arg in node.args:
            get_type(arg, symtab)

    elif isinstance(node, InputStmt):
        print(f" Semantic: Input statement for '{node.var_name}'")
        symtab.lookup(node.var_name)
        symtab.mark_initialized(node.var_name)

    elif isinstance(node, Var):
        print(f" Semantic: Variable use '{node.name}'")
        symtab.lookup(node.name)
        if not symtab.is_initialized(node.name):
            print(f" Warning: '{node.name}' used before initialization")

    elif isinstance(node, IfStmt):
        print(" Semantic: If statement")
        get_type(node.cond, symtab)   # validate condition expression
        symtab.enter_scope()
        for stmt in node.then:        #  Fix: was using node.then_body / node.body
            analyze(stmt, symtab, line_num)
        symtab.exit_scope()
        if node.else_:
            symtab.enter_scope()
            for stmt in node.else_:   #  Fix: was using node.else_body
                analyze(stmt, symtab, line_num)
            symtab.exit_scope()

    elif isinstance(node, WhileStmt):
        print(" Semantic: While statement")
        get_type(node.cond, symtab)
        symtab.enter_scope()
        for stmt in node.body:
            analyze(stmt, symtab, line_num)
        symtab.exit_scope()

    elif isinstance(node, ForStmt):
        print(" Semantic: For statement")
        symtab.enter_scope()
        symtab.declare(node.var, 'unknown')
        symtab.mark_initialized(node.var)
        for stmt in node.body:
            analyze(stmt, symtab, line_num)
        symtab.exit_scope()

    elif isinstance(node, FuncDef):
        print(f" Semantic: Function definition '{node.name}'")
        symtab.declare(node.name, 'func')
        symtab.enter_scope()
        for param in node.params:
            symtab.declare(param, 'unknown')
            symtab.mark_initialized(param)
        for stmt in node.body:
            analyze(stmt, symtab)
        symtab.exit_scope()

    elif isinstance(node, ContinueStmt):
        print(" Semantic: Continue statement")

    elif isinstance(node, BreakStmt):
        print(" Semantic: Break statement")

    elif isinstance(node, ArrayDecl):
        print(f" Semantic: Array declaration '{node.name}' of type '{node.elem_type}[]'")
        symtab.declare(node.name, f"{node.elem_type}[]")  #  Fix: was broken indentation
        symtab.mark_initialized(node.name)
        if node.init_list:
            for item in node.init_list:
                item_type = get_type(item, symtab)
                if not compatible(item_type, node.elem_type):
                    raise SemanticError(
                        f"Type mismatch in array init for '{node.name}': "
                        f"expected {node.elem_type}, got {item_type}"
                    )

    elif isinstance(node, ArrayAccess):
        print(f" Semantic: Array access '{node.array}[...]'")
        array_type = symtab.get_type(node.array)
        if not array_type.endswith('[]'):
            raise SemanticError(f"'{node.array}' is not an array")
        get_type(node.index, symtab)

    elif isinstance(node, MemberAccess):
        print(f" Semantic: Member access '.{node.member}'")
        # .length and similar are valid — no error needed

    elif isinstance(node, LoadDataset):
        print(f" Semantic: Load dataset '{node.name}'")
        symtab.declare(node.name, 'dataset')
        symtab.mark_initialized(node.name)

    elif isinstance(node, FilterStmt):
        print(f" Semantic: Filter on '{node.dataset}'")
        symtab.lookup(node.dataset)
        get_type(node.cond, symtab)

    elif isinstance(node, Call):
        print(f" Semantic: Function call '{node.name}'")
        for arg in node.args:
            get_type(arg, symtab)

    else:
        print(f" Semantic: Unhandled node type '{node.__class__.__name__}'")


def get_type(expr, symtab):
    if isinstance(expr, Number):
        # Fix: whole floats (0.0, 1.0) are treated as int-compatible
        v = expr.value
        if isinstance(v, float) and v.is_integer():
            return 'int'
        return 'float'

    if isinstance(expr, UnitExpr):
        return 'float'

    if isinstance(expr, StringLit):
        return 'string'

    if isinstance(expr, BoolLit):
        return 'bool'

    if isinstance(expr, Var):
        return symtab.get_type(expr.name)

    if isinstance(expr, BinOp):
        left_t  = get_type(expr.left,  symtab)
        right_t = get_type(expr.right, symtab)
        # comparison operators always return bool
        if expr.op in ('==', '!=', '<', '>', '<=', '>=', 'and', 'or'):
            return 'bool'
        if compatible(left_t, right_t):
            # int op float → float
            if 'float' in (left_t, right_t):
                return 'float'
            return left_t
        raise SemanticError(f"Incompatible types in binary op: {left_t} vs {right_t}")

    if isinstance(expr, UnaryOp):
        return get_type(expr.expr, symtab)

    if isinstance(expr, ArrayAccess):
        array_type = symtab.get_type(expr.array)
        return array_type.replace('[]', '') if array_type.endswith('[]') else 'unknown'

    if isinstance(expr, MemberAccess):
        # .length always returns int
        if expr.member == 'length':
            return 'int'
        return 'unknown'

    if isinstance(expr, Call):
        return 'unknown'

    return 'unknown'


def compatible(t1, t2):
    if t1 == t2:
        return True
    if 'unknown' in (t1, t2):
        return True
    #  Fix: int and float are mutually compatible (lexer emits all numbers as float)
    if set([t1, t2]) <= {'int', 'float'}:
        return True
    return False
