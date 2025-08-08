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
        
        # بررسی انقضای VIP
        if user and user.get('vip_status') == 1 and user.get('vip_expiry_date'):
            expiry_date = datetime.fromisoformat(user['vip_expiry_date'])
            if datetime.now() > expiry_date:
                cursor.execute("UPDATE users SET vip_status = 0, vip_expiry_date = NULL WHERE user_id = ?", (user_id,))
                conn.commit()
                cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
                user = cursor.fetchone()

        # ریست کردن شمارنده انتقال روزانه اگر تاریخ عوض شده باشد
        today_str = datetime.today().date().isoformat()
        if user and user.get('last_transfer_date') != today_str:
             cursor.execute("UPDATE users SET daily_transfer_count = 0 WHERE user_id = ?", (user_id,))
             conn.commit()
             cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
             user = cursor.fetchone()
             
        return user

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

# (تمام توابع دیگر پایگاه داده بدون تغییر اینجا قرار می‌گیرند)
# ...
def update_points(user_id, amount):
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET points = points + ? WHERE user_id = ?", (amount, user_id))
        conn.commit()
# ... و غیره

