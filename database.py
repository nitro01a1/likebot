# database.py

import sqlite3
from datetime import datetime
import logging

logger = logging.getLogger(__name__)
DB_NAME = 'bot_database.db'

def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, first_name TEXT NOT NULL, points INTEGER DEFAULT 0, last_daily_claim TEXT, is_banned INTEGER DEFAULT 0, referred_by INTEGER)')
    cursor.execute('CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL)')
    conn.commit()
    default_costs = {'cost_free_like': '1', 'cost_account_info': '1', 'cost_free_stars': '3'}
    for key, value in default_costs.items():
        cursor.execute("INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)", (key, value))
    conn.commit()
    conn.close()

def get_setting(key: str, default: str = None) -> str:
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT value FROM settings WHERE key = ?", (key,))
    result = cursor.fetchone()
    conn.close()
    return result[0] if result else default

def set_setting(key: str, value: str):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    try:
        cursor.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, value))
        conn.commit()
        logger.info(f"Setting '{key}' updated to '{value}' successfully.")
    except Exception as e:
        logger.error(f"Failed to set setting {key}: {e}")
    finally:
        conn.close()

def get_or_create_user(user_id, first_name, referred_by=None):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
    user = cursor.fetchone()
    if not user:
        cursor.execute("INSERT INTO users (user_id, first_name, referred_by) VALUES (?, ?, ?)", (user_id, first_name, referred_by))
        conn.commit()
        logger.info(f"New user created: {user_id} - Referred by: {referred_by}")
        cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
        user = cursor.fetchone()
    conn.close()
    if user:
        return {"user_id": user[0], "first_name": user[1], "points": user[2], "last_daily_claim": user[3], "is_banned": bool(user[4]), "referred_by": user[5]}
    return None

def update_points(user_id, amount):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    try:
        cursor.execute("UPDATE users SET points = points + ? WHERE user_id = ?", (amount, user_id))
        conn.commit()
        logger.info(f"Points for user {user_id} changed by {amount}.")
    except Exception as e:
        logger.error(f"Failed to update points for {user_id}: {e}")
    finally:
        conn.close()

def set_daily_claim(user_id):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    now = datetime.now().isoformat()
    cursor.execute("UPDATE users SET last_daily_claim = ? WHERE user_id = ?", (now, user_id))
    conn.commit()
    conn.close()

def get_all_users():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT user_id, first_name, points FROM users")
    users = cursor.fetchall()
    conn.close()
    return users

def set_ban_status(user_id, status: bool):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    try:
        cursor.execute("UPDATE users SET is_banned = ? WHERE user_id = ?", (int(status), user_id))
        conn.commit()
        logger.info(f"Ban status for user {user_id} set to {status}.")
    except Exception as e:
        logger.error(f"Failed to set ban status for {user_id}: {e}")
    finally:
        conn.close()

def get_user_count():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM users")
    count = cursor.fetchone()[0]
    conn.close()
    return count
