import os

def fix():
    file_path = 'backend/btc/analyzer.py'
    with open(file_path, 'r', encoding='utf-8') as f:
        content = f.read()

    target = '''    except Exception:
        pass


    return {'''

    injection = '''    except Exception:
        pass

    if grade == "GRADE C / ML MODEL" and 45 <= prob <= 55:
        direction = "PASS"
        pred = "PASS"
        grade = "GRADE C / PASS"
        badge = "⚪ PASS (CHOP)"
        prob = 50
        catalysts = ["Model edge too weak. Sitting out."]

    return {'''

    content = content.replace(target, injection)

    with open(file_path, 'w', encoding='utf-8') as f:
        f.write(content)

if __name__ == '__main__':
    fix()
    print("Patched analyzer.py to explicitly return PASS for chop zone!")
