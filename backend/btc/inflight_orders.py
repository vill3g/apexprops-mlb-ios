"""Bot orders that are in flight, keyed by (user_id, ticker, side).

The worker's Kalshi position sync records positions it can't find in the database as
manual trades. Two things used to make it mislabel the bot's own orders:
  * the position shows up on Kalshi a moment before the bot writes its trade record;
  * an order whose HTTP response timed out may still have filled, and then the bot never
    writes a record at all.
The trade engine registers each LIVE order here before sending it, so the sync can skip
a position the bot is still recording and label a timed-out order's fill as the bot's.
Both the engine and the sync run inside the worker process, so memory is enough.
"""
import threading
import time

PENDING_TTL = 30.0       # order sent; the engine is about to write its record
AMBIGUOUS_TTL = 20 * 60  # response timed out; it may have filled (covers the whole market)

_lock = threading.Lock()
_orders = {}


def _key(user_id, ticker, side):
    return (int(user_id), str(ticker or ""), str(side or "").upper())


def mark_pending(user_id, ticker, side, labels: dict) -> None:
    with _lock:
        _orders[_key(user_id, ticker, side)] = {"ts": time.time(), "state": "pending", "labels": dict(labels or {})}


def mark_ambiguous(user_id, ticker, side) -> None:
    with _lock:
        entry = _orders.get(_key(user_id, ticker, side))
        if entry:
            entry.update(ts=time.time(), state="ambiguous")


def clear(user_id, ticker, side) -> None:
    with _lock:
        _orders.pop(_key(user_id, ticker, side), None)


def lookup(user_id, ticker, side):
    """The live entry for this position, or None. Expired entries are dropped."""
    now = time.time()
    with _lock:
        for k in [k for k, v in _orders.items()
                  if now - v["ts"] > (AMBIGUOUS_TTL if v["state"] == "ambiguous" else PENDING_TTL)]:
            _orders.pop(k, None)
        entry = _orders.get(_key(user_id, ticker, side))
        return dict(entry) if entry else None

def has_inflight(user_id, ticker):
    """Returns True if there is any pending or ambiguous order for this ticker."""
    now = time.time()
    uid = int(user_id)
    t = str(ticker or "")
    with _lock:
        for k in [k for k, v in _orders.items()
                  if now - v["ts"] > (AMBIGUOUS_TTL if v["state"] == "ambiguous" else PENDING_TTL)]:
            _orders.pop(k, None)
        for (u, tkr, s), v in _orders.items():
            if u == uid and tkr == t:
                return True
        return False
