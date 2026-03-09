# ast_nodes.py
class Node:
    """Base class for all AST nodes"""
    def __init__(self, kind, **kwargs):
        self.kind = kind
        self.__dict__.update(kwargs)

    def __repr__(self):
        args = ', '.join(f"{k}={v!r}" for k,v in self.__dict__.items() if k != 'kind')
        return f"{self.kind}({args})"

# Example nodes for core constructs
class Program(Node):
    def __init__(self, statements):
        super().__init__('Program', statements=statements)

class VarDecl(Node):
    def __init__(self, type_name, name, init=None):
        super().__init__('VarDecl', type=type_name, name=name, init=init)

class Assignment(Node):
    def __init__(self, name, expr):
        super().__init__('Assign', name=name, expr=expr)

class IfStmt(Node):
    def __init__(self, cond, then_body, else_body=None):
        super().__init__('If', cond=cond, then=then_body, else_=else_body)

class WhileStmt(Node):
    def __init__(self, cond, body):
        super().__init__('While', cond=cond, body=body)

class ForStmt(Node):
    def __init__(self, var, iterable, body):
        super().__init__('For', var=var, iterable=iterable, body=body)

class FuncDef(Node):
    def __init__(self, name, params, body, ret=None):
        super().__init__('FuncDef', name=name, params=params, body=body, return_=ret)

class Call(Node):
    def __init__(self, name, args):
        super().__init__('Call', name=name, args=args)

class PrintStmt(Node):
    def __init__(self, args):
        super().__init__('Print', args=args)   # args is list of expressions

# Astronomy specific
class LoadDataset(Node):
    def __init__(self, name, filename):
        super().__init__('LoadDataset', name=name, file=filename)

class FilterStmt(Node):
    def __init__(self, dataset, cond):
        super().__init__('Filter', dataset=dataset, cond=cond)

class CoordDecl(Node):
    def __init__(self, name, ra, dec):
        super().__init__('CoordDecl', name=name, ra=ra, dec=dec)

# Expressions (simple recursive)
class BinOp(Node):
    def __init__(self, left, op, right):
        super().__init__('BinOp', left=left, op=op, right=right)

class UnaryOp(Node):
    def __init__(self, op, expr):
        super().__init__('UnaryOp', op=op, expr=expr)

class Number(Node):
    def __init__(self, value):
        super().__init__('Number', value=value)

class StringLit(Node):
    def __init__(self, value):
        super().__init__('String', value=value)

class InputStmt(Node):
    def __init__(self, var_name):
        super().__init__('InputStmt', var_name=var_name)

class BoolLit(Node):
    def __init__(self, value):
        super().__init__('Bool', value=value)

class Var(Node):
    def __init__(self, name):
        super().__init__('Var', name=name)

class UnitExpr(Node):
    def __init__(self, value, unit):
        super().__init__('UnitExpr', value=value, unit=unit)

class RaDec(Node):
    def __init__(self, ra, dec):
        super().__init__('RaDec', ra=ra, dec=dec)
