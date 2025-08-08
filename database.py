# file: database.py

import sqlite3
from datetime import datetime

def setup_database():
    """
    جدول هزینه‌ها را در پایگاه داده ایجاد می‌کند اگر وجود نداشته باشد.
    """
    conn = sqlite3.connect('expenses.db')
    cursor = conn.cursor()
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS expenses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER NOT NULL,
            amount REAL NOT NULL,
            description TEXT NOT NULL,
            created_at TEXT NOT NULL
        )
    ''')
    conn.commit()
    conn.close()

def add_expense(user_id: int, amount: float, description: str):
    """
    یک هزینه جدید به پایگاه داده اضافه می‌کند.
    """
    conn = sqlite3.connect('expenses.db')
    cursor = conn.cursor()
    # استفاده از زمان محلی
    created_at = datetime.now().strftime('%Y-%m-%d %H:%M:%S')
    cursor.execute(
        "INSERT INTO expenses (user_id, amount, description, created_at) VALUES (?, ?, ?, ?)",
        (user_id, amount, description, created_at)
    )
    conn.commit()
    conn.close()

def get_expenses(user_id: int):
    """
    تمام هزینه‌های یک کاربر خاص را از پایگاه داده بازیابی می‌کند.
    """
    conn = sqlite3.connect('expenses.db')
    cursor = conn.cursor()
    cursor.execute("SELECT id, amount, description FROM expenses WHERE user_id = ? ORDER BY created_at DESC", (user_id,))
    expenses = cursor.fetchall()
    conn.close()
    return expenses

def delete_expense(expense_id: int, user_id: int) -> bool:
    """
    یک هزینه مشخص را بر اساس ID آن حذف می‌کند و بررسی می‌کند که متعلق به کاربر باشد.
    """
    conn = sqlite3.connect('expenses.db')
    cursor = conn.cursor()
    cursor.execute("DELETE FROM expenses WHERE id = ? AND user_id = ?", (expense_id, user_id))
    # بررسی اینکه آیا ردیفی حذف شده است یا خیر
    deleted_rows = cursor.rowcount
    conn.commit()
    conn.close()
    return deleted_rows > 0

def get_expense_by_id(expense_id: int, user_id: int):
    """
    یک هزینه مشخص را برای ویرایش بازیابی می‌کند.
    """
    conn = sqlite3.connect('expenses.db')
    cursor = conn.cursor()
    cursor.execute("SELECT id, amount, description FROM expenses WHERE id = ? AND user_id = ?", (expense_id, user_id))
    expense = cursor.fetchone()
    conn.close()
    return expense


def update_expense(expense_id: int, user_id: int, new_amount: float, new_description: str) -> bool:
    """
    یک هزینه موجود را به‌روزرسانی می‌کند.
    """
    conn = sqlite3.connect('expenses.db')
    cursor = conn.cursor()
    cursor.execute(
        "UPDATE expenses SET amount = ?, description = ? WHERE id = ? AND user_id = ?",
        (new_amount, new_description, expense_id, user_id)
    )
    updated_rows = cursor.rowcount
    conn.commit()
    conn.close()
    return updated_rows > 0

