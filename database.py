# database.py (نسخه جدید برای اتصال به PostgreSQL/Supabase)

import os
import psycopg2
from psycopg2.extras import DictCursor
from datetime import datetime, date
import logging

logger = logging.getLogger(__name__)

# خواندن آدرس دیتابیس از متغیرهای محیطی که در Render تنظیم کردید
DATABASE_URL = os.environ.get('DATABASE_URL')

def get_connection():
    """یک اتصال جدید به دیتابیس برقرار می‌کند."""
    return psycopg2.connect(DATABASE_URL)

def init_db():
    """جداول اولیه دیتابیس را در صورت عدم وجود ایجاد می‌کند."""
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            # از SERIAL PRIMARY KEY به جای INTEGER PRIMARY KEY AUTOINCREMENT استفاده می‌شود
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS users (
                    user_id BIGINT PRIMARY KEY,
                    first_name TEXT NOT NULL,
                    points INTEGER DEFAULT 0,
                    last_daily_claim TEXT,
                    is_banned BOOLEAN DEFAULT FALSE,
                    referred_by BIGINT,
                    last_transfer_date TEXT 
                )
            ''')
            cursor.execute('CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT NOT NULL)')
            cursor.execute('''
                CREATE TABLE IF NOT EXISTS transfer_history (
                    id SERIAL PRIMARY KEY,
                    sender_id BIGINT NOT NULL,
                    sender_name TEXT NOT NULL,
                    recipient_id BIGINT NOT NULL,
                    recipient_name TEXT NOT NULL,
                    amount_sent INTEGER NOT NULL,
                    tax_amount INTEGER NOT NULL,
                    amount_received INTEGER NOT NULL,
                    timestamp TEXT NOT NULL
                )
            ''')
            conn.commit()
            
            default_costs = {'cost_free_like': '1', 'cost_account_info': '1', 'cost_free_stars': '3'}
            for key, value in default_costs.items():
                cursor.execute("INSERT INTO settings (key, value) VALUES (%s, %s) ON CONFLICT (key) DO NOTHING", (key, value))
            conn.commit()
    finally:
        conn.close()

def get_setting(key: str, default: str = None) -> str:
    """خواندن یک مقدار از جدول تنظیمات."""
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT value FROM settings WHERE key = %s", (key,))
            result = cursor.fetchone()
            return result[0] if result else default
    finally:
        conn.close()

def set_setting(key: str, value: str):
    """ذخیره یا به‌روزرسانی یک مقدار در جدول تنظیمات."""
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            # ON CONFLICT برای PostgreSQL معادل INSERT OR REPLACE است
            cursor.execute("INSERT INTO settings (key, value) VALUES (%s, %s) ON CONFLICT (key) DO UPDATE SET value = EXCLUDED.value", (key, value))
            conn.commit()
    finally:
        conn.close()

def get_or_create_user(user_id, first_name, referred_by=None):
    """گرفتن اطلاعات کاربر یا ساخت کاربر جدید."""
    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=DictCursor) as cursor:
            cursor.execute("SELECT * FROM users WHERE user_id = %s", (user_id,))
            user = cursor.fetchone()
            if not user:
                if first_name is None or first_name == "Unknown":
                    return None
                cursor.execute(
                    "INSERT INTO users (user_id, first_name, referred_by, points) VALUES (%s, %s, %s, %s) RETURNING *",
                    (user_id, first_name, referred_by, 1 if referred_by else 0) # امتیاز اولیه برای کاربر جدید
                )
                user = cursor.fetchone()
                conn.commit()
            return dict(user) if user else None
    finally:
        conn.close()

def update_points(user_id, amount):
    """افزایش یا کاهش امتیاز یک کاربر."""
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("UPDATE users SET points = points + %s WHERE user_id = %s", (amount, user_id))
            conn.commit()
    finally:
        conn.close()
        
def set_transfer_date(user_id):
    """ثبت تاریخ انتقال امتیاز کاربر."""
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            today_str = date.today().isoformat()
            cursor.execute("UPDATE users SET last_transfer_date = %s WHERE user_id = %s", (today_str, user_id))
            conn.commit()
    finally:
        conn.close()

def log_transfer(sender_id, sender_name, recipient_id, recipient_name, amount_sent, tax, amount_received):
    """ثبت یک رکورد در تاریخچه انتقالات."""
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            cursor.execute('''
                INSERT INTO transfer_history 
                (sender_id, sender_name, recipient_id, recipient_name, amount_sent, tax_amount, amount_received, timestamp)
                VALUES (%s, %s, %s, %s, %s, %s, %s, %s)
            ''', (sender_id, sender_name, recipient_id, recipient_name, amount_sent, tax, amount_received, timestamp))
            conn.commit()
    finally:
        conn.close()

def get_transfer_history(limit: int = 20):
    """گرفتن تاریخچه انتقالات."""
    conn = get_connection()
    try:
        with conn.cursor(cursor_factory=DictCursor) as cursor:
            cursor.execute("SELECT * FROM transfer_history ORDER BY id DESC LIMIT %s", (limit,))
            return [dict(row) for row in cursor.fetchall()]
    finally:
        conn.close()

def get_top_users(limit: int = 3):
    """گرفتن لیست کاربران برتر."""
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT first_name, points, user_id FROM users ORDER BY points DESC LIMIT %s", (limit,))
            return cursor.fetchall()
    finally:
        conn.close()

def set_ban_status(user_id, status: bool):
    """تنظیم وضعیت مسدود بودن کاربر."""
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("UPDATE users SET is_banned = %s WHERE user_id = %s", (status, user_id))
            conn.commit()
    finally:
        conn.close()
        
# ... (سایر توابع مثل set_daily_claim, get_all_users و ... را هم می‌توانید به همین شکل بازنویسی کنید)
# برای کامل بودن، در اینجا چند تابع دیگر را هم قرار می‌دهم:

def set_daily_claim(user_id):
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            now_iso = datetime.now().isoformat()
            cursor.execute("UPDATE users SET last_daily_claim = %s WHERE user_id = %s", (now_iso, user_id))
            conn.commit()
    finally:
        conn.close()

def get_all_users():
    conn = get_connection()
    try:
        with conn.cursor() as cursor:
            cursor.execute("SELECT user_id, first_name, points FROM users")
            return cursor.fetchall()
    finally:
        conn.close()
