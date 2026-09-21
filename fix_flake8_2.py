import re

def remove_global(file_path, var_name):
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()
    
    # Just remove lines like `global _ob_cache`
    new_content = re.sub(r'^[ \t]*global\s+' + var_name + r'\s*$', '', content, flags=re.MULTILINE)
    
    if new_content != content:
        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(new_content)
        print("Fixed", file_path)

remove_global('backend/btc/data_fetcher.py', r'_ob_cache')
remove_global('backend/btc/kalshi_client.py', r'_kalshi_cache,\s*_kalshi_cache_times')
remove_global('backend/btc/ml_engine.py', r'_ml_engine_instances')

