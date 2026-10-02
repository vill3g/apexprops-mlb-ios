import json
import logging
import os
import shutil
import sqlite3
import threading
import time

logger = logging.getLogger(__name__)

DB_PATH = os.environ.get("USERS_DB_PATH", os.path.join(os.path.dirname(__file__), '..', 'data', 'users.db'))
DATA_DIR = os.environ.get("USERS_DATA_DIR", os.path.join(os.path.dirname(__file__), '..', 'data'))

_user_locks = {}
_user_locks_lock = threading.Lock()

class CrossProcessLock:
    """Thread lock + OS file lock. The web server and the background worker are separate
    processes that read-modify-write the same per-user files and rows; a plain
    threading.Lock only protected against other threads in the same process."""

    def __init__(self, name: str, timeout: float = 60.0):
        self._thread_lock = threading.RLock()
        self._path = os.path.join(DATA_DIR, "locks", f"{name}.lock")
        self._timeout = timeout
        self._fh = None
        self._count = 0

    def _os_lock(self):
        os.makedirs(os.path.dirname(self._path), exist_ok=True)
        self._fh = open(self._path, "a+b")
        deadline = time.time() + self._timeout
        while True:
            try:
                if os.name == "nt":
                    import msvcrt
                    self._fh.seek(0)
                    msvcrt.locking(self._fh.fileno(), msvcrt.LK_NBLCK, 1)
                else:
                    import fcntl
                    fcntl.flock(self._fh.fileno(), fcntl.LOCK_EX | fcntl.LOCK_NB)
                return
            except OSError:
                if time.time() > deadline:
                    self._fh.close()
                    self._fh = None
                    raise TimeoutError(f"Timed out waiting for lock {self._path}")
                time.sleep(0.05)

    def _os_unlock(self):
        if self._fh is None:
            return
        try:
            if os.name == "nt":
                import msvcrt
                self._fh.seek(0)
                msvcrt.locking(self._fh.fileno(), msvcrt.LK_UNLCK, 1)
            else:
                import fcntl
                fcntl.flock(self._fh.fileno(), fcntl.LOCK_UN)
        finally:
            self._fh.close()
            self._fh = None

    def acquire(self, blocking: bool = True, timeout: float = -1) -> bool:
        if not self._thread_lock.acquire(blocking, timeout):
            return False
        if self._count == 0:
            try:
                self._os_lock()
            except Exception:
                self._thread_lock.release()
                raise
        self._count += 1
        return True

    def release(self):
        if self._count == 0:
            raise RuntimeError("release unlocked lock")
        self._count -= 1
        if self._count == 0:
            try:
                self._os_unlock()
            finally:
                self._thread_lock.release()
        else:
            self._thread_lock.release()

    def __enter__(self):
        self.acquire()
        return self

    def __exit__(self, *exc):
        self.release()
        return False


def get_user_lock(user_id):
    user_id = str(user_id)
    with _user_locks_lock:
        if user_id not in _user_locks:
            _user_locks[user_id] = CrossProcessLock(f"user_{user_id}")
        return _user_locks[user_id]

import threading

_thread_local = threading.local()

def _open_db_connection():
    conn = sqlite3.connect(DB_PATH, check_same_thread=False)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL;")
    conn.execute("PRAGMA synchronous=NORMAL;")
    _thread_local.connection = conn
    _thread_local.db_path = DB_PATH
    return conn

def get_db_connection():
    conn = getattr(_thread_local, 'connection', None)
    # Reopen if this thread has no connection, it was closed, or DB_PATH changed
    # (tests point DB_PATH at a temporary database).
    if conn is None or getattr(_thread_local, 'db_path', None) != DB_PATH:
        return _open_db_connection()
    try:
        conn.execute('SELECT 1')
    except sqlite3.ProgrammingError:
        return _open_db_connection()
    return conn

REQUIRED_COLUMNS = {
    "trade_size_dollars": "REAL DEFAULT 5.0",
    "paper_trade_size_dollars": "REAL DEFAULT 50.0",
    "stop_loss_pct": "REAL DEFAULT 50.0",
    "stop_loss_enabled": "BOOLEAN DEFAULT 1",
    "one_click_trade": "BOOLEAN DEFAULT 0",
    "auto_force_trade": "BOOLEAN DEFAULT 0",
    "target_asset": "TEXT DEFAULT 'BTC'",
    "trading_style": "TEXT DEFAULT 'AUTO'",
    "signal_source": "TEXT DEFAULT 'RL_DQN'",
    "take_profit_pct": "REAL DEFAULT 50.0",
    "take_profit_enabled": "BOOLEAN DEFAULT 1",
    "max_daily_trades": "INTEGER DEFAULT 10",
    "max_daily_risk": "REAL DEFAULT 50.0",
    "trailing_stop_enabled": "BOOLEAN DEFAULT 0",
    "trailing_stop_activation_pct": "REAL DEFAULT 35.0",
    "trailing_stop_distance_pct": "REAL DEFAULT 6.0",
    "second_entry_enabled": "BOOLEAN DEFAULT 0",
    "second_entry_max_ask": "REAL DEFAULT 0.75",
    "reentry_after_stop_loss": "BOOLEAN DEFAULT 0",
    "model_choice": "TEXT DEFAULT 'RL_DQN'",
    "train_window": "INTEGER DEFAULT 4000",
    "regularization_c": "REAL DEFAULT 0.5",
    "class_weight": "TEXT DEFAULT 'balanced'",
    "xgb_estimators": "INTEGER DEFAULT 300",
    "xgb_max_depth": "INTEGER DEFAULT 5",
    "xgb_learning_rate": "REAL DEFAULT 0.1",
    "ignore_pass_technical": "BOOLEAN DEFAULT 0",
    "one_shot_ai": "BOOLEAN DEFAULT 0",
    "profile_pic": "TEXT DEFAULT NULL",
    "notify_trade_results": "BOOLEAN DEFAULT 1",
    "notify_market_trends": "BOOLEAN DEFAULT 1",
    # id of the newest "What's New" update this user has seen (see backend/announcements.json)
    "last_seen_update": "TEXT DEFAULT NULL",
    # id of the update whose header bell the user hid early ("Hide bell")
    "dismissed_update": "TEXT DEFAULT NULL",
    # Edge guard: skip entries whose expected profit after fees is below min_edge_cents
    "edge_gate_enabled": "BOOLEAN DEFAULT 1",
    "min_edge_cents": "REAL DEFAULT 0.0",
    "use_kelly_criterion": "BOOLEAN DEFAULT 0",
}

def init_db():
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS trades (
                id TEXT PRIMARY KEY,
                user_id INTEGER NOT NULL,
                ticker TEXT,
                side TEXT,
                entry_price REAL,
                exit_price REAL,
                count INTEGER DEFAULT 0,
                pnl REAL DEFAULT 0.0,
                status TEXT DEFAULT 'OPEN',
                mode TEXT DEFAULT 'PAPER',
                reason TEXT,
                exit_reason TEXT,
                trading_style TEXT,
                signal_source TEXT,
                timestamp REAL,
                settled_at REAL,
                ml_reasoning TEXT,
                catalysts TEXT,
                raw_json TEXT,
                min_seen_bid REAL,
                FOREIGN KEY (user_id) REFERENCES users(id)
            )
        ''')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_trades_user_status ON trades(user_id, status)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_trades_user_mode ON trades(user_id, mode)')

        cursor.executescript('''
            

CREATE TABLE IF NOT EXISTS user_profiles (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    profile_name TEXT NOT NULL,
    settings_json TEXT NOT NULL,
    created_at TEXT
);

CREATE TABLE IF NOT EXISTS support_tickets (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER,
    username TEXT,
    issue_text TEXT,
    status TEXT DEFAULT 'OPEN',
    bot_recommendation TEXT,
    created_at TEXT
);

CREATE TABLE IF NOT EXISTS users (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                username TEXT UNIQUE NOT NULL,
                password_hash TEXT NOT NULL,
                kalshi_key_id TEXT,
                kalshi_priv_key_encrypted TEXT,
                is_active BOOLEAN DEFAULT 1,
                role TEXT DEFAULT 'user',
                trading_mode TEXT DEFAULT 'PAPER',
                paper_balance REAL DEFAULT 500.0,
                ai_enabled BOOLEAN DEFAULT 1,
                trade_size_pct REAL DEFAULT 20.0,
                stop_loss_pct REAL DEFAULT 50.0,
                one_click_trade BOOLEAN DEFAULT 0
            )
        ''')
        conn.commit()

        # Schema auto-migration: check for missing columns and alter table
        cursor.execute("PRAGMA table_info(users)")
        existing_cols = {row[1] for row in cursor.fetchall()}
        for col_name, col_def in REQUIRED_COLUMNS.items():
            if col_name not in existing_cols:
                try:
                    cursor.execute(f"ALTER TABLE users ADD COLUMN {col_name} {col_def}")
                    conn.commit()
                except sqlite3.OperationalError as e:
                    logger.warning(f"Failed to add column {col_name}: {e}")

        # Trades schema auto-migration
        cursor.execute("PRAGMA table_info(trades)")
        existing_trade_cols = {row[1] for row in cursor.fetchall()}
        if "min_seen_bid" not in existing_trade_cols:
            try:
                cursor.execute("ALTER TABLE trades ADD COLUMN min_seen_bid REAL")
                conn.commit()
            except sqlite3.OperationalError as e:
                logger.warning(f"Failed to add min_seen_bid to trades: {e}")
        
        # Ensure performance indexes exist (idempotent with IF NOT EXISTS)
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_users_is_active ON users(is_active)")
        cursor.execute("CREATE INDEX IF NOT EXISTS idx_users_username ON users(username)")
        conn.commit()
        _limit_admins_to_owner_once(cursor)
        conn.commit()
        _fix_bot_trades_labeled_manual_once(cursor)
        conn.commit()
    finally:
        conn.close()


# ── Manual vs. bot trades ───────────────────────────────────────────────────────────
# A trade is "manual" only if the user OPENED it by hand (trade buttons, owner 1-click,
# or a position found on their Kalshi account that the bot didn't place). How it was
# CLOSED (MANUAL_CLOSE, stop-loss...) never makes an auto trade manual.
_BOT_REASON_MARKERS = ("AI_COPY", "AI_SIGNAL", "FORCE_", "SECOND_ENTRY", "RECONCIL", "SCALPER", "RL_")
_EXIT_REASON_PREFIXES = ("MANUAL_CLOSE", "SETTLEMENT", "STOP_LOSS", "TAKE_PROFIT", "TRAILING_STOP")


def _reason_is_bot(reason) -> bool:
    r = str(reason or "").upper()
    return any(m in r for m in _BOT_REASON_MARKERS)


def is_manual_entry(trade) -> bool:
    if not isinstance(trade, dict):
        return False
    reason = str(trade.get("reason") or "").upper().strip()
    if trade.get("is_auto") is True or trade.get("bot_recovered") or _reason_is_bot(reason):
        return False
    if reason.startswith(_EXIT_REASON_PREFIXES):
        return False  # legacy record with its exit reason stored in 'reason'
    if reason == "MANUAL" or reason.startswith("MANUAL_") or trade.get("manual_sync"):
        return True
    if trade.get("is_manual") is True or str(trade.get("trade_source") or "").upper() == "MANUAL":
        return True
    return (str(trade.get("trading_style") or "").upper() == "MANUAL"
            or str(trade.get("signal_source") or "").upper() == "MANUAL")


def bot_style_from_reason(reason):
    """'AI_COPY (SNIPER)' -> 'SNIPER'"""
    import re
    m = re.search(r"\(([A-Z_]+)\)", str(reason or "").upper())
    return m.group(1) if m else None


def _fix_bot_trades_labeled_manual_once(cursor):
    """One-time repair (Sep 2026): some bot trades were saved with trading_style /
    signal_source 'MANUAL', so they showed as manual trades. Restore the style from
    the trade's reason (e.g. 'AI_COPY (SNIPER)'); the unknown source is cleared so the
    app falls back to the user's signal source. Only labels change, never P&L."""
    key = "bot_trades_manual_labels_fixed_v1"
    try:
        cursor.execute("CREATE TABLE IF NOT EXISTS app_meta (key TEXT PRIMARY KEY, value TEXT)")
        cursor.execute("SELECT value FROM app_meta WHERE key = ?", (key,))
        if cursor.fetchone():
            return
        cursor.execute("SELECT id, raw_json FROM trades WHERE UPPER(COALESCE(trading_style,'')) = 'MANUAL' "
                       "OR UPPER(COALESCE(signal_source,'')) = 'MANUAL'")
        fixed = 0
        for trade_id, raw in cursor.fetchall():
            try:
                t = json.loads(raw or "{}")
            except (TypeError, ValueError):
                continue
            if not _reason_is_bot(t.get("reason")):
                continue
            style = bot_style_from_reason(t.get("reason")) or "AUTO"
            t["trading_style"] = style
            t.pop("signal_source", None)
            t["is_manual"] = False
            cursor.execute("UPDATE trades SET trading_style = ?, signal_source = NULL, raw_json = ? WHERE id = ?",
                           (style, json.dumps(t), trade_id))
            fixed += 1
        cursor.execute("INSERT INTO app_meta (key, value) VALUES (?, ?)", (key, str(fixed)))
        if fixed:
            logger.warning(f"[Trades] Relabeled {fixed} bot trade(s) that had been saved as MANUAL.")
    except sqlite3.Error as e:
        logger.warning(f"[Trades] Manual-label repair skipped: {e}")


# The owner account: the only account allowed to manage roles, LIVE trading, deletions
# and resets from the admin panel. Override with SAAS_OWNER_USERNAME in .env.
OWNER_USERNAME = os.environ.get("SAAS_OWNER_USERNAME", "Vill3.G").strip()


def is_owner_account(user) -> bool:
    return bool(user) and str(user.get("username", "")).lower() == OWNER_USERNAME.lower()


def _limit_admins_to_owner_once(cursor):
    """One-time cleanup (Sep 2026): every account had been given the admin role.
    Demote everyone except the owner. Runs once; admins promoted later are kept."""
    try:
        cursor.execute("CREATE TABLE IF NOT EXISTS app_meta (key TEXT PRIMARY KEY, value TEXT)")
        cursor.execute("SELECT value FROM app_meta WHERE key = 'admins_limited_to_owner_v1'")
        if cursor.fetchone():
            return
        cursor.execute("SELECT id FROM users WHERE LOWER(username) = LOWER(?)", (OWNER_USERNAME,))
        if not cursor.fetchone():
            return  # owner account not created yet: don't lock anyone out
        cursor.execute("UPDATE users SET role = 'admin' WHERE LOWER(username) = LOWER(?)", (OWNER_USERNAME,))
        cursor.execute("UPDATE users SET role = 'user' WHERE role = 'admin' AND LOWER(username) != LOWER(?)", (OWNER_USERNAME,))
        demoted = cursor.rowcount
        cursor.execute("INSERT INTO app_meta (key, value) VALUES ('admins_limited_to_owner_v1', ?)",
                       (str(int(time.time())),))
        logger.warning(f"[Security] Admin role limited to owner '{OWNER_USERNAME}'; demoted {demoted} other account(s).")
    except sqlite3.Error as e:
        logger.warning(f"[Security] Admin cleanup skipped: {e}")

def update_user_ai_enabled(user_id: int, enabled: bool):
    conn = get_db_connection()
    try:
        c = conn.cursor()
        c.execute("UPDATE users SET ai_enabled = ? WHERE id = ?", (1 if enabled else 0, user_id))
        conn.commit()
    finally:
        conn.close()
    try:
        from backend.btc.auto_executor import invalidate_saas_users_cache
        invalidate_saas_users_cache(user_id)
    except Exception as e:
        logger.warning(f"Failed to invalidate cache: {e}")

def update_user_trading_mode(user_id: int, mode: str):
    conn = get_db_connection()
    try:
        c = conn.cursor()
        c.execute("UPDATE users SET trading_mode = ? WHERE id = ?", (mode, user_id))
        conn.commit()
    finally:
        conn.close()

    try:
        from backend.btc.auto_executor.saas_broadcaster import \
            invalidate_saas_users_cache
        invalidate_saas_users_cache(user_id)
    except Exception as e:
        logger.warning(f"Failed to invalidate cache: {e}")

    # Synchronize user's isolated trading_config.json
    try:
        user_cfg_file = os.path.join(DATA_DIR, 'users', str(user_id), 'trading_config.json')
        if os.path.exists(user_cfg_file):
            with get_user_lock(user_id):
                with open(user_cfg_file, 'r', encoding='utf-8') as f:
                    cfg_data = json.load(f)
                if isinstance(cfg_data, dict):
                    cfg_data['mode'] = mode
                    if 'ai_settings' in cfg_data and isinstance(cfg_data['ai_settings'], dict):
                        cfg_data['ai_settings']['dryRun'] = (mode.upper() == 'PAPER')
                    from backend.btc.io_utils import atomic_json_write
                    atomic_json_write(user_cfg_file, cfg_data)
    except (json.JSONDecodeError, FileNotFoundError, OSError) as e:
        logger.warning(f"Failed to update user config: {e}")

    # Synchronize in-memory executor if one exists
    try:
        from backend.core.registry import _guest_executors
        key = f"GUEST:{user_id}:BTC"
        if key in _guest_executors:
            ex = _guest_executors[key]
            ex.mode = mode
            if hasattr(ex, "ai_settings") and isinstance(ex.ai_settings, dict):
                ex.ai_settings["dryRun"] = (mode.upper() == "PAPER")
            ex._save_config()
    except Exception as e:
        logger.warning(f"Failed to sync in-memory executor: {e}")

def update_user_paper_balance(user_id: int, new_balance: float):
    conn = get_db_connection()
    try:
        c = conn.cursor()
        c.execute("UPDATE users SET paper_balance = ? WHERE id = ?", (new_balance, user_id))
        conn.commit()
    finally:
        conn.close()

    users_dir = os.path.join(DATA_DIR, 'users')
    if not os.path.exists(users_dir):
        os.makedirs(users_dir, exist_ok=True)

def deduct_user_paper_balance(user_id: int, cost: float) -> bool:
    """Atomically deduct cost from user's paper balance if sufficient funds exist."""
    conn = get_db_connection()
    try:
        c = conn.cursor()
        c.execute("UPDATE users SET paper_balance = paper_balance - ? WHERE id = ? AND paper_balance >= ?", (cost, user_id, cost))
        conn.commit()
        return c.rowcount > 0
    finally:
        conn.close()

def credit_user_paper_balance(user_id: int, amount: float) -> None:
    """Atomically credit settlement or profit to user's paper balance."""
    conn = get_db_connection()
    try:
        c = conn.cursor()
        c.execute("UPDATE users SET paper_balance = paper_balance + ? WHERE id = ?", (amount, user_id))
        conn.commit()
    finally:
        conn.close()

def get_user_by_username(username):
    conn = get_db_connection()
    
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE username = ?", (username,))
        row = cursor.fetchone()
        return dict(row) if row else None
    finally:
        conn.close()

def get_user_by_id(user_id):
    conn = get_db_connection()
    
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,))
        row = cursor.fetchone()
        return dict(row) if row else None
    finally:
        conn.close()

def create_user(username, password_hash):
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("INSERT INTO users (username, password_hash) VALUES (?, ?)", (username, password_hash))
        user_id = cursor.lastrowid
        conn.commit()
        
        user_dir = os.path.join(DATA_DIR, 'users', str(user_id))
        os.makedirs(user_dir, exist_ok=True)
        with open(os.path.join(user_dir, 'trades_history.json'), 'w') as f:
            json.dump([], f)
            
        return user_id
    except sqlite3.IntegrityError:
        return None
    finally:
        conn.close()

def update_user_kalshi_keys(user_id, key_id, priv_key_encrypted):
    conn = get_db_connection()
    try:
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET kalshi_key_id = ?, kalshi_priv_key_encrypted = ? WHERE id = ?", 
                      (key_id, priv_key_encrypted, user_id))
        conn.commit()
    finally:
        conn.close()

def get_all_active_users():
    conn = get_db_connection()
    
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE is_active = 1")
        rows = cursor.fetchall()
        return [
            dict(row) for row in rows
            if not str(row['username']).lower().startswith(('reset_test_', 'pytest_', 'test_se_'))
        ]
    finally:
        conn.close()

def get_all_users():
    conn = get_db_connection()
    
    try:
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users ORDER BY id ASC")
        rows = cursor.fetchall()
        return [dict(row) for row in rows]
    finally:
        conn.close()

def update_user_edge_gate(user_id: int, enabled=None, min_edge_cents=None) -> None:
    """Save a user's edge-guard settings. None leaves a value unchanged."""
    from backend.btc.fees import MIN_EDGE_CENTS_LIMIT
    sets, vals = [], []
    if enabled is not None:
        sets.append("edge_gate_enabled = ?"); vals.append(1 if enabled else 0)
    if min_edge_cents is not None:
        sets.append("min_edge_cents = ?"); vals.append(round(min(max(float(min_edge_cents), 0.0), MIN_EDGE_CENTS_LIMIT), 1))
    if not sets:
        return
    conn = get_db_connection()
    conn.execute(f"UPDATE users SET {', '.join(sets)} WHERE id = ?", vals + [int(user_id)])
    conn.commit()


def admin_update_user(user_id: int, updates: dict) -> bool:
    """Update user fields directly from admin control panel."""
    allowed_cols = {
        "is_active", "role", "trading_mode", "paper_balance", "ai_enabled",
        "trade_size_dollars", "paper_trade_size_dollars", "stop_loss_pct", "stop_loss_enabled", "take_profit_pct", "take_profit_enabled",
        "trading_style", "signal_source", "auto_force_trade", "one_click_trade",
        "trailing_stop_enabled", "trailing_stop_activation_pct", "trailing_stop_distance_pct",
        "second_entry_enabled", "second_entry_max_ask", "reentry_after_stop_loss", "ignore_pass_technical",
        "one_shot_ai", "max_daily_trades", "max_daily_risk",
        "model_choice", "train_window", "regularization_c", "class_weight",
        "edge_gate_enabled", "min_edge_cents", "use_kelly_criterion"
    }
    filtered = {k: v for k, v in updates.items() if k in allowed_cols}
    if not filtered:
        return False
    set_clauses = [f"{col} = ?" for col in filtered.keys()]
    values = list(filtered.values()) + [user_id]
    conn = get_db_connection()
    try:
        c = conn.cursor()
        c.execute(f"UPDATE users SET {', '.join(set_clauses)} WHERE id = ?", values)
        conn.commit()
    finally:
        conn.close()
    if c.rowcount > 0:
        try:
            from backend.btc.auto_executor import invalidate_saas_users_cache
            invalidate_saas_users_cache(user_id)
        except Exception as e:
            logger.warning(f"Failed to invalidate cache: {e}")
    return c.rowcount > 0

def reset_user_paper_balance_and_pnl(user_id: int, balance: float = 500.0, archive_all: bool = False) -> bool:
    """
    Resets a user's paper trading balance to `balance` (default 500.0)
    AND resets their paper trading PnL by archiving trades.
    If archive_all is True, all trades (including historical test live trades) are archived.
    If archive_all is False, only paper trades are archived and live trades are preserved.
    """
    conn = get_db_connection()
    updated = False
    try:
        c = conn.cursor()
        c.execute("UPDATE users SET paper_balance = ? WHERE id = ?", (float(balance), user_id))
        updated = c.rowcount > 0
        # CRITICAL: Delete PAPER trades to reset PnL. Never delete LIVE trades.
        c.execute("DELETE FROM trades WHERE user_id = ? AND mode = 'PAPER'", (user_id,))
        conn.commit()
    finally:
        conn.close()

    if not updated:
        return False

    # Reset paper trades & PnL in user directory
    user_dir = os.path.join(DATA_DIR, "users", str(user_id))
    hist_path = os.path.join(user_dir, "trades_history.json")
    archive_path = os.path.join(user_dir, "trades_history_archive.json")

    with get_user_lock(user_id):
        if os.path.exists(hist_path):
            try:
                with open(hist_path, "r", encoding="utf-8") as f:
                    trades = json.load(f)
                if not isinstance(trades, list):
                    trades = []
            except (json.JSONDecodeError, FileNotFoundError, OSError) as e:
                logger.warning(f"Failed to read trades history: {e}")
                trades = []

            trades_to_archive = [t for t in trades if t.get("mode", "PAPER") == "PAPER"]
            trades_to_keep = [t for t in trades if t.get("mode") == "LIVE"]

            if trades_to_archive:
                os.makedirs(user_dir, exist_ok=True)
                existing_archive = []
                if os.path.exists(archive_path):
                    try:
                        with open(archive_path, "r", encoding="utf-8") as f:
                            existing_archive = json.load(f)
                        if not isinstance(existing_archive, list):
                            existing_archive = []
                    except (json.JSONDecodeError, FileNotFoundError, OSError) as e:
                        logger.warning(f"Failed to read existing archive: {e}")
                        existing_archive = []

                reset_ts = time.time()
                for pt in trades_to_archive:
                    pt["archived_at_reset"] = reset_ts

                existing_archive.extend(trades_to_archive)
                from backend.btc.io_utils import atomic_json_write
                atomic_json_write(archive_path, existing_archive)

                # Write back remaining trades
                atomic_json_write(hist_path, trades_to_keep)
            else:
                from backend.btc.io_utils import atomic_json_write
                atomic_json_write(hist_path, trades_to_keep)

    # Sync guest balance cache if present
    guest_bal_path = os.path.join(DATA_DIR, "guests", str(user_id), "paper_balance.json")
    if os.path.exists(os.path.dirname(guest_bal_path)):
        try:
            from backend.btc.io_utils import atomic_json_write
            atomic_json_write(guest_bal_path, {"balance": float(balance)})
        except (FileNotFoundError, OSError) as e:
            logger.warning(f"Failed to sync guest balance cache: {e}")

    # Evict in-memory guest executor so it reloads clean history & balance
    try:
        from backend.core.registry import _evict_guest_executor
        _evict_guest_executor(str(user_id))
    except Exception as e:
        logger.warning(f"Failed to evict guest executor: {e}")

    return True

def reset_all_users_paper_balance_and_pnl(balance: float = 500.0, archive_all: bool = True) -> dict:
    """
    Resets paper balance to `balance` (default 500.0) and resets Net PnL to $0.00
    for all registered users. Safely archives historical trades into trades_history_archive.json.
    """
    users = get_all_users()
    results = {}
    for u in users:
        uid = u["id"]
        # Skip transient internal test accounts
        if str(u["username"]).lower().startswith(('reset_test_', 'pytest_', 'test_se_')):
            continue
        results[uid] = reset_user_paper_balance_and_pnl(uid, balance=balance, archive_all=archive_all)
    return results

def admin_reset_paper_balance(user_id: int, balance: float = 500.0) -> bool:
    """Reset a user's paper trading balance and paper PnL."""
    return reset_user_paper_balance_and_pnl(user_id, balance)

def delete_user_by_id(user_id: int) -> bool:
    """Delete a user account, their user directory, and evict in-memory executors."""
    conn = get_db_connection()
    try:
        c = conn.cursor()
        c.execute("DELETE FROM users WHERE id = ?", (user_id,))
        deleted = c.rowcount > 0
        if deleted:
            # Remove the account's trade records too (otherwise they linger as orphans)
            c.execute("DELETE FROM trades WHERE user_id = ?", (user_id,))
        conn.commit()
    finally:
        conn.close()

    if deleted:
        user_dir = os.path.join(DATA_DIR, 'users', str(user_id))
        if os.path.exists(user_dir):
            try:
                shutil.rmtree(user_dir, ignore_errors=True)
            except OSError as e:
                logger.warning(f"Failed to delete user directory: {e}")
        try:
            from backend.core.registry import _evict_guest_executor
            _evict_guest_executor(str(user_id))
        except Exception as e:
            logger.warning(f"Failed to evict guest executor: {e}")

    return deleted

def update_user_config(
    user_id: int, 
    trade_size_dollars: float, 
    paper_trade_size_dollars: float,
    stop_loss_pct: float, 
    stop_loss_enabled: bool = True, 
    one_click_trade: bool = False, 
    auto_force_trade: bool = False, 
    target_asset: str = "BTC",
    trading_style: str = "AUTO", 
    signal_source: str = "RL_DQN", 
    take_profit_pct: float = 50.0,
    take_profit_enabled: bool = True, 
    max_daily_trades: int = 10, 
    max_daily_risk: float = 50.0, 
    trailing_stop_enabled: bool = False, 
    trailing_stop_activation_pct: float = 35.0, 
    trailing_stop_distance_pct: float = 6.0, 
    second_entry_enabled: bool = False,
    second_entry_max_ask: float = 0.75,
    reentry_after_stop_loss: bool = False,
    model_choice: str = "RL_DQN", 
    train_window: int = 4000, 
    regularization_c: float = 0.5, 
    class_weight: str = "balanced", 
    xgb_estimators: int = 300, 
    xgb_max_depth: int = 5, 
    xgb_learning_rate: float = 0.1, 
    ignore_pass_technical: bool = False, 
    one_shot_ai: bool = False,
    notify_trade_results: bool = True,
    notify_market_trends: bool = True,
    use_kelly_criterion: bool = False
):
    conn = get_db_connection()
    try:
        c = conn.cursor()
        c.execute('''
            UPDATE users 
            SET trade_size_dollars = ?, paper_trade_size_dollars = ?, stop_loss_pct = ?, stop_loss_enabled = ?, one_click_trade = ?, auto_force_trade = ?, 
                target_asset = ?, trading_style = ?, signal_source = ?, take_profit_pct = ?, max_daily_trades = ?, take_profit_enabled = ?, 
                max_daily_risk = ?, trailing_stop_enabled = ?, trailing_stop_activation_pct = ?, 
                trailing_stop_distance_pct = ?, second_entry_enabled = ?, second_entry_max_ask = ?, reentry_after_stop_loss = ?,
                model_choice = ?, train_window = ?, regularization_c = ?, class_weight = ?, 
                xgb_estimators = ?, xgb_max_depth = ?, xgb_learning_rate = ?, 
                ignore_pass_technical = ?, one_shot_ai = ?, notify_trade_results = ?, notify_market_trends = ?,
                use_kelly_criterion = ?
            WHERE id = ?
        ''', (
            trade_size_dollars, paper_trade_size_dollars, stop_loss_pct, 1 if stop_loss_enabled else 0, 1 if one_click_trade else 0, 1 if auto_force_trade else 0, 
            target_asset, trading_style, signal_source, take_profit_pct, max_daily_trades, 1 if take_profit_enabled else 0, max_daily_risk, 
            1 if trailing_stop_enabled else 0, trailing_stop_activation_pct, trailing_stop_distance_pct, 
            1 if second_entry_enabled else 0, second_entry_max_ask, 1 if reentry_after_stop_loss else 0,
            model_choice, train_window, regularization_c, class_weight, 
            xgb_estimators, xgb_max_depth, xgb_learning_rate, 
            1 if ignore_pass_technical else 0, 1 if one_shot_ai else 0,  1 if notify_trade_results else 0, 1 if notify_market_trends else 0,
            1 if use_kelly_criterion else 0, user_id
        ))
        conn.commit()
    finally:
        conn.close()
    try:
        from backend.btc.auto_executor import invalidate_saas_users_cache
        invalidate_saas_users_cache(user_id)
    except Exception as e:
        logger.warning(f"Failed to invalidate cache: {e}")


def copy_user_settings(source_user_id: int, target_user_id: int) -> dict:
    """
    Copies all trading strategy, AI model, and execution risk settings from
    source_user_id to target_user_id, STRICTLY PRESERVING target user's trade size
    (trade_size_dollars and trade_size_pct remain untouched).
    """
    if int(source_user_id) == int(target_user_id):
        raise ValueError("Cannot copy settings from your own account.")

    source_user = get_user_by_id(source_user_id)
    if not source_user:
        raise ValueError(f"Source trader #{source_user_id} not found.")

    target_user = get_user_by_id(target_user_id)
    if not target_user:
        raise ValueError(f"Target trader #{target_user_id} not found.")

    # Strategy, indicators, risk limits, and AI model hyperparameters to copy
    # NOTE: trade_size_dollars and trade_size_pct are STRICTLY EXCLUDED to preserve caller's capital allocation
    copy_fields = {
        "stop_loss_pct": float(source_user.get("stop_loss_pct", 50.0)),
        "stop_loss_enabled": int(bool(source_user.get("stop_loss_enabled", 1))),
        "take_profit_pct": float(source_user.get("take_profit_pct", 50.0)),
        "take_profit_enabled": int(bool(source_user.get("take_profit_enabled", 1))),
        "one_click_trade": int(bool(source_user.get("one_click_trade", 0))),
        "auto_force_trade": int(bool(source_user.get("auto_force_trade", 0))),
        "trading_style": str(source_user.get("trading_style", "AUTO")),
        "signal_source": str(source_user.get("signal_source", "RL_DQN")),
        "max_daily_trades": int(source_user.get("max_daily_trades", 10)),
        "max_daily_risk": float(source_user.get("max_daily_risk", 50.0)),
        "trailing_stop_enabled": int(bool(source_user.get("trailing_stop_enabled", 0))),
        "trailing_stop_activation_pct": float(source_user.get("trailing_stop_activation_pct", 35.0)),
        "trailing_stop_distance_pct": float(source_user.get("trailing_stop_distance_pct", 6.0)),
        "second_entry_enabled": int(bool(source_user.get("second_entry_enabled", 0))),
        "second_entry_max_ask": float(source_user.get("second_entry_max_ask", 0.75)),
        "reentry_after_stop_loss": int(bool(source_user.get("reentry_after_stop_loss", 0))),
        "model_choice": str(source_user.get("model_choice", "RL_DQN")),
        "train_window": int(source_user.get("train_window", 4000)),
        "regularization_c": float(source_user.get("regularization_c", 0.5)),
        "class_weight": str(source_user.get("class_weight", "balanced")),
        "xgb_estimators": int(source_user.get("xgb_estimators", 300)),
        "xgb_max_depth": int(source_user.get("xgb_max_depth", 5)),
        "xgb_learning_rate": float(source_user.get("xgb_learning_rate", 0.1)),
        "ignore_pass_technical": int(bool(source_user.get("ignore_pass_technical", 0))),
        "one_shot_ai": int(bool(source_user.get("one_shot_ai", 0))),
        "edge_gate_enabled": int(bool(source_user.get("edge_gate_enabled", 1))),
        "min_edge_cents": float(source_user.get("min_edge_cents", 0.0) or 0.0),
        "use_kelly_criterion": int(bool(source_user.get("use_kelly_criterion", 0)))
    }

    set_clauses = [f"{col} = ?" for col in copy_fields.keys()]
    values = list(copy_fields.values()) + [int(target_user_id)]

    conn = get_db_connection()
    try:
        c = conn.cursor()
        c.execute(f"UPDATE users SET {', '.join(set_clauses)} WHERE id = ?", values)
        conn.commit()
    finally:
        pass

    # Evict executor cache so new settings load cleanly into memory
    try:
        from backend.core.registry import _evict_guest_executor
        _evict_guest_executor(str(target_user_id))
    except Exception as e:
        logger.warning(f"Failed to evict guest executor: {e}")

    # Update in-memory executor if active
    try:
        from backend.core.registry import get_auto_executor
        ex = get_auto_executor("BTC", guest_id=int(target_user_id))
        new_settings = ex.ai_settings.copy() if hasattr(ex, 'ai_settings') else {}
        for k, v in copy_fields.items():
            new_settings[k] = v
        ex.set_ai_settings(new_settings)
        ex.set_risk_limits(
            max_daily_risk=copy_fields["max_daily_risk"],
            max_daily_trades=copy_fields["max_daily_trades"]
        )
    except Exception as e:
        logger.warning(f"Failed to update in-memory executor: {e}")

    return {
        "source_user_id": int(source_user_id),
        "source_username": source_user.get("username"),
        "target_user_id": int(target_user_id),
        "target_username": target_user.get("username"),
        "copied_settings": copy_fields,
        "preserved_trade_size_dollars": target_user.get("trade_size_dollars", 5.0),
        "preserved_trade_size_pct": target_user.get("trade_size_pct", 20.0)
    }


def enrich_trade_metadata(trade: dict, default_style: str = "AUTO", default_source: str = "RL_DQN", default_model: str = "RL_DQN") -> dict:
    """Enriches a raw trade record with resolved trading_style, signal_source,
    model_choice, and tactical booleans (is_manual, is_profit_reentry, is_reversal).
    Mutates and returns the trade dict for convenience.
    """
    if not isinstance(trade, dict):
        return trade

    reason = str(trade.get("reason", "") or "").upper()

    is_manual = is_manual_entry(trade)
    trade["is_manual"] = is_manual
    if not is_manual:
        # older bot trades were sometimes saved with style/source "MANUAL"
        if str(trade.get("trading_style") or "").upper() == "MANUAL":
            trade["trading_style"] = bot_style_from_reason(reason)
        if str(trade.get("signal_source") or "").upper() == "MANUAL":
            trade["signal_source"] = None

    # 1. Trading Style
    style = trade.get("trading_style")
    if not style:
        if is_manual:
            style = "MANUAL"
        elif "MOMENTUM" in reason:
            style = "MOMENTUM_SURFER"
        elif "SNIPER" in reason:
            style = "SNIPER"
        elif "AMBUSH" in reason:
            style = "AMBUSH"
        elif "CHOP" in reason:
            style = "CHOP"
        elif "THIRD_ENTRY" in reason or trade.get("is_third_entry") or trade.get("reentry_index") == 3:
            style = "THIRD_ENTRY"
        elif "SECOND_ENTRY" in reason or trade.get("is_second_entry") or trade.get("reentry_index") == 2:
            style = "SECOND_ENTRY"
        elif "AUTO_FORCE" in reason or "FORCE" in reason:
            style = "FORCE"
        else:
            style = default_style or "AUTO"
    trade["trading_style"] = str(style)

    # 2. Signal Source
    source = trade.get("signal_source")
    if not source:
        if is_manual:
            source = "MANUAL"
        elif "TECHNICAL" in reason:
            source = "TECHNICAL_ONLY"
        elif "SWARM" in reason or "ENSEMBLE" in reason:
            source = "SWARM"
        elif "RL_DQN" in reason or "DQN" in reason:
            source = "RL_DQN"
        elif "AI_SIGNAL" in reason or "AI_COPY" in reason:
            source = default_source or "BLEND"
        else:
            source = default_source or "BLEND"
    trade["signal_source"] = str(source)

    # 3. Model Choice
    if not trade.get("model_choice"):
        trade["model_choice"] = default_model or "RL_DQN"

    # 4. Tactical booleans
    trade["is_profit_reentry"] = bool(trade.get("is_profit_reentry") or trade.get("is_second_entry") or trade.get("is_third_entry") or "SECOND_ENTRY" in reason or "THIRD_ENTRY" in reason)
    trade["is_third_entry"] = bool(trade.get("is_third_entry") or trade.get("reentry_index") == 3 or "THIRD_ENTRY" in reason)
    trade["is_reversal"] = bool(trade.get("is_reversal") or trade.get("is_reverse") or "REVERSAL" in reason)

    # 5. AI Edge & Conviction Probability
    if trade.get("probability_percent") is None:
        snap = trade.get("market_snapshot")
        if isinstance(snap, str):   # stored as a JSON string by the trade engine
            try:
                snap = json.loads(snap)
            except (TypeError, ValueError):
                snap = None
        snap = snap if isinstance(snap, dict) else {}
        if trade.get("confidence") is not None:
            trade["probability_percent"] = float(trade["confidence"])
        elif trade.get("predicted_probability") is not None:
            trade["probability_percent"] = round(float(trade["predicted_probability"]) * 100.0, 1)
        elif trade.get("ml_prob") is not None:
            mp = float(trade["ml_prob"])
            trade["probability_percent"] = round(max(mp, 1.0 - mp) * 100.0, 1)
        elif snap.get("probability_percent") is not None:
            trade["probability_percent"] = float(snap["probability_percent"])
        elif snap.get("confidence") is not None:
            trade["probability_percent"] = float(snap["confidence"])

    return trade


