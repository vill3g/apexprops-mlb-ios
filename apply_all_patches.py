import os
import subprocess

scripts = [
    "fix_chart.py",
    "fix_header.py",
    "fix_spacing.py",
    "fix_spacing2.py",
    "fix_ptr.py",
    "fix_profile.py",
    "fix_size_html.py",
    "fix_html_dropdown.py",
    "remove_dot.py",
    "remove_mode.py",
    "fix_bubble.py",
    "fix_mobile_layout.py",
    "fix_tv_logo.py",
    "fix_tv_logo2.py",
    "fix_tv_logo3.py",
    "fix_tv_logo_remove.py",
    "fix_tv_logo_clip.py",
    "revert_grid.py",
    "fix_gap.py",
    "fix_labels.py",
    "tighten.py",
    "add_notifications_ui.py",
    "add_push_btn.py",
    "fix_tooltips6.py",
    "fix_tooltips7.py",
    "fix_tooltips8.py",
    "fix_tooltips9.py",
    "fix_ui_text.py",
    "patch_saas_index.py",
    "patch_saas_heatmap.py",
    "cache_bust.py",
    "fix_saas_mobile.py",
    "move_support_btn.py",
    "fix_html.py",
    "fix_saas.py",
    "fix_move.py"
]

for s in scripts:
    print(f"Running {s}...")
    try:
        res = subprocess.run([r'C:\Users\Vill3\Desktop\kalshi-ai-trader\.venv\Scripts\python.exe', s], capture_output=True, text=True)
        if res.returncode != 0:
            print(f"  Failed: {res.stderr}")
        else:
            print(f"  Success.")
    except Exception as e:
        print(f"  Error: {e}")
