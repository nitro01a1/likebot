# main.py (نسخه نهایی با رفع باگ و قابلیت‌های جدید)

import logging
import os
import math
from datetime import datetime, timedelta, date
import random
import re

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler, MessageHandler,
    ContextTypes, ConversationHandler, filters
)
from telegram.constants import ParseMode

import config
import database

# --- تنظیمات اولیه ---
logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

# --- تعریف استیت‌ها و دیکشنری‌ها ---
AWAITING_ID, AWAITING_STARS_DETAILS = 0, 1
AWAITING_USER_ID_MANAGE, AWAITING_COST_AMOUNT = range(2, 4)
AWAITING_RECIPIENT_ID, AWAITING_TRANSFER_AMOUNT = range(4, 6)
AWAITING_ADMIN_MESSAGE = 7

SERVICE_MAP = {
    'لایک رایگان🔥': 'free_like',
    'اطلاعات اکانت📄': 'account_info',
    'استارز رایگان⭐': 'free_stars',
    'گیفت تدی🗿': 'teddy_gift'
}
SERVICE_NAME_MAP_FA = {v: k for k, v in SERVICE_MAP.items()}
USER_SERVICES = {
    'free_like': 'لایک رایگان🔥',
    'account_info': 'اطلاعات اکانت📄',
    'free_stars': 'استارز رایگان⭐',
    'teddy_gift': 'گیفت تدی🗿',
    'daily_bonus': 'امتیاز روزانه🎁',
    'transfer_points': 'انتقال امتیاز 🔄'
}

# ==============================================================================
# توابع کمکی و کیبورد
# ==============================================================================
def get_main_reply_keyboard():
    return ReplyKeyboardMarkup([
        ['لایک رایگان🔥', 'اطلاعات اکانت📄', 'استارز رایگان⭐'],
        ['گیفت تدی🗿', 'امتیاز روزانه🎁', 'انتقال امتیاز 🔄'],
        ['حساب کاربری👤', '🏆 نفرات برتر', 'پشتیبانی📞']
    ], resize_keyboard=True)

def calculate_transfer_tax(amount: int) -> int:
    if 3 <= amount < 5: return 1
    if 5 <= amount < 7: return 2
    if 7 <= amount < 10: return 3
    if 10 <= amount < 15: return 4
    if 15 <= amount < 20: return 5
    if amount >= 20: return 7
    return 0

async def check_user_preconditions(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    user = update.effective_user
    bot_is_on = database.get_setting('bot_status', 'true') == 'true'
    if not bot_is_on and user.id != config.ADMIN_ID:
        if update.message:
            await update.message.reply_text("🔴 ربات در حال تعمیر است. لطفا بعدا تلاش کنید.")
        elif update.callback_query:
            await update.callback_query.answer("🔴 ربات در حال تعمیر است.", show_alert=True)
        return False
        
    db_user = database.get_or_create_user(user.id, user.first_name)
    if not db_user:
        await update.message.reply_text("مشکلی در دسترسی به اطلاعات شما پیش آمد.")
        return False
    if db_user.get('is_banned'):
        await update.message.reply_text("شما توسط ادمین مسدود شده‌اید.")
        return False
        
    for channel in config.FORCED_JOIN_CHANNELS:
        try:
            member = await context.bot.get_chat_member(chat_id=channel, user_id=user.id)
            if member.status not in ['member', 'administrator', 'creator']:
                join_links = "\n".join(f"➡️ {ch}" for ch in config.FORCED_JOIN_CHANNELS)
                await update.message.reply_text(f"برای استفاده از ربات، باید در کانال‌های زیر عضو شوید:\n{join_links}")
                return False
        except Exception as e:
            logger.error(f"Error checking membership for {channel}: {e}")
            await update.message.reply_text("خطایی در بررسی عضویت کانال رخ داد.")
            return False
    return True

# ==============================================================================
# کنترلرهای اصلی کاربران
# ==============================================================================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    # ... (کد کامل تابع start بدون تغییر)

# ... (تمام توابع دیگر کاربران تا بخش گفتگوها بدون تغییر)

# ==============================================================================
# گفتگوی دریافت خدمات
# ==============================================================================
async def service_entry_point(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    # ... (کد کامل این تابع که شامل چک کردن فعال بودن سرویس است)

async def receive_id_and_process(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    # <<< MODIFIED: چک کردن وضعیت ربات در این مرحله هم اضافه شد
    if not await check_user_preconditions(update, context): return ConversationHandler.END
    # ... (بقیه کد تابع)

# ... (بقیه توابع گفتگوها با اضافه شدن چک در هر مرحله)
async def receive_recipient_id(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not await check_user_preconditions(update, context): return ConversationHandler.END
    # ... (بقیه کد تابع)

async def process_transfer(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not await check_user_preconditions(update, context): return ConversationHandler.END
    # ... (بقیه کد تابع)
    
# ==============================================================================
# کنترلرهای ادمین و گفتگوهای مربوطه
# ==============================================================================
async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    # ... (کد کامل پنل ادمین)
    keyboard = [
        [InlineKeyboardButton(f"وضعیت ربات: {bot_status_text}", callback_data='toggle_bot_status')],
        [InlineKeyboardButton(f"خطای ثانویه: {error_status_text}", callback_data='toggle_secondary_error')],
        [InlineKeyboardButton("مدیریت کاربر 👤", callback_data='admin_manage_user'), InlineKeyboardButton("تنظیم هزینه‌ها ⚙️", callback_data='admin_set_costs')],
        [InlineKeyboardButton("مدیریت وضعیت سرویس‌ها 🔧", callback_data='admin_manage_services')],
        [InlineKeyboardButton("تاریخچه انتقالات 📜", callback_data='admin_transfer_history')],
        [InlineKeyboardButton("لیست کاربران 👥", callback_data='list_users_page_1')]
    ]
    # ...
    
# ... (تمام توابع ادمین شامل صفحه‌بندی و پروفایل کامل کاربر)

# ==============================================================================
# تابع اصلی و راه‌اندازی ربات
# ==============================================================================
def main() -> None:
    # ... (بخش database.init_db و application.builder)

    manage_user_conv = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(manage_user_entry, pattern='^admin_manage_user$'),
            CallbackQueryHandler(ask_for_admin_message, pattern=r'^send_msg_')
        ],
        states={
            AWAITING_USER_ID_MANAGE: [MessageHandler(filters.TEXT & ~filters.COMMAND, show_user_manage_options)],
            AWAITING_ADMIN_MESSAGE: [MessageHandler(filters.TEXT & ~filters.COMMAND, send_message_from_admin)]
        },
        fallbacks=[CommandHandler('cancel', cancel_conversation), CallbackQueryHandler(admin_panel, pattern='^back_to_admin_panel$')],
    )

    # ... (بقیه گفتگوها)
    
    # ثبت کنترلرها
    # ...
    application.add_handler(CallbackQueryHandler(list_users_callback, pattern=r'^list_users_page_'))
    application.add_handler(CallbackQueryHandler(show_transfer_history, pattern=r'^transfer_history_page_'))
    application.add_handler(CallbackQueryHandler(list_users_callback, pattern='^admin_list_users$')) # برای کلیک اولیه
    application.add_handler(CallbackQueryHandler(show_transfer_history, pattern='^admin_transfer_history$')) # برای کلیک اولیه
    # ...
    
    logger.info("Starting bot with polling...")
    application.run_polling()

if __name__ == "__main__":
    main()
