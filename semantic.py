# semantic.py  –  Lumen semantic analyser
# All SemanticErrors now include line numbers.
# Handles: struct, class, pointer, reference, switch, try/catch, type aliases,
#          parameter modes, const declarations, user-defined types.

from ast_nodes import *

# ─── Unit categories ──────────────────────────────────────────────────────────
UNIT_CATEGORIES = {
    'km': 'distance', 'pc': 'distance', 'au': 'distance', 'ly': 'distance',
    's': 'time', 'min': 'time', 'hr': 'time',
    'deg': 'angle', 'arcsec': 'angle', 'arcmin': 'angle', 'rad': 'angle',
    'jy': 'flux', 'mag': 'magnitude', 'k': 'temperature',
    'hz': 'frequency', 'mhz': 'frequency', 'ghz': 'frequency',
}


def _unit_cat(unit_str):
    if not unit_str:
        return None
    return UNIT_CATEGORIES.get(unit_str.split()[0].lower())


# ─── Diagnostics ─────────────────────────────────────────────────────────────
class SemanticError(Exception):
    pass


class SemanticWarning:
    _warnings = []

    @classmethod
    def reset(cls):
        cls._warnings = []

    @classmethod
    def add(cls, msg):
        cls._warnings.append(msg)
        print(f"  ⚠  Warning: {msg}")

    @classmethod
    def all_warnings(cls):
        return list(cls._warnings)


def _err(msg, lineno=None):
    loc = f" (line {lineno})" if lineno else ""
    raise SemanticError(msg + loc)


# ─── Symbol table ─────────────────────────────────────────────────────────────
class SymbolTable:
    def __init__(self):
        self.scopes     = [{}]
        self._use_counts = [{}]
        self.struct_defs = {}   # name → {field_name: type}
        self.class_defs  = {}   # name → {fields, methods, parent}
        self.type_aliases = {}  # alias → base_type

    def enter_scope(self):
        self.scopes.append({})
        self._use_counts.append({})

    def exit_scope(self, warn_unused=True):
        if len(self.scopes) == 1:
            return
        if warn_unused:
            for name, info in self.scopes[-1].items():
                if self._use_counts[-1].get(name, 0) == 0 and info['type'] not in ('func', 'class', 'struct'):
                    SemanticWarning.add(f"Variable '{name}' declared but never used")
        self.scopes.pop()
        self._use_counts.pop()

    def declare(self, name, type_name, lineno=None, const=False):
        cur = self.scopes[-1]
        if name in cur:
            _err(f"Redeclaration of '{name}' in same scope", lineno)
        cur[name] = {'type': type_name, 'initialized': False,
                     'unit': None, 'const': const}
        self._use_counts[-1][name] = 0

    def lookup(self, name, lineno=None):
        for scope, uses in zip(reversed(self.scopes), reversed(self._use_counts)):
            if name in scope:
                return scope[name], uses
        _err(f"Undefined variable '{name}'", lineno)

    def mark_initialized(self, name, unit=None):
        info, _ = self.lookup(name)
        info['initialized'] = True
        if unit:
            info['unit'] = unit

    def mark_used(self, name):
        for scope, uses in zip(reversed(self.scopes), reversed(self._use_counts)):
            if name in scope:
                uses[name] = uses.get(name, 0) + 1
                return

    def is_initialized(self, name):
        info, _ = self.lookup(name)
        return info['initialized']

    def get_type(self, name, lineno=None):
        info, _ = self.lookup(name, lineno)
        return info['type']

    def get_unit(self, name):
        try:
            info, _ = self.lookup(name)
            return info.get('unit')
        except Exception:
            return None

    def resolve_type(self, t):
        """Follow type aliases."""
        return self.type_aliases.get(t, t)


# ─── Type helpers ─────────────────────────────────────────────────────────────
def compatible(t1, t2):
    t1 = t1.rstrip('*&')
    t2 = t2.rstrip('*&')
    if t1 == t2: return True
    if 'unknown' in (t1, t2): return True
    if set([t1, t2]) <= {'int', 'float'}: return True
    return False


def get_type(expr, symtab):
    """Return (type_str, unit_str_or_None)."""
    ln = getattr(expr, 'lineno', None)

    if isinstance(expr, Number):
        v = expr.value
        return ('int' if isinstance(v, float) and v.is_integer() else 'float'), None

    if isinstance(expr, UnitExpr):
        return 'float', expr.unit

    if isinstance(expr, StringLit):
        return 'string', None

    if isinstance(expr, BoolLit):
        return 'bool', None

    if isinstance(expr, Var):
        symtab.mark_used(expr.name)
        try:
            t = symtab.get_type(expr.name, ln)
            u = symtab.get_unit(expr.name)
            if not symtab.is_initialized(expr.name):
                SemanticWarning.add(f"'{expr.name}' used before initialisation (line {ln or '?'})")
            return t, u
        except SemanticError:
            raise

    if isinstance(expr, SelfExpr):
        return 'self', None

    if isinstance(expr, BinOp):
        lt, lu = get_type(expr.left,  symtab)
        rt, ru = get_type(expr.right, symtab)
        if expr.op in ('==', '!=', '<', '>', '<=', '>=', 'and', 'or'):
            return 'bool', None
        # unit dimension check
        lcat, rcat = _unit_cat(lu), _unit_cat(ru)
        if expr.op in ('+', '-'):
            if lu and ru and lcat != rcat:
                _err(f"Unit mismatch in '{expr.op}': '{lu}' ({lcat}) vs '{ru}' ({rcat}). "
                     f"Convert to same unit first.", ln)
            if lu is None and ru is not None:
                SemanticWarning.add(f"Left operand of '{expr.op}' has no unit but right has '{ru}' (line {ln or '?'})")
            if ru is None and lu is not None:
                SemanticWarning.add(f"Right operand of '{expr.op}' has no unit but left has '{lu}' (line {ln or '?'})")
        result_unit = lu or ru
        if not compatible(lt, rt):
            _err(f"Incompatible types in '{expr.op}': {lt} vs {rt}", ln)
        result_type = 'float' if 'float' in (lt, rt) else lt
        return result_type, result_unit

    if isinstance(expr, UnaryOp):
        return get_type(expr.expr, symtab)

    if isinstance(expr, AddressOf):
        try:
            t = symtab.get_type(expr.name, ln)
            return t + '*', None
        except Exception:
            return 'unknown*', None

    if isinstance(expr, Deref):
        t, _ = get_type(expr.expr, symtab)
        return t.rstrip('*'), None

    if isinstance(expr, ArrayAccess):
        base = symtab.get_type(expr.array, ln)
        return (base.replace('[]', '') if base.endswith('[]') else 'unknown'), None

    if isinstance(expr, MemberAccess):
        if expr.member == 'length':
            return 'int', None
        return 'unknown', None

    if isinstance(expr, Call):
        return 'unknown', None

    if isinstance(expr, NewExpr):
        return expr.class_name, None

    if isinstance(expr, StructLit):
        return expr.struct_name, None

    return 'unknown', None


# ─── Statement analyser ───────────────────────────────────────────────────────
def analyze(node, symtab=None, _in_loop=False):
    if symtab is None:
        symtab = SymbolTable()
        SemanticWarning.reset()

    ln = getattr(node, 'lineno', None)

    if isinstance(node, Program):
        unreachable = False
        for stmt in node.statements:
            if unreachable:
                SemanticWarning.add("Unreachable code after break/continue/return")
                break
            unreachable = analyze(stmt, symtab, _in_loop)
        symtab.exit_scope(warn_unused=True)
        return

    if isinstance(node, TypeAlias):
        symtab.type_aliases[node.alias] = node.base_type
        return False

    if isinstance(node, (VarDecl, ConstDecl)):
        is_const = isinstance(node, ConstDecl)
        symtab.declare(node.name, node.type, lineno=ln, const=is_const)
        if node.init:
            it, iu = get_type(node.init, symtab)
            resolved = symtab.resolve_type(node.type)
            if not compatible(resolved, it):
                _err(f"Type mismatch in declaration of '{node.name}': expected {node.type}, got {it}", ln)
            if node.type == 'float' and isinstance(node.init, Number) and iu is None:
                SemanticWarning.add(
                    f"Float '{node.name}' assigned plain number with no unit at line {ln or '?'}. "
                    f"Did you mean to add a unit (e.g. pc, deg, km)?"
                )
            symtab.mark_initialized(node.name, unit=iu)
        return False

    if isinstance(node, PointerDecl):
        symtab.declare(node.name, node.base_type + '*', lineno=ln)
        if node.init:
            symtab.mark_initialized(node.name)
        return False

    if isinstance(node, ReferenceDecl):
        symtab.declare(node.name, node.base_type + '&', lineno=ln)
        symtab.mark_initialized(node.name)
        return False

    if isinstance(node, Assignment):
        info, _ = symtab.lookup(node.name, ln)
        if info.get('const'):
            _err(f"Cannot assign to const variable '{node.name}'", ln)
        et, eu = get_type(node.expr, symtab)
        if not compatible(info['type'], et):
            _err(f"Type mismatch in assignment to '{node.name}': expected {info['type']}, got {et}", ln)
        symtab.mark_initialized(node.name, unit=eu)
        return False

    if isinstance(node, DerefAssign):
        # Just validate the RHS type
        get_type(node.expr, symtab)
        return False

    if isinstance(node, PrintStmt):
        for arg in node.args:
            get_type(arg, symtab)
        return False

    if isinstance(node, InputStmt):
        symtab.lookup(node.var_name, ln)
        symtab.mark_initialized(node.var_name)
        return False

    if isinstance(node, IfStmt):
        ct, _ = get_type(node.cond, symtab)
        symtab.enter_scope()
        _body(node.then, symtab, _in_loop)
        symtab.exit_scope()
        if node.else_:
            symtab.enter_scope()
            _body(node.else_, symtab, _in_loop)
            symtab.exit_scope()
        return False

    if isinstance(node, SwitchStmt):
        get_type(node.expr, symtab)
        for val_expr, body_stmts in node.cases:
            get_type(val_expr, symtab)
            symtab.enter_scope()
            _body(body_stmts, symtab, _in_loop)
            symtab.exit_scope()
        if node.default_body:
            symtab.enter_scope()
            _body(node.default_body, symtab, _in_loop)
            symtab.exit_scope()
        return False

    if isinstance(node, WhileStmt):
        get_type(node.cond, symtab)
        symtab.enter_scope()
        _body(node.body, symtab, _in_loop=True)
        symtab.exit_scope()
        return False

    if isinstance(node, ForStmt):
        symtab.enter_scope()
        symtab.declare(node.var, 'unknown', lineno=ln)
        symtab.mark_initialized(node.var)
        _body(node.body, symtab, _in_loop=True)
        symtab.exit_scope()
        return False

    if isinstance(node, ContinueStmt):
        if not _in_loop:
            _err("'continue' used outside of a loop", ln)
        return True

    if isinstance(node, BreakStmt):
        if not _in_loop:
            _err("'break' used outside of a loop", ln)
        return True

    if isinstance(node, ReturnStmt):
        if node.expr:
            get_type(node.expr, symtab)
        return True

    if isinstance(node, TryStmt):
        symtab.enter_scope()
        _body(node.try_body, symtab, _in_loop)
        symtab.exit_scope()
        symtab.enter_scope()
        symtab.declare(node.catch_var, 'string', lineno=ln)
        symtab.mark_initialized(node.catch_var)
        _body(node.catch_body, symtab, _in_loop)
        symtab.exit_scope()
        if node.finally_body:
            symtab.enter_scope()
            _body(node.finally_body, symtab, _in_loop)
            symtab.exit_scope()
        return False

    if isinstance(node, ThrowStmt):
        get_type(node.expr, symtab)
        return True

    if isinstance(node, FuncDef):
        symtab.declare(node.name, 'func', lineno=ln)
        symtab.enter_scope()
        for param in node.params:
            if isinstance(param, Param):
                symtab.declare(param.name, param.type, lineno=ln)
                symtab.mark_initialized(param.name)
            else:
                symtab.declare(param, 'unknown', lineno=ln)
                symtab.mark_initialized(param)
        _body(node.body, symtab, _in_loop=False)
        symtab.exit_scope(warn_unused=False)
        return False

    if isinstance(node, ArrayDecl):
        symtab.declare(node.name, f"{node.elem_type}[]", lineno=ln)
        symtab.mark_initialized(node.name)
        for item in node.init_list:
            it, _ = get_type(item, symtab)
            if not compatible(it, node.elem_type):
                _err(f"Type mismatch in array '{node.name}': expected {node.elem_type}, got {it}", ln)
        return False

    if isinstance(node, StructDef):
        symtab.declare(node.name, 'struct', lineno=ln)
        symtab.struct_defs[node.name] = {fname: ftype for ftype, fname in node.fields}
        return False

    if isinstance(node, ClassDef):
        symtab.declare(node.name, 'class', lineno=ln)
        symtab.class_defs[node.name] = {
            'fields': node.fields,
            'methods': [m.name for m in node.methods],
            'parent': node.parent
        }
        symtab.enter_scope()
        for ftype, fname in node.fields:
            symtab.declare(fname, ftype, lineno=ln)
            symtab.mark_initialized(fname)
        for method in node.methods:
            analyze(method, symtab, _in_loop=False)
        symtab.exit_scope(warn_unused=False)
        return False

    if isinstance(node, LoadDataset):
        symtab.declare(node.name, 'dataset', lineno=ln)
        symtab.mark_initialized(node.name)
        return False

    if isinstance(node, FilterStmt):
        symtab.lookup(node.dataset, ln)
        symtab.mark_used(node.dataset)
        get_type(node.cond, symtab)
        return False

    if isinstance(node, CoordDecl):
        _, ra_u  = get_type(node.ra,  symtab)
        _, dec_u = get_type(node.dec, symtab)
        if ra_u and _unit_cat(ra_u) != 'angle':
            _err(f"RA for '{node.name}' has unit '{ra_u}' (not angle)", ln)
        if dec_u and _unit_cat(dec_u) != 'angle':
            _err(f"Dec for '{node.name}' has unit '{dec_u}' (not angle)", ln)
        symtab.declare(node.name, 'coord', lineno=ln)
        symtab.mark_initialized(node.name)
        return False

    if isinstance(node, Call):
        for arg in node.args:
            get_type(arg, symtab)
        return False

    if isinstance(node, (MemberAccess, ArrayAccess)):
        return False

    print(f"  Semantic: unhandled node '{node.__class__.__name__}'")
    return False


def _body(stmts, symtab, _in_loop):
    unreachable = False
    for stmt in stmts:
        if unreachable:
            SemanticWarning.add("Unreachable statement after break/continue/return")
            break
        unreachable = analyze(stmt, symtab, _in_loop=_in_loop)
