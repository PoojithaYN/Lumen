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
    print(" Codegen: Processing", len(ir), "IR instructions")
    
    if not ir:
        code.append('print("No statements to execute (empty program)")')
    
    var_types = {}  # simple tracking
    
    for instr in ir:
        print(f" → Generating code for: {instr.op}")
        
        if instr.op == 'declare':
            code.append(f"{instr.name} = None  # {instr.type}")
            var_types[instr.name] = instr.type
        
        elif instr.op == 'assign':
            value_code = ir_to_code(instr.value, var_types)
            code.append(f"{instr.name} = {value_code}")
        
        elif instr.op == 'print':
            expr_code = ir_to_code(instr.expr, var_types)
            code.append(f"print({expr_code})")
        
        elif instr.op == 'load_dataset':
            code.append(f"{instr.name} = pd.read_csv('{instr.file}')")
        
        elif instr.op == 'filter':
            cond_code = ir_to_code(instr.cond, var_types)
            code.append(f"{instr.dataset} = {instr.dataset}[{cond_code}]")
        
        elif instr.op == 'coord':
            ra_code = ir_to_code(instr.ra, var_types)
            dec_code = ir_to_code(instr.dec, var_types)
            code.append(f"{instr.name} = SkyCoord(ra={ra_code}*u.deg, dec={dec_code}*u.deg, frame='icrs')")
        
        elif instr.op == 'unit':
            code.append(f"{instr.value} * u.{instr.unit}")
        
        elif instr.op == 'binop':
            left = ir_to_code(instr.left, var_types)
            right = ir_to_code(instr.right, var_types)
            code.append(f"({left} {instr.op} {right})")
        
        elif instr.op == 'if':
            cond_code = ir_to_code(instr.cond, var_types)
            code.append(f"if {cond_code}:")
            # then body (indent)
            for sub in instr.then_body:
                code.append("    " + ir_to_code(sub, var_types))
            if instr.else_body:
                code.append("else:")
                for sub in instr.else_body:
                    code.append("    " + ir_to_code(sub, var_types))
        
        elif instr.op == 'while':
            cond_code = ir_to_code(instr.cond, var_types)
            code.append(f"while {cond_code}:")
            for sub in instr.body:
                code.append("    " + ir_to_code(sub, var_types))
        
        elif instr.op == 'continue':
            code.append("    continue")
        
        elif instr.op == 'break':
            code.append("    break")
        elif instr.op == 'array_decl':
            init_codes = [ir_to_code(x, var_types) for x in instr.init]
            code.append(f"{instr.name} = [{', '.join(init_codes)}]")

        elif instr.op == 'array_access':
            array_code = ir_to_code(instr.array, var_types)
            index_code = ir_to_code(instr.index, var_types)
            code.append(f"{array_code}[{index_code}]")
        elif instr.op == 'array_decl':
            init_codes = [ir_to_code(x, var_types) for x in instr.init]
            code.append(f"{instr.name} = [{', '.join(init_codes)}]")

        elif instr.op == 'array_access':
            array_code = ir_to_code(instr.array, var_types)
            index_code = ir_to_code(instr.index, var_types)
            code.append(f"{array_code}[{index_code}]")
        elif ir_node.op == 'member_access':
            expr_code = ir_to_code(ir_node.expr, var_types)
            return f"{expr_code}.{ir_node.member}"
        
        # Add more ops as needed
    
    return "\n".join(code)

def ir_to_code(ir_node, var_types):
    if ir_node.op == 'number':
        return str(ir_node.value)
    if ir_node.op == 'var':
        return ir_node.name
    if ir_node.op == 'unit':
        if ' ' in ir_node.unit:  # e.g. "km s"
            parts = ir_node.unit.split()
            return f"{ir_node.value} * u.{parts[0]} / u.{parts[1]}"  # "220.0 * u.km / u.s"
        else:
            return f"{ir_node.value} * u.{ir_node.unit}"
    if ir_node.op == 'binop':
        left = ir_to_code(ir_node.left, var_types)
        right = ir_to_code(ir_node.right, var_types)
        op = ir_node.op if ir_node.op != '^' else '**'  # Python uses **
        return f"({left} {op} {right})"
    return "???"

print("\nGenerated code ready for execution.")
