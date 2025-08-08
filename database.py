# file: database.py

import sqlite3
from datetime import datetime

DB_NAME = 'bot_database.db'

def init_db():
    """
    پایگاه داده و تمام جداول مورد نیاز را ایجاد می‌کند.
    این تابع باید در ابتدای اجرای ربات فراخوانی شود.
    """
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()

        # جدول کاربران
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS users (
                user_id INTEGER PRIMARY KEY,
                first_name TEXT NOT NULL,
                points INTEGER DEFAULT 0,
                is_banned BOOLEAN DEFAULT 0,
                referred_by INTEGER,
                last_daily_claim TEXT,
                last_transfer_date TEXT
            )
        ''')

        # جدول تنظیمات کلیدی-مقداری
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT
            )
        ''')

        # جدول کدهای هدیه
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS gift_codes (
                code TEXT PRIMARY KEY,
                points INTEGER NOT NULL,
                usage_limit INTEGER NOT NULL,
                usage_count INTEGER DEFAULT 0
            )
        ''')

        # جدول برای پیگیری استفاده کاربران از کدهای هدیه
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS gift_code_redemptions (
                code TEXT,
                user_id INTEGER,
                PRIMARY KEY (code, user_id),
                FOREIGN KEY (code) REFERENCES gift_codes(code) ON DELETE CASCADE,
                FOREIGN KEY (user_id) REFERENCES users(user_id)
            )
        ''')
        
        # جدول تاریخچه انتقالات
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS transfer_logs (
                log_id INTEGER PRIMARY KEY AUTOINCREMENT,
                sender_id INTEGER,
                sender_name TEXT,
                recipient_id INTEGER,
                recipient_name TEXT,
                amount_sent INTEGER,
                tax_amount INTEGER,
                amount_received INTEGER,
                timestamp TEXT
            )
        ''')
        
        conn.commit()

def dict_factory(cursor, row):
    """نتایج کوئری را به صورت دیکشنری برمیگرداند"""
    fields = [column[0] for column in cursor.description]
    return {key: value for key, value in zip(fields, row)}

# --- توابع مدیریت کاربران ---

def get_or_create_user(user_id, first_name, referred_by=None):
    """یک کاربر را بر اساس آیدی دریافت یا ایجاد می‌کند."""
    with sqlite3.connect(DB_NAME) as conn:
        conn.row_factory = dict_factory
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
        user = cursor.fetchone()
        if not user:
            # اگر کاربر وجود نداشت و معرف داشت، آن را ثبت کن
            cursor.execute(
                "INSERT INTO users (user_id, first_name, referred_by) VALUES (?, ?, ?)",
                (user_id, first_name, referred_by)
            )
            conn.commit()
            cursor.execute("SELECT * FROM users WHERE user_id = ?", (user_id,))
            user = cursor.fetchone()
        return user

def user_exists(user_id: int) -> bool:
    """بررسی میکند آیا کاربر در دیتابیس وجود دارد یا خیر"""
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT 1 FROM users WHERE user_id = ?", (user_id,))
        return cursor.fetchone() is not None

def update_points(user_id, amount):
    """امتیاز یک کاربر را به مقدار مشخص شده (مثبت یا منفی) تغییر می‌دهد."""
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET points = points + ? WHERE user_id = ?", (amount, user_id))
        conn.commit()

def set_ban_status(user_id, is_banned):
    """وضعیت بن بودن کاربر را تغییر می‌دهد."""
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute("UPDATE users SET is_banned = ? WHERE user_id = ?", (int(is_banned), user_id))
        conn.commit()

def get_referral_count(user_id: int) -> int:
    """تعداد کاربرانی که توسط یک فرد مشخص دعوت شده‌اند را برمی‌گرداند."""
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM users WHERE referred_by = ?", (user_id,))
        return cursor.fetchone()[0]

def get_top_users(limit=3):
    """کاربران برتر بر اساس امتیاز را برمی‌گرداند."""
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT first_name, points, user_id FROM users ORDER BY points DESC LIMIT ?", (limit,))
        return cursor.fetchall()
        
def get_all_users(limit=10, offset=0):
    """لیست تمام کاربران را به صورت صفحه‌بندی شده برمی‌گرداند."""
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT user_id, first_name, points FROM users ORDER BY user_id LIMIT ? OFFSET ?", (limit, offset))
        return cursor.fetchall()

def get_user_count():
    """تعداد کل کاربران را برمیگرداند"""
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(user_id) FROM users")
        return cursor.fetchone()[0]

def set_daily_claim(user_id):
    """زمان آخرین دریافت جایزه روزانه را ثبت می‌کند."""
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        now_iso = datetime.now().isoformat()
        cursor.execute("UPDATE users SET last_daily_claim = ? WHERE user_id = ?", (now_iso, user_id))
        conn.commit()

def set_transfer_date(user_id):
    """تاریخ آخرین انتقال وجه را ثبت می‌کند."""
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        today_iso = datetime.today().date().isoformat()
        cursor.execute("UPDATE users SET last_transfer_date = ? WHERE user_id = ?", (today_iso, user_id))
        conn.commit()

# --- توابع مدیریت تنظیمات ---

def get_setting(key, default=None):
    """یک مقدار را از جدول تنظیمات بر اساس کلید دریافت می‌کند."""
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT value FROM settings WHERE key = ?", (key,))
        result = cursor.fetchone()
        return result[0] if result else default

def set_setting(key, value):
    """یک مقدار را در جدول تنظیمات ذخیره یا به‌روزرسانی می‌کند."""
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, value))
        conn.commit()

# --- توابع مدیریت کد هدیه ---

def add_gift_code(code, points, usage_limit):
    """یک کد هدیه جدید اضافه می‌کند."""
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        try:
            cursor.execute("INSERT INTO gift_codes (code, points, usage_limit) VALUES (?, ?, ?)", (code, points, usage_limit))
            conn.commit()
            return True
        except sqlite3.IntegrityError: # اگر کد تکراری باشد
            return False

def redeem_gift_code(user_id, code):
    """منطق استفاده از کد هدیه توسط کاربر."""
    with sqlite3.connect(DB_NAME) as conn:
        conn.row_factory = dict_factory
        cursor = conn.cursor()
        
        # کد را پیدا کن
        cursor.execute("SELECT * FROM gift_codes WHERE code = ?", (code,))
        gift_code = cursor.fetchone()
        if not gift_code:
            return "not_found", 0

        # چک کن ظرفیت تمام نشده باشد
        if gift_code['usage_count'] >= gift_code['usage_limit']:
            return "limit_reached", 0
        
        # چک کن کاربر قبلا استفاده نکرده باشد
        cursor.execute("SELECT 1 FROM gift_code_redemptions WHERE code = ? AND user_id = ?", (code, user_id))
        if cursor.fetchone():
            return "already_used", 0
            
        # تمام شرایط اوکی است: امتیاز را بده و لاگ ثبت کن
        update_points(user_id, gift_code['points'])
        cursor.execute("UPDATE gift_codes SET usage_count = usage_count + 1 WHERE code = ?", (code,))
        cursor.execute("INSERT INTO gift_code_redemptions (code, user_id) VALUES (?, ?)", (code, user_id))
        conn.commit()
        return "success", gift_code['points']

def get_all_gift_codes():
    """لیست تمام کدهای هدیه را برمی‌گرداند."""
    with sqlite3.connect(DB_NAME) as conn:
        conn.row_factory = dict_factory
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM gift_codes ORDER BY code")
        return cursor.fetchall()
        
def get_users_of_gift_code(code):
    """لیست کاربرانی که از یک کد خاص استفاده کرده‌اند را برمی‌گرداند."""
    with sqlite3.connect(DB_NAME) as conn:
        conn.row_factory = dict_factory
        cursor = conn.cursor()
        cursor.execute("""
            SELECT u.user_id, u.first_name 
            FROM users u
            JOIN gift_code_redemptions r ON u.user_id = r.user_id
            WHERE r.code = ?
        """, (code,))
        return cursor.fetchall()

def delete_gift_code(code):
    """یک کد هدیه را حذف می‌کند. به دلیل تنظیم ON DELETE CASCADE، رکوردهای مربوطه در جدول دیگر نیز حذف میشوند"""
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute("DELETE FROM gift_codes WHERE code = ?", (code,))
        conn.commit()
        return cursor.rowcount > 0


# --- توابع مدیریت تاریخچه انتقالات ---

def log_transfer(**kwargs):
    """یک رکورد انتقال وجه را در تاریخچه ثبت می‌کند."""
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        timestamp = datetime.now().strftime("%Y-%m-%d %H:%M")
        cursor.execute("""
            INSERT INTO transfer_logs (sender_id, sender_name, recipient_id, recipient_name, amount_sent, tax_amount, amount_received, timestamp)
            VALUES (:sender_id, :sender_name, :recipient_id, :recipient_name, :amount_sent, :tax, :amount_received, :timestamp)
        """, {**kwargs, "timestamp": timestamp})
        conn.commit()

def get_transfer_history(limit=10, offset=0):
    """تاریخچه انتقالات را به صورت صفحه‌بندی شده برمی‌گرداند."""
    with sqlite3.connect(DB_NAME) as conn:
        conn.row_factory = dict_factory
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM transfer_logs ORDER BY log_id DESC LIMIT ? OFFSET ?", (limit, offset))
        return cursor.fetchall()

def get_transfer_count():
    """تعداد کل رکوردهای انتقال را برمی‌گرداند."""
    with sqlite3.connect(DB_NAME) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM transfer_logs")
        return cursor.fetchone()[0]

if __name__ == '__main__':
    # این تابع را یک بار به صورت دستی اجرا کنید تا فایل دیتابیس ساخته شود
    # python database.py
    print("Initializing database...")
    init_db()
    print("Database initialized successfully.")
