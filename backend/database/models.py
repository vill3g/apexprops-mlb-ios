import sqlite3
import os
import json

DB_PATH = os.path.join(os.path.dirname(__file__), '..', 'data', 'users.db')
DATA_DIR = os.path.join(os.path.dirname(__file__), '..', 'data')

import threading
_user_locks = {}
_user_locks_lock = threading.Lock()

def get_user_lock(user_id):
    user_id = str(user_id)
    with _user_locks_lock:
        if user_id not in _user_locks:
            _user_locks[user_id] = threading.Lock()
        return _user_locks[user_id]

def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute('''
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
            stop_loss_pct REAL DEFAULT 10.0,
            one_click_trade BOOLEAN DEFAULT 0
        )
    ''')
    conn.commit()
    conn.close()

def update_user_ai_enabled(user_id: int, enabled: bool):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("UPDATE users SET ai_enabled = ? WHERE id = ?", (1 if enabled else 0, user_id))
    conn.commit()
    conn.close()

def update_user_trading_mode(user_id: int, mode: str):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("UPDATE users SET trading_mode = ? WHERE id = ?", (mode, user_id))
    conn.commit()
    conn.close()

def update_user_paper_balance(user_id: int, new_balance: float):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute("UPDATE users SET paper_balance = ? WHERE id = ?", (new_balance, user_id))
    conn.commit()
    conn.close()

    # Ensure user data directories exist
    users_dir = os.path.join(DATA_DIR, 'users')
    if not os.path.exists(users_dir):
        os.makedirs(users_dir, exist_ok=True)

def get_user_by_username(username):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE username = ?", (username,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None

def get_user_by_id(user_id):
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE id = ?", (user_id,))
    row = cursor.fetchone()
    conn.close()
    return dict(row) if row else None

def create_user(username, password_hash):
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    try:
        cursor.execute("INSERT INTO users (username, password_hash) VALUES (?, ?)", (username, password_hash))
        user_id = cursor.lastrowid
        conn.commit()
        
        # Create empty trades history for this user
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
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET kalshi_key_id = ?, kalshi_priv_key_encrypted = ? WHERE id = ?", 
                  (key_id, priv_key_encrypted, user_id))
    conn.commit()
    conn.close()

def get_all_active_users():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE is_active = 1")
    rows = cursor.fetchall()
    conn.close()
    return [dict(row) for row in rows]

def update_user_config(user_id: int, trade_size_dollars: float, stop_loss_pct: float, one_click_trade: bool, auto_force_trade: bool = False, trading_style: str = "AUTO", signal_source: str = "ML_ENSEMBLE", take_profit_pct: float = 50.0, max_daily_trades: int = 10, max_daily_risk: float = 50.0, trailing_stop_enabled: bool = False, trailing_stop_activation_pct: float = 35.0, trailing_stop_distance_pct: float = 6.0, model_choice: str = "Swarm", train_window: int = 4000, regularization_c: float = 0.5, class_weight: str = "balanced", xgb_estimators: int = 300, xgb_max_depth: int = 5, xgb_learning_rate: float = 0.1, ignore_pass_technical: bool = False, one_shot_ai: bool = False):
    conn = sqlite3.connect(DB_PATH)
    c = conn.cursor()
    c.execute('''
        UPDATE users 
        SET trade_size_dollars = ?, stop_loss_pct = ?, one_click_trade = ?, auto_force_trade = ?, trading_style = ?, signal_source = ?, take_profit_pct = ?, max_daily_trades = ?, max_daily_risk = ?, trailing_stop_enabled = ?, trailing_stop_activation_pct = ?, trailing_stop_distance_pct = ?, model_choice = ?, train_window = ?, regularization_c = ?, class_weight = ?, xgb_estimators = ?, xgb_max_depth = ?, xgb_learning_rate = ?, ignore_pass_technical = ?, one_shot_ai = ?
        WHERE id = ?
    ''', (trade_size_dollars, stop_loss_pct, 1 if one_click_trade else 0, 1 if auto_force_trade else 0, trading_style, signal_source, take_profit_pct, max_daily_trades, max_daily_risk, 1 if trailing_stop_enabled else 0, trailing_stop_activation_pct, trailing_stop_distance_pct, model_choice, train_window, regularization_c, class_weight, xgb_estimators, xgb_max_depth, xgb_learning_rate, 1 if ignore_pass_technical else 0, 1 if one_shot_ai else 0, user_id))
    conn.commit()
    conn.close()
