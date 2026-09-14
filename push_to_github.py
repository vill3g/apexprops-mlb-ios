import os
import sys
import argparse
import subprocess
import urllib.request
import json
import base64

base_dir = os.path.abspath(os.path.dirname(__file__))

def get_token():
    token = os.environ.get("GITHUB_TOKEN") or os.environ.get("GH_TOKEN")
    if token:
        return token.strip()
    try:
        out = subprocess.check_output(["gh.exe", "auth", "token"]).decode().strip()
        if out:
            return out
    except Exception:
        pass
    token_file = os.path.join(base_dir, ".local_token")
    if os.path.exists(token_file):
        try:
            with open(token_file, "r", encoding="utf-8") as f:
                return f.read().strip()
        except Exception:
            pass
    return ""

def get_tracked_files():
    tracked = set()
    # 1. Try git ls-files if git CLI is available
    try:
        t = subprocess.check_output(["git", "ls-files"], cwd=base_dir).decode().splitlines()
        tracked.update(t)
    except Exception:
        pass

    # 2. Try dulwich if available in Python environment
    try:
        import dulwich.repo
        r = dulwich.repo.Repo(base_dir)
        index = r.open_index()
        tracked.update(path.decode('utf-8', errors='replace') for path in index)
    except Exception:
        pass

    # Include explicit core and newly added files
    core_files = [
        "package.json", "capacitor.config.json", "README.md", "static/index.html",
        "static/trades.html", "static/manifest.json", "backend/main.py",
        "backend/btc/__init__.py", "backend/btc/analyzer.py", "backend/btc/auto_executor.py",
        "backend/btc/data_fetcher.py", "backend/btc/dual_ml_engine.py", "backend/btc/indicators.py",
        "backend/btc/io_utils.py", "backend/btc/kalshi_client.py", "backend/btc/kalshi_trader.py",
        "backend/btc/loss_analyzer.py", "backend/btc/ml_engine.py", "backend/btc/paper_balance.py",
        "backend/btc/pattern_detector.py", "backend/btc/scalp_engine.py", "backend/btc/scalp_config.json",
        "backend/btc/trend_boxes.py", "backend/btc/backtest.py",
        "tests/test_trend_boxes.py", "tests/test_audit_findings.py", "tests/test_remediation.py",
        "tests/test_accuracy_improvements.py", "tests/test_analyzer_blend.py",
        "tests/test_force_trade_pass.py",
        "static/assets/logo_monogram.jpg", "static/assets/logo.png",
        "static/assets/logo_minimal.jpg", "static/assets/logo_shield.jpg"
    ]
    tracked.update(core_files)

    blacklist = {
        "backend/kalshi_credentials.json",
        "backend/btc/paper_balance.json",
        "backend/data/trades_history.json",
        "backend/data/trading_config.json.live"
    }

    clean = []
    for f in sorted(tracked):
        if f in blacklist:
            continue
        if f.endswith((".ipa", ".pyc", ".tmp", ".log", ".db")):
            continue
        if f.startswith(("dist/", ".git/", ".mypy_cache/", ".pytest_cache/", "node_modules/")):
            continue
        clean.append(f)
    return clean

def upload_files(repo: str, message: str = "Update iPad portrait single-row navigation & latest trading engine updates"):
    token = get_token()
    if not token:
        print("Warning: No GitHub token found via GITHUB_TOKEN, gh.exe, or .local_token. Requests will be unauthenticated.")

    headers = {
        "Accept": "application/vnd.github+json",
        "User-Agent": "ApexProps-Uploader"
    }
    if token:
        headers["Authorization"] = f"Bearer {token}"

    files_to_upload = get_tracked_files()

    print(f"Target repository: {repo}")
    print(f"Discovered {len(files_to_upload)} files to synchronize.")

    for rel_path in files_to_upload:
        full_path = os.path.join(base_dir, rel_path.replace('/', os.sep))
        if not os.path.exists(full_path) or os.path.isdir(full_path):
            continue

        with open(full_path, "rb") as f:
            content_bytes = f.read()

        b64_content = base64.b64encode(content_bytes).decode("utf-8")
        url = f"https://api.github.com/repos/{repo}/contents/{rel_path}"

        success = False
        for attempt in range(4):
            sha = None
            try:
                req = urllib.request.Request(url, headers=headers)
                with urllib.request.urlopen(req) as resp:
                    data = json.loads(resp.read().decode())
                    sha = data.get("sha")
                    remote_content = data.get("content", "").replace("\n", "").strip()
                    if remote_content == b64_content:
                        print(f"Skipping identical: {rel_path}")
                        success = True
                        break
            except urllib.error.HTTPError as e:
                if e.code != 404:
                    print(f"Check error on {rel_path}: {e}")

            payload = {
                "message": f"{message} ({rel_path})",
                "content": b64_content,
                "branch": "main"
            }
            if sha:
                payload["sha"] = sha

            req = urllib.request.Request(url, data=json.dumps(payload).encode("utf-8"), headers=headers, method="PUT")
            try:
                with urllib.request.urlopen(req) as resp:
                    print(f"Uploaded: {rel_path} -> HTTP {resp.status}")
                    success = True
                    import time
                    time.sleep(0.8)
                    break
            except Exception as e:
                print(f"Attempt {attempt + 1} failed for {rel_path}: {e}")
                import time
                time.sleep(1.5 * (attempt + 1))

        if not success:
            print(f"FAILED permanently to upload: {rel_path}")

    print("Upload complete!")

def main():
    parser = argparse.ArgumentParser(description="Push select project files to a GitHub repo via the Contents API.")
    parser.add_argument(
        "--repo",
        default=os.environ.get("GITHUB_TARGET_REPO", "vill3g/kalshi-ai-trader"),
        help="owner/repo, e.g. vill3g/kalshi-ai-trader. Required via --repo or GITHUB_TARGET_REPO env var; no default."
    )
    parser.add_argument(
        "--message",
        default="Update iPad portrait single-row navigation & latest trading engine updates",
        help="Commit message for updated files."
    )
    args = parser.parse_args()

    if not args.repo:
        raise SystemExit("Specify --repo owner/name or set GITHUB_TARGET_REPO. No default repo is assumed.")

    upload_files(args.repo, args.message)

if __name__ == "__main__":
    main()
