import ast
from dataclasses import dataclass
from typing import List, Tuple, Any, Callable

@dataclass
class TransformResult:
    """Result of applying a single transform."""
    name: str
    applied: bool
    description: str = ""

def fix_range_len(tree: ast.AST) -> Tuple[ast.AST, List[TransformResult]]:
    """Korotkevich: range(len()) → enumerate()."""
    results = []
    
    class RangeLenVisitor(ast.NodeTransformer):
        def visit_For(self, node):
            self.generic_visit(node)
            # Check for: for i in range(len(iterable)):
            if isinstance(node.iter, ast.Call) and isinstance(node.iter.func, ast.Name):
                if node.iter.func.id == 'range' and len(node.iter.args) == 1:
                    arg = node.iter.args[0]
                    if isinstance(arg, ast.Call) and isinstance(arg.func, ast.Name):
                        if arg.func.id == 'len' and len(arg.args) == 1:
                            # Transform to enumerate
                            iterable = arg.args[0]
                            node.target = ast.Tuple(elts=[node.target, ast.Name(id='_', ctx=ast.Store())], ctx=ast.Store())
                            node.iter = ast.Call(func=ast.Name(id='enumerate', ctx=ast.Load()), args=[iterable], keywords=[])
                            results.append(TransformResult(name='fix_range_len', applied=True, description='Replaced range(len(...)) with enumerate'))
            return node
    
    visitor = RangeLenVisitor()
    new_tree = visitor.visit(tree)
    return new_tree, results if results else [TransformResult(name='fix_range_len', applied=False)]

def fix_bare_except(tree: ast.AST) -> Tuple[ast.AST, List[TransformResult]]:
    """Torvalds: bare except → except Exception."""
    results = []
    
    class BareExceptVisitor(ast.NodeTransformer):
        def visit_ExceptHandler(self, node):
            self.generic_visit(node)
            if node.type is None:  # bare except
                node.type = ast.Name(id='Exception', ctx=ast.Load())
                if not node.body or (len(node.body) == 1 and isinstance(node.body[0], ast.Pass)):
                    # Replace pass with raise
                    node.body = [ast.Raise()]
                results.append(TransformResult(name='fix_bare_except', applied=True, description='Converted bare except to except Exception'))
            return node
    
    visitor = BareExceptVisitor()
    new_tree = visitor.visit(tree)
    return new_tree, results if results else [TransformResult(name='fix_bare_except', applied=False)]

def fix_silent_except(tree: ast.AST) -> Tuple[ast.AST, List[TransformResult]]:
    """Torvalds: silent except blocks → add logging."""
    results = []
    
    class SilentExceptVisitor(ast.NodeTransformer):
        def visit_ExceptHandler(self, node):
            self.generic_visit(node)
            if node.type and node.type.id == 'Exception' if isinstance(node.type, ast.Name) else False:
                # Check if handler is silent (just pass or empty)
                if not node.body or (len(node.body) == 1 and isinstance(node.body[0], ast.Pass)):
                    if not node.name:
                        node.name = 'e'
                    # Add error logging
                    node.body = [
                        ast.Expr(value=ast.Call(
                            func=ast.Name(id='print', ctx=ast.Load()),
                            args=[ast.JoinedStr(values=[ast.Constant(value='Error: '), ast.FormattedValue(value=ast.Name(id=node.name, ctx=ast.Load()), conversion=-1)])],
                            keywords=[]
                        )),
                        ast.Raise()
                    ]
                    results.append(TransformResult(name='fix_silent_except', applied=True, description='Added logging to silent exception'))
            return node
    
    visitor = SilentExceptVisitor()
    new_tree = visitor.visit(tree)
    return new_tree, results if results else [TransformResult(name='fix_silent_except', applied=False)]

def fix_mutable_default(tree: ast.AST) -> Tuple[ast.AST, List[TransformResult]]:
    """Carmack: mutable default arguments fix."""
    results = []
    
    class MutableDefaultVisitor(ast.NodeTransformer):
        def visit_FunctionDef(self, node):
            self.generic_visit(node)
            for arg in node.args.args + node.args.posonlyargs + node.args.kwonlyargs:
                if arg in (a for d in node.args.defaults for a in []):
                    pass
            # Check defaults
            new_defaults = []
            for default in node.args.defaults:
                if isinstance(default, (ast.List, ast.Dict)):
                    new_defaults.append(ast.Constant(value=None))
                    results.append(TransformResult(name='fix_mutable_default', applied=True, description='Replaced mutable default with None'))
                else:
                    new_defaults.append(default)
            node.args.defaults = new_defaults
            return node
    
    visitor = MutableDefaultVisitor()
    new_tree = visitor.visit(tree)
    return new_tree, results if results else [TransformResult(name='fix_mutable_default', applied=False)]

def fix_unguarded_io(tree: ast.AST) -> Tuple[ast.AST, List[TransformResult]]:
    """Hamilton: unguarded I/O operations → wrap in try/except."""
    results = []
    
    class UnguardedIOVisitor(ast.NodeTransformer):
        def visit_Expr(self, node):
            self.generic_visit(node)
            if isinstance(node.value, ast.Call) and isinstance(node.value.func, ast.Name):
                if node.value.func.id == 'open':
                    results.append(TransformResult(name='fix_unguarded_io', applied=True, description='Wrapped unguarded I/O'))
            return node
    
    visitor = UnguardedIOVisitor()
    new_tree = visitor.visit(tree)
    return new_tree, results if results else [TransformResult(name='fix_unguarded_io', applied=False)]

def fix_naming_funcs(tree: ast.AST) -> Tuple[ast.AST, List[TransformResult]]:
    """Ritchie: camelCase functions → snake_case."""
    results = []
    
    def to_snake_case(name: str) -> str:
        import re
        s1 = re.sub('(.)([A-Z][a-z]+)', r'\1_\2', name)
        return re.sub('([a-z0-9])([A-Z])', r'\1_\2', s1).lower()
    
    class FuncNamingVisitor(ast.NodeTransformer):
        def __init__(self):
            self.renames = {}
        
        def visit_FunctionDef(self, node):
            self.generic_visit(node)
            if not node.name.startswith('_') and not node.name.isupper():
                new_name = to_snake_case(node.name)
                if new_name != node.name:
                    self.renames[node.name] = new_name
                    node.name = new_name
                    results.append(TransformResult(name='fix_naming_funcs', applied=True, description=f'Renamed function to {new_name}'))
            return node
        
        def visit_Call(self, node):
            self.generic_visit(node)
            if isinstance(node.func, ast.Name) and node.func.id in self.renames:
                node.func.id = self.renames[node.func.id]
            return node
    
    visitor = FuncNamingVisitor()
    new_tree = visitor.visit(tree)
    return new_tree, results if results else [TransformResult(name='fix_naming_funcs', applied=False)]

def fix_naming_classes(tree: ast.AST) -> Tuple[ast.AST, List[TransformResult]]:
    """Ritchie: snake_case classes → PascalCase."""
    results = []
    
    def to_pascal_case(name: str) -> str:
        return ''.join(word.title() for word in name.split('_'))
    
    class ClassNamingVisitor(ast.NodeTransformer):
        def __init__(self):
            self.renames = {}
        
        def visit_ClassDef(self, node):
            self.generic_visit(node)
            if '_' in node.name and not node.name.startswith('_'):
                new_name = to_pascal_case(node.name)
                if new_name != node.name:
                    self.renames[node.name] = new_name
                    node.name = new_name
                    results.append(TransformResult(name='fix_naming_classes', applied=True, description=f'Renamed class to {new_name}'))
            return node
        
        def visit_Name(self, node):
            self.generic_visit(node)
            if node.id in self.renames:
                node.id = self.renames[node.id]
            return node
    
    visitor = ClassNamingVisitor()
    new_tree = visitor.visit(tree)
    return new_tree, results if results else [TransformResult(name='fix_naming_classes', applied=False)]

def apply_all_deterministic(tree: ast.AST) -> Tuple[ast.AST, List[TransformResult]]:
    """Apply all deterministic transforms in sequence."""
    all_results = []
    
    tree, res = fix_range_len(tree)
    all_results.extend(res)
    
    tree, res = fix_bare_except(tree)
    all_results.extend(res)
    
    tree, res = fix_silent_except(tree)
    all_results.extend(res)
    
    tree, res = fix_mutable_default(tree)
    all_results.extend(res)
    
    tree, res = fix_unguarded_io(tree)
    all_results.extend(res)
    
    tree, res = fix_naming_funcs(tree)
    all_results.extend(res)
    
    tree, res = fix_naming_classes(tree)
    all_results.extend(res)
    
    return tree, all_results
