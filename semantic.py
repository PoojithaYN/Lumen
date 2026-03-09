# semantic.py
from ast_nodes import *  # import your Node classes

class SemanticError(Exception):
    pass

def analyze(node):
    print(f"  Semantic: Analyzing {node.__class__.__name__}")
    """Simple semantic pass: check types, units, etc."""
    if isinstance(node, Program):
        for stmt in node.statements:
            analyze(stmt)
    
    elif isinstance(node, VarDecl):
        if node.init:
            init_type = get_type(node.init)
            if init_type != node.type and not compatible(init_type, node.type):
                raise SemanticError(f"Type mismatch: {node.type} = {init_type}")
    
    elif isinstance(node, UnitExpr):
        print(f"    → Unit check: {node.value} {node.unit}")
        # Very basic unit validation
        allowed_units = {'km', 's', 'deg', 'arcsec', 'pc', 'Jy', 'mag'}
        if node.unit not in allowed_units:
            raise SemanticError(f"Unknown unit: {node.unit}")
        # Later: check compound like 'km s' → velocity dimension
    
    elif isinstance(node, CoordDecl):
        # Simple check: ra 0–360, dec -90–90
        if not (0 <= node.ra.value <= 360):
            raise SemanticError("RA must be 0–360 degrees")
        if not (-90 <= node.dec.value <= 90):
            raise SemanticError("Dec must be -90 to +90 degrees")
    
    # Add more checks: undeclared vars, function calls, etc.
    # For now this is enough for Demo 4

def get_type(expr):
    if isinstance(expr, Number):
        return 'float'
    if isinstance(expr, UnitExpr):
        return 'float'  # assume unit expr is float
    if isinstance(expr, Var):
        return 'unknown'  # later symbol table
    return 'unknown'

def compatible(t1, t2):
    return t1 == t2 or t1 == 'unknown' or t2 == 'unknown'
