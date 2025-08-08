# database.py (نسخه کامل و نهایی با قابلیت شمارش رفرال)

import sqlite3
from datetime import datetime, date
import logging

logger = logging.getLogger(__name__)
DB_NAME = 'bot_database.db'

def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    # جداول قبلی
    cursor.execute('CREATE TABLE IF NOT EXISTS users (user_id INTEGER PRIMARY KEY, first_name TEXT NOT NULL, points INTEGER DEFAULT 0, last_daily_claim TEXT, is_banned INTEGER DEFAULT 0, referred_by INTEGER, last_transfer_date TEXT)')
    cursor.execute('CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL)')
    cursor.execute('CREATE TABLE IF NOT EXISTS transfer_history (id INTEGER PRIMARY KEY AUTOINCREMENT, sender_id INTEGER, sender_name TEXT, recipient_id INTEGER, recipient_name TEXT, amount_sent INTEGER, tax_amount INTEGER, amount_received INTEGER, timestamp TEXT)')
    
    # جداول کدهای هدیه
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS gift_codes (
            code TEXT PRIMARY KEY,
            points INTEGER NOT NULL,
            usage_limit INTEGER NOT NULL,
            usage_count INTEGER NOT NULL DEFAULT 0
        )
    ''')
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS gift_code_usage (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            code TEXT NOT NULL,
            user_id INTEGER NOT NULL,
            UNIQUE(code, user_id)
        )
    ''')

    conn.commit()
    default_settings = {
        'cost_free_like': '1', 'cost_account_info': '1', 'cost_free_stars': '3',
        'cost_teddy_gift': '35',
        'service_free_like_status': 'true', 'service_account_info_status': 'true',
        'service_free_stars_status': 'true', 'service_teddy_gift_status': 'true',
        'service_daily_bonus_status': 'true', 'service_transfer_points_status': 'true'
    }
    for key, value in default_settings.items():
        cursor.execute("INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)", (key, value))
    conn.commit()
    conn.close()

# --- بقیه توابع دیتابیس بدون تغییر ---
def user_exists(user_id):
    conn = sqlite3.connect(DB_NAME); cursor = conn.cursor(); cursor.execute("SELECT 1 FROM users WHERE user_id = ?", (user_id,)); exists = cursor.fetchone() is not None; conn.close(); return exists
def get_setting(key: str, default: str = None) -> str:
    conn = sqlite3.connect(DB_NAME); cursor = conn.cursor(); cursor.execute("SELECT value FROM settings WHERE key = ?", (key,)); result = cursor.fetchone(); conn.close(); return result[0] if result else default
def set_setting(key: str, value: str):
    conn = sqlite3.connect(DB_NAME); cursor = conn.cursor(); cursor.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, value)); conn.commit(); conn.close()
def get_or_create_user(user_id, first_name, referred_by=None):
    conn = sqlite3.connect(DB_NAME); conn.row_factory = sqlite3.Row; cursor = conn.cursor(); cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)); user = cursor.fetchone()
    if not user:
        if first_name is None or first_name == "Unknown": conn.close(); return None
        cursor.execute("INSERT INTO users (user_id, first_name, referred_by) VALUES (?, ?, ?)", (user_id, first_name, referred_by)); conn.commit(); cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,)); user = cursor.fetchone()
    conn.close(); return dict(user) if user else None
def update_points(user_id, amount):
    conn = sqlite3.connect(DB_NAME); cursor = conn.cursor(); cursor.execute("UPDATE users SET points = points + ? WHERE user_id = ?", (amount, user_id)); conn.commit(); conn.close()
def set_daily_claim(user_id):
    conn = sqlite3.connect(DB_NAME); cursor = conn.cursor(); now = datetime.now().isoformat(); cursor.execute("UPDATE users SET last_daily_claim = ? WHERE user_id = ?", (now, user_id)); conn.commit(); conn.close()
def set_transfer_date(user_id):
    conn = sqlite3.connect(DB_NAME); cursor = conn.cursor(); today_str = date.today().isoformat(); cursor.execute("UPDATE users SET last_transfer_date = ? WHERE user_id = ?", (today_str, user_id)); conn.commit(); conn.close()
def delete_user(user_id):
    conn = sqlite3.connect(DB_NAME); cursor = conn.cursor(); cursor.execute("DELETE FROM users WHERE user_id = ?", (user_id,)); conn.commit(); conn.close()
def log_transfer(sender_id, sender_name, recipient_id, recipient_name, amount_sent, tax, amount_received):
    conn = sqlite3.connect(DB_NAME); cursor = conn.cursor(); timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    cursor.execute('''INSERT INTO transfer_history (sender_id, sender_name, recipient_id, recipient_name, amount_sent, tax_amount, amount_received, timestamp) VALUES (?, ?, ?, ?, ?, ?, ?, ?)''', (sender_id, sender_name, recipient_id, recipient_name, amount_sent, tax, amount_received, timestamp)); conn.commit(); conn.close()
def get_transfer_history(limit: int = 10, offset: int = 0):
    conn = sqlite3.connect(DB_NAME); conn.row_factory = sqlite3.Row; cursor = conn.cursor(); cursor.execute("SELECT * FROM transfer_history ORDER BY id DESC LIMIT ? OFFSET ?", (limit, offset)); history = cursor.fetchall(); conn.close(); return [dict(row) for row in history]
def get_transfer_count():
    conn = sqlite3.connect(DB_NAME); cursor = conn.cursor(); cursor.execute("SELECT COUNT(*) FROM transfer_history"); count = cursor.fetchone()[0]; conn.close(); return count
def get_all_users(limit: int = 10, offset: int = 0):
    conn = sqlite3.connect(DB_NAME); cursor = conn.cursor(); cursor.execute("SELECT user_id, first_name, points FROM users ORDER BY user_id DESC LIMIT ? OFFSET ?", (limit, offset)); users = cursor.fetchall(); conn.close(); return users
def get_top_users(limit: int = 3):
    conn = sqlite3.connect(DB_NAME); cursor = conn.cursor(); cursor.execute("SELECT first_name, points, user_id FROM users ORDER BY points DESC LIMIT ?", (limit,)); top_users = cursor.fetchall(); conn.close(); return top_users
def set_ban_status(user_id, status: bool):
    conn = sqlite3.connect(DB_NAME); cursor = conn.cursor(); cursor.execute("UPDATE users SET is_banned = ? WHERE user_id = ?", (int(status), user_id)); conn.commit(); conn.close()
def get_user_count():
    conn = sqlite3.connect(DB_NAME); cursor = conn.cursor(); cursor.execute("SELECT COUNT(*) FROM users"); count = cursor.fetchone()[0]; conn.close(); return count
def add_gift_code(code: str, points: int, usage_limit: int) -> bool:
    conn = sqlite3.connect(DB_NAME); cursor = conn.cursor()
    try: cursor.execute("INSERT INTO gift_codes (code, points, usage_limit) VALUES (?, ?, ?)", (code, points, usage_limit)); conn.commit(); return True
    except sqlite3.IntegrityError: return False
    finally: conn.close()
def delete_gift_code(code: str) -> bool:
    conn = sqlite3.connect(DB_NAME); cursor = conn.cursor()
    try: cursor.execute("DELETE FROM gift_codes WHERE code = ?", (code,)); cursor.execute("DELETE FROM gift_code_usage WHERE code = ?", (code,)); conn.commit(); return True
    except Exception as e: logger.error(f"Error deleting gift code {code}: {e}"); return False
    finally: conn.close()
def redeem_gift_code(user_id: int, code: str) -> (str, int):
    conn = sqlite3.connect(DB_NAME); conn.row_factory = sqlite3.Row; cursor = conn.cursor()
    cursor.execute("SELECT 1 FROM gift_code_usage WHERE code = ? AND user_id = ?", (code, user_id))
    if cursor.fetchone(): conn.close(); return "already_used", 0
    cursor.execute("SELECT * FROM gift_codes WHERE code = ?", (code,))
    gift_code = cursor.fetchone()
    if not gift_code: conn.close(); return "not_found", 0
    if gift_code['usage_count'] >= gift_code['usage_limit']: conn.close(); return "limit_reached", 0
    try:
        points_value = gift_code['points']
        cursor.execute("UPDATE users SET points = points + ? WHERE user_id = ?", (points_value, user_id))
        cursor.execute("UPDATE gift_codes SET usage_count = usage_count + 1 WHERE code = ?", (code,))
        cursor.execute("INSERT INTO gift_code_usage (code, user_id) VALUES (?, ?)", (code, user_id))
        conn.commit(); conn.close(); return "success", points_value
    except Exception as e: conn.rollback(); conn.close(); logger.error(f"Error in redeem_gift_code transaction: {e}"); return "error", 0
def get_all_gift_codes():
    conn = sqlite3.connect(DB_NAME); conn.row_factory = sqlite3.Row; cursor = conn.cursor()
    cursor.execute("SELECT * FROM gift_codes ORDER BY code"); codes = cursor.fetchall(); conn.close(); return [dict(row) for row in codes]
def get_users_of_gift_code(code: str):
    conn = sqlite3.connect(DB_NAME); conn.row_factory = sqlite3.Row; cursor = conn.cursor()
    query = "SELECT u.user_id, u.first_name FROM gift_code_usage AS gu JOIN users AS u ON gu.user_id = u.user_id WHERE gu.code = ? ORDER BY gu.id ASC"
    cursor.execute(query, (code,)); users = cursor.fetchall(); conn.close(); return [dict(row) for row in users]

# --- تابع جدید ---
def get_referral_count(user_id: int) -> int:
    """تعداد کاربرانی که توسط یک نفر دعوت شده‌اند را شمارش می‌کند"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM users WHERE referred_by = ?", (user_id,))
    count = cursor.fetchone()[0]
    conn.close()
    return count
