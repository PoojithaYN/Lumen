# symbol_table.py
class SymbolTable:
    def __init__(self):
        self.scopes = [{}]  # list of dicts: global scope + nested

    def enter_scope(self):
        self.scopes.append({})

    def exit_scope(self):
        if len(self.scopes) > 1:
            self.scopes.pop()

    def declare(self, name, type_name):
        current = self.scopes[-1]
        if name in current:
            raise SemanticError(f"Redeclaration of '{name}' in same scope")
        current[name] = {'type': type_name, 'initialized': False}

    def lookup(self, name):
        for scope in reversed(self.scopes):
            if name in scope:
                return scope[name]
        raise SemanticError(f"Undefined variable '{name}'")

    def mark_initialized(self, name):
        sym = self.lookup(name)
        sym['initialized'] = True

    def is_initialized(self, name):
        sym = self.lookup(name)
        return sym['initialized']
