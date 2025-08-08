# file: database.py

import sqlite3
from datetime import datetime, timedelta

DB_NAME = 'bot_database.db'

def init_db():
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        
        # اجرای دستورات ساخت جدول اصلی
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                first_name TEXT NOT NULL,
                points INTEGER DEFAULT 0,
                is_banned BOOLEAN DEFAULT 0,
                referred_by INTEGER,
                last_daily_claim TEXT,
                last_transfer_date TEXT,
                vip_status INTEGER DEFAULT 0,
                vip_expiry_date TEXT,
                daily_transfer_count INTEGER DEFAULT 0
            )
        ''')

        # تلاش برای افزودن ستون‌های جدید به جدول موجود برای سازگاری با دیتابیس‌های قدیمی
        try:
            cursor.execute("ALTER TABLE users ADD COLUMN vip_status INTEGER DEFAULT 0")
            cursor.execute("ALTER TABLE users ADD COLUMN vip_expiry_date TEXT")
            cursor.execute("ALTER TABLE users ADD COLUMN daily_transfer_count INTEGER DEFAULT 0")
        except sqlite3.OperationalError:
            pass  # ستون‌ها از قبل وجود دارند

        # ایجاد بقیه جداول
        cursor.execute('CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT)')
        cursor.execute('CREATE TABLE IF NOT EXISTS lottery_tickets (ticket_id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER NOT NULL, round_id TEXT NOT NULL, FOREIGN KEY (user_id) REFERENCES users(user_id))')
        cursor.execute('CREATE TABLE IF NOT EXISTS gift_codes (code TEXT PRIMARY KEY, points INTEGER NOT NULL, usage_limit INTEGER NOT NULL, usage_count INTEGER DEFAULT 0)')
        cursor.execute('CREATE TABLE IF NOT EXISTS gift_code_redemptions (code TEXT, user_id INTEGER, PRIMARY KEY (code, user_id), FOREIGN KEY (code) REFERENCES gift_codes(code) ON DELETE CASCADE)')
        cursor.execute('CREATE TABLE IF NOT EXISTS transfer_logs (log_id INTEGER PRIMARY KEY AUTOINCREMENT, sender_id INTEGER, sender_name TEXT, recipient_id INTEGER, recipient_name TEXT, amount_sent INTEGER, tax_amount INTEGER, amount_received INTEGER, timestamp TEXT)')
        
        conn.commit()

def dict_factory(cursor, row):
    fields = [column[0] for column in cursor.description]
    return {key: value for key, value in zip(fields, row)}

def get_or_create_user(user_id, first_name, referred_by=None):
    with sqlite3.connect(DB_NAME) as conn:
        conn.row_factory = dict_factory
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
        user = cursor.fetchone()
        if not user:
            cursor.execute("INSERT INTO users (user_id, first_name, referred_by) VALUES (?, ?, ?)", (user_id, first_name, referred_by))
            conn.commit()
            cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
            user = cursor.fetchone()
        
        if user and user.get('vip_status') == 1 and user.get('vip_expiry_date'):
            expiry_date = datetime.fromisoformat(user['vip_expiry_date'])
            if datetime.now() > expiry_date:
                cursor.execute("UPDATE users SET vip_status = 0, vip_expiry_date = NULL WHERE user_id = ?", (user_id,))
                conn.commit()
                cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
                user = cursor.fetchone()

        today_str = datetime.today().date().isoformat()
        if user and user.get('last_transfer_date') != today_str:
             cursor.execute("UPDATE users SET daily_transfer_count = 0 WHERE user_id = ?", (user_id,))
             conn.commit()
             cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
             user = cursor.fetchone()
             
        return user

def user_exists(user_id: int) -> bool:
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT 1 FROM users WHERE user_id = ?", (user_id,))
        return cursor.fetchone() is not None

def update_points(user_id, amount):
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET points = points + ? WHERE user_id = ?", (amount, user_id))
        conn.commit()

def set_ban_status(user_id, is_banned):
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET is_banned = ? WHERE user_id = ?", (int(is_banned), user_id))
        conn.commit()

def get_referral_count(user_id: int) -> int:
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM users WHERE referred_by = ?", (user_id,))
        return cursor.fetchone()[0]

def get_top_users(limit=3):
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT first_name, points, user_id FROM users ORDER BY points DESC LIMIT ?", (limit,))
        return cursor.fetchall()

def get_all_users(limit=10, offset=0):
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT user_id, first_name, points FROM users ORDER BY user_id LIMIT ? OFFSET ?", (limit, offset))
        return cursor.fetchall()

def get_user_count():
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(user_id) FROM users")
        return cursor.fetchone()[0]

def set_daily_claim(user_id):
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        now_iso = datetime.now().isoformat()
        cursor.execute("UPDATE users SET last_daily_claim = ? WHERE user_id = ?", (now_iso, user_id))
        conn.commit()

def set_transfer_date(user_id):
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        today_iso = datetime.today().date().isoformat()
        cursor.execute("UPDATE users SET last_transfer_date = ? WHERE user_id = ?", (today_iso, user_id))
        conn.commit()

def get_setting(key, default=None):
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT value FROM settings WHERE key = ?", (key,))
        result = cursor.fetchone()
        return result[0] if result else default

def set_setting(key, value):
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, value))
        conn.commit()

def add_gift_code(code, points, usage_limit):
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        try:
            cursor.execute("INSERT INTO gift_codes (code, points, usage_limit) VALUES (?, ?, ?)", (code, points, usage_limit))
            conn.commit()
            return True
        except sqlite3.IntegrityError:
            return False

def redeem_gift_code(user_id, code):
    with sqlite3.connect(DB_NAME) as conn:
        conn.row_factory = dict_factory
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM gift_codes WHERE code = ?", (code,))
        gift_code = cursor.fetchone()
        if not gift_code: return "not_found", 0
        if gift_code['usage_count'] >= gift_code['usage_limit']: return "limit_reached", 0
        cursor.execute("SELECT 1 FROM gift_code_redemptions WHERE code = ? AND user_id = ?", (code, user_id))
        if cursor.fetchone(): return "already_used", 0
        update_points(user_id, gift_code['points'])
        cursor.execute("UPDATE gift_codes SET usage_count = usage_count + 1 WHERE code = ?", (code,))
        cursor.execute("INSERT INTO gift_code_redemptions (code, user_id) VALUES (?, ?)", (code, user_id))
        conn.commit()
        return "success", gift_code['points']

def get_all_gift_codes():
    with sqlite3.connect(DB_NAME) as conn:
        conn.row_factory = dict_factory
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM gift_codes ORDER BY code")
        return cursor.fetchall()

def get_users_of_gift_code(code):
    with sqlite3.connect(DB_NAME) as conn:
        conn.row_factory = dict_factory
        cursor = conn.cursor()
        cursor.execute("SELECT u.user_id, u.first_name FROM users u JOIN gift_code_redemptions r ON u.user_id = r.user_id WHERE r.code = ?", (code,))
        return cursor.fetchall()

def delete_gift_code(code):
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM gift_codes WHERE code = ?", (code,))
        conn.commit()
        return cursor.rowcount > 0

def log_transfer(**kwargs):
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
        cursor.execute("INSERT INTO transfer_logs (sender_id, sender_name, recipient_id, recipient_name, amount_sent, tax_amount, amount_received, timestamp) VALUES (:sender_id, :sender_name, :recipient_id, :recipient_name, :amount_sent, :tax, :amount_received, :timestamp)", {**kwargs, "timestamp": timestamp})
        conn.commit()

def get_transfer_history(limit=10, offset=0):
    with sqlite3.connect(DB_NAME) as conn:
        conn.row_factory = dict_factory
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM transfer_logs ORDER BY log_id DESC LIMIT ? OFFSET ?", (limit, offset))
        return cursor.fetchall()

def get_transfer_count():
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM transfer_logs")
        return cursor.fetchone()[0]

def set_vip_status(user_id, duration_days):
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        expiry_date = datetime.now() + timedelta(days=duration_days)
        cursor.execute("UPDATE users SET vip_status = 1, vip_expiry_date = ? WHERE user_id = ?", (expiry_date.isoformat(), user_id))
        conn.commit()

def increment_transfer_count(user_id):
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        today_str = datetime.today().date().isoformat()
        cursor.execute("UPDATE users SET daily_transfer_count = daily_transfer_count + 1, last_transfer_date = ? WHERE user_id = ?", (today_str, user_id))
        conn.commit()

def get_vip_users(limit=10, offset=0):
    with sqlite3.connect(DB_NAME) as conn:
        conn.row_factory = dict_factory
        cursor = conn.cursor()
        cursor.execute("SELECT user_id, first_name, vip_expiry_date FROM users WHERE vip_status = 1 ORDER BY vip_expiry_date DESC LIMIT ? OFFSET ?", (limit, offset))
        return cursor.fetchall()

def get_vip_user_count():
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM users WHERE vip_status = 1")
        return cursor.fetchone()[0]

def buy_lottery_ticket(user_id, round_id):
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute("INSERT INTO lottery_tickets (user_id, round_id) VALUES (?, ?)", (user_id, round_id))
        conn.commit()

def get_tickets_for_round(round_id):
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT user_id FROM lottery_tickets WHERE round_id = ?", (round_id,))
        return [row[0] for row in cursor.fetchall()]

def clear_tickets_for_round(round_id):
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM lottery_tickets WHERE round_id = ?", (round_id,))
        conn.commit()

def get_all_user_ids(only_active=True):
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        query = "SELECT user_id FROM users"
        if only_active:
            query += " WHERE is_banned = 0"
        cursor.execute(query)
        return [row[0] for row in cursor.fetchall()]
