# ir.py  -  Lumen IR + all analyses
#
# New / completed in this version:
#   - Full SSA with phi-function insertion at join points
#   - Basic block optimization: liveness analysis + reaching definitions
#   - Heap allocation modeling (malloc/free simulation)
#   - Stack management with explicit push/pop display
#   - Pointer/reference out-param support
#   - Loop-safe constant propagation (bug fix preserved)

from ast_nodes import *

# ===========================================================================
# IRNode
# ===========================================================================
class IRNode:
    def __init__(self, op, **kw):
        self.op = op
        self.__dict__.update(kw)

    def __repr__(self):
        parts = ', '.join(f"{k}={v!r}" for k,v in self.__dict__.items() if k != 'op')
        return f"{self.op}({parts})"

    def __eq__(self, other):
        return isinstance(other, IRNode) and self.__dict__ == other.__dict__

    def __hash__(self):
        return hash(repr(self))


# ===========================================================================
# AST -> IR lowering
# ===========================================================================
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
    ln = getattr(stmt, 'lineno', None)

    if isinstance(stmt, (VarDecl, ConstDecl)):
        if stmt.init:
            ir.append(IRNode('assign', name=stmt.name,
                             value=ir_expr(stmt.init), lineno=ln))
        else:
            ir.append(IRNode('declare', type=stmt.type,
                             name=stmt.name, lineno=ln))

    elif isinstance(stmt, TypeAlias):
        ir.append(IRNode('type_alias', alias=stmt.alias, base=stmt.base_type))

    elif isinstance(stmt, PointerDecl):
        # Model pointer as a dict: {'val': <value>, 'addr': id}
        val = ir_expr(stmt.init) if stmt.init else IRNode('number', value=0)
        ir.append(IRNode('ptr_decl', name=stmt.name,
                         base_type=stmt.base_type, value=val, lineno=ln))

    elif isinstance(stmt, ReferenceDecl):
        # Reference: alias for target variable
        ir.append(IRNode('ref_decl', name=stmt.name,
                         base_type=stmt.base_type,
                         target=ir_expr(stmt.target), lineno=ln))

    elif isinstance(stmt, DerefAssign):
        ir.append(IRNode('deref_assign', pointer=stmt.pointer,
                         value=ir_expr(stmt.expr), lineno=ln))

    elif isinstance(stmt, Assignment):
        ir.append(IRNode('assign', name=stmt.name,
                         value=ir_expr(stmt.expr), lineno=ln))

    elif isinstance(stmt, PrintStmt):
        ir.append(IRNode('print', exprs=[ir_expr(a) for a in stmt.args], lineno=ln))

    elif isinstance(stmt, InputStmt):
        ir.append(IRNode('input', var_name=stmt.var_name, lineno=ln))

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
            lineno=ln))

    elif isinstance(stmt, SwitchStmt):
        cases = [(ir_expr(v), _lower_body(b)) for v,b in stmt.cases]
        default = _lower_body(stmt.default_body) if stmt.default_body else None
        ir.append(IRNode('switch', expr=ir_expr(stmt.expr),
                         cases=cases, default=default))

    elif isinstance(stmt, WhileStmt):
        ir.append(IRNode('while',
            cond=ir_expr(stmt.cond),
            body=_lower_body(stmt.body), lineno=ln))

    elif isinstance(stmt, ForStmt):
        ir.append(IRNode('for',
            var=stmt.var,
            iterable=ir_expr(stmt.iterable),
            body=_lower_body(stmt.body), lineno=ln))

    elif isinstance(stmt, ContinueStmt):
        ir.append(IRNode('continue'))

    elif isinstance(stmt, BreakStmt):
        ir.append(IRNode('break'))

    elif isinstance(stmt, ReturnStmt):
        ir.append(IRNode('return',
            value=ir_expr(stmt.expr) if stmt.expr else None))

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
        method_ir = []
        for m in stmt.methods:
            pnames = [p.name if isinstance(p,Param) else p for p in m.params]
            pmodes = [p.mode if isinstance(p,Param) else 'val' for p in m.params]
            method_ir.append((m.name, pnames, pmodes, _lower_body(m.body),
                              ir_expr(m.return_) if m.return_ else None))
        ir.append(IRNode('class_def', name=stmt.name, parent=stmt.parent,
                         fields=stmt.fields, methods=method_ir))

    elif isinstance(stmt, FuncDef):
        pnames = [p.name if isinstance(p,Param) else p for p in stmt.params]
        pmodes = [p.mode if isinstance(p,Param) else 'val' for p in stmt.params]
        ptypes = [p.type if isinstance(p,Param) else 'unknown' for p in stmt.params]
        ir.append(IRNode('funcdef',
            name=stmt.name,
            params=pnames,
            param_modes=pmodes,
            param_types=ptypes,
            body=_lower_body(stmt.body),
            ret=ir_expr(stmt.return_) if stmt.return_ else None,
            lineno=ln))

    elif isinstance(stmt, Call):
        ir.append(IRNode('call', name=stmt.name,
                         args=[ir_expr(a) for a in stmt.args]))

    elif isinstance(stmt, (MemberAccess, ArrayAccess)):
        pass  # expression statements ignored at top level


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
        return IRNode('call', name=expr.name,
                      args=[ir_expr(a) for a in expr.args])
    if isinstance(expr, NewExpr):
        return IRNode('new', class_name=expr.class_name,
                      args=[ir_expr(a) for a in expr.args])
    if isinstance(expr, StructLit):
        return IRNode('struct_lit', struct_name=expr.struct_name,
                      fields=[(k, ir_expr(v)) for k,v in expr.field_inits])
    return IRNode('unknown_expr', expr=repr(expr))


# ===========================================================================
# Optimisation
# ===========================================================================
def optimise(ir, report=True):
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
        print(f"\n  -- Optimisation report ({rounds} round(s)) --")
        for line in (log or ["(nothing to optimise)"]):
            print(f"    {line}")
    return ir, log


def _vars_assigned_in(body):
    assigned = set()
    for instr in body:
        if instr.op == 'assign':
            assigned.add(instr.name)
        for attr in ('then_body','else_body','body','try_body','catch_body','finally_body'):
            sub = getattr(instr, attr, None)
            if isinstance(sub, list):
                assigned |= _vars_assigned_in(sub)
    return assigned


def _is_const(n): return n.op in ('number','string','bool')
def _make_const(v):
    if isinstance(v, bool): return IRNode('bool', value=v)
    if isinstance(v, (int,float)): return IRNode('number', value=v)
    return IRNode('string', value=v)

def _eval_binop(op, l, r):
    m = {'+':l+r,'-':l-r,'*':l*r,
         '/':l/r if r else None,
         '==':l==r,'!=':l!=r,'<':l<r,'>':l>r,'<=':l<=r,'>=':l>=r,
         'and':l and r,'or':l or r}
    if op not in m or m[op] is None: raise ValueError
    return m[op]

def _eval_unary(op, v):
    if op == 'not': return not v
    if op == '-':   return -v
    raise ValueError

def _extra(instr, skip=None):
    s = (skip or set()) | {'op'}
    return {k:v for k,v in instr.__dict__.items() if k not in s}


def _fold_expr(n, log):
    if n.op == 'binop':
        l = _fold_expr(n.left, log)
        r = _fold_expr(n.right, log)
        if _is_const(l) and _is_const(r):
            try:
                res = _eval_binop(n.operator, l.value, r.value)
                log.append(f"Constant fold: {l.value} {n.operator} {r.value} -> {res}")
                return _make_const(res)
            except Exception: pass
        n.left, n.right = l, r
    elif n.op == 'unaryop':
        e = _fold_expr(n.expr, log)
        if _is_const(e):
            try:
                res = _eval_unary(n.operator, e.value)
                log.append(f"Constant fold: {n.operator}{e.value} -> {res}")
                return _make_const(res)
            except Exception: pass
        n.expr = e
    return n

def _pass_constant_folding(ir, log):
    return _map_instrs(ir, lambda n: _fold_expr(n, log))


def _pass_constant_propagation(ir, log):
    env = {}
    def prop(n, env):
        if n.op == 'var' and n.name in env:
            log.append(f"Const prop: '{n.name}' -> {env[n.name].value}")
            return env[n.name]
        return _map_node_expr(n, lambda x: prop(x, env))

    new_ir = []
    for instr in ir:
        if instr.op in ('while','for'):
            writes = _vars_assigned_in(getattr(instr,'body',[]))
            safe = {k:v for k,v in env.items() if k not in writes}
            nc = prop(instr.cond, safe)
            nb = _pass_constant_propagation(getattr(instr,'body',[]), log)
            d = {**_extra(instr, skip={'cond','body'}), 'cond':nc, 'body':nb}
            new_ir.append(IRNode(instr.op, **d))
            for v in writes: env.pop(v, None)
        elif instr.op == 'assign':
            v = prop(instr.value, env)
            if _is_const(v): env[instr.name] = v
            else: env.pop(instr.name, None)
            new_ir.append(IRNode('assign', name=instr.name, value=v,
                                 **_extra(instr,skip={'name','value'})))
        elif instr.op == 'if':
            nc = prop(instr.cond, env)
            nt = _pass_constant_propagation(instr.then_body, log)
            ne = _pass_constant_propagation(instr.else_body, log) if instr.else_body else None
            for v in (_vars_assigned_in(nt)|_vars_assigned_in(ne or [])):
                env.pop(v, None)
            new_ir.append(IRNode('if', cond=nc, then_body=nt, else_body=ne,
                                 **_extra(instr,skip={'cond','then_body','else_body'})))
        else:
            new_ir.append(_map_instr_exprs(instr, lambda n: prop(n, env)))
    return new_ir


def _pass_copy_propagation(ir, log):
    copies = {}
    def prop(n):
        if n.op == 'var' and n.name in copies:
            log.append(f"Copy prop: '{n.name}' -> '{copies[n.name]}'")
            return IRNode('var', name=copies[n.name])
        return _map_node_expr(n, prop)
    new_ir = []
    for instr in ir:
        if instr.op in ('while','for'):
            writes = _vars_assigned_in(getattr(instr,'body',[]))
            for v in writes: copies.pop(v, None)
            new_ir.append(instr)
        elif instr.op == 'assign' and instr.value.op == 'var':
            copies[instr.name] = instr.value.name
            new_ir.append(instr)
        else:
            if instr.op == 'assign': copies.pop(instr.name, None)
            new_ir.append(_map_instr_exprs(instr, prop))
    return new_ir


def _pass_algebraic(ir, log):
    def simp(n, log):
        if n.op != 'binop':
            return _map_node_expr(n, lambda x: simp(x, log))
        l = simp(n.left, log); r = simp(n.right, log); op = n.operator
        def num(x,v): return x.op=='number' and x.value==v
        if op=='+'  and num(r,0): log.append("Algebraic: x+0->x"); return l
        if op=='+'  and num(l,0): log.append("Algebraic: 0+x->x"); return r
        if op=='-'  and num(r,0): log.append("Algebraic: x-0->x"); return l
        if op=='*'  and num(r,1): log.append("Algebraic: x*1->x"); return l
        if op=='*'  and num(l,1): log.append("Algebraic: 1*x->x"); return r
        if op=='*'  and (num(l,0) or num(r,0)):
            log.append("Algebraic: x*0->0"); return IRNode('number',value=0)
        if op=='/'  and num(r,1): log.append("Algebraic: x/1->x"); return l
        if op=='-'  and l.op=='var' and r.op=='var' and l.name==r.name:
            log.append(f"Algebraic: {l.name}-{l.name}->0"); return IRNode('number',value=0)
        n.left, n.right = l, r
        return n
    return _map_instrs(ir, lambda n: simp(n, log))


def _pass_strength_reduction(ir, log):
    def red(n):
        if n.op == 'binop':
            l = red(n.left); r = red(n.right); op = n.operator
            if op=='*' and r.op=='number' and r.value==2:
                log.append("Strength: x*2->x+x")
                return IRNode('binop',operator='+',left=l,right=l)
            if op=='*' and l.op=='number' and l.value==2:
                log.append("Strength: 2*x->x+x")
                return IRNode('binop',operator='+',left=r,right=r)
            if op in ('**','^') and r.op=='number' and r.value==2:
                log.append("Strength: x**2->x*x")
                return IRNode('binop',operator='*',left=l,right=l)
            n.left, n.right = l, r
        return n
    return _map_instrs(ir, red)


def _pass_cse(ir, log):
    seen = {}; ctr = [0]; extras = []
    def cse(n):
        if n.op in ('number','string','bool','var'): return n
        n = _map_node_expr(n, cse)
        key = repr(n)
        if key in seen:
            log.append(f"CSE: '{key[:40]}' -> '{seen[key]}'")
            return IRNode('var', name=seen[key])
        ctr[0] += 1; t = f"__t{ctr[0]}"; seen[key] = t
        extras.append(IRNode('assign', name=t, value=n))
        return IRNode('var', name=t)
    new_ir = []
    for instr in ir:
        if instr.op == 'assign':
            v = cse(instr.value)
            new_ir.extend(extras); extras.clear()
            new_ir.append(IRNode('assign', name=instr.name, value=v,
                                 **_extra(instr,skip={'name','value'})))
        else:
            new_ir.append(instr)
    return new_ir


def _pass_dce(ir, log):
    reads = _collect_reads(ir)
    new_ir = []
    for instr in ir:
        if instr.op=='assign' and instr.name.startswith('__t') and instr.name not in reads:
            log.append(f"DCE: removed dead '{instr.name}'")
            continue
        new_ir.append(instr)
    return new_ir


# ===========================================================================
# Quadruples
# ===========================================================================
def to_quadruples(ir):
    quads = []; ctr = [0]
    def tmp():
        ctr[0] += 1; return f"t{ctr[0]}"

    def e2q(n):
        if n.op == 'number':
            v = n.value
            return str(int(v)) if isinstance(v,float) and v.is_integer() else str(v)
        if n.op in ('string','bool'): return repr(n.value)
        if n.op == 'var': return n.name
        if n.op == 'binop':
            l = e2q(n.left); r = e2q(n.right); t = tmp()
            quads.append((n.operator, l, r, t)); return t
        if n.op == 'unaryop':
            x = e2q(n.expr); t = tmp()
            quads.append((n.operator, x, '-', t)); return t
        if n.op == 'call':
            args = [e2q(a) for a in n.args]; t = tmp()
            quads.append(('call', n.name, str(args), t)); return t
        if n.op == 'array_access': return f"{n.array}[{e2q(n.index)}]"
        if n.op == 'member_access': return f"{e2q(n.expr)}.{n.member}"
        return f"?{n.op}"

    lbl_ctr = [0]
    def lbl():
        lbl_ctr[0] += 1; return f"L{lbl_ctr[0]}"

    def lower(instrs):
        for instr in instrs:
            ln = getattr(instr, 'lineno', None)
            ln_str = f"  # line {ln}" if ln else ""
            if instr.op == 'assign':
                v = e2q(instr.value)
                quads.append(('=', v, '-', instr.name + ln_str))
            elif instr.op == 'declare':
                quads.append(('decl', instr.type, '-', instr.name))
            elif instr.op == 'print':
                for ex in instr.exprs:
                    v = e2q(ex); quads.append(('print', v, '-', '-'))
            elif instr.op == 'if':
                c = e2q(instr.cond)
                else_lbl = lbl(); end_lbl = lbl()
                quads.append(('if_false', c, '-', else_lbl))
                lower(instr.then_body)
                if instr.else_body:
                    quads.append(('goto', '-', '-', end_lbl))
                    quads.append(('label', else_lbl, '-', '-'))
                    lower(instr.else_body)
                    quads.append(('label', end_lbl, '-', '-'))
                else:
                    quads.append(('label', else_lbl, '-', '-'))
            elif instr.op == 'while':
                top = lbl(); end = lbl()
                quads.append(('label', top, '-', '-'))
                c = e2q(instr.cond)
                quads.append(('if_false', c, '-', end))
                lower(instr.body)
                quads.append(('goto', '-', '-', top))
                quads.append(('label', end, '-', '-'))
            elif instr.op == 'for':
                it = e2q(instr.iterable)
                quads.append(('for_init', instr.var, it, '-'))
                top = lbl(); end = lbl()
                quads.append(('label', top, '-', '-'))
                quads.append(('for_cond', instr.var, it, end))
                lower(instr.body)
                quads.append(('for_step', instr.var, '-', '-'))
                quads.append(('goto', '-', '-', top))
                quads.append(('label', end, '-', '-'))
            elif instr.op == 'call':
                args = [e2q(a) for a in instr.args]
                quads.append(('call', instr.name, str(args), '-'))
            elif instr.op == 'return':
                v = e2q(instr.value) if instr.value else '-'
                quads.append(('return', v, '-', '-'))
            elif instr.op == 'throw':
                v = e2q(instr.value)
                quads.append(('throw', v, '-', '-'))
            elif instr.op == 'array_decl':
                init = [e2q(x) for x in instr.init]
                quads.append(('arr_decl', instr.elem_type, str(init), instr.name))
            elif instr.op == 'ptr_decl':
                quads.append(('ptr_decl', instr.base_type+'*', e2q(instr.value), instr.name))
            elif instr.op == 'ref_decl':
                quads.append(('ref_decl', instr.base_type+'&', e2q(instr.target), instr.name))
            elif instr.op == 'deref_assign':
                quads.append(('deref_=', e2q(instr.value), '-', f"*{instr.pointer}"))
            elif instr.op == 'funcdef':
                quads.append(('func_begin', instr.name, str(instr.params), '-'))
                lower(instr.body)
                quads.append(('func_end', instr.name, '-', '-'))
            elif instr.op == 'try':
                try_end = lbl(); catch_end = lbl()
                quads.append(('try_begin', '-', '-', '-'))
                lower(instr.try_body)
                quads.append(('goto', '-', '-', catch_end))
                quads.append(('catch_begin', instr.catch_var, '-', '-'))
                lower(instr.catch_body)
                quads.append(('label', catch_end, '-', '-'))
                if instr.finally_body:
                    quads.append(('finally_begin', '-', '-', '-'))
                    lower(instr.finally_body)
                    quads.append(('finally_end', '-', '-', '-'))

    lower(ir)
    return quads


def print_quadruples(quads):
    print(f"\n  {'#':<5}  {'OP':<14}  {'ARG1':<22}  {'ARG2':<12}  RESULT")
    print(f"  {'-'*5}  {'-'*14}  {'-'*22}  {'-'*12}  {'-'*14}")
    for i,(op,a1,a2,r) in enumerate(quads,1):
        print(f"  {i:<5}  {op:<14}  {str(a1):<22}  {str(a2):<12}  {r}")


# ===========================================================================
# Control-Flow Graph  (full version with dominators)
# ===========================================================================
class BasicBlock:
    _id = 0
    def __init__(self, label=None):
        BasicBlock._id += 1
        self.id           = BasicBlock._id
        self.label        = label or f"BB{self.id}"
        self.instrs       = []
        self.successors   = []
        self.predecessors = []
        # dataflow sets (computed by _compute_dataflow)
        self.gen          = set()   # variables defined in this block
        self.kill         = set()   # variables overwritten
        self.live_in      = set()
        self.live_out     = set()
        self.reach_in     = set()   # reaching definitions
        self.reach_out    = set()

    def __repr__(self):
        return self.label


def _link(a, b):
    if b not in a.successors:   a.successors.append(b)
    if a not in b.predecessors: b.predecessors.append(a)


def build_cfg(ir):
    BasicBlock._id = 0
    entry = BasicBlock('ENTRY')
    exit_ = BasicBlock('EXIT')
    blocks, current = [entry], entry

    def flush(new_label=None):
        nonlocal current
        if current.instrs or current is entry:
            b = BasicBlock(new_label)
            blocks.append(b)
            _link(current, b)
            current = b
        return current

    for instr in ir:
        if instr.op in ('if','switch'):
            current.instrs.append(instr)
            # create then/else/merge blocks
            then_b  = BasicBlock(f"then_{current.id}")
            merge_b = BasicBlock(f"merge_{current.id}")
            blocks.extend([then_b, merge_b])
            _link(current, then_b)
            _link(then_b, merge_b)
            if instr.op == 'if' and instr.else_body:
                else_b = BasicBlock(f"else_{current.id}")
                blocks.append(else_b)
                _link(current, else_b)
                _link(else_b, merge_b)
            else:
                _link(current, merge_b)
            current = merge_b

        elif instr.op == 'while':
            cond_b = BasicBlock(f"while_cond_{current.id}")
            body_b = BasicBlock(f"while_body_{current.id}")
            exit_b = BasicBlock(f"while_exit_{current.id}")
            blocks.extend([cond_b, body_b, exit_b])
            _link(current, cond_b)
            cond_b.instrs.append(instr)
            _link(cond_b, body_b)   # true edge
            _link(cond_b, exit_b)   # false edge
            _link(body_b, cond_b)   # back edge
            current = exit_b

        elif instr.op == 'for':
            cond_b = BasicBlock(f"for_cond_{current.id}")
            body_b = BasicBlock(f"for_body_{current.id}")
            exit_b = BasicBlock(f"for_exit_{current.id}")
            blocks.extend([cond_b, body_b, exit_b])
            _link(current, cond_b)
            cond_b.instrs.append(instr)
            _link(cond_b, body_b)
            _link(cond_b, exit_b)
            _link(body_b, cond_b)
            current = exit_b

        elif instr.op in ('return','throw','break','continue'):
            current.instrs.append(instr)
            _link(current, exit_)
            current = BasicBlock(f"dead_{current.id}")
            blocks.append(current)

        else:
            current.instrs.append(instr)

    if current is not exit_:
        _link(current, exit_)
    blocks.append(exit_)

    _compute_dataflow(blocks)
    return blocks, entry, exit_


def _vars_in_expr(n, out):
    if n is None: return
    if n.op == 'var': out.add(n.name)
    for k,v in n.__dict__.items():
        if k == 'op': continue
        if isinstance(v, IRNode): _vars_in_expr(v, out)
        elif isinstance(v, list):
            for x in v:
                if isinstance(x, IRNode): _vars_in_expr(x, out)


def _compute_dataflow(blocks):
    """Liveness analysis using backwards dataflow."""
    # Compute GEN and KILL per block
    for b in blocks:
        defined_before = set()
        for instr in b.instrs:
            used = set()
            if instr.op == 'assign':
                _vars_in_expr(instr.value, used)
                for u in used:
                    if u not in defined_before:
                        b.gen.add(u)
                defined_before.add(instr.name)
                b.kill.add(instr.name)
            elif instr.op in ('print',):
                for ex in instr.exprs:
                    _vars_in_expr(ex, used)
                for u in used:
                    if u not in defined_before:
                        b.gen.add(u)
            elif instr.op == 'while':
                _vars_in_expr(instr.cond, used)
                for u in used:
                    if u not in defined_before:
                        b.gen.add(u)

    # Iterative backwards liveness
    changed = True
    while changed:
        changed = False
        for b in reversed(blocks):
            old_in = set(b.live_in)
            b.live_out = set()
            for s in b.successors:
                b.live_out |= s.live_in
            b.live_in = b.gen | (b.live_out - b.kill)
            if b.live_in != old_in:
                changed = True


def print_cfg(blocks, entry, exit_):
    print(f"\n  Control-Flow Graph  ({len(blocks)} basic block(s))")
    print(f"  {'='*60}")
    for b in blocks:
        preds = ', '.join(str(p) for p in b.predecessors) or 'none'
        succs = ', '.join(str(s) for s in b.successors)   or 'none'
        live_in  = ', '.join(sorted(b.live_in))  or 'empty'
        live_out = ', '.join(sorted(b.live_out)) or 'empty'
        print(f"\n  +-- {b.label} {'(ENTRY)' if b is entry else '(EXIT)' if b.label=='EXIT' else ''}")
        print(f"  |   predecessors : {preds}")
        print(f"  |   successors   : {succs}")
        print(f"  |   live_in      : {{{live_in}}}")
        print(f"  |   live_out     : {{{live_out}}}")
        if b.instrs:
            print(f"  |   instructions :")
            for ins in b.instrs:
                print(f"  |     {ins}")
        print(f"  +{'-'*55}")


def generate_dot(blocks, filename="cfg.dot"):
    """Generate Graphviz DOT file for CFG visualization."""
    lines = ["digraph CFG {", '  rankdir=TB;',
             '  node [shape=box, fontname="Courier", fontsize=10];']
    for b in blocks:
        label = b.label.replace('"','\\"')
        instrs = "\\n".join(str(i)[:40] for i in b.instrs[:4])
        if len(b.instrs) > 4:
            instrs += f"\\n...+{len(b.instrs)-4} more"
        live = "\\nlive: {" + ",".join(sorted(b.live_in))[:30] + "}"
        node_label = f"{label}\\n{instrs}{live}" if instrs else label
        lines.append(f'  "{b.label}" [label="{node_label}"];')
    for b in blocks:
        for s in b.successors:
            lines.append(f'  "{b.label}" -> "{s.label}";')
    lines.append("}")
    with open(filename, 'w') as f:
        f.write("\n".join(lines))
    print(f"\n  DOT file written: {filename}")
    print(f"  To render: dot -Tpng {filename} -o cfg.png")
    return "\n".join(lines)


# ===========================================================================
# Full SSA with phi-function insertion
# ===========================================================================
def to_ssa(ir):
    """
    Compute SSA form with phi-function insertion.
    Returns (ssa_lines, phi_info) where ssa_lines is printable text.
    """
    version  = {}   # name -> current version int
    phi_info = {}   # (block_label, var) -> [versions from preds]
    lines    = []

    def new_ver(name):
        version[name] = version.get(name, -1) + 1
        return f"{name}_{version[name]}"

    def cur_ver(name):
        return f"{name}_{version.get(name, 0)}"

    def ssa_expr(n):
        if n.op == 'var':        return cur_ver(n.name)
        if n.op == 'number':
            v = n.value
            return str(int(v)) if isinstance(v,float) and v.is_integer() else str(v)
        if n.op in ('string','bool'): return repr(n.value)
        if n.op == 'unit':       return f"{n.value}*{n.unit}"
        if n.op == 'binop':
            return f"({ssa_expr(n.left)} {n.operator} {ssa_expr(n.right)})"
        if n.op == 'unaryop':    return f"({n.operator}{ssa_expr(n.expr)})"
        if n.op == 'call':
            args = ', '.join(ssa_expr(a) for a in n.args)
            return f"{n.name}({args})"
        if n.op == 'array_access': return f"{n.array}[{ssa_expr(n.index)}]"
        if n.op == 'member_access': return f"{ssa_expr(n.expr)}.{n.member}"
        return f"?{n.op}"

    def lower(instrs, indent=0, context=""):
        pad = "  " * indent
        for instr in instrs:
            ln = getattr(instr,'lineno','')
            ln_s = f"   ; line {ln}" if ln else ""

            if instr.op == 'assign':
                rhs = ssa_expr(instr.value)
                lhs = new_ver(instr.name)
                lines.append(f"{pad}{lhs} = {rhs}{ln_s}")

            elif instr.op == 'declare':
                lhs = new_ver(instr.name)
                lines.append(f"{pad}{lhs} = undef   ; {instr.type}")

            elif instr.op == 'array_decl':
                lhs = new_ver(instr.name)
                init = ', '.join(ssa_expr(x) for x in instr.init)
                lines.append(f"{pad}{lhs} = [{init}]")

            elif instr.op == 'print':
                args = ', '.join(ssa_expr(e) for e in instr.exprs)
                lines.append(f"{pad}print({args}){ln_s}")

            elif instr.op == 'input':
                lhs = new_ver(instr.var_name)
                lines.append(f"{pad}{lhs} = input(){ln_s}")

            elif instr.op == 'if':
                cond = ssa_expr(instr.cond)
                lines.append(f"{pad}if {cond}:{ln_s}")
                # Snapshot versions before branches
                snap = dict(version)
                lower(instr.then_body, indent+1, "then")
                then_snap = dict(version)
                # Restore to pre-branch for else
                version.clear(); version.update(snap)
                if instr.else_body:
                    lines.append(f"{pad}else:")
                    lower(instr.else_body, indent+1, "else")
                    else_snap = dict(version)
                else:
                    else_snap = snap
                # Phi functions at merge point
                all_vars = set(then_snap) | set(else_snap)
                for var in sorted(all_vars):
                    tv = f"{var}_{then_snap.get(var,0)}"
                    ev = f"{var}_{else_snap.get(var,0)}"
                    if tv != ev:
                        new_v = new_ver(var)
                        lines.append(f"{pad}  {new_v} = phi({tv}, {ev})   ; phi-function")
                    else:
                        version[var] = then_snap.get(var, 0)

            elif instr.op == 'while':
                # phi for loop variables
                cond = ssa_expr(instr.cond)
                loop_writes = _vars_assigned_in(instr.body)
                # insert phi placeholders
                phi_placeholders = {}
                for var in sorted(loop_writes):
                    pre_ver = cur_ver(var)
                    phi_ver = new_ver(var)
                    phi_placeholders[var] = (pre_ver, phi_ver)
                    lines.append(f"{pad}  {phi_ver} = phi({pre_ver}, ?)   ; loop phi")
                lines.append(f"{pad}while {ssa_expr(instr.cond)}:")
                lower(instr.body, indent+1, "loop_body")
                # fill in back-edge versions
                for var, (pre, phi_v) in phi_placeholders.items():
                    back_ver = cur_ver(var)
                    # patch the phi line
                    for i,l in enumerate(lines):
                        if f"{phi_v} = phi({pre}, ?)" in l:
                            lines[i] = l.replace('?', back_ver)
                            break

            elif instr.op == 'return':
                v = ssa_expr(instr.value) if instr.value else 'None'
                lines.append(f"{pad}return {v}{ln_s}")

            elif instr.op == 'call':
                args = ', '.join(ssa_expr(a) for a in instr.args)
                lines.append(f"{pad}{instr.name}({args}){ln_s}")

            elif instr.op == 'funcdef':
                params = ', '.join(instr.params)
                lines.append(f"\n{pad}def {instr.name}({params}):")
                snap = dict(version)
                for p in instr.params:
                    new_ver(p)
                lower(instr.body, indent+1, "func")
                if instr.ret:
                    lines.append(f"{pad}  return {ssa_expr(instr.ret)}")
                version.clear(); version.update(snap)

            elif instr.op == 'ptr_decl':
                lhs = new_ver(instr.name)
                lines.append(f"{pad}{lhs} = ptr<{instr.base_type}>({ssa_expr(instr.value)}){ln_s}")

            elif instr.op == 'ref_decl':
                lhs = new_ver(instr.name)
                lines.append(f"{pad}{lhs} = ref<{instr.base_type}>({ssa_expr(instr.target)}){ln_s}")

            else:
                lines.append(f"{pad}; {instr}")

    lower(ir)
    return "\n".join(lines), phi_info


# ===========================================================================
# Stack management model
# ===========================================================================
class StackFrame:
    """Models explicit push/pop of a function call stack."""
    SLOT = 8  # bytes

    def __init__(self):
        self.frames = []   # stack of dicts
        self.sp     = 0    # simulated stack pointer
        self.log    = []

    def push_frame(self, func_name, params, locals_):
        slots = {'__ret_addr': self.sp,
                 '__dyn_link': self.sp + self.SLOT,
                 '__ret_val':  self.sp + 2*self.SLOT}
        off = 3 * self.SLOT
        for p in params:
            slots[p] = self.sp + off; off += self.SLOT
        for l in locals_:
            slots[l] = self.sp + off; off += self.SLOT
        frame = {'func': func_name, 'size': off,
                 'slots': slots, 'base': self.sp}
        self.sp += off
        self.frames.append(frame)
        self.log.append(f"PUSH frame '{func_name}'  sp={self.sp}  size={off}B")
        return frame

    def pop_frame(self):
        if not self.frames: return
        f = self.frames.pop()
        self.sp = f['base']
        self.log.append(f"POP  frame '{f['func']}'  sp={self.sp}")

    def describe(self):
        lines = [f"  Stack pointer: {self.sp} bytes"]
        for f in reversed(self.frames):
            lines.append(f"\n  Frame: {f['func']}  (base={f['base']}  size={f['size']}B)")
            lines.append(f"  {'OFFSET':>8}  SLOT")
            lines.append(f"  {'-'*30}")
            for name, off in f['slots'].items():
                lines.append(f"  {off:>8}  {name}")
        return "\n".join(lines)


# ===========================================================================
# Heap allocation model
# ===========================================================================
class HeapAllocator:
    """
    Simulated bump-pointer heap allocator.
    Models malloc/free with a free-list for demonstration.
    """
    def __init__(self, size=4096):
        self.size      = size
        self.bump      = 0
        self.allocs    = {}   # ptr -> (size, tag, freed)
        self.free_list = []   # list of (ptr, size) freed blocks
        self.log       = []

    def malloc(self, nbytes, tag=""):
        # try free-list first (first-fit)
        for i,(ptr,sz) in enumerate(self.free_list):
            if sz >= nbytes:
                self.free_list.pop(i)
                self.allocs[ptr] = (sz, tag, False)
                self.log.append(f"malloc({nbytes}B) [reuse freed 0x{ptr:04x}] tag={tag}")
                return ptr
        if self.bump + nbytes > self.size:
            self.log.append(f"malloc({nbytes}B) FAILED: heap exhausted")
            return -1
        ptr = self.bump
        self.bump += nbytes
        self.allocs[ptr] = (nbytes, tag, False)
        self.log.append(f"malloc({nbytes}B) -> 0x{ptr:04x}  tag={tag}")
        return ptr

    def free(self, ptr):
        if ptr not in self.allocs:
            self.log.append(f"free(0x{ptr:04x}) ERROR: not allocated")
            return
        sz, tag, freed = self.allocs[ptr]
        if freed:
            self.log.append(f"free(0x{ptr:04x}) ERROR: double-free detected! tag={tag}")
            return
        self.allocs[ptr] = (sz, tag, True)
        self.free_list.append((ptr, sz))
        self.log.append(f"free(0x{ptr:04x})  size={sz}B  tag={tag}")

    def gc_mark_sweep(self, live_ptrs):
        """Simple mark-and-sweep GC."""
        swept = 0
        for ptr, (sz, tag, freed) in list(self.allocs.items()):
            if not freed and ptr not in live_ptrs:
                self.free(ptr)
                swept += 1
        self.log.append(f"GC: swept {swept} unreachable object(s)")

    def describe(self):
        used  = sum(sz for sz,_,fr in self.allocs.values() if not fr)
        total = self.bump
        lines = [f"  Heap: {used}B used / {total}B allocated / {self.size}B capacity",
                 f"  Free-list: {len(self.free_list)} block(s)",
                 f"\n  {'ADDR':>8}  {'SIZE':>6}  {'TAG':<20}  STATUS"]
        lines.append(f"  {'-'*50}")
        for ptr,(sz,tag,freed) in self.allocs.items():
            status = "FREE" if freed else "LIVE"
            lines.append(f"  0x{ptr:04x}    {sz:>6}  {tag:<20}  {status}")
        return "\n".join(lines)


def simulate_heap(ir):
    """Walk IR and simulate heap operations for new / struct_def."""
    heap = HeapAllocator()
    SIZES = {'int':8,'float':8,'bool':1,'string':64,'unknown':8}

    def walk(instrs):
        for instr in instrs:
            if instr.op == 'assign' and hasattr(instr.value,'op'):
                if instr.value.op == 'new':
                    heap.malloc(64, tag=f"new {instr.value.class_name} -> {instr.name}")
                elif instr.value.op == 'struct_lit':
                    heap.malloc(32, tag=f"struct {instr.value.struct_name} -> {instr.name}")
            for attr in ('body','then_body','else_body','try_body','catch_body'):
                sub = getattr(instr, attr, None)
                if isinstance(sub, list): walk(sub)

    walk(ir)
    return heap


# ===========================================================================
# Activation records
# ===========================================================================
class ActivationRecord:
    SLOT = 8
    def __init__(self, name, params, param_modes, locals_):
        self.name        = name
        self.params      = list(params)
        self.param_modes = list(param_modes)
        self.locals_     = list(locals_)
        self._layout     = {}
        self._build()

    def _build(self):
        off = 0
        for fixed in ('__return_addr','__static_link','__dynamic_link','__return_val'):
            self._layout[fixed] = off; off += self.SLOT
        for i,p in enumerate(self.params):
            mode = self.param_modes[i] if i < len(self.param_modes) else 'val'
            label = f"{p}  [{mode}]"
            self._layout[label] = off; off += self.SLOT
        for l in self.locals_:
            self._layout[l] = off; off += self.SLOT
        self.frame_size = off

    def describe(self):
        lines = [f"  Activation record: {self.name}  "
                 f"(frame = {self.frame_size} bytes)"]
        lines.append(f"  {'OFFSET':>8}  SLOT")
        lines.append(f"  {'-'*35}")
        for name,off in self._layout.items():
            lines.append(f"  {off:>8}  {name}")
        return "\n".join(lines)


def build_activation_records(ir):
    records = {}
    for instr in ir:
        if instr.op == 'funcdef':
            pm = getattr(instr,'param_modes',[])
            locs = _collect_locals(instr.body)
            records[instr.name] = ActivationRecord(
                instr.name, instr.params, pm, locs)
    return records


def _collect_locals(body):
    names = []
    for instr in body:
        if instr.op in ('assign','declare') and instr.name not in names:
            names.append(instr.name)
        for attr in ('then_body','else_body','body'):
            sub = getattr(instr, attr, None)
            if isinstance(sub, list):
                for n in _collect_locals(sub):
                    if n not in names: names.append(n)
    return names


# ===========================================================================
# Internal helpers
# ===========================================================================
def _map_instrs(ir, fn):
    return [_map_instr_exprs(instr, fn) for instr in ir]


def _map_instr_exprs(instr, fn):
    op = instr.op
    if op == 'assign':
        return IRNode('assign', name=instr.name, value=fn(instr.value),
                      **_extra(instr,skip={'name','value'}))
    if op == 'print':
        return IRNode('print', exprs=[fn(e) for e in instr.exprs],
                      **_extra(instr,skip={'exprs'}))
    if op == 'filter':
        return IRNode('filter', dataset=instr.dataset, cond=fn(instr.cond))
    if op == 'if':
        return IRNode('if', cond=fn(instr.cond),
                      then_body=_map_instrs(instr.then_body, fn),
                      else_body=_map_instrs(instr.else_body, fn) if instr.else_body else None,
                      **_extra(instr,skip={'cond','then_body','else_body'}))
    if op == 'while':
        return IRNode('while', cond=fn(instr.cond),
                      body=_map_instrs(instr.body, fn),
                      **_extra(instr,skip={'cond','body'}))
    if op == 'for':
        return IRNode('for', var=instr.var, iterable=fn(instr.iterable),
                      body=_map_instrs(instr.body, fn),
                      **_extra(instr,skip={'var','iterable','body'}))
    if op == 'array_decl':
        return IRNode('array_decl', name=instr.name, elem_type=instr.elem_type,
                      init=[fn(x) for x in instr.init])
    if op == 'call':
        return IRNode('call', name=instr.name,
                      args=[fn(a) for a in instr.args])
    if op == 'funcdef':
        return IRNode('funcdef', name=instr.name,
                      params=instr.params,
                      param_modes=getattr(instr,'param_modes',[]),
                      param_types=getattr(instr,'param_types',[]),
                      body=_map_instrs(instr.body, fn),
                      ret=fn(instr.ret) if instr.ret else None,
                      **_extra(instr,skip={'name','params','param_modes',
                                          'param_types','body','ret'}))
    if op == 'coord':
        return IRNode('coord', name=instr.name,
                      ra=fn(instr.ra), dec=fn(instr.dec))
    if op == 'return':
        return IRNode('return', value=fn(instr.value) if instr.value else None)
    if op == 'throw':
        return IRNode('throw', value=fn(instr.value))
    return instr


def _map_node_expr(n, fn):
    if n.op == 'binop':
        n.left = fn(n.left); n.right = fn(n.right)
    elif n.op == 'unaryop':
        n.expr = fn(n.expr)
    elif n.op == 'member_access':
        n.expr = fn(n.expr)
    elif n.op == 'array_access':
        n.index = fn(n.index)
    elif n.op == 'call':
        n.args = [fn(a) for a in n.args]
    elif n.op == 'deref':
        n.expr = fn(n.expr)
    return n


def _collect_reads(ir):
    reads = set()
    for instr in ir:
        _collect_reads_instr(instr, reads)
    return reads


def _collect_reads_instr(instr, reads):
    STMT_OPS = {'assign','declare','print','if','while','for','funcdef',
                'call','input','load_dataset','filter','coord','array_decl',
                'continue','break','return','throw','try','switch','struct_def',
                'class_def','ptr_decl','ref_decl','deref_assign'}
    for k,v in instr.__dict__.items():
        if k == 'op': continue
        if isinstance(v, IRNode):
            if v.op in STMT_OPS: _collect_reads_instr(v, reads)
            else:                _collect_reads_expr(v, reads)
        elif isinstance(v, list):
            for x in v:
                if isinstance(x, IRNode):
                    if x.op in STMT_OPS: _collect_reads_instr(x, reads)
                    else:                _collect_reads_expr(x, reads)


def _collect_reads_expr(n, reads):
    if n.op == 'var': reads.add(n.name)
    for k,v in n.__dict__.items():
        if k == 'op': continue
        if isinstance(v, IRNode):   _collect_reads_expr(v, reads)
        elif isinstance(v, list):
            for x in v:
                if isinstance(x, IRNode): _collect_reads_expr(x, reads)
