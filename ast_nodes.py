# ast_nodes.py  –  Lumen AST node definitions
# Covers all language constructs including new: struct, class, pointer,
# reference, switch/case, try/except, parameter modes, user-defined types.

class Node:
    """Base class for all AST nodes."""
    def __init__(self, kind, **kwargs):
        self.kind = kind
        self.lineno = kwargs.pop('lineno', None)
        self.__dict__.update(kwargs)

    def __repr__(self):
        args = ', '.join(f"{k}={v!r}" for k, v in self.__dict__.items()
                        if k not in ('kind',))
        return f"{self.kind}({args})"


# ─── Top-level ────────────────────────────────────────────────────────────────
class Program(Node):
    def __init__(self, statements):
        super().__init__('Program', statements=statements)


# ─── Declarations ─────────────────────────────────────────────────────────────
class VarDecl(Node):
    def __init__(self, type_name, name, init=None, lineno=None):
        super().__init__('VarDecl', type=type_name, name=name, init=init, lineno=lineno)

class ConstDecl(Node):
    """const int X = 5;"""
    def __init__(self, type_name, name, init, lineno=None):
        super().__init__('ConstDecl', type=type_name, name=name, init=init, lineno=lineno)

class ArrayDecl(Node):
    def __init__(self, elem_type, name, init_list, lineno=None):
        super().__init__('ArrayDecl', elem_type=elem_type, name=name,
                         init_list=init_list or [], lineno=lineno)

class PointerDecl(Node):
    """int* p = &x;"""
    def __init__(self, base_type, name, init=None, lineno=None):
        super().__init__('PointerDecl', base_type=base_type, name=name,
                         init=init, lineno=lineno)

class ReferenceDecl(Node):
    """int& r = x;"""
    def __init__(self, base_type, name, target, lineno=None):
        super().__init__('ReferenceDecl', base_type=base_type, name=name,
                         target=target, lineno=lineno)

class TypeAlias(Node):
    """type Magnitude = float;"""
    def __init__(self, alias, base_type, lineno=None):
        super().__init__('TypeAlias', alias=alias, base_type=base_type, lineno=lineno)


# ─── Struct ───────────────────────────────────────────────────────────────────
class StructDef(Node):
    """
    struct Star {
        float ra;
        float dec;
        float magnitude;
    }
    """
    def __init__(self, name, fields, lineno=None):
        # fields: list of (type_str, field_name)
        super().__init__('StructDef', name=name, fields=fields, lineno=lineno)

class StructLit(Node):
    """Star { ra: 83.8 deg, dec: -5.4 deg, magnitude: 1.3 mag }"""
    def __init__(self, struct_name, field_inits, lineno=None):
        # field_inits: list of (field_name, expr)
        super().__init__('StructLit', struct_name=struct_name,
                         field_inits=field_inits, lineno=lineno)


# ─── Class ────────────────────────────────────────────────────────────────────
class ClassDef(Node):
    """
    class Telescope {
        float aperture;
        def observe(target) { ... }
    }
    """
    def __init__(self, name, parent, fields, methods, lineno=None):
        super().__init__('ClassDef', name=name, parent=parent,
                         fields=fields, methods=methods, lineno=lineno)

class NewExpr(Node):
    """new Telescope(args)"""
    def __init__(self, class_name, args, lineno=None):
        super().__init__('NewExpr', class_name=class_name, args=args, lineno=lineno)

class SelfExpr(Node):
    def __init__(self, lineno=None):
        super().__init__('Self', lineno=lineno)


# ─── Assignment ───────────────────────────────────────────────────────────────
class Assignment(Node):
    def __init__(self, name, expr, lineno=None):
        super().__init__('Assign', name=name, expr=expr, lineno=lineno)

class DerefAssign(Node):
    """*p = expr;"""
    def __init__(self, pointer, expr, lineno=None):
        super().__init__('DerefAssign', pointer=pointer, expr=expr, lineno=lineno)


# ─── Control flow ─────────────────────────────────────────────────────────────
class IfStmt(Node):
    def __init__(self, cond, then_body, else_body=None, lineno=None):
        super().__init__('If', cond=cond, then=then_body,
                         else_=else_body, lineno=lineno)

class SwitchStmt(Node):
    """
    switch (expr) {
        case 1: { ... }
        case 2: { ... }
        default: { ... }
    }
    """
    def __init__(self, expr, cases, default_body=None, lineno=None):
        # cases: list of (value_expr, body_stmts)
        super().__init__('Switch', expr=expr, cases=cases,
                         default_body=default_body, lineno=lineno)

class WhileStmt(Node):
    def __init__(self, cond, body, lineno=None):
        super().__init__('While', cond=cond, body=body, lineno=lineno)

class ForStmt(Node):
    def __init__(self, var, iterable, body, lineno=None):
        super().__init__('For', var=var, iterable=iterable,
                         body=body, lineno=lineno)

class ContinueStmt(Node):
    def __init__(self, lineno=None):
        super().__init__('ContinueStmt', lineno=lineno)

class BreakStmt(Node):
    def __init__(self, lineno=None):
        super().__init__('BreakStmt', lineno=lineno)

class ReturnStmt(Node):
    def __init__(self, expr=None, lineno=None):
        super().__init__('Return', expr=expr, lineno=lineno)


# ─── Exception handling ───────────────────────────────────────────────────────
class TryStmt(Node):
    """
    try {
        ...
    } catch (err) {
        ...
    } finally {
        ...
    }
    """
    def __init__(self, try_body, catch_var, catch_body, finally_body=None, lineno=None):
        super().__init__('Try', try_body=try_body, catch_var=catch_var,
                         catch_body=catch_body, finally_body=finally_body,
                         lineno=lineno)

class ThrowStmt(Node):
    """throw expr;"""
    def __init__(self, expr, lineno=None):
        super().__init__('Throw', expr=expr, lineno=lineno)


# ─── Functions ────────────────────────────────────────────────────────────────
class Param(Node):
    """
    Parameter with optional passing mode:
      mode = 'val'  →  pass by value     (default)
      mode = 'ref'  →  pass by reference  (&x)
      mode = 'out'  →  output parameter   (out x)
      mode = 'const'→  read-only value    (const x)
    """
    def __init__(self, name, type_name='unknown', mode='val', lineno=None):
        super().__init__('Param', name=name, type=type_name,
                         mode=mode, lineno=lineno)

class FuncDef(Node):
    def __init__(self, name, params, body, ret=None, ret_type=None, lineno=None):
        # params: list of Param nodes (or plain strings for backward compat)
        super().__init__('FuncDef', name=name, params=params,
                         body=body, return_=ret, ret_type=ret_type, lineno=lineno)

class Call(Node):
    def __init__(self, name, args, lineno=None):
        super().__init__('Call', name=name, args=args, lineno=lineno)

class MethodCall(Node):
    """obj.method(args)"""
    def __init__(self, obj, method, args, lineno=None):
        super().__init__('MethodCall', obj=obj, method=method,
                         args=args, lineno=lineno)


# ─── I/O ──────────────────────────────────────────────────────────────────────
class PrintStmt(Node):
    def __init__(self, args, lineno=None):
        super().__init__('Print', args=args, lineno=lineno)

class InputStmt(Node):
    def __init__(self, var_name, lineno=None):
        super().__init__('InputStmt', var_name=var_name, lineno=lineno)


# ─── Astronomy ────────────────────────────────────────────────────────────────
class LoadDataset(Node):
    def __init__(self, name, filename, lineno=None):
        super().__init__('LoadDataset', name=name, file=filename, lineno=lineno)

class FilterStmt(Node):
    def __init__(self, dataset, cond, lineno=None):
        super().__init__('Filter', dataset=dataset, cond=cond, lineno=lineno)

class CoordDecl(Node):
    def __init__(self, name, ra, dec, lineno=None):
        super().__init__('CoordDecl', name=name, ra=ra, dec=dec, lineno=lineno)


# ─── Expressions ──────────────────────────────────────────────────────────────
class BinOp(Node):
    def __init__(self, left, op, right, lineno=None):
        super().__init__('BinOp', left=left, op=op, right=right, lineno=lineno)

class UnaryOp(Node):
    def __init__(self, op, expr, lineno=None):
        super().__init__('UnaryOp', op=op, expr=expr, lineno=lineno)

class AddressOf(Node):
    """&x  — take address"""
    def __init__(self, name, lineno=None):
        super().__init__('AddressOf', name=name, lineno=lineno)

class Deref(Node):
    """*p  — dereference"""
    def __init__(self, expr, lineno=None):
        super().__init__('Deref', expr=expr, lineno=lineno)

class Number(Node):
    def __init__(self, value, lineno=None):
        super().__init__('Number', value=value, lineno=lineno)

class StringLit(Node):
    def __init__(self, value, lineno=None):
        super().__init__('String', value=value, lineno=lineno)

class BoolLit(Node):
    def __init__(self, value, lineno=None):
        super().__init__('Bool', value=value, lineno=lineno)

class Var(Node):
    def __init__(self, name, lineno=None):
        super().__init__('Var', name=name, lineno=lineno)

class UnitExpr(Node):
    def __init__(self, value, unit, lineno=None):
        super().__init__('UnitExpr', value=value, unit=unit, lineno=lineno)

class RaDec(Node):
    def __init__(self, ra, dec, lineno=None):
        super().__init__('RaDec', ra=ra, dec=dec, lineno=lineno)

class ArrayAccess(Node):
    def __init__(self, array, index, lineno=None):
        super().__init__('ArrayAccess', array=array, index=index, lineno=lineno)

class MemberAccess(Node):
    def __init__(self, expr, member, lineno=None):
        super().__init__('MemberAccess', expr=expr, member=member, lineno=lineno)
