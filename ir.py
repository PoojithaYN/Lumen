# ir.py
from ast_nodes import (
    Program, VarDecl, Assignment, PrintStmt, LoadDataset, FilterStmt, CoordDecl,
    Number, StringLit, BoolLit, Var, UnitExpr, RaDec, BinOp, UnaryOp,
    IfStmt, WhileStmt, ContinueStmt, BreakStmt, ArrayDecl, ArrayAccess, MemberAccess,
    ForStmt, FuncDef, Call, InputStmt
)


class IRNode:
    def __init__(self, op, **kwargs):
        self.op = op
        self.__dict__.update(kwargs)

    def __repr__(self):
        args = ', '.join(f"{k}={v!r}" for k, v in self.__dict__.items() if k != 'op')
        return f"{self.op}({args})"


def ast_to_ir(ast):
    ir = []
    for stmt in ast.statements:

        if isinstance(stmt, VarDecl):
            if stmt.init:
                ir.append(IRNode('assign', name=stmt.name, value=ir_expr(stmt.init)))
            else:
                ir.append(IRNode('declare', type=stmt.type, name=stmt.name))

        elif isinstance(stmt, Assignment):
            ir.append(IRNode('assign', name=stmt.name, value=ir_expr(stmt.expr)))

        elif isinstance(stmt, PrintStmt):
            ir.append(IRNode('print', exprs=[ir_expr(a) for a in stmt.args]))

        elif isinstance(stmt, InputStmt):
            ir.append(IRNode('input', var_name=stmt.var_name))

        elif isinstance(stmt, LoadDataset):
            ir.append(IRNode('load_dataset', name=stmt.name, file=stmt.file))

        elif isinstance(stmt, FilterStmt):
            ir.append(IRNode('filter', dataset=stmt.dataset, cond=ir_expr(stmt.cond)))

        elif isinstance(stmt, CoordDecl):
            ir.append(IRNode('coord', name=stmt.name, ra=ir_expr(stmt.ra), dec=ir_expr(stmt.dec)))

        elif isinstance(stmt, IfStmt):
            ir.append(IRNode('if',
                cond=ir_expr(stmt.cond),
                then_body=ast_to_ir_body(stmt.then),
                else_body=ast_to_ir_body(stmt.else_) if stmt.else_ else None
            ))

        elif isinstance(stmt, WhileStmt):
            ir.append(IRNode('while',
                cond=ir_expr(stmt.cond),
                body=ast_to_ir_body(stmt.body)
            ))

        elif isinstance(stmt, ForStmt):
            ir.append(IRNode('for',
                var=stmt.var,
                iterable=ir_expr(stmt.iterable),
                body=ast_to_ir_body(stmt.body)
            ))

        elif isinstance(stmt, ContinueStmt):
            ir.append(IRNode('continue'))

        elif isinstance(stmt, BreakStmt):
            ir.append(IRNode('break'))

        elif isinstance(stmt, ArrayDecl):
            ir.append(IRNode('array_decl',
                name=stmt.name,
                elem_type=stmt.elem_type,
                init=[ir_expr(x) for x in stmt.init_list]
            ))

        elif isinstance(stmt, ArrayAccess):
            ir.append(IRNode('array_access',
                array=stmt.array,
                index=ir_expr(stmt.index)
            ))

        elif isinstance(stmt, MemberAccess):
            ir.append(IRNode('member_access',
                expr=ir_expr(stmt.expr),
                member=stmt.member
            ))

        elif isinstance(stmt, FuncDef):
            ir.append(IRNode('funcdef',
                name=stmt.name,
                params=stmt.params,
                body=ast_to_ir_body(stmt.body),
                ret=ir_expr(stmt.return_) if stmt.return_ else None
            ))

        elif isinstance(stmt, Call):
            ir.append(IRNode('call',
                name=stmt.name,
                args=[ir_expr(a) for a in stmt.args]
            ))

    return ir


def ast_to_ir_body(body):
    """Wraps a plain list of statements so ast_to_ir can process it."""
    class _Wrap:
        def __init__(self, stmts):
            self.statements = stmts
    return ast_to_ir(_Wrap(body))


def ir_expr(expr):
    if isinstance(expr, Number):
        return IRNode('number', value=expr.value)

    if isinstance(expr, StringLit):
        return IRNode('string', value=expr.value)

    if isinstance(expr, BoolLit):
        return IRNode('bool', value=expr.value)

    if isinstance(expr, UnitExpr):
        return IRNode('unit', value=expr.value, unit=expr.unit)

    if isinstance(expr, Var):
        return IRNode('var', name=expr.name)

    if isinstance(expr, BinOp):
        # ✅ Use 'operator' not 'op' to avoid clash with IRNode's own .op field
        return IRNode('binop',
            operator=expr.op,
            left=ir_expr(expr.left),
            right=ir_expr(expr.right)
        )

    if isinstance(expr, UnaryOp):
        return IRNode('unaryop',
            operator=expr.op,
            expr=ir_expr(expr.expr)
        )

    if isinstance(expr, MemberAccess):
        return IRNode('member_access',
            expr=ir_expr(expr.expr),
            member=expr.member
        )

    if isinstance(expr, ArrayAccess):
        return IRNode('array_access',
            array=expr.array,
            index=ir_expr(expr.index)
        )

    if isinstance(expr, Call):
        return IRNode('call',
            name=expr.name,
            args=[ir_expr(a) for a in expr.args]
        )

    return IRNode('unknown_expr', expr=expr)
