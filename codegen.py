# codegen.py  -  Lumen -> Python backend
# Handles: pointer/ref out-params (list-wrap trick), all constructs

from ir import IRNode

def generate_python(ir):
    lines = [
        "# -- Lumen generated code --",
        "from astropy import units as u",
        "from astropy.coordinates import SkyCoord",
        "import numpy as np",
        "import pandas as pd",
        "import sys",
        "",
    ]
    if not ir:
        lines.append('print("(empty program)")')
    var_types = {}
    # collect out-param functions for call-site wrapping
    out_funcs = _collect_out_funcs(ir)
    for instr in ir:
        _gen(instr, lines, var_types, indent=0, out_funcs=out_funcs)
    return "\n".join(lines)


def _collect_out_funcs(ir):
    """Return dict: func_name -> [indices of out/ref params]."""
    result = {}
    for instr in ir:
        if instr.op == 'funcdef':
            modes = getattr(instr, 'param_modes', [])
            out_indices = [i for i,m in enumerate(modes) if m in ('out','ref')]
            if out_indices:
                result[instr.name] = out_indices
        for attr in ('body','then_body','else_body'):
            sub = getattr(instr, attr, None)
            if isinstance(sub, list):
                result.update(_collect_out_funcs(sub))
    return result


def _gen(instr, lines, var_types, indent, out_funcs=None):
    out_funcs = out_funcs or {}
    pad = "    " * indent
    op  = instr.op

    if op == 'declare':
        lines.append(f"{pad}{instr.name} = None  # {instr.type}")
        var_types[instr.name] = instr.type

    elif op == 'assign':
        lines.append(f"{pad}{instr.name} = {_e(instr.value)}")

    elif op == 'ptr_decl':
        # Model pointer as a Python list [value] so it can be mutated via index
        val = _e(instr.value)
        lines.append(f"{pad}{instr.name} = [{val}]  # ptr<{instr.base_type}>")

    elif op == 'ref_decl':
        # Reference: alias - just assign
        lines.append(f"{pad}{instr.name} = {_e(instr.target)}  # ref<{instr.base_type}>")

    elif op == 'deref_assign':
        # *p = val  -> p[0] = val
        lines.append(f"{pad}{instr.pointer}[0] = {_e(instr.value)}  # deref assign")

    elif op == 'type_alias':
        lines.append(f"{pad}# type {instr.alias} = {instr.base}")

    elif op == 'print':
        args = ', '.join(_e(e) for e in instr.exprs)
        lines.append(f"{pad}print({args})")

    elif op == 'input':
        lines.append(f"{pad}{instr.var_name} = input()")

    elif op == 'array_decl':
        init = ', '.join(_e(x) for x in instr.init)
        lines.append(f"{pad}{instr.name} = [{init}]")

    elif op == 'array_access':
        lines.append(f"{pad}{instr.array}[{_e(instr.index)}]")

    elif op == 'member_access':
        obj = _e(instr.expr)
        attr = f"len({obj})" if instr.member == 'length' else f"{obj}.{instr.member}"
        lines.append(f"{pad}{attr}")

    elif op == 'load_dataset':
        lines.append(f"{pad}{instr.name} = pd.read_csv('{instr.file}')")

    elif op == 'filter':
        lines.append(f"{pad}{instr.dataset} = {instr.dataset}[{_e(instr.cond)}]")

    elif op == 'coord':
        lines.append(f"{pad}{instr.name} = SkyCoord("
                     f"ra={_e(instr.ra)}*u.deg, dec={_e(instr.dec)}*u.deg, frame='icrs')")

    elif op == 'if':
        lines.append(f"{pad}if {_e(instr.cond)}:")
        if instr.then_body:
            for sub in instr.then_body:
                _gen(sub, lines, var_types, indent+1, out_funcs)
        else:
            lines.append(f"{pad}    pass")
        if instr.else_body:
            lines.append(f"{pad}else:")
            for sub in instr.else_body:
                _gen(sub, lines, var_types, indent+1, out_funcs)

    elif op == 'switch':
        first = True
        for val_node, body in instr.cases:
            kw = 'if' if first else 'elif'
            lines.append(f"{pad}{kw} {_e(instr.expr)} == {_e(val_node)}:")
            if body:
                for sub in body: _gen(sub, lines, var_types, indent+1, out_funcs)
            else:
                lines.append(f"{pad}    pass")
            first = False
        if instr.default:
            lines.append(f"{pad}else:")
            for sub in instr.default: _gen(sub, lines, var_types, indent+1, out_funcs)

    elif op == 'while':
        lines.append(f"{pad}while {_e(instr.cond)}:")
        if instr.body:
            for sub in instr.body: _gen(sub, lines, var_types, indent+1, out_funcs)
        else:
            lines.append(f"{pad}    pass")

    elif op == 'for':
        lines.append(f"{pad}for {instr.var} in {_e(instr.iterable)}:")
        if instr.body:
            for sub in instr.body: _gen(sub, lines, var_types, indent+1, out_funcs)
        else:
            lines.append(f"{pad}    pass")

    elif op == 'continue':
        lines.append(f"{pad}continue")

    elif op == 'break':
        lines.append(f"{pad}break")

    elif op == 'return':
        v = _e(instr.value) if instr.value else 'None'
        lines.append(f"{pad}return {v}")

    elif op == 'throw':
        lines.append(f"{pad}raise Exception({_e(instr.value)})")

    elif op == 'try':
        lines.append(f"{pad}try:")
        if instr.try_body:
            for sub in instr.try_body: _gen(sub, lines, var_types, indent+1, out_funcs)
        else:
            lines.append(f"{pad}    pass")
        lines.append(f"{pad}except Exception as {instr.catch_var}:")
        if instr.catch_body:
            for sub in instr.catch_body: _gen(sub, lines, var_types, indent+1, out_funcs)
        else:
            lines.append(f"{pad}    pass")
        if instr.finally_body:
            lines.append(f"{pad}finally:")
            for sub in instr.finally_body: _gen(sub, lines, var_types, indent+1, out_funcs)

    elif op == 'struct_def':
        lines.append(f"{pad}class {instr.name}:")
        field_names = [n for _,n in instr.fields]
        params = ', '.join(field_names)
        lines.append(f"{pad}    def __init__(self, {params}):")
        for _,field in instr.fields:
            lines.append(f"{pad}        self.{field} = {field}")
        if not instr.fields:
            lines.append(f"{pad}    pass")
        lines.append("")

    elif op == 'class_def':
        parent = f"({instr.parent})" if instr.parent else ""
        lines.append(f"{pad}class {instr.name}{parent}:")
        if instr.fields:
            fps = ', '.join(n for _,n in instr.fields)
            lines.append(f"{pad}    def __init__(self, {fps}):")
            for _,f in instr.fields:
                lines.append(f"{pad}        self.{f} = {f}")
        for m_name, m_params, m_modes, m_body, m_ret in instr.methods:
            ps = ', '.join(['self'] + list(m_params))
            lines.append(f"{pad}    def {m_name}({ps}):")
            if m_body:
                for sub in m_body:
                    _gen(sub, lines, var_types, indent+2, out_funcs)
            else:
                lines.append(f"{pad}        pass")
            if m_ret:
                lines.append(f"{pad}        return {_e(m_ret)}")
        lines.append("")

    elif op == 'funcdef':
        modes  = getattr(instr, 'param_modes', [])
        params = list(instr.params)
        # out/ref params become list params: def f(x_list) where x_list=[val]
        param_strs = []
        for i,p in enumerate(params):
            m = modes[i] if i < len(modes) else 'val'
            if m in ('out','ref'):
                param_strs.append(f"{p}_ref")   # caller passes [val]
            else:
                param_strs.append(p)
        lines.append(f"{pad}def {instr.name}({', '.join(param_strs)}):")

        # inside body, unwrap ref params
        for i,p in enumerate(params):
            m = modes[i] if i < len(modes) else 'val'
            if m in ('out','ref'):
                lines.append(f"{pad}    {p} = {p}_ref[0]")

        if instr.body:
            for sub in instr.body:
                _gen(sub, lines, var_types, indent+1, out_funcs)
        else:
            lines.append(f"{pad}    pass")

        # write back out/ref params before return
        for i,p in enumerate(params):
            m = modes[i] if i < len(modes) else 'val'
            if m in ('out','ref'):
                lines.append(f"{pad}    {p}_ref[0] = {p}")

        if instr.ret:
            lines.append(f"{pad}    return {_e(instr.ret)}")
        lines.append("")

    elif op == 'call':
        # wrap out/ref args in lists
        out_idx = out_funcs.get(instr.name, [])
        arg_strs = []
        for i,a in enumerate(instr.args):
            if i in out_idx:
                arg_strs.append(f"[{_e(a)}]")
            else:
                arg_strs.append(_e(a))
        lines.append(f"{pad}{instr.name}({', '.join(arg_strs)})")

    else:
        lines.append(f"{pad}pass  # unhandled: {op}")


def _e(node):
    if node is None: return 'None'
    op = node.op

    if op == 'number':
        v = node.value
        return str(int(v)) if isinstance(v,float) and v.is_integer() else str(v)
    if op == 'string':  return repr(node.value)
    if op == 'bool':    return 'True' if node.value else 'False'
    if op == 'var':     return node.name
    if op == 'unit':
        if ' ' in node.unit:
            parts = node.unit.split()
            return f"{node.value} * u.{parts[0]} / u.{parts[1]}"
        return f"{node.value} * u.{node.unit}"
    if op == 'binop':
        l = _e(node.left); r = _e(node.right)
        om = {'==':'==','!=':'!=','&&':'and','||':'or',
              'and':'and','or':'or','^':'**'}
        o = om.get(node.operator, node.operator)
        return f"({l} {o} {r})"
    if op == 'unaryop':
        e = _e(node.expr)
        m = {'not':'not ','-':'-'}
        return f"{m.get(node.operator, node.operator)}{e}"
    if op == 'member_access':
        obj = _e(node.expr)
        return f"len({obj})" if node.member=='length' else f"{obj}.{node.member}"
    if op == 'array_access':
        return f"{node.array}[{_e(node.index)}]"
    if op == 'call':
        args = ', '.join(_e(a) for a in node.args)
        return f"{node.name}({args})"
    if op == 'new':
        args = ', '.join(_e(a) for a in node.args)
        return f"{node.class_name}({args})"
    if op == 'addr_of':
        return f"[{node.name}]  # &{node.name}"
    if op == 'deref':
        return f"{_e(node.expr)}[0]  # deref"
    if op == 'struct_lit':
        args = ', '.join(_e(v) for _,v in node.fields)
        return f"{node.struct_name}({args})"
    if op == 'unknown_expr':
        return f"None  # unknown: {node.expr!r}"
    return f"None  # unhandled: {op}"
