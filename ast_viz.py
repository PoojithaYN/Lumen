# ast_viz.py  –  Lumen AST visualiser
# Produces a box-drawing tree, a one-line summary per node, and
# an optional compact s-expression dump.

from ast_nodes import Node


# ─── Tree printer ─────────────────────────────────────────────────────────────
def visualise_ast(node, title="AST"):
    lines = [f"  ╔══ {title} {'═'*(46-len(title))}╗"]
    _render(node, lines, prefix="  ║  ", is_last=True, depth=0)
    lines.append("  ╚" + "═" * 50 + "╝")
    return "\n".join(lines)


def _label(node):
    """One-line description of a node."""
    if node is None:
        return "None"
    kind = getattr(node, 'kind', node.__class__.__name__)
    extras = []
    for key in ('name', 'type', 'op', 'value', 'var', 'dataset',
                 'alias', 'base_type', 'member', 'operator',
                 'catch_var', 'base', 'struct_name', 'class_name', 'parent'):
        val = getattr(node, key, None)
        if val is not None and not isinstance(val, (list, Node)):
            extras.append(f"{key}={val!r}")
    lineno = getattr(node, 'lineno', None)
    if lineno:
        extras.append(f"line={lineno}")
    suffix = "  " + ", ".join(extras) if extras else ""
    return f"{kind}{suffix}"


def _child_items(node):
    """Return (label, child_node_or_list) pairs for all interesting children."""
    items = []
    skip = {'kind', 'lineno'}
    for key, val in node.__dict__.items():
        if key in skip:
            continue
        # skip scalars we already show in the label
        if key in ('name', 'type', 'op', 'value', 'var', 'dataset',
                   'alias', 'base_type', 'member', 'operator', 'catch_var',
                   'base', 'struct_name', 'class_name', 'parent'):
            continue
        if val is None:
            continue
        if isinstance(val, list) and not val:
            continue
        items.append((key, val))
    return items


def _render(node, lines, prefix, is_last, depth):
    if depth > 20:
        lines.append(prefix + "  ...")
        return

    connector = "└─ " if is_last else "├─ "
    lines.append(prefix + connector + _label(node))
    ext = "   " if is_last else "│  "

    children = _child_items(node)
    for i, (key, val) in enumerate(children):
        is_last_child = (i == len(children) - 1)
        child_prefix = prefix + ext
        child_connector = "└─ " if is_last_child else "├─ "

        if isinstance(val, Node):
            lines.append(child_prefix + child_connector + f"[{key}]")
            _render(val, lines,
                    prefix=child_prefix + ("   " if is_last_child else "│  "),
                    is_last=True, depth=depth+1)

        elif isinstance(val, list):
            lines.append(child_prefix + child_connector + f"[{key}]  ({len(val)} items)")
            list_prefix = child_prefix + ("   " if is_last_child else "│  ")
            for j, item in enumerate(val):
                last_item = (j == len(val) - 1)
                if isinstance(item, Node):
                    _render(item, lines, prefix=list_prefix,
                            is_last=last_item, depth=depth+1)
                elif isinstance(item, tuple):
                    lines.append(list_prefix + ("└─ " if last_item else "├─ ") + repr(item))
                else:
                    lines.append(list_prefix + ("└─ " if last_item else "├─ ") + repr(item))
        else:
            lines.append(child_prefix + child_connector + f"{key} = {val!r}")


# ─── S-expression dump ────────────────────────────────────────────────────────
def sexp(node, indent=0):
    """Compact parenthesised representation for debugging."""
    if node is None:
        return "nil"
    pad = "  " * indent
    kind = getattr(node, 'kind', node.__class__.__name__)
    parts = [kind]
    for key, val in node.__dict__.items():
        if key in ('kind', 'lineno'):
            continue
        if isinstance(val, Node):
            parts.append(f"\n{pad}  ({sexp(val, indent+1)})")
        elif isinstance(val, list):
            if val:
                inner = "\n".join(f"{pad}    {sexp(v, indent+2)}" if isinstance(v, Node)
                                  else f"{pad}    {v!r}" for v in val)
                parts.append(f"\n{pad}  [{key}:\n{inner}\n{pad}  ]")
        else:
            parts.append(f"{key}:{val!r}")
    return "(" + " ".join(parts) + ")"


# ─── Entry point ──────────────────────────────────────────────────────────────
if __name__ == "__main__":
    import sys
    from lexer  import lexer
    from parser import parser

    if len(sys.argv) < 2:
        print("Usage: python ast_viz.py <file.lumen>")
        sys.exit(1)

    src = open(sys.argv[1]).read()
    ast = parser.parse(src, lexer=lexer)
    if ast:
        print(visualise_ast(ast))
    else:
        print("Parse failed.")
