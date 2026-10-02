"""Web push (iOS 16.4+ home-screen app, Android, desktop browsers).

Subscriptions are stored per user in <DATA_DIR>/users/<id>/push_subs.json (a list, so a
user's phone and computer both get alerts). VAPID keys live in <DATA_DIR>/vapid.json.
"""
import json
import logging
import os
import threading

logger = logging.getLogger(__name__)

try:
    from pywebpush import WebPushException, webpush
except ImportError:          # pip install pywebpush
    webpush = None
    WebPushException = Exception

# Apple rejects push requests whose VAPID "sub" isn't a real https:// URL or mailto: address
VAPID_SUBJECT = os.environ.get("VAPID_SUBJECT", "https://moneyprinter.ngrok.app")
MAX_SUBS_PER_USER = 5
_lock = threading.Lock()


def _data_dir():
    from backend.database.models import DATA_DIR
    return os.path.abspath(DATA_DIR)


def _vapid_keys():
    try:
        with open(os.path.join(_data_dir(), "vapid.json"), "r") as f:
            return json.load(f)
    except (OSError, ValueError):
        return None


def vapid_public_key():
    keys = _vapid_keys()
    return keys.get("public_key") if keys else None


def _subs_path(user_id):
    return os.path.join(_data_dir(), "users", str(int(user_id)), "push_subs.json")


def _load_subs(user_id):
    subs = []
    try:
        with open(_subs_path(user_id), "r") as f:
            subs = json.load(f) or []
    except (OSError, ValueError):
        pass
    legacy = os.path.join(_data_dir(), "users", str(int(user_id)), "push_sub.json")
    if os.path.exists(legacy):         # older single-subscription file
        try:
            with open(legacy, "r") as f:
                old = json.load(f)
            if old and old.get("endpoint") not in {s.get("endpoint") for s in subs}:
                subs.append(old)
        except (OSError, ValueError):
            pass
    return [s for s in subs if isinstance(s, dict) and s.get("endpoint")]


def _save_subs(user_id, subs):
    path = _subs_path(user_id)
    os.makedirs(os.path.dirname(path), exist_ok=True)
    tmp = path + ".tmp"
    with open(tmp, "w") as f:
        json.dump(subs[-MAX_SUBS_PER_USER:], f)
    os.replace(tmp, path)


def save_subscription(user_id, sub: dict) -> bool:
    if not isinstance(sub, dict) or not str(sub.get("endpoint", "")).startswith("https://") \
            or not isinstance(sub.get("keys"), dict) or not sub["keys"].get("p256dh") or not sub["keys"].get("auth"):
        return False
    clean = {"endpoint": sub["endpoint"], "keys": {"p256dh": sub["keys"]["p256dh"], "auth": sub["keys"]["auth"]}}
    with _lock:
        subs = [s for s in _load_subs(user_id) if s.get("endpoint") != clean["endpoint"]]
        subs.append(clean)
        _save_subs(user_id, subs)
    return True


def has_subscription(user_id) -> bool:
    return bool(_load_subs(user_id))


def send_web_push(user_id: int, title: str, body: str, url: str = "/saas_dashboard.html") -> int:
    """Send to every device the user subscribed. Returns how many deliveries succeeded.
    Expired subscriptions (404/410) are removed."""
    if webpush is None:
        logger.warning("[WebPush] pywebpush is not installed; run: pip install pywebpush")
        return 0
    keys = _vapid_keys()
    subs = _load_subs(user_id)
    if not keys or not subs:
        return 0
    payload = json.dumps({"title": title, "body": body, "url": url})
    sent, dead = 0, set()
    for sub in subs:
        try:
            webpush(subscription_info=sub, data=payload, vapid_private_key=keys["private_key"],
                    vapid_claims={"sub": VAPID_SUBJECT}, ttl=3600, headers={"Urgency": "high"}, timeout=10)
            sent += 1
        except WebPushException as ex:
            status = getattr(getattr(ex, "response", None), "status_code", None)
            logger.warning(f"[WebPush] user {user_id}: delivery failed ({status}): {ex}")
            if status in (404, 410):
                dead.add(sub.get("endpoint"))
        except Exception as e:
            logger.warning(f"[WebPush] user {user_id}: {e}")
    if dead:
        with _lock:
            _save_subs(user_id, [s for s in _load_subs(user_id) if s.get("endpoint") not in dead])
            legacy = os.path.join(_data_dir(), "users", str(int(user_id)), "push_sub.json")
            try:
                os.remove(legacy)
            except OSError:
                pass
    return sent


def send_web_push_async(user_id: int, title: str, body: str, url: str = "/saas_dashboard.html") -> None:
    """Fire-and-forget, so a slow push service never delays trading or settlement."""
    threading.Thread(target=send_web_push, args=(user_id, title, body, url), daemon=True,
                     name=f"webpush-{user_id}").start()


def notify_trade_closed(user_id, trade: dict) -> None:
    """Called once when a trade goes from OPEN to closed. Sends 'Trade Won' for winning
    trades (paper and live) if the user has trade-result notifications on."""
    try:
        pnl = float(trade.get("pnl") or 0)
        if pnl <= 0:
            return
        # The user closed it themselves (Close / Close All): they already know, no alert
        if "MANUAL" in str(trade.get("exit_reason") or "").upper():
            return
        from backend.database.models import get_user_by_id
        user = get_user_by_id(int(user_id))
        if not user or not user.get("notify_trade_results", 1) or not has_subscription(user_id):
            return
        mode = str(trade.get("mode") or "PAPER").upper()
        side = str(trade.get("side") or "").upper()
        count = trade.get("count") or 0
        try:
            count = int(float(count)) if float(count).is_integer() else round(float(count), 2)
        except (TypeError, ValueError):
            pass
        how = str(trade.get("exit_reason") or "").split(" (")[0].replace("_", " ").title()
        title = f"Trade Won! +${pnl:,.2f} ({'LIVE' if mode == 'LIVE' else 'Paper'})"
        body = f"{side} x{count} on {trade.get('ticker', 'Kalshi')}" + (f" · {how}" if how else "")
        send_web_push_async(user_id, title, body)
    except Exception as e:
        logger.warning(f"[WebPush] notify_trade_closed failed: {e}")
