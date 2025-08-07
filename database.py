# database.py

import sqlite3
from datetime import datetime

DB_NAME = 'bot_database.db'

def init_db():
    """ پایگاه داده و جدول کاربران را ایجاد می‌کند """
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            first_name TEXT NOT NULL,
            points INTEGER DEFAULT 0,
            last_daily_claim TEXT,
            is_banned INTEGER DEFAULT 0,
            referred_by INTEGER
        )
    ''')
    conn.commit()
    conn.close()

def get_or_create_user(user_id, first_name, referred_by=None):
    """ یک کاربر را بر اساس آیدی دریافت یا ایجاد می‌کند """
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
    user = cursor.fetchone()
    if not user:
        cursor.execute(
            "INSERT INTO users (user_id, first_name, referred_by) VALUES (?, ?, ?)",
            (user_id, first_name, referred_by)
        )
        conn.commit()
        cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
        user = cursor.fetchone()
    conn.close()
    # تبدیل نتیجه به دیکشنری برای دسترسی راحت‌تر
    if user:
        return {
            "user_id": user[0], "first_name": user[1], "points": user[2],
            "last_daily_claim": user[3], "is_banned": bool(user[4]), "referred_by": user[5]
        }
    return None

def update_points(user_id, amount):
    """ امتیاز کاربر را به مقدار مشخص شده تغییر می‌دهد (می‌تواند منفی باشد) """
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET points = points + ? WHERE user_id = ?", (amount, user_id))
    conn.commit()
    conn.close()

def set_daily_claim(user_id):
    """ زمان آخرین دریافت امتیاز روزانه را ثبت می‌کند """
    now = datetime.now().isoformat()
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET last_daily_claim = ? WHERE user_id = ?", (now, user_id))
    conn.commit()
    conn.close()

def get_all_users():
    """ لیستی از تمام کاربران را برمی‌گرداند """
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT user_id, first_name, points FROM users")
    users = cursor.fetchall()
    conn.close()
    return users

def set_ban_status(user_id, status: bool):
    """ وضعیت بن بودن کاربر را تغییر می‌دهد """
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("UPDATE users SET is_banned = ? WHERE user_id = ?", (int(status), user_id))
    conn.commit()
    conn.close()

def get_user_count():
    """ تعداد کل کاربران را برمی‌گرداند """
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM users")
    count = cursor.fetchone()[0]
    conn.close()
    return count
