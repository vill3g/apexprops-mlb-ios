import os
import re
from html.parser import HTMLParser

VOID_TAGS = {
    'area', 'base', 'br', 'col', 'embed', 'hr', 'img', 'input',
    'link', 'meta', 'param', 'source', 'track', 'wbr'
}

class FullHTMLAuditor(HTMLParser):
    def __init__(self, filename):
        super().__init__()
        self.filename = filename
        self.stack = []
        self.errors = []
        self.ids = {}
        self.duplicate_ids = []
        self.deprecated_or_bad_attrs = []
        self.unclosed_at_end = []

    def handle_starttag(self, tag, attrs):
        line, col = self.getpos()
        t = tag.lower()
        
        # Check attributes
        attr_dict = {}
        for k, v in attrs:
            if k == 'id':
                if v:
                    if v in self.ids:
                        self.duplicate_ids.append((v, line, col, self.ids[v]))
                    else:
                        self.ids[v] = (line, col)
            attr_dict[k] = v

        if t not in VOID_TAGS:
            self.stack.append((t, line, col, attr_dict))

    def handle_endtag(self, tag):
        t = tag.lower()
        line, col = self.getpos()
        if t in VOID_TAGS:
            self.errors.append((f"Explicit closing tag </{t}> for void element", line, col))
            return
        
        if not self.stack:
            self.errors.append((f"Unexpected closing tag </{t}> with empty stack", line, col))
            return

        top, s_line, s_col, s_attrs = self.stack[-1]
        if top == t:
            self.stack.pop()
        else:
            # Look backwards in stack
            found_idx = -1
            for i in range(len(self.stack) - 1, -1, -1):
                if self.stack[i][0] == t:
                    found_idx = i
                    break
            if found_idx != -1:
                # unclosed elements in between
                unclosed = self.stack[found_idx + 1:]
                for ut, ul, uc, ua in unclosed:
                    u_id = f" id='{ua.get('id')}'" if 'id' in ua else ""
                    self.errors.append((
                        f"Unclosed <{ut}{u_id}> opened at line {ul}:{uc} (closed prematurely by </{t}> at {line}:{col})",
                        ul, uc
                    ))
                self.stack = self.stack[:found_idx]
            else:
                self.errors.append((
                    f"Spurious closing tag </{t}> at line {line}:{col} (top of stack is <{top}> opened at {s_line}:{s_col})",
                    line, col
                ))

def audit_html_file(filepath):
    print(f"\n==========================================")
    print(f"AUDITING: {filepath}")
    print(f"==========================================")
    if not os.path.exists(filepath):
        print("File does not exist!")
        return

    with open(filepath, 'r', encoding='utf-8', errors='replace') as f:
        content = f.read()

    auditor = FullHTMLAuditor(filepath)
    try:
        auditor.feed(content)
    except Exception as e:
        print(f"Parser crashed on {filepath}: {e}")

    print(f"Total lines parsed: {content.count(chr(10)) + 1}")
    print(f"Stack remaining at EOF: {len(auditor.stack)}")
    for t, l, c, a in auditor.stack:
        u_id = f" id='{a.get('id')}'" if 'id' in a else ""
        print(f"  Unclosed tag at EOF: <{t}{u_id}> opened at line {l}:{c}")

    print(f"\nTag / Nesting Errors ({len(auditor.errors)}):")
    for err, l, c in auditor.errors:
        print(f"  [L{l}:C{c}] {err}")

    print(f"\nDuplicate IDs ({len(auditor.duplicate_ids)}):")
    for id_val, l, c, orig in auditor.duplicate_ids:
        print(f"  Duplicate id='{id_val}' at L{l}:C{c} (first defined at L{orig[0]}:C{orig[1]})")

for path in [
    'static/saas_dashboard.html',
    'static/login.html',
    'static/trades.html',
    'static/admin_mobile.html',
    'static/index.html'
]:
    audit_html_file(path)
