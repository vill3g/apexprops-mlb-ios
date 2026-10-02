import re

with open('C:\\Users\\Vill3\\Desktop\\kalshi-ai-trader\\static\\js\\dashboard.js', 'r', encoding='utf-8') as f:
    content = f.read()

old_block = '''    } catch (e) {
        console.error('Failed to fetch trading tip:', e);
    }'''

new_block = '''    } catch (e) {
        if (force) alert("Network error: " + e.message);
        console.error('Failed to fetch trading tip:', e);
    }'''

if old_block in content:
    content = content.replace(old_block, new_block)
    with open('C:\\Users\\Vill3\\Desktop\\kalshi-ai-trader\\static\\js\\dashboard.js', 'w', encoding='utf-8') as f:
        f.write(content)
    print("Replaced!")
else:
    print("Could not find block.")
