# semantic.py
from ast_nodes import *  # import your Node classes

class SemanticError(Exception):
    pass

class SymbolTable:
    def __init__(self):
        self.scopes = [{}]  # list of dicts: global + nested scopes

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
            line_num += 1  # rough line tracking

    elif isinstance(node, VarDecl):
        print(f" Semantic: Declaring '{node.name}' as '{node.type}'")
        symtab.declare(node.name, node.type)
        if node.init:
            init_type = get_type(node.init, symtab)
            if not compatible(init_type, node.type):
                raise SemanticError(f"Type mismatch in declaration of '{node.name}': expected {node.type}, got {init_type}")
            symtab.mark_initialized(node.name)

    elif isinstance(node, Assignment):
        print(f" Semantic: Assignment to '{node.name}'")
        var = symtab.lookup(node.name)
        expr_type = get_type(node.expr, symtab)
        if not compatible(var['type'], expr_type):
            raise SemanticError(f"Type mismatch in assignment to '{node.name}': expected {var['type']}, got {expr_type}")
        symtab.mark_initialized(node.name)

    elif isinstance(node, PrintStmt):
        print(" Semantic: Print statement")
        for arg in node.args:
            get_type(arg, symtab)  # ensure vars are declared

    elif isinstance(node, Var):
        print(f" Semantic: Variable use '{node.name}'")
        symtab.lookup(node.name)
        if not symtab.is_initialized(node.name):
            print(f" Warning: '{node.name}' used before initialization")

    # Block structures - enter/exit scope
    elif isinstance(node, (IfStmt, WhileStmt, ForStmt)):
        symtab.enter_scope()
        body = node.then if hasattr(node, 'then') else node.body
        for stmt in body:
            analyze(stmt, symtab, line_num)
            line_num += 1
        if hasattr(node, 'else_') and node.else_:
            for stmt in node.else_:
                analyze(stmt, symtab, line_num)
                line_num += 1
        symtab.exit_scope()

    # Function definition - enter new scope for parameters and body
    elif isinstance(node, FuncDef):
        print(f" Semantic: Function definition '{node.name}'")
        symtab.enter_scope()
        # Declare parameters
        for param in node.params:
            symtab.declare(param, 'unknown')  # type can be refined later
        for stmt in node.body:
            analyze(stmt, symtab)
        symtab.exit_scope()

    # Continue and Break - basic recognition (add loop check later)
    elif isinstance(node, ContinueStmt):
        print(" Semantic: Continue statement")

    elif isinstance(node, BreakStmt):
        print(" Semantic: Break statement")

    elif isinstance(node, ArrayDecl):
        print(f" Semantic: Array declaration '{node.name}' of type '{node.elem_type}[]'")
        symtab.declare(node.name, f"{node.elem_type}[]")
        symtab.mark_initialized(node.name)
        if node.init_list:
            for item in node.init_list:
                item_type = get_type(item, symtab)
                if not compatible(item_type, node.elem_type):
                    raise SemanticError(f"Type mismatch in array init for '{node.name}'")

    elif isinstance(node, ArrayAccess):
        print(f" Semantic: Array access '{node.array}[...]'")
        array_type = symtab.get_type(node.array)
        if not array_type.endswith('[]'):
            raise SemanticError(f"'{node.array}' is not an array")
        get_type(node.index, symtab)  # index should be int/float
    
    elif isinstance(node, MemberAccess):
        print(f"  Semantic: Member access '{node.member}' on '{node.expr}'")
    # Future: check if expr is array and member is 'length', etc.
        get_type(node.expr, symtab)
    # Add more node types as needed

def get_type(expr, symtab):
    if isinstance(expr, Number) or isinstance(expr, UnitExpr):
        return 'float'
    if isinstance(expr, StringLit):
        return 'string'
    if isinstance(expr, BoolLit):
        return 'bool'
    if isinstance(expr, Var):
        return symtab.get_type(expr.name)
    if isinstance(expr, BinOp):
        left_t = get_type(expr.left, symtab)
        right_t = get_type(expr.right, symtab)
        if left_t == right_t:
            return left_t
        raise SemanticError(f"Incompatible types in binary op: {left_t} vs {right_t}")
    if isinstance(expr, Call):
        # Future: lookup function return type
        return 'unknown'
    return 'unknown'

def compatible(t1, t2):
    return t1 == t2 or t1 == 'unknown' or t2 == 'unknown' or (t1 == 'float' and t2 == 'float')
