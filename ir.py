# ir.py
from ast_nodes import (   # ← ADD THIS LINE
    Program, VarDecl, Assignment, PrintStmt, LoadDataset, FilterStmt, CoordDecl,
    Number, StringLit, BoolLit, Var, UnitExpr, RaDec, BinOp, UnaryOp
)  # add all classes you check with isinstance()
class IRNode:
    def __init__(self, op, **kwargs):
        self.op = op
        self.__dict__.update(kwargs)

    def __repr__(self):
        args = ', '.join(f"{k}={v!r}" for k,v in self.__dict__.items() if k != 'op')
        return f"{self.op}({args})"

def ast_to_ir(ast):
    ir = []
    for stmt in ast.statements:
        if isinstance(stmt, VarDecl):
            if stmt.init:
                ir.append(IRNode('assign', name=stmt.name, value=ir_expr(stmt.init)))
            else:
                ir.append(IRNode('declare', type=stmt.type, name=stmt.name))
        elif isinstance(stmt, PrintStmt):
            # Assume single arg for now, or take first
                if stmt.args:
                    ir.append(IRNode('print', expr=ir_expr(stmt.args[0])))
                else:
                     ir.append(IRNode('print', expr=IRNode('string', value='""')))  # empty print
        elif isinstance(stmt, LoadDataset):
            ir.append(IRNode('load_dataset', name=stmt.name, file=stmt.file))
        elif isinstance(stmt, FilterStmt):
            ir.append(IRNode('filter', dataset=stmt.dataset, cond=ir_expr(stmt.cond)))
        elif isinstance(stmt, CoordDecl):
            ir.append(IRNode('coord', name=stmt.name, ra=ir_expr(stmt.ra), dec=ir_expr(stmt.dec)))
        # Add more as needed
    return ir

def ir_expr(expr):
    if isinstance(expr, Number):
        return IRNode('number', value=expr.value)
    if isinstance(expr, UnitExpr):
        return IRNode('unit', value=expr.value, unit=expr.unit)
    if isinstance(expr, Var):
        return IRNode('var', name=expr.name)
    if isinstance(expr, BinOp):
        return IRNode('binop', left=ir_expr(expr.left), op=expr.op, right=ir_expr(expr.right))
    return IRNode('unknown_expr', expr=expr)
