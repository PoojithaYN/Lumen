# codegen.py
from ir import IRNode


def generate_python(ir):
    code = [
        "from astropy import units as u",
        "from astropy.coordinates import SkyCoord",
        "import numpy as np",
        "import pandas as pd",
        "",
    ]
    print("  Codegen: Processing", len(ir), "IR instructions")
    if not ir:
        code.append('print("No statements to execute (empty program)")')

    var_types = {}

    for instr in ir:
        print(f"    → Generating code for: {instr.op}")
        gen_instr(instr, code, var_types, indent=0)

    return "\n".join(code)


def gen_instr(instr, code, var_types, indent=0):
    pad = "    " * indent

    if instr.op == 'declare':
        code.append(f"{pad}{instr.name} = None  # {instr.type}")
        var_types[instr.name] = instr.type

    elif instr.op == 'assign':
        code.append(f"{pad}{instr.name} = {ir_to_code(instr.value, var_types)}")

    elif instr.op == 'print':
        args = ', '.join(ir_to_code(e, var_types) for e in instr.exprs)
        code.append(f"{pad}print({args})")

    elif instr.op == 'input':
        code.append(f"{pad}{instr.var_name} = input()")

    elif instr.op == 'array_decl':
        init = ', '.join(ir_to_code(x, var_types) for x in instr.init)
        code.append(f"{pad}{instr.name} = [{init}]")

    elif instr.op == 'array_access':
        index = ir_to_code(instr.index, var_types)
        code.append(f"{pad}{instr.array}[{index}]")

    elif instr.op == 'member_access':
        obj = ir_to_code(instr.expr, var_types)
        if instr.member == 'length':
            code.append(f"{pad}len({obj})")
        else:
            code.append(f"{pad}{obj}.{instr.member}")

    elif instr.op == 'load_dataset':
        code.append(f"{pad}{instr.name} = pd.read_csv('{instr.file}')")

    elif instr.op == 'filter':
        cond_code = ir_to_code(instr.cond, var_types)
        code.append(f"{pad}{instr.dataset} = {instr.dataset}[{cond_code}]")

    elif instr.op == 'coord':
        ra_code  = ir_to_code(instr.ra,  var_types)
        dec_code = ir_to_code(instr.dec, var_types)
        code.append(f"{pad}{instr.name} = SkyCoord(ra={ra_code}*u.deg, dec={dec_code}*u.deg, frame='icrs')")

    elif instr.op == 'if':
        cond_code = ir_to_code(instr.cond, var_types)
        code.append(f"{pad}if {cond_code}:")
        if instr.then_body:
            for sub in instr.then_body:
                gen_instr(sub, code, var_types, indent + 1)
        else:
            code.append(f"{pad}    pass")
        if instr.else_body:
            code.append(f"{pad}else:")
            for sub in instr.else_body:
                gen_instr(sub, code, var_types, indent + 1)

    elif instr.op == 'while':
        cond_code = ir_to_code(instr.cond, var_types)
        code.append(f"{pad}while {cond_code}:")
        if instr.body:
            for sub in instr.body:
                gen_instr(sub, code, var_types, indent + 1)
        else:
            code.append(f"{pad}    pass")

    elif instr.op == 'for':
        iterable = ir_to_code(instr.iterable, var_types)
        code.append(f"{pad}for {instr.var} in {iterable}:")
        if instr.body:
            for sub in instr.body:
                gen_instr(sub, code, var_types, indent + 1)
        else:
            code.append(f"{pad}    pass")

    elif instr.op == 'continue':
        code.append(f"{pad}continue")

    elif instr.op == 'break':
        code.append(f"{pad}break")

    elif instr.op == 'funcdef':
        params = ', '.join(instr.params)
        code.append(f"{pad}def {instr.name}({params}):")
        if instr.body:
            for sub in instr.body:
                gen_instr(sub, code, var_types, indent + 1)
        else:
            code.append(f"{pad}    pass")
        if instr.ret:
            code.append(f"{pad}    return {ir_to_code(instr.ret, var_types)}")

    elif instr.op == 'call':
        args = ', '.join(ir_to_code(a, var_types) for a in instr.args)
        code.append(f"{pad}{instr.name}({args})")

    else:
        code.append(f"{pad}pass  # unhandled op: {instr.op}")


def ir_to_code(ir_node, var_types=None):
    if var_types is None:
        var_types = {}

    if ir_node.op == 'number':
        v = ir_node.value
        # Cast whole floats to int so array indices are 0 not 0.0
        return str(int(v)) if isinstance(v, float) and v.is_integer() else str(v)

    if ir_node.op == 'string':
        return repr(ir_node.value)

    if ir_node.op == 'bool':
        return 'True' if ir_node.value else 'False'

    if ir_node.op == 'var':
        return ir_node.name

    if ir_node.op == 'unit':
        if ' ' in ir_node.unit:
            parts = ir_node.unit.split()
            return f"{ir_node.value} * u.{parts[0]} / u.{parts[1]}"
        return f"{ir_node.value} * u.{ir_node.unit}"

    if ir_node.op == 'binop':
        left  = ir_to_code(ir_node.left,  var_types)
        right = ir_to_code(ir_node.right, var_types)
        op_map = {
            '==': '==', '!=': '!=',
            '&&': 'and', '||': 'or',
            'and': 'and', 'or': 'or',
            '^': '**'
        }
        # ✅ Use ir_node.operator (the symbol) not ir_node.op (which is always 'binop')
        op = op_map.get(ir_node.operator, ir_node.operator)
        return f"({left} {op} {right})"

    if ir_node.op == 'unaryop':
        expr = ir_to_code(ir_node.expr, var_types)
        op_map = {'not': 'not ', '-': '-'}
        # ✅ Use ir_node.operator here too
        return f"{op_map.get(ir_node.operator, ir_node.operator)}{expr}"

    if ir_node.op == 'member_access':
        obj = ir_to_code(ir_node.expr, var_types)
        if ir_node.member == 'length':
            return f"len({obj})"
        return f"{obj}.{ir_node.member}"

    if ir_node.op == 'array_access':
        index = ir_to_code(ir_node.index, var_types)
        return f"{ir_node.array}[{index}]"

    if ir_node.op == 'call':
        args = ', '.join(ir_to_code(a, var_types) for a in ir_node.args)
        return f"{ir_node.name}({args})"

    if ir_node.op == 'unknown_expr':
        return f"None  # unknown: {ir_node.expr!r}"

    return f"None  # unhandled: {ir_node.op}"
