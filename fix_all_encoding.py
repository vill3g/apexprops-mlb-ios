# -*- coding: utf-8 -*-
"""
Fix all encoding corruption across the app.
Uses unicode escapes to avoid encoding issues in the script itself.
"""
import os
import re
import sys

CENT = '\u00a2'       # cent sign
MIDDOT = '\u00b7'     # middle dot
REPL = '\ufffd'       # replacement character
DEGREE = '\u00b0'     # degree sign
ENDASH = '\u2013'     # en dash
EMDASH = '\u2014'     # em dash
COPY = '\u00a9'       # copyright
BULLET = '\u2022'     # bullet

# --- Emoji code points ---
ROBOT = '\U0001F916'
TARGET = '\U0001F3AF'
CRYSTAL = '\U0001F52E'
SURFER = '\U0001F3C4'
TIGER = '\U0001F405'
AXE = '\U0001FA93'
BRAIN = '\U0001F9E0'
BEE = '\U0001F41D'
SPARKLES = '\u2728'
TORNADO = '\U0001F32A\uFE0F'
CHART = '\U0001F4C8'
CANDLE = '\U0001F56F\uFE0F'
TEST_TUBE = '\U0001F9EA'
RED_CIRCLE = '\U0001F534'
LIGHTNING = '\u26A1'
GUN = '\U0001F52B'
MONEYBAG = '\U0001F4B0'
GEAR = '\u2699\uFE0F'
TROPHY = '\U0001F3C6'
COMPASS = '\U0001F9ED'
SHIELD = '\U0001F6E1\uFE0F'
RECEIPT = '\U0001F9FE'
DNA = '\U0001F9EC'
SATELLITE = '\U0001F4E1'
BULB = '\U0001F4A1'
HOURGLASS = '\u231B'
REFRESH = '\U0001F504'
ROCKET = '\U0001F680'
FIRE = '\U0001F525'
FOOTBALL = '\U0001F3C8'
DIAMOND = '\U0001F48E'
BTC_SYMBOL = '\u20BF'
MONEY = '\U0001F4B0'
GREEN_UP = '\u2B06\uFE0F'
RED_DOWN = '\u2B07\uFE0F'
TRIANGLE_UP = '\U0001F53A'
CLOSE_X = '\u2715'
STOP_SIGN = '\U0001F6D1'


def read_file(path):
    """Try reading with utf-8, fall back to latin-1."""
    for enc in ('utf-8', 'latin-1'):
        try:
            with open(path, 'r', encoding=enc) as f:
                return f.read()
        except (UnicodeDecodeError, UnicodeError):
            continue
    return None


def write_file(path, content):
    """Write as UTF-8 without BOM."""
    with open(path, 'w', encoding='utf-8', newline='\n') as f:
        f.write(content)


def fix_dashboard_js(base):
    path = os.path.join(base, 'static', 'js', 'dashboard.js')
    if not os.path.exists(path):
        print(f"  SKIP (not found): {path}")
        return
    content = read_file(path)
    if content is None:
        print(f"  ERROR reading: {path}")
        return

    orig = content

    # Fix REPL+\x07 pattern (was likely a bell char from bad encoding)
    content = content.replace(REPL + '\x07', MIDDOT)

    # Fix cent sign mojibake: REPL used where cent sign should be
    # Pattern: number followed by REPL (e.g. "75<REPL>" -> "75 cents")
    content = re.sub(r'(\d)' + REPL, r'\1' + CENT, content)
    # Pattern: --REPL (price placeholder)
    content = content.replace('--' + REPL, '--' + CENT)
    # Pattern: }REPL (template literal ending with cent)
    content = content.replace('}' + REPL, '}' + CENT)
    # Pattern: 'REPL' as standalone cent
    content = content.replace("'" + REPL + "'", "'" + CENT + "'")
    # Any remaining standalone REPL
    content = content.replace(REPL, CENT)

    # Fix ?? emoji patterns (corrupted emojis turned to literal ??)
    content = content.replace('?? Prediction', CRYSTAL + ' Prediction')
    content = content.replace('?? PREDICTION', CRYSTAL + ' PREDICTION')
    content = content.replace('?? AUTO', ROBOT + ' AUTO')
    content = content.replace('?? SNIPER', TARGET + ' SNIPER')
    content = content.replace('?? Sniper', TARGET + ' Sniper')
    content = content.replace('?? AMBUSH', TIGER + ' AMBUSH')
    content = content.replace('?? Ambush', TIGER + ' Ambush')
    content = content.replace('?? CHOP', AXE + ' CHOP')
    content = content.replace('?? Chop', AXE + ' Chop')
    content = content.replace('?? MOMENTUM', SURFER + ' MOMENTUM')
    content = content.replace('?? Momentum', SURFER + ' Momentum')
    content = content.replace('?? Deep Q-Network', BRAIN + ' Deep Q-Network')
    content = content.replace('??? God-Tier', BEE + SPARKLES + ' God-Tier')
    content = content.replace('??? Blend', TORNADO + ' Blend')
    content = content.replace('?? Blend', TORNADO + ' Blend')
    content = content.replace('? BLEND', TORNADO + ' BLEND')
    content = content.replace('?? 100% AI', BRAIN + ' 100% AI')
    content = content.replace('?? 100% Chart', CHART + ' 100% Chart')
    content = content.replace('??? Technical Force', LIGHTNING + ' Technical Force')
    content = content.replace('?? 1-Shot', GUN + ' 1-Shot')
    content = content.replace('?? Net P&L', MONEYBAG + ' Net P&L')
    content = content.replace('?? Win Rate', TARGET + ' Win Rate')
    content = content.replace('?? Trades', CHART + ' Trades')
    content = content.replace('?? PAPER MODE:', TEST_TUBE + ' PAPER MODE:')
    content = content.replace('? PAPER MODE', TEST_TUBE + ' PAPER MODE')
    content = content.replace('? LIVE MODE', RED_CIRCLE + ' LIVE MODE')
    content = content.replace('? SCALPER', LIGHTNING + ' SCALPER')
    content = content.replace('? LINE', CHART + ' LINE')
    content = content.replace('? CANDLES', CANDLE + ' CANDLES')

    if content != orig:
        write_file(path, content)
        print(f"  FIXED: {path}")
    else:
        print(f"  CLEAN: {path}")


def fix_saas_dashboard(base):
    path = os.path.join(base, 'static', 'saas_dashboard.html')
    if not os.path.exists(path):
        print(f"  SKIP (not found): {path}")
        return
    content = read_file(path)
    if content is None:
        print(f"  ERROR reading: {path}")
        return

    orig = content

    # Fix REPL chars
    content = content.replace(REPL + '\x07', MIDDOT)
    content = re.sub(r'(\d)' + REPL, r'\1' + CENT, content)
    content = content.replace('--' + REPL, '--' + CENT)
    content = content.replace('}' + REPL, '}' + CENT)
    content = content.replace("'" + REPL + "'", "'" + CENT + "'")
    content = content.replace(REPL, '')

    # Fix ?? emoji patterns
    content = content.replace('?? SNIPER', TARGET + ' SNIPER')
    content = content.replace('?? AMBUSH', TIGER + ' AMBUSH')
    content = content.replace('?? CHOP', AXE + ' CHOP')
    content = content.replace('?? MOMENTUM', SURFER + ' MOMENTUM')
    content = content.replace('?? PREDICTION', CRYSTAL + ' PREDICTION')
    content = content.replace('?? AUTO', ROBOT + ' AUTO')
    content = content.replace('?? Sniper', TARGET + ' Sniper')
    content = content.replace('?? Prediction', CRYSTAL + ' Prediction')
    content = content.replace('?? Momentum', SURFER + ' Momentum')
    content = content.replace('?? Ambush', TIGER + ' Ambush')
    content = content.replace('?? Chop', AXE + ' Chop')
    content = content.replace('?? Deep Q-Network', BRAIN + ' Deep Q-Network')
    content = content.replace('????? God-Tier', BEE + SPARKLES + ' God-Tier')
    content = content.replace('??? God-Tier', BEE + SPARKLES + ' God-Tier')
    content = content.replace('??? Blend', TORNADO + ' Blend')
    content = content.replace('?? Blend', TORNADO + ' Blend')
    content = content.replace('?? 100% AI', BRAIN + ' 100% AI')
    content = content.replace('?? 100% Chart', CHART + ' 100% Chart')
    content = content.replace('??? Technical Force', LIGHTNING + ' Technical Force')
    content = content.replace('?? 1-Shot', GUN + ' 1-Shot')
    content = content.replace('?? Net P&L', MONEYBAG + ' Net P&L')
    content = content.replace('?? Win Rate', TARGET + ' Win Rate')
    content = content.replace('?? Trades', CHART + ' Trades')
    content = content.replace('?? PAPER MODE:', TEST_TUBE + ' PAPER MODE:')
    content = content.replace('? PAPER MODE', TEST_TUBE + ' PAPER MODE')
    content = content.replace('? LIVE MODE', RED_CIRCLE + ' LIVE MODE')
    content = content.replace('? SCALPER', LIGHTNING + ' SCALPER')
    content = content.replace('? LINE', CHART + ' LINE')
    content = content.replace('? CANDLES', CANDLE + ' CANDLES')
    content = content.replace('? BLEND', TORNADO + ' BLEND')

    if content != orig:
        write_file(path, content)
        print(f"  FIXED: {path}")
    else:
        print(f"  CLEAN: {path}")


def fix_app_js(base):
    path = os.path.join(base, 'static', 'js', 'app.js')
    if not os.path.exists(path):
        print(f"  SKIP (not found): {path}")
        return
    content = read_file(path)
    if content is None:
        print(f"  ERROR reading: {path}")
        return

    orig = content

    content = content.replace(REPL + '\x07', MIDDOT)
    content = re.sub(r'(\d)' + REPL, r'\1' + CENT, content)
    content = content.replace('--' + REPL, '--' + CENT)
    content = content.replace('}' + REPL, '}' + CENT)
    content = content.replace("'" + REPL + "'", "'" + CENT + "'")
    content = content.replace(REPL, '')

    if content != orig:
        write_file(path, content)
        print(f"  FIXED: {path}")
    else:
        print(f"  CLEAN: {path}")


def fix_admin_users_js(base):
    path = os.path.join(base, 'static', 'js', 'admin_users.js')
    if not os.path.exists(path):
        print(f"  SKIP (not found): {path}")
        return
    content = read_file(path)
    if content is None:
        print(f"  ERROR reading: {path}")
        return

    orig = content

    content = content.replace(REPL + '\x07', MIDDOT)
    content = re.sub(r'(\d)' + REPL, r'\1' + CENT, content)
    content = content.replace('--' + REPL, '--' + CENT)
    content = content.replace('}' + REPL, '}' + CENT)
    content = content.replace("'" + REPL + "'", "'" + CENT + "'")
    content = content.replace(REPL, '')

    if content != orig:
        write_file(path, content)
        print(f"  FIXED: {path}")
    else:
        print(f"  CLEAN: {path}")


def fix_contract_eval(base):
    path = os.path.join(base, 'backend', 'btc', 'analyzer', 'contract_eval.py')
    if not os.path.exists(path):
        print(f"  SKIP (not found): {path}")
        return
    content = read_file(path)
    if content is None:
        print(f"  ERROR reading: {path}")
        return

    orig = content

    content = content.replace('?? Prediction', CRYSTAL + ' Prediction')
    content = content.replace('?? PRED:', CRYSTAL + ' PRED:')
    content = content.replace(REPL, '')

    if content != orig:
        write_file(path, content)
        print(f"  FIXED: {path}")
    else:
        print(f"  CLEAN: {path}")


def fix_json_files(base):
    """Fix ?? in JSON data files."""
    json_paths = [
        os.path.join(base, 'backend', 'data', 'signal_snapshot.json'),
    ]
    # Also fix user trade histories
    users_dir = os.path.join(base, 'backend', 'data', 'users')
    if os.path.isdir(users_dir):
        for uid in os.listdir(users_dir):
            th = os.path.join(users_dir, uid, 'trades_history.json')
            if os.path.isfile(th):
                json_paths.append(th)

    # Also top-level data trades_history
    top_th = os.path.join(base, 'data', 'trades_history.json')
    if os.path.isfile(top_th):
        json_paths.append(top_th)

    for path in json_paths:
        if not os.path.isfile(path):
            continue
        content = read_file(path)
        if content is None:
            continue
        orig = content
        content = content.replace('?? Prediction', CRYSTAL + ' Prediction')
        content = content.replace('?? PRED:', CRYSTAL + ' PRED:')
        content = content.replace(REPL, '')
        if content != orig:
            write_file(path, content)
            print(f"  FIXED: {path}")


def verify_js_syntax(base):
    """Run node --check on JS files."""
    js_files = [
        os.path.join(base, 'static', 'js', 'dashboard.js'),
        os.path.join(base, 'static', 'js', 'app.js'),
        os.path.join(base, 'static', 'js', 'admin_users.js'),
    ]
    for path in js_files:
        if not os.path.exists(path):
            continue
        ret = os.system(f'node -c "{path}"')
        status = "OK" if ret == 0 else "SYNTAX ERROR"
        print(f"  {status}: {os.path.basename(path)}")


if __name__ == '__main__':
    base = r'C:\Users\Vill3\Desktop\kalshi-ai-trader'
    print("=== Fixing encoding corruption ===")
    print()
    print("[1/6] dashboard.js")
    fix_dashboard_js(base)
    print("[2/6] saas_dashboard.html")
    fix_saas_dashboard(base)
    print("[3/6] app.js")
    fix_app_js(base)
    print("[4/6] admin_users.js")
    fix_admin_users_js(base)
    print("[5/6] contract_eval.py")
    fix_contract_eval(base)
    print("[6/6] JSON data files")
    fix_json_files(base)
    print()
    print("=== Verifying JS syntax ===")
    verify_js_syntax(base)
    print()
    print("Done!")
