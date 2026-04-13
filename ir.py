# ir.py  –  Lumen IR generation, optimisation, CFG, SSA, quadruples
#
# CRITICAL FIX: constant propagation and folding are now LOOP-SAFE.
# Variables assigned inside loop bodies are removed from the constant
# environment before the loop condition is processed, so we never
# freeze a loop condition to a literal.
#
# FIX 2: _extra() now skips all keys that are ever passed explicitly
# in IRNode constructor calls, preventing "multiple values for keyword
# argument" TypeError in all optimisation passes.
#
# Optimisation passes (in order, iterated to fixed-point):
#   1. Constant folding
#   2. Constant propagation   ← loop-safe
#   3. Copy propagation       ← loop-safe
#   4. Algebraic simplification  (peephole-style identities)
#   5. Strength reduction
#   6. Common sub-expression elimination
#   7. Dead-code elimination
#
# Additional analyses:
#   • Quadruple dump (op, arg1, arg2, result)
#   • Control-flow graph (basic-block split)
#   • SSA renaming (subscript notation for display)

from ast_nodes import *


# ─── IRNode ───────────────────────────────────────────────────────────────────
class IRNode:
    def __init__(self, op, **kwargs):
        self.op = op
        self.__dict__.update(kwargs)

    def __repr__(self):
        args = ', '.join(f"{k}={v!r}" for k, v in self.__dict__.items() if k != 'op')
        return f"{self.op}({args})"

    def __eq__(self, other):
        return isinstance(other, IRNode) and self.__dict__ == other.__dict__

    def __hash__(self):
        return hash(repr(self))


# ─── AST → IR ─────────────────────────────────────────────────────────────────
def ast_to_ir(ast):
    ir = []
    for stmt in ast.statements:
        _lower_stmt(stmt, ir)
    return ir


def _lower_body(stmts):
    class _W:
        def __init__(self, s): self.statements = s
    return ast_to_ir(_W(stmts))


def _lower_stmt(stmt, ir):
    # ── variable / const declarations ─────────────────────────────────────────
    if isinstance(stmt, (VarDecl, ConstDecl)):
        init_val = stmt.init if hasattr(stmt, 'init') else None
        if init_val:
            ir.append(IRNode('assign', name=stmt.name, value=ir_expr(init_val),
                             lineno=getattr(stmt, 'lineno', None)))
        else:
            ir.append(IRNode('declare', type=stmt.type, name=stmt.name,
                             lineno=getattr(stmt, 'lineno', None)))

    elif isinstance(stmt, TypeAlias):
        ir.append(IRNode('type_alias', alias=stmt.alias, base=stmt.base_type))

    elif isinstance(stmt, PointerDecl):
        val = ir_expr(stmt.init) if stmt.init else IRNode('number', value=0)
        ir.append(IRNode('ptr_decl', name=stmt.name, base_type=stmt.base_type,
                         value=val, lineno=getattr(stmt, 'lineno', None)))

    elif isinstance(stmt, ReferenceDecl):
        ir.append(IRNode('ref_decl', name=stmt.name, base_type=stmt.base_type,
                         target=ir_expr(stmt.target),
                         lineno=getattr(stmt, 'lineno', None)))

    elif isinstance(stmt, DerefAssign):
        ir.append(IRNode('deref_assign', pointer=stmt.pointer,
                         value=ir_expr(stmt.expr),
                         lineno=getattr(stmt, 'lineno', None)))

    elif isinstance(stmt, Assignment):
        ir.append(IRNode('assign', name=stmt.name, value=ir_expr(stmt.expr),
                         lineno=getattr(stmt, 'lineno', None)))

    elif isinstance(stmt, PrintStmt):
        ir.append(IRNode('print', exprs=[ir_expr(a) for a in stmt.args],
                         lineno=getattr(stmt, 'lineno', None)))

    elif isinstance(stmt, InputStmt):
        ir.append(IRNode('input', var_name=stmt.var_name,
                         lineno=getattr(stmt, 'lineno', None)))

    elif isinstance(stmt, LoadDataset):
        ir.append(IRNode('load_dataset', name=stmt.name, file=stmt.file))

    elif isinstance(stmt, FilterStmt):
        ir.append(IRNode('filter', dataset=stmt.dataset, cond=ir_expr(stmt.cond)))

    elif isinstance(stmt, CoordDecl):
        ir.append(IRNode('coord', name=stmt.name,
                         ra=ir_expr(stmt.ra), dec=ir_expr(stmt.dec)))

    elif isinstance(stmt, IfStmt):
        ir.append(IRNode('if',
            cond=ir_expr(stmt.cond),
            then_body=_lower_body(stmt.then),
            else_body=_lower_body(stmt.else_) if stmt.else_ else None,
            lineno=getattr(stmt, 'lineno', None)))

    elif isinstance(stmt, SwitchStmt):
        cases = [(ir_expr(v), _lower_body(b)) for v, b in stmt.cases]
        default = _lower_body(stmt.default_body) if stmt.default_body else None
        ir.append(IRNode('switch', expr=ir_expr(stmt.expr), cases=cases, default=default))

    elif isinstance(stmt, WhileStmt):
        ir.append(IRNode('while',
            cond=ir_expr(stmt.cond),
            body=_lower_body(stmt.body),
            lineno=getattr(stmt, 'lineno', None)))

    elif isinstance(stmt, ForStmt):
        ir.append(IRNode('for',
            var=stmt.var,
            iterable=ir_expr(stmt.iterable),
            body=_lower_body(stmt.body),
            lineno=getattr(stmt, 'lineno', None)))

    elif isinstance(stmt, ContinueStmt):
        ir.append(IRNode('continue'))

    elif isinstance(stmt, BreakStmt):
        ir.append(IRNode('break'))

    elif isinstance(stmt, ReturnStmt):
        val = ir_expr(stmt.expr) if stmt.expr else None
        ir.append(IRNode('return', value=val))

    elif isinstance(stmt, TryStmt):
        ir.append(IRNode('try',
            try_body=_lower_body(stmt.try_body),
            catch_var=stmt.catch_var,
            catch_body=_lower_body(stmt.catch_body),
            finally_body=_lower_body(stmt.finally_body) if stmt.finally_body else None))

    elif isinstance(stmt, ThrowStmt):
        ir.append(IRNode('throw', value=ir_expr(stmt.expr)))

    elif isinstance(stmt, ArrayDecl):
        ir.append(IRNode('array_decl',
            name=stmt.name, elem_type=stmt.elem_type,
            init=[ir_expr(x) for x in stmt.init_list]))

    elif isinstance(stmt, StructDef):
        ir.append(IRNode('struct_def', name=stmt.name, fields=stmt.fields))

    elif isinstance(stmt, ClassDef):
        method_ir = [(m.name, m.params, _lower_body(m.body),
                      ir_expr(m.return_) if m.return_ else None)
                     for m in stmt.methods]
        ir.append(IRNode('class_def', name=stmt.name, parent=stmt.parent,
                         fields=stmt.fields, methods=method_ir))

    elif isinstance(stmt, FuncDef):
        param_names = [p.name if isinstance(p, Param) else p for p in stmt.params]
        param_modes = [p.mode if isinstance(p, Param) else 'val' for p in stmt.params]
        ir.append(IRNode('funcdef',
            name=stmt.name,
            params=param_names,
            param_modes=param_modes,
            body=_lower_body(stmt.body),
            ret=ir_expr(stmt.return_) if stmt.return_ else None,
            lineno=getattr(stmt, 'lineno', None)))

    elif isinstance(stmt, Call):
        ir.append(IRNode('call', name=stmt.name,
                         args=[ir_expr(a) for a in stmt.args]))

    elif isinstance(stmt, MemberAccess):
        ir.append(IRNode('member_access', expr=ir_expr(stmt.expr), member=stmt.member))

    elif isinstance(stmt, ArrayAccess):
        ir.append(IRNode('array_access', array=stmt.array, index=ir_expr(stmt.index)))


def ir_expr(expr):
    if expr is None:
        return IRNode('number', value=0)
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
    if isinstance(expr, SelfExpr):
        return IRNode('var', name='self')
    if isinstance(expr, BinOp):
        return IRNode('binop', operator=expr.op,
                      left=ir_expr(expr.left), right=ir_expr(expr.right))
    if isinstance(expr, UnaryOp):
        return IRNode('unaryop', operator=expr.op, expr=ir_expr(expr.expr))
    if isinstance(expr, AddressOf):
        return IRNode('addr_of', name=expr.name)
    if isinstance(expr, Deref):
        return IRNode('deref', expr=ir_expr(expr.expr))
    if isinstance(expr, MemberAccess):
        return IRNode('member_access', expr=ir_expr(expr.expr), member=expr.member)
    if isinstance(expr, ArrayAccess):
        return IRNode('array_access', array=expr.array, index=ir_expr(expr.index))
    if isinstance(expr, Call):
        return IRNode('call', name=expr.name, args=[ir_expr(a) for a in expr.args])
    if isinstance(expr, NewExpr):
        return IRNode('new', class_name=expr.class_name,
                      args=[ir_expr(a) for a in expr.args])
    if isinstance(expr, StructLit):
        return IRNode('struct_lit', struct_name=expr.struct_name,
                      fields=[(k, ir_expr(v)) for k, v in expr.field_inits])
    return IRNode('unknown_expr', expr=repr(expr))


# ─── Optimisation driver ──────────────────────────────────────────────────────
def optimise(ir, report=True):
    """
    Run all IR passes to fixed-point.  Returns (optimised_ir, log_lines).
    LOOP-SAFE: variables modified inside loop bodies are invalidated from
    the constant/copy environment before the loop condition is simplified.
    """
    log = []
    prev = None
    rounds = 0
    while repr(ir) != prev and rounds < 15:
        prev = repr(ir)
        rounds += 1
        ir = _pass_constant_folding(ir, log)
        ir = _pass_constant_propagation(ir, log)
        ir = _pass_copy_propagation(ir, log)
        ir = _pass_algebraic(ir, log)
        ir = _pass_strength_reduction(ir, log)
        ir = _pass_cse(ir, log)
        ir = _pass_dce(ir, log)

    if report:
        print(f"\n  ── Optimisation report ({rounds} round(s)) ──")
        for line in (log or ["(nothing to optimise)"]):
            print(f"    {line}")
    return ir, log


# ─── Loop-variable collector ──────────────────────────────────────────────────
def _vars_assigned_in(body):
    """Return set of variable names assigned anywhere inside a body (loop)."""
    assigned = set()
    for instr in body:
        if instr.op == 'assign':
            assigned.add(instr.name)
        for attr in ('then_body', 'else_body', 'body', 'try_body',
                     'catch_body', 'finally_body'):
            sub = getattr(instr, attr, None)
            if isinstance(sub, list):
                assigned |= _vars_assigned_in(sub)
    return assigned


# ─── Internal helpers ─────────────────────────────────────────────────────────
# FIX: _extra() must skip every key that callers pass explicitly,
# otherwise IRNode() gets duplicate keyword arguments → TypeError.
_ALWAYS_SKIP = {
    'op',
    # assign
    'name', 'value',
    # print
    'exprs',
    # if
    'cond', 'then_body', 'else_body',
    # while / for
    'body', 'iterable', 'var',
    # array_decl
    'init',
    # funcdef
    'ret', 'params', 'param_modes',
    # coord
    'ra', 'dec',
    # filter / switch
    'dataset', 'cases', 'default',
    # ref / ptr
    'target', 'base_type',
    # return / throw
    # (value already in set)
    # try
    'try_body', 'catch_var', 'catch_body', 'finally_body',
    # member / array access
    'expr', 'member', 'array', 'index',
    # call / new / struct_lit
    'args', 'class_name', 'struct_name', 'fields',
}


def _extra(instr, skip=None):
    """
    Return a dict of instr attributes that are NOT being passed explicitly
    in the current IRNode() call.  Merges caller-supplied skip set with
    the global _ALWAYS_SKIP so we never get duplicate keyword errors.
    """
    combined = _ALWAYS_SKIP | (skip or set())
    return {k: v for k, v in instr.__dict__.items() if k not in combined}


# ─── Pass 1: Constant folding ─────────────────────────────────────────────────
def _fold_expr(node, log):
    if node.op == 'binop':
        l = _fold_expr(node.left,  log)
        r = _fold_expr(node.right, log)
        if _is_const(l) and _is_const(r):
            try:
                result = _eval_binop(node.operator, l.value, r.value)
                log.append(f"Constant fold: {l.value} {node.operator} {r.value} → {result}")
                return _make_const(result)
            except Exception:
                pass
        node.left, node.right = l, r
    elif node.op == 'unaryop':
        e = _fold_expr(node.expr, log)
        if _is_const(e):
            try:
                result = _eval_unary(node.operator, e.value)
                log.append(f"Constant fold: {node.operator} {e.value} → {result}")
                return _make_const(result)
            except Exception:
                pass
        node.expr = e
    return node


def _pass_constant_folding(ir, log):
    return _map_instrs(ir, lambda n: _fold_expr(n, log))


# ─── Pass 2: Constant propagation (LOOP-SAFE) ────────────────────────────────
def _pass_constant_propagation(ir, log):
    env = {}

    def prop(node, env):
        if node.op == 'var' and node.name in env:
            log.append(f"Constant propagation: '{node.name}' → {env[node.name].value}")
            return env[node.name]
        return _map_node_expr(node, lambda n: prop(n, env))

    new_ir = []
    for instr in ir:
        if instr.op in ('while', 'for'):
            # invalidate variables written inside the loop before simplifying cond
            loop_writes = _vars_assigned_in(getattr(instr, 'body', []))
            safe_env = {k: v for k, v in env.items() if k not in loop_writes}
            new_cond = prop(instr.cond, safe_env)
            new_body = _pass_constant_propagation(instr.body, log) if hasattr(instr, 'body') else instr.body
            # rebuild node preserving only non-explicit fields via lineno etc.
            extra = _extra(instr)
            new_ir.append(IRNode(instr.op, cond=new_cond, body=new_body,
                                 **({'var': instr.var, 'iterable': instr.iterable}
                                    if instr.op == 'for' else {}),
                                 **extra))
            # After a loop: invalidate vars the loop may have changed
            for v in loop_writes:
                env.pop(v, None)
        elif instr.op == 'assign':
            v = prop(instr.value, env)
            if _is_const(v):
                env[instr.name] = v
            else:
                env.pop(instr.name, None)
            new_ir.append(IRNode('assign', name=instr.name, value=v,
                                 **_extra(instr)))
        elif instr.op == 'if':
            new_cond = prop(instr.cond, env)
            new_then = _pass_constant_propagation(instr.then_body, log)
            new_else = _pass_constant_propagation(instr.else_body, log) if instr.else_body else None
            # Both branches may assign; invalidate those
            then_writes = _vars_assigned_in(new_then)
            else_writes = _vars_assigned_in(new_else or [])
            for v in then_writes | else_writes:
                env.pop(v, None)
            new_ir.append(IRNode('if', cond=new_cond, then_body=new_then,
                                 else_body=new_else, **_extra(instr)))
        else:
            new_ir.append(_map_instr_exprs(instr, lambda n: prop(n, env)))
    return new_ir


# ─── Pass 3: Copy propagation (LOOP-SAFE) ────────────────────────────────────
def _pass_copy_propagation(ir, log):
    copies = {}

    def prop(node):
        if node.op == 'var' and node.name in copies:
            log.append(f"Copy propagation: '{node.name}' → '{copies[node.name]}'")
            return IRNode('var', name=copies[node.name])
        return _map_node_expr(node, prop)

    new_ir = []
    for instr in ir:
        if instr.op in ('while', 'for'):
            loop_writes = _vars_assigned_in(getattr(instr, 'body', []))
            for v in loop_writes:
                copies.pop(v, None)
            new_ir.append(instr)
        elif instr.op == 'assign' and instr.value.op == 'var':
            copies[instr.name] = instr.value.name
            new_ir.append(instr)
        else:
            if instr.op == 'assign':
                copies.pop(instr.name, None)
            new_ir.append(_map_instr_exprs(instr, prop))
    return new_ir


# ─── Pass 4: Algebraic simplification (peephole) ─────────────────────────────
def _simplify(node, log):
    if node.op != 'binop':
        return _map_node_expr(node, lambda n: _simplify(n, log))
    l = _simplify(node.left, log)
    r = _simplify(node.right, log)
    op = node.operator

    def num(n, v): return n.op == 'number' and n.value == v

    if op == '+' and num(r, 0): log.append("Algebraic: x + 0 → x"); return l
    if op == '+' and num(l, 0): log.append("Algebraic: 0 + x → x"); return r
    if op == '-' and num(r, 0): log.append("Algebraic: x - 0 → x"); return l
    if op == '*' and num(r, 1): log.append("Algebraic: x * 1 → x"); return l
    if op == '*' and num(l, 1): log.append("Algebraic: 1 * x → x"); return r
    if op == '*' and (num(l, 0) or num(r, 0)):
        log.append("Algebraic: x * 0 → 0"); return IRNode('number', value=0)
    if op == '/' and num(r, 1): log.append("Algebraic: x / 1 → x"); return l
    if op in ('==',) and l.op == 'var' and r.op == 'var' and l.name == r.name:
        log.append(f"Algebraic: x == x → True"); return IRNode('bool', value=True)
    if op == '-' and l.op == 'var' and r.op == 'var' and l.name == r.name:
        log.append(f"Algebraic: x - x → 0"); return IRNode('number', value=0)
    node.left, node.right = l, r
    return node


def _pass_algebraic(ir, log):
    return _map_instrs(ir, lambda n: _simplify(n, log))


# ─── Pass 5: Strength reduction ───────────────────────────────────────────────
def _pass_strength_reduction(ir, log):
    def reduce_expr(node):
        if node.op == 'binop':
            l = reduce_expr(node.left)
            r = reduce_expr(node.right)
            op = node.operator
            if op == '*' and r.op == 'number' and r.value == 2:
                log.append("Strength reduction: x * 2 → x + x")
                return IRNode('binop', operator='+', left=l, right=l)
            if op == '*' and l.op == 'number' and l.value == 2:
                log.append("Strength reduction: 2 * x → x + x")
                return IRNode('binop', operator='+', left=r, right=r)
            if op in ('**', '^') and r.op == 'number' and r.value == 2:
                log.append("Strength reduction: x ** 2 → x * x")
                return IRNode('binop', operator='*', left=l, right=l)
            node.left, node.right = l, r
        return node
    return _map_instrs(ir, reduce_expr)


# ─── Pass 6: Common sub-expression elimination ────────────────────────────────
def _pass_cse(ir, log):
    seen = {}
    counter = [0]
    extra_assigns = []

    def cse_expr(node):
        if node.op in ('number', 'string', 'bool', 'var'):
            return node
        node = _map_node_expr(node, cse_expr)
        key = repr(node)
        if key in seen:
            log.append(f"CSE: '{key[:50]}' → '{seen[key]}'")
            return IRNode('var', name=seen[key])
        counter[0] += 1
        tname = f"__t{counter[0]}"
        seen[key] = tname
        extra_assigns.append(IRNode('assign', name=tname, value=node))
        return IRNode('var', name=tname)

    new_ir = []
    for instr in ir:
        if instr.op == 'assign':
            v = cse_expr(instr.value)
            new_ir.extend(extra_assigns); extra_assigns.clear()
            new_ir.append(IRNode('assign', name=instr.name, value=v,
                                 **_extra(instr)))
        else:
            new_ir.append(instr)
    return new_ir


# ─── Pass 7: Dead-code elimination ────────────────────────────────────────────
def _pass_dce(ir, log):
    reads = _collect_reads(ir)
    new_ir = []
    for instr in ir:
        if instr.op == 'assign' and instr.name.startswith('__t') and instr.name not in reads:
            log.append(f"Dead code eliminated: '{instr.name}'")
            continue
        new_ir.append(instr)
    return new_ir


# ─── Quadruples ───────────────────────────────────────────────────────────────
def to_quadruples(ir):
    """
    Convert flat IR to a list of quadruples: (op, arg1, arg2, result).
    This is a classic compiler IR table form.
    """
    quads = []
    tmp_count = [0]

    def new_tmp():
        tmp_count[0] += 1
        return f"t{tmp_count[0]}"

    def expr_to_quads(node):
        if node.op == 'number':
            return str(int(node.value)) if isinstance(node.value, float) and node.value.is_integer() else str(node.value)
        if node.op in ('string', 'bool'):
            return repr(node.value)
        if node.op == 'var':
            return node.name
        if node.op == 'binop':
            l = expr_to_quads(node.left)
            r = expr_to_quads(node.right)
            t = new_tmp()
            quads.append((node.operator, l, r, t))
            return t
        if node.op == 'unaryop':
            e = expr_to_quads(node.expr)
            t = new_tmp()
            quads.append((node.operator, e, '-', t))
            return t
        if node.op == 'call':
            args = [expr_to_quads(a) for a in node.args]
            t = new_tmp()
            quads.append(('call', node.name, str(args), t))
            return t
        return f"?{node.op}"

    def lower(instrs):
        for instr in instrs:
            if instr.op == 'assign':
                v = expr_to_quads(instr.value)
                quads.append(('=', v, '-', instr.name))
            elif instr.op == 'print':
                for e in instr.exprs:
                    v = expr_to_quads(e)
                    quads.append(('print', v, '-', '-'))
            elif instr.op == 'if':
                c = expr_to_quads(instr.cond)
                quads.append(('if_false', c, '-', 'else_label'))
                lower(instr.then_body)
                if instr.else_body:
                    quads.append(('goto', '-', '-', 'end_label'))
                    quads.append(('label', 'else_label', '-', '-'))
                    lower(instr.else_body)
                quads.append(('label', 'end_label', '-', '-'))
            elif instr.op == 'while':
                quads.append(('label', 'loop_start', '-', '-'))
                c = expr_to_quads(instr.cond)
                quads.append(('if_false', c, '-', 'loop_end'))
                lower(instr.body)
                quads.append(('goto', '-', '-', 'loop_start'))
                quads.append(('label', 'loop_end', '-', '-'))
            elif instr.op == 'call':
                args = [expr_to_quads(a) for a in instr.args]
                quads.append(('call', instr.name, str(args), '-'))
            elif instr.op == 'return':
                v = expr_to_quads(instr.value) if instr.value else '-'
                quads.append(('return', v, '-', '-'))

    lower(ir)
    return quads


def print_quadruples(quads):
    print(f"\n  {'#':<4}  {'OP':<12}  {'ARG1':<20}  {'ARG2':<10}  {'RESULT'}")
    print(f"  {'─'*4}  {'─'*12}  {'─'*20}  {'─'*10}  {'─'*10}")
    for i, (op, a1, a2, res) in enumerate(quads, 1):
        print(f"  {i:<4}  {op:<12}  {str(a1):<20}  {str(a2):<10}  {res}")


# ─── Control-flow graph ───────────────────────────────────────────────────────
class BasicBlock:
    def __init__(self, id):
        self.id = id
        self.instrs = []
        self.successors = []
        self.predecessors = []

    def __repr__(self):
        return f"BB{self.id}[{len(self.instrs)} instrs]"


def build_cfg(ir):
    """
    Split flat IR into basic blocks.
    Leaders: first instr, any target of a branch, instr after a branch.
    Returns list of BasicBlock objects.
    """
    blocks = []
    current = BasicBlock(0)

    def flush():
        nonlocal current
        if current.instrs:
            blocks.append(current)
            current = BasicBlock(len(blocks))

    for instr in ir:
        if instr.op in ('if', 'while', 'for', 'switch'):
            current.instrs.append(instr)
            flush()
        elif instr.op in ('break', 'continue', 'return', 'throw'):
            current.instrs.append(instr)
            flush()
        else:
            current.instrs.append(instr)

    flush()

    # Link successors naively (sequential flow)
    for i, b in enumerate(blocks):
        last = b.instrs[-1] if b.instrs else None
        if last and last.op in ('return', 'throw'):
            pass  # no successor
        elif i + 1 < len(blocks):
            b.successors.append(blocks[i + 1])
            blocks[i + 1].predecessors.append(b)
        if last and last.op in ('if', 'while', 'for'):
            pass  # simplified

    return blocks


def print_cfg(blocks):
    print(f"\n  Control-Flow Graph  ({len(blocks)} basic block(s))")
    print(f"  {'─'*50}")
    for b in blocks:
        succs = ', '.join(f"BB{s.id}" for s in b.successors) or 'EXIT'
        preds = ', '.join(f"BB{p.id}" for p in b.predecessors) or 'ENTRY'
        print(f"\n  ┌─ BB{b.id}  (pred: {preds})  (succ: {succs})")
        for instr in b.instrs:
            print(f"  │  {instr}")
        print(f"  └{'─'*48}")


# ─── SSA (display-level) ─────────────────────────────────────────────────────
def to_ssa_display(ir):
    """
    Produce an SSA-annotated string representation.
    Each assignment to a variable gets a version subscript (x_0, x_1 …).
    Reads are rewritten to the current version.
    This is display-only (not used for code generation).
    """
    version = {}
    lines = []

    def ver(name, define=False):
        if define:
            version[name] = version.get(name, -1) + 1
        return f"{name}_{version.get(name, 0)}"

    def ssa_expr(node):
        if node.op == 'var':
            return ver(node.name)
        if node.op == 'number':
            v = node.value
            return str(int(v)) if isinstance(v, float) and v.is_integer() else str(v)
        if node.op in ('string', 'bool'):
            return repr(node.value)
        if node.op == 'binop':
            return f"({ssa_expr(node.left)} {node.operator} {ssa_expr(node.right)})"
        if node.op == 'unaryop':
            return f"({node.operator}{ssa_expr(node.expr)})"
        if node.op == 'call':
            args = ', '.join(ssa_expr(a) for a in node.args)
            return f"{node.name}({args})"
        return f"?{node.op}"

    def lower(instrs, indent=0):
        pad = "  " * indent
        for instr in instrs:
            if instr.op == 'assign':
                rhs = ssa_expr(instr.value)
                lhs = ver(instr.name, define=True)
                lines.append(f"{pad}{lhs} = {rhs}")
            elif instr.op == 'declare':
                lhs = ver(instr.name, define=True)
                lines.append(f"{pad}{lhs} = ⊥  # declared, uninit")
            elif instr.op == 'print':
                args = ', '.join(ssa_expr(e) for e in instr.exprs)
                lines.append(f"{pad}print({args})")
            elif instr.op == 'if':
                cond = ssa_expr(instr.cond)
                lines.append(f"{pad}if {cond}:")
                lower(instr.then_body, indent + 1)
                if instr.else_body:
                    lines.append(f"{pad}else:")
                    lower(instr.else_body, indent + 1)
            elif instr.op == 'while':
                cond = ssa_expr(instr.cond)
                lines.append(f"{pad}while {cond}:  # φ-functions elided")
                lower(instr.body, indent + 1)
            elif instr.op == 'return':
                v = ssa_expr(instr.value) if instr.value else 'None'
                lines.append(f"{pad}return {v}")
            elif instr.op == 'call':
                args = ', '.join(ssa_expr(a) for a in instr.args)
                lines.append(f"{pad}{instr.name}({args})")
            else:
                lines.append(f"{pad}# {instr}")

    lower(ir)
    return '\n'.join(lines)


# ─── Activation record / stack layout ────────────────────────────────────────
class ActivationRecord:
    """
    Models the runtime activation record (stack frame) for a function.
    Slots:
      [return_addr][static_link][dynamic_link][return_val][params...][locals...]
    """
    SLOT_SIZE = 8   # bytes (64-bit)

    def __init__(self, func_name, params, locals_):
        self.func_name  = func_name
        self.params     = list(params)
        self.locals_    = list(locals_)
        self._layout    = {}
        self._build()

    def _build(self):
        offset = 0
        for fixed in ('__return_addr', '__static_link', '__dynamic_link', '__return_val'):
            self._layout[fixed] = offset
            offset += self.SLOT_SIZE
        for p in self.params:
            self._layout[p] = offset
            offset += self.SLOT_SIZE
        for l in self.locals_:
            self._layout[l] = offset
            offset += self.SLOT_SIZE
        self.frame_size = offset

    def describe(self):
        lines = [f"  Activation record: {self.func_name}  "
                 f"(frame size = {self.frame_size} bytes)"]
        lines.append(f"  {'OFFSET':>8}  SLOT")
        lines.append(f"  {'─'*8}  {'─'*30}")
        for name, off in self._layout.items():
            lines.append(f"  {off:>8}  {name}")
        return '\n'.join(lines)


def build_activation_records(ir):
    """Walk IR and build an ActivationRecord for every funcdef."""
    records = {}
    for instr in ir:
        if instr.op == 'funcdef':
            params = instr.params
            locals_ = _collect_locals(instr.body)
            ar = ActivationRecord(instr.name, params, locals_)
            records[instr.name] = ar
    return records


def _collect_locals(body):
    names = []
    for instr in body:
        if instr.op in ('assign', 'declare') and instr.name not in names:
            names.append(instr.name)
        for attr in ('then_body', 'else_body', 'body'):
            sub = getattr(instr, attr, None)
            if isinstance(sub, list):
                for n in _collect_locals(sub):
                    if n not in names:
                        names.append(n)
    return names


# ─── Optimisation helpers ─────────────────────────────────────────────────────
def _is_const(node):
    return node.op in ('number', 'string', 'bool')


def _make_const(v):
    if isinstance(v, bool): return IRNode('bool', value=v)
    if isinstance(v, (int, float)): return IRNode('number', value=v)
    return IRNode('string', value=v)


def _eval_binop(op, l, r):
    ops = {'+': l+r, '-': l-r, '*': l*r,
           '/': l/r if r else None,
           '==': l==r, '!=': l!=r,
           '<': l<r, '>': l>r, '<=': l<=r, '>=': l>=r,
           'and': l and r, 'or': l or r}
    if op not in ops or ops[op] is None:
        raise ValueError
    return ops[op]


def _eval_unary(op, v):
    if op == 'not': return not v
    if op == '-': return -v
    raise ValueError


def _map_instrs(ir, expr_fn):
    return [_map_instr_exprs(instr, expr_fn) for instr in ir]


def _map_instr_exprs(instr, fn):
    op = instr.op
    if op == 'assign':
        return IRNode('assign', name=instr.name, value=fn(instr.value),
                      **_extra(instr))
    if op == 'print':
        return IRNode('print', exprs=[fn(e) for e in instr.exprs],
                      **_extra(instr))
    if op == 'filter':
        return IRNode('filter', dataset=instr.dataset, cond=fn(instr.cond))
    if op == 'if':
        return IRNode('if', cond=fn(instr.cond),
                      then_body=_map_instrs(instr.then_body, fn),
                      else_body=_map_instrs(instr.else_body, fn) if instr.else_body else None,
                      **_extra(instr))
    if op == 'while':
        return IRNode('while', cond=fn(instr.cond),
                      body=_map_instrs(instr.body, fn),
                      **_extra(instr))
    if op == 'for':
        return IRNode('for', var=instr.var, iterable=fn(instr.iterable),
                      body=_map_instrs(instr.body, fn),
                      **_extra(instr))
    if op == 'array_decl':
        return IRNode('array_decl', name=instr.name, elem_type=instr.elem_type,
                      init=[fn(x) for x in instr.init])
    if op == 'call':
        return IRNode('call', name=instr.name, args=[fn(a) for a in instr.args])
    if op == 'funcdef':
        return IRNode('funcdef', name=instr.name, params=instr.params,
                      param_modes=getattr(instr, 'param_modes', []),
                      body=_map_instrs(instr.body, fn),
                      ret=fn(instr.ret) if instr.ret else None,
                      **_extra(instr))
    if op == 'coord':
        return IRNode('coord', name=instr.name, ra=fn(instr.ra), dec=fn(instr.dec))
    if op == 'return':
        return IRNode('return', value=fn(instr.value) if instr.value else None)
    if op == 'throw':
        return IRNode('throw', value=fn(instr.value))
    return instr


def _map_node_expr(node, fn):
    if node.op == 'binop':
        node.left  = fn(node.left)
        node.right = fn(node.right)
    elif node.op == 'unaryop':
        node.expr = fn(node.expr)
    elif node.op == 'member_access':
        node.expr = fn(node.expr)
    elif node.op == 'array_access':
        node.index = fn(node.index)
    elif node.op == 'call':
        node.args = [fn(a) for a in node.args]
    elif node.op == 'deref':
        node.expr = fn(node.expr)
    return node


def _collect_reads(ir):
    reads = set()
    for instr in ir:
        _collect_reads_instr(instr, reads)
    return reads


def _collect_reads_instr(instr, reads):
    for k, v in instr.__dict__.items():
        if k == 'op': continue
        if isinstance(v, IRNode):
            _collect_reads_expr(v, reads)
        elif isinstance(v, list):
            for item in v:
                if isinstance(item, IRNode):
                    if hasattr(item, 'op') and item.op in (
                        'assign', 'declare', 'print', 'if', 'while', 'for', 'funcdef',
                        'call', 'input', 'load_dataset', 'filter', 'coord',
                        'array_decl', 'continue', 'break', 'return', 'throw', 'try'):
                        _collect_reads_instr(item, reads)
                    else:
                        _collect_reads_expr(item, reads)


def _collect_reads_expr(node, reads):
    if node.op == 'var':
        reads.add(node.name)
    for k, v in node.__dict__.items():
        if k == 'op': continue
        if isinstance(v, IRNode):
            _collect_reads_expr(v, reads)
        elif isinstance(v, list):
            for item in v:
                if isinstance(item, IRNode):
                    _collect_reads_expr(item, reads)
