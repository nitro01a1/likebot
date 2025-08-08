# database.py (نسخه کامل و نهایی برای PythonAnywhere با SQLite)

import sqlite3
from datetime import datetime, date
import logging

logger = logging.getLogger(__name__)
DB_NAME = 'bot_database.db'

def init_db():
    """ایجاد جداول اولیه دیتابیس در صورت عدم وجود."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    # جدول کاربران
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            first_name TEXT NOT NULL,
            points INTEGER DEFAULT 0,
            last_daily_claim TEXT,
            is_banned INTEGER DEFAULT 0,
            referred_by INTEGER,
            last_transfer_date TEXT 
        )
    ''')
    
    # جدول تنظیمات
    cursor.execute('CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL)')
    
    # جدول تاریخچه انتقالات
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS transfer_history (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            sender_id INTEGER NOT NULL,
            sender_name TEXT NOT NULL,
            recipient_id INTEGER NOT NULL,
            recipient_name TEXT NOT NULL,
            amount_sent INTEGER NOT NULL,
            tax_amount INTEGER NOT NULL,
            amount_received INTEGER NOT NULL,
            timestamp TEXT NOT NULL
        )
    ''')
    conn.commit()

    # افزودن هزینه‌ها و وضعیت‌های پیش‌فرض سرویس‌ها در صورتی که وجود نداشته باشند
    default_settings = {
        'cost_free_like': '1', 'cost_account_info': '1', 'cost_free_stars': '3',
        'cost_teddy_gift': '35',
        'service_free_like_status': 'true',
        'service_account_info_status': 'true',
        'service_free_stars_status': 'true',
        'service_teddy_gift_status': 'true',
        'service_daily_bonus_status': 'true',
        'service_transfer_points_status': 'true'
    }
    for key, value in default_settings.items():
        cursor.execute("INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)", (key, value))
    
    conn.commit()
    conn.close()

def get_setting(key: str, default: str = None) -> str:
    """خواندن یک مقدار از جدول تنظیمات."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT value FROM settings WHERE key = ?", (key,))
    result = cursor.fetchone()
    conn.close()
    return result[0] if result else default

def set_setting(key: str, value: str):
    """ذخیره یا به‌روزرسانی یک مقدار در جدول تنظیمات."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    try:
        cursor.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, value))
        conn.commit()
    finally:
        conn.close()

def get_or_create_user(user_id, first_name, referred_by=None):
    """گرفتن اطلاعات کاربر یا ساخت کاربر جدید در صورت عدم وجود."""
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
    user = cursor.fetchone()
    if not user:
        if first_name is None or first_name == "Unknown":
             conn.close()
             return None
        cursor.execute("INSERT INTO users (user_id, first_name, referred_by) VALUES (?, ?, ?)", (user_id, first_name, referred_by))
        conn.commit()
        cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
        user = cursor.fetchone()
    conn.close()
    return dict(user) if user else None

def update_points(user_id, amount):
    """افزایش یا کاهش امتیاز یک کاربر."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    try:
        cursor.execute("UPDATE users SET points = points + ? WHERE user_id = ?", (amount, user_id))
        conn.commit()
    finally:
        conn.close()

def set_daily_claim(user_id):
    """ثبت تاریخ دریافت جایزه روزانه."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    now = datetime.now().isoformat()
    cursor.execute("UPDATE users SET last_daily_claim = ? WHERE user_id = ?", (now, user_id))
    conn.commit()
    conn.close()

def set_transfer_date(user_id):
    """ثبت تاریخ انتقال امتیاز کاربر."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    today_str = date.today().isoformat()
    try:
        cursor.execute("UPDATE users SET last_transfer_date = ? WHERE user_id = ?", (today_str, user_id))
        conn.commit()
    finally:
        conn.close()

def delete_user(user_id):
    """حذف یک کاربر از دیتابیس."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    try:
        cursor.execute("DELETE FROM users WHERE user_id = ?", (user_id,))
        conn.commit()
    finally:
        conn.close()

def log_transfer(sender_id, sender_name, recipient_id, recipient_name, amount_sent, tax, amount_received):
    """ثبت یک رکورد در تاریخچه انتقالات."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    try:
        cursor.execute('''
            INSERT INTO transfer_history 
            (sender_id, sender_name, recipient_id, recipient_name, amount_sent, tax_amount, amount_received, timestamp)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        ''', (sender_id, sender_name, recipient_id, recipient_name, amount_sent, tax, amount_received, timestamp))
        conn.commit()
    finally:
        conn.close()

def get_transfer_history(limit: int = 20):
    """گرفتن تاریخچه انتقالات برای نمایش به ادمین."""
    conn = sqlite3.connect(DB_NAME)
    conn.row_factory = sqlite3.Row
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM transfer_history ORDER BY id DESC LIMIT ?", (limit,))
    history = cursor.fetchall()
    conn.close()
    return [dict(row) for row in history]

def get_all_users():
    """گرفتن لیست تمام کاربران."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT user_id, first_name, points FROM users")
    users = cursor.fetchall()
    conn.close()
    return users

def get_top_users(limit: int = 3):
    """گرفتن لیست کاربران برتر."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT first_name, points, user_id FROM users ORDER BY points DESC LIMIT ?", (limit,))
    top_users = cursor.fetchall()
    conn.close()
    return top_users

def set_ban_status(user_id, status: bool):
    """تنظیم وضعیت مسدود بودن کاربر."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    try:
        cursor.execute("UPDATE users SET is_banned = ? WHERE user_id = ?", (int(status), user_id))
        conn.commit()
    finally:
        conn.close()

def get_user_count():
    """گرفتن تعداد کل کاربران."""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM users")
    count = cursor.fetchone()[0]
    conn.close()
    return count
