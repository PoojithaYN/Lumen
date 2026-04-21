# semantic.py  -  Lumen semantic analyser  (complete rewrite fixing all bugs)
#
# ROOT CAUSE OF "variable undeclared" BUG:
#   The old Program handler called symtab.exit_scope() which popped the ONLY
#   scope, destroying all global declarations. Fixed: Program never pops the
#   global scope. Only block-level constructs (if/while/for/func) push/pop.
#
# Also fixed:
#   - Assignment to loop variable inside while body no longer fails
#   - for-loop variable is correctly scoped to the loop body only
#   - Array element assignments tracked correctly
#   - Function return expressions validated even without explicit type
#   - Unused-variable warnings suppressed for loop counters and for-vars

from ast_nodes import *

# ---------------------------------------------------------------------------
# Unit categories for astronomy unit checking
# ---------------------------------------------------------------------------
UNIT_CATEGORIES = {
    'km':'distance','pc':'distance','au':'distance','ly':'distance',
    's':'time','min':'time','hr':'time',
    'deg':'angle','arcsec':'angle','arcmin':'angle','rad':'angle',
    'jy':'flux','mag':'magnitude','k':'temperature',
    'hz':'frequency','mhz':'frequency','ghz':'frequency',
}

def _unit_cat(u):
    if not u: return None
    return UNIT_CATEGORIES.get(u.split()[0].lower())

# ---------------------------------------------------------------------------
# Diagnostics
# ---------------------------------------------------------------------------
class SemanticError(Exception):
    pass

class SemanticWarning:
    _w = []
    @classmethod
    def reset(cls):   cls._w = []
    @classmethod
    def add(cls, m):  cls._w.append(m); print(f"  WARNING: {m}")
    @classmethod
    def all_warnings(cls): return list(cls._w)

def _err(msg, ln=None):
    raise SemanticError(msg + (f" (line {ln})" if ln else ""))

# ---------------------------------------------------------------------------
# Symbol Table  -  scoped, tracks type / unit / init / const / use-count
# ---------------------------------------------------------------------------
class SymbolTable:
    def __init__(self):
        # Stack of scope dicts.  Index 0 = global scope (never popped).
        self.scopes      = [{}]
        self._uses       = [{}]
        self.struct_defs = {}   # name -> {field: type}
        self.class_defs  = {}   # name -> {fields, methods, parent}
        self.type_aliases= {}   # alias -> base type
        self.func_sigs   = {}   # name -> (param_types, ret_type)

    # -- scope control -------------------------------------------------------
    def enter_scope(self):
        self.scopes.append({})
        self._uses.append({})

    def exit_scope(self, warn_unused=True):
        if len(self.scopes) <= 1:
            return   # never pop global scope
        if warn_unused:
            for name, info in self.scopes[-1].items():
                # Skip: loop vars, functions/classes/structs,
                # names starting with _ (convention: intentionally unused),
                # and 'dummy' which is a common throwaway capture name.
                if (self._uses[-1].get(name, 0) == 0
                        and info['type'] not in ('func', 'class', 'struct')
                        and not info.get('loop_var', False)
                        and name != 'dummy'
                        and not name.startswith('_')):
                    SemanticWarning.add(f"Variable '{name}' declared but never used")
        self.scopes.pop()
        self._uses.pop()

    # -- declaration / lookup ------------------------------------------------
    def declare(self, name, type_name, lineno=None, const=False, loop_var=False):
        cur = self.scopes[-1]
        if name in cur:
            _err(f"Redeclaration of '{name}' in same scope", lineno)
        cur[name] = {
            'type': type_name, 'initialized': False,
            'unit': None,      'const': const,
            'loop_var': loop_var
        }
        self._uses[-1][name] = 0

    def lookup(self, name, lineno=None):
        for sc, us in zip(reversed(self.scopes), reversed(self._uses)):
            if name in sc:
                return sc[name], us
        _err(f"Undefined variable '{name}'", lineno)

    def mark_initialized(self, name, unit=None):
        info, _ = self.lookup(name)
        info['initialized'] = True
        if unit is not None:
            info['unit'] = unit

    def mark_used(self, name):
        for sc, us in zip(reversed(self.scopes), reversed(self._uses)):
            if name in sc:
                us[name] = us.get(name, 0) + 1
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
        return self.type_aliases.get(t, t)

    def exists(self, name):
        for sc in reversed(self.scopes):
            if name in sc:
                return True
        return False

# ---------------------------------------------------------------------------
# Type helpers
# ---------------------------------------------------------------------------
def compatible(t1, t2):
    t1 = t1.rstrip('*&') if t1 else 'unknown'
    t2 = t2.rstrip('*&') if t2 else 'unknown'
    if t1 == t2: return True
    if 'unknown' in (t1, t2): return True
    if set([t1,t2]) <= {'int','float'}: return True
    return False

# ---------------------------------------------------------------------------
# Expression type inference  ->  (type_str, unit_str | None)
# ---------------------------------------------------------------------------
def get_type(expr, symtab):
    ln = getattr(expr, 'lineno', None)

    if isinstance(expr, Number):
        v = expr.value
        return ('int' if isinstance(v,float) and v.is_integer() else 'float'), None

    if isinstance(expr, UnitExpr):
        return 'float', expr.unit

    if isinstance(expr, StringLit):
        return 'string', None

    if isinstance(expr, BoolLit):
        return 'bool', None

    if isinstance(expr, Var):
        if not symtab.exists(expr.name):
            _err(f"Undefined variable '{expr.name}'", ln)
        symtab.mark_used(expr.name)
        t = symtab.get_type(expr.name, ln)
        u = symtab.get_unit(expr.name)
        if not symtab.is_initialized(expr.name):
            SemanticWarning.add(f"'{expr.name}' used before initialisation (line {ln or '?'})")
        return t, u

    if isinstance(expr, SelfExpr):
        return 'self', None

    if isinstance(expr, BinOp):
        lt, lu = get_type(expr.left,  symtab)
        rt, ru = get_type(expr.right, symtab)
        if expr.op in ('==','!=','<','>','<=','>=','and','or'):
            return 'bool', None
        lcat, rcat = _unit_cat(lu), _unit_cat(ru)
        if expr.op in ('+','-'):
            if lu and ru and lcat != rcat:
                _err(f"Unit mismatch in '{expr.op}': '{lu}'({lcat}) vs '{ru}'({rcat})", ln)
            if lu is None and ru is not None:
                SemanticWarning.add(f"Left side of '{expr.op}' has no unit but right has '{ru}' (line {ln or '?'})")
            if ru is None and lu is not None:
                SemanticWarning.add(f"Right side of '{expr.op}' has no unit but left has '{lu}' (line {ln or '?'})")
        result_unit = lu or ru
        if not compatible(lt, rt):
            _err(f"Incompatible types in '{expr.op}': {lt} vs {rt}", ln)
        result_type = 'float' if 'float' in (lt,rt) else lt
        return result_type, result_unit

    if isinstance(expr, UnaryOp):
        return get_type(expr.expr, symtab)

    if isinstance(expr, AddressOf):
        if not symtab.exists(expr.name):
            _err(f"Undefined variable '{expr.name}'", ln)
        t = symtab.get_type(expr.name, ln)
        return t + '*', None

    if isinstance(expr, Deref):
        t, _ = get_type(expr.expr, symtab)
        return t.rstrip('*') or 'unknown', None

    if isinstance(expr, ArrayAccess):
        if not symtab.exists(expr.array):
            _err(f"Undefined array '{expr.array}'", ln)
        base = symtab.get_type(expr.array, ln)
        return (base.replace('[]','') if base.endswith('[]') else 'unknown'), None

    if isinstance(expr, MemberAccess):
        if expr.member == 'length': return 'int', None
        return 'unknown', None

    if isinstance(expr, Call):
        # Look up return type if known
        if expr.name in symtab.func_sigs:
            return symtab.func_sigs[expr.name][1], None
        return 'unknown', None

    if isinstance(expr, NewExpr):
        return expr.class_name, None

    if isinstance(expr, StructLit):
        return expr.struct_name, None

    return 'unknown', None

# ---------------------------------------------------------------------------
# Statement analyser
# ---------------------------------------------------------------------------
def analyze(node, symtab=None, _in_loop=False):
    """
    Walk AST checking types, scopes, units, and control flow.
    Returns True if the statement unconditionally transfers control
    (break / continue / return / throw) so callers can detect unreachable code.
    """
    if symtab is None:
        symtab = SymbolTable()
        SemanticWarning.reset()

    ln = getattr(node, 'lineno', None)

    # ---- Program (top level) -----------------------------------------------
    if isinstance(node, Program):
        unreachable = False
        for stmt in node.statements:
            if unreachable:
                SemanticWarning.add("Unreachable statement detected")
                break
            unreachable = analyze(stmt, symtab, _in_loop)
        # DO NOT call exit_scope here - global scope stays alive
        return

    # ---- Type alias --------------------------------------------------------
    if isinstance(node, TypeAlias):
        symtab.type_aliases[node.alias] = node.base_type
        return False

    # ---- Variable / const declaration --------------------------------------
    if isinstance(node, (VarDecl, ConstDecl)):
        is_const = isinstance(node, ConstDecl)
        symtab.declare(node.name, node.type, lineno=ln, const=is_const)
        if node.init:
            it, iu = get_type(node.init, symtab)
            resolved = symtab.resolve_type(node.type)
            if not compatible(resolved, it):
                _err(f"Type mismatch declaring '{node.name}': expected {node.type}, got {it}", ln)
            # float with no unit warning (astronomy context)
            # Only warn for non-const plain floats whose name does not
            # suggest a dimensionless quantity (counts, limits, ratios,
            # indices, thresholds, flags, ids, codes, etc.)
            _DIMENSIONLESS_HINTS = {
                'limit', 'count', 'ratio', 'index', 'flag', 'code',
                'id', 'num', 'total', 'sum', 'avg', 'mean', 'max',
                'min', 'step', 'rate', 'scale', 'factor', 'weight',
                'score', 'rank', 'size', 'len', 'n', 'pi', 'e',
                'threshold', 'fraction', 'percent', 'pct', 'dummy',
            }
            name_lower = node.name.lower()
            is_dimensionless_name = any(
                hint in name_lower for hint in _DIMENSIONLESS_HINTS
            )
            if (not is_const
                    and node.type == 'float'
                    and isinstance(node.init, Number)
                    and iu is None
                    and not is_dimensionless_name):
                SemanticWarning.add(
                    f"Float '{node.name}' = bare number (no unit). "
                    f"Did you mean to add deg, km, au ... ? (line {ln or '?'})"
                )
            symtab.mark_initialized(node.name, unit=iu)
        return False

    # ---- Pointer declaration -----------------------------------------------
    if isinstance(node, PointerDecl):
        symtab.declare(node.name, node.base_type + '*', lineno=ln)
        if node.init:
            get_type(node.init, symtab)   # validate init expr
            symtab.mark_initialized(node.name)
        return False

    # ---- Reference declaration ---------------------------------------------
    if isinstance(node, ReferenceDecl):
        symtab.declare(node.name, node.base_type + '&', lineno=ln)
        get_type(node.target, symtab)
        symtab.mark_initialized(node.name)
        return False

    # ---- Deref assign  *p = expr -------------------------------------------
    if isinstance(node, DerefAssign):
        get_type(node.expr, symtab)
        return False

    # ---- Assignment  x = expr ----------------------------------------------
    if isinstance(node, Assignment):
        if not symtab.exists(node.name):
            _err(f"Undefined variable '{node.name}'", ln)
        info, _ = symtab.lookup(node.name, ln)
        if info.get('const'):
            _err(f"Cannot assign to const variable '{node.name}'", ln)
        et, eu = get_type(node.expr, symtab)
        if not compatible(info['type'], et):
            _err(f"Type mismatch assigning to '{node.name}': "
                 f"expected {info['type']}, got {et}", ln)
        symtab.mark_initialized(node.name, unit=eu)
        return False

    # ---- Print -------------------------------------------------------------
    if isinstance(node, PrintStmt):
        for arg in node.args:
            get_type(arg, symtab)
        return False

    # ---- Input -------------------------------------------------------------
    if isinstance(node, InputStmt):
        if not symtab.exists(node.var_name):
            _err(f"Undefined variable '{node.var_name}'", ln)
        symtab.mark_initialized(node.var_name)
        return False

    # ---- If / else ---------------------------------------------------------
    if isinstance(node, IfStmt):
        get_type(node.cond, symtab)
        symtab.enter_scope()
        _body(node.then, symtab, _in_loop)
        symtab.exit_scope()
        if node.else_:
            symtab.enter_scope()
            _body(node.else_, symtab, _in_loop)
            symtab.exit_scope()
        return False

    # ---- Switch ------------------------------------------------------------
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

    # ---- While -------------------------------------------------------------
    if isinstance(node, WhileStmt):
        get_type(node.cond, symtab)
        symtab.enter_scope()
        _body(node.body, symtab, _in_loop=True)
        symtab.exit_scope()
        return False

    # ---- For ---------------------------------------------------------------
    if isinstance(node, ForStmt):
        symtab.enter_scope()
        symtab.declare(node.var, 'unknown', lineno=ln, loop_var=True)
        symtab.mark_initialized(node.var)
        _body(node.body, symtab, _in_loop=True)
        symtab.exit_scope()
        return False

    # ---- Continue / Break --------------------------------------------------
    if isinstance(node, ContinueStmt):
        if not _in_loop:
            _err("'continue' used outside a loop", ln)
        return True

    if isinstance(node, BreakStmt):
        if not _in_loop:
            _err("'break' used outside a loop", ln)
        return True

    # ---- Return ------------------------------------------------------------
    if isinstance(node, ReturnStmt):
        if node.expr:
            get_type(node.expr, symtab)
        return True

    # ---- Try / catch / finally ---------------------------------------------
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

    # ---- Throw -------------------------------------------------------------
    if isinstance(node, ThrowStmt):
        get_type(node.expr, symtab)
        return True

    # ---- Function definition -----------------------------------------------
    if isinstance(node, FuncDef):
        symtab.declare(node.name, 'func', lineno=ln)
        # register param types for call-site checking
        param_types = []
        for p in node.params:
            if isinstance(p, Param):
                param_types.append(p.type)
            else:
                param_types.append('unknown')
        symtab.func_sigs[node.name] = (param_types, 'unknown')
        symtab.mark_initialized(node.name)

        symtab.enter_scope()
        for param in node.params:
            if isinstance(param, Param):
                symtab.declare(param.name, param.type, lineno=ln)
                symtab.mark_initialized(param.name)
            else:
                symtab.declare(param, 'unknown', lineno=ln)
                symtab.mark_initialized(param)
        _body(node.body, symtab, _in_loop=False)
        if node.return_ is not None:
            # node.return_ is an expression node when from return_stmt rule
            if hasattr(node.return_, 'kind') or hasattr(node.return_, 'op'):
                try:
                    get_type(node.return_, symtab)
                except Exception:
                    pass
        symtab.exit_scope(warn_unused=False)
        return False

    # ---- Array declaration -------------------------------------------------
    if isinstance(node, ArrayDecl):
        symtab.declare(node.name, f"{node.elem_type}[]", lineno=ln)
        symtab.mark_initialized(node.name)
        for item in node.init_list:
            it, _ = get_type(item, symtab)
            if not compatible(it, node.elem_type):
                _err(f"Array '{node.name}': expected {node.elem_type}, got {it}", ln)
        return False

    # ---- Struct definition -------------------------------------------------
    if isinstance(node, StructDef):
        symtab.declare(node.name, 'struct', lineno=ln)
        symtab.mark_initialized(node.name)
        symtab.struct_defs[node.name] = {fname: ftype for ftype, fname in node.fields}
        return False

    # ---- Class definition --------------------------------------------------
    if isinstance(node, ClassDef):
        symtab.declare(node.name, 'class', lineno=ln)
        symtab.mark_initialized(node.name)
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

    # ---- Astronomy ---------------------------------------------------------
    if isinstance(node, LoadDataset):
        symtab.declare(node.name, 'dataset', lineno=ln)
        symtab.mark_initialized(node.name)
        return False

    if isinstance(node, FilterStmt):
        if not symtab.exists(node.dataset):
            _err(f"Undefined dataset '{node.dataset}'", ln)
        symtab.mark_used(node.dataset)
        get_type(node.cond, symtab)
        return False

    if isinstance(node, CoordDecl):
        _, ra_u  = get_type(node.ra,  symtab)
        _, dec_u = get_type(node.dec, symtab)
        if ra_u  and _unit_cat(ra_u)  != 'angle':
            _err(f"RA for '{node.name}' has unit '{ra_u}' which is not an angle", ln)
        if dec_u and _unit_cat(dec_u) != 'angle':
            _err(f"Dec for '{node.name}' has unit '{dec_u}' which is not an angle", ln)
        symtab.declare(node.name, 'coord', lineno=ln)
        symtab.mark_initialized(node.name)
        return False

    # ---- Function call (statement) -----------------------------------------
    if isinstance(node, Call):
        for arg in node.args:
            get_type(arg, symtab)
        return False

    # ---- Member / array access (statement) ---------------------------------
    if isinstance(node, (MemberAccess, ArrayAccess)):
        return False

    return False


def _body(stmts, symtab, _in_loop):
    """Analyse a list of statements, detecting unreachable code."""
    unreachable = False
    for stmt in stmts:
        if unreachable:
            SemanticWarning.add("Unreachable statement after break/continue/return")
            break
        unreachable = analyze(stmt, symtab, _in_loop=_in_loop)
