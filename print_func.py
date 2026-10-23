with open('backend/sports_bridge/prediction_client.py', 'r', encoding='utf-8') as f:
    text = f.read()

import ast
tree = ast.parse(text)
for node in ast.walk(tree):
    if isinstance(node, ast.FunctionDef) and node.name == 'predict_for_event':
        print(ast.unparse(node))
