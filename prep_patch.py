with open('fixes/sports_order_safety/sports_order_safety.patch', 'r') as f:
    text = f.read()

# Start from executor.py, end before tests
start = text.find('--- a/backend/sports_bridge/executor.py')
end = text.find('--- a/tests/test_sports_dashboard.py')
executor_patch = text[start:end]

with open('clean_executor.patch', 'w') as f:
    f.write(executor_patch)
