# main.py

import logging
import os
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

SERVICE_MAP = {
    'لایک رایگان🔥': 'free_like',
    'اطلاعات اکانت📄': 'account_info',
    'استارز رایگان⭐': 'free_stars',
    'گیفت تدی🗿': 'teddy_gift' # <<< NEW
}
SERVICE_NAME_MAP_FA = {v: k for k, v in SERVICE_MAP.items()}
# لیست تمام سرویس‌هایی که کاربر مستقیماً با آنها تعامل دارد
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
        ['گیفت تدی🗿', 'امتیاز روزانه🎁', 'انتقال امتیاز 🔄'], # <<< NEW
        ['حساب کاربری👤', '🏆 نفرات برتر', 'پشتیبانی📞']
    ], resize_keyboard=True)

# ... (سایر توابع کمکی مثل calculate_transfer_tax و check_user_preconditions بدون تغییر) ...

# ==============================================================================
# کنترلرهای اصلی کاربران
# ==============================================================================
# ... (توابع start, profile_handler, support_handler, show_top_users, cancel_conversation بدون تغییر) ...

async def daily_bonus_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # <<< MODIFIED: چک کردن وضعیت فعال بودن سرویس
    if database.get_setting('service_daily_bonus_status', 'true') == 'false':
        await update.message.reply_text("❌ این سرویس در حال حاضر توسط مدیر غیرفعال شده است.")
        return
    if not await check_user_preconditions(update, context): return
    # ... (بقیه کد تابع بدون تغییر)

# ==============================================================================
# گفتگوی دریافت خدمات
# ==============================================================================
async def service_entry_point(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    service_key = SERVICE_MAP.get(update.message.text)
    # <<< MODIFIED: چک کردن وضعیت فعال بودن سرویس
    if database.get_setting(f'service_{service_key}_status', 'true') == 'false':
        await update.message.reply_text("❌ این سرویس در حال حاضر توسط مدیر غیرفعال شده است.")
        return ConversationHandler.END

    if not await check_user_preconditions(update, context): return ConversationHandler.END
    
    cost = int(database.get_setting(f'cost_{service_key}', '1'))
    user = update.effective_user
    db_user = database.get_or_create_user(user.id, user.first_name)
    if db_user['points'] < cost:
        await update.message.reply_text(f"❌ امتیاز شما برای «{update.message.text}» کافی نیست! (نیاز به {cost} امتیاز)")
        return ConversationHandler.END
        
    context.user_data['service_key'] = service_key; context.user_data['cost'] = cost
    database.update_points(user.id, -cost)
    new_points = database.get_or_create_user(user.id, user.first_name)['points']

    # <<< MODIFIED: پیام سفارشی برای سرویس جدید
    prompt_message = "برای تکمیل سفارش، آیدی عددی خود را ارسال کنید.\nبرای لغو /cancel را بزنید."
    if service_key == 'teddy_gift':
        prompt_message = "لطفاً آیدی عددی و آیدی اکانت تلگرام خود (مثلا @username) را در یک پیام وارد کنید.\nبرای لغو /cancel را بزنید."
    elif service_key == 'free_stars':
         prompt_message = "لطفا ایدی عددی حساب خود در ربات، لینک کانال و پست را در یک متن ارسال کنید.\nبرای لغو /cancel را بزنید."
         await update.message.reply_text(f"✅ {cost} امتیاز کسر شد. موجودی جدید: {new_points}.\n\n{prompt_message}")
         return AWAITING_STARS_DETAILS

    await update.message.reply_text(f"✅ {cost} امتیاز کسر شد. موجودی جدید: {new_points}.\n\n{prompt_message}")
    return AWAITING_ID

async def receive_id_and_process(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = update.effective_user; details = update.message.text; service_key = context.user_data.get('service_key')

    # <<< MODIFIED: اعتبارسنجی فقط برای سرویس‌های مشخص
    if service_key in ['free_like', 'account_info']:
        if not details.isdigit():
            await update.message.reply_text("❌ ورودی نامعتبر است. لطفاً فقط عدد وارد کنید."); return AWAITING_ID
        if not (5 <= len(details) <= 14):
            await update.message.reply_text("❌ تعداد ارقام باید بین ۵ تا ۱۴ باشد."); return AWAITING_ID
            
    service_display_name = SERVICE_NAME_MAP_FA.get(service_key, "سرویس نامشخص")
    forward_text = f"درخواست جدید:\n کاربر: {user.first_name} ({user.id})\n نوع: {service_display_name}\n اطلاعات ارسالی: {details}"
    await context.bot.send_message(chat_id=config.ADMIN_ID, text=forward_text)
    
    final_message = "سفارش شما با موفقیت ثبت شد صبور باشید✅" if service_key == 'teddy_gift' else "درخواست شما با موفقیت ثبت شد."
    sent_message = await update.message.reply_text(f"{final_message}\nامتیاز شما: {database.get_or_create_user(user.id, user.first_name)['points']}")
    
    is_secondary_error_enabled = database.get_setting('secondary_error_enabled', 'false') == 'true'
    if is_secondary_error_enabled and service_key in ['free_like', 'account_info']:
        await sent_message.reply_text(database.get_setting('secondary_error_message'))
        
    context.user_data.clear(); return ConversationHandler.END

# ... (گفتگوی ستاره رایگان بدون تغییر)

# ==============================================================================
# گفتگوی انتقال امتیاز
# ==============================================================================
async def transfer_entry(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    # <<< MODIFIED: چک کردن وضعیت فعال بودن سرویس
    if database.get_setting('service_transfer_points_status', 'true') == 'false':
        await update.message.reply_text("❌ این سرویس در حال حاضر توسط مدیر غیرفعال شده است.")
        return ConversationHandler.END
    # ... (بقیه کد تابع بدون تغییر)

# ... (بقیه توابع انتقال امتیاز بدون تغییر)

# ==============================================================================
# کنترلرهای ادمین و گفتگوهای مربوطه
# ==============================================================================
async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    # ... (کد قبلی پنل ادمین)
    keyboard = [
        # ... (دکمه‌های قبلی)
        [InlineKeyboardButton("مدیریت وضعیت سرویس‌ها 🔧", callback_data='admin_manage_services')], # <<< NEW
        # ... (بقیه دکمه‌ها)
    ]
    # ...
    if update.callback_query:
        await update.callback_query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.MARKDOWN)
    else:
        await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.MARKDOWN)


# <<< NEW: مجموعه توابع جدید برای مدیریت وضعیت سرویس‌ها
async def manage_services_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    keyboard = []
    for service_key, service_name in USER_SERVICES.items():
        status = database.get_setting(f'service_{service_key}_status', 'true') == 'true'
        status_text = "فعال 🟢" if status else "غیرفعال 🔴"
        keyboard.append([
            InlineKeyboardButton(f"{service_name}: {status_text}", callback_data=f'toggle_service_{service_key}')
        ])
    
    keyboard.append([InlineKeyboardButton(" بازگشت به پنل اصلی ↩️", callback_data='back_to_admin_panel')])
    await query.edit_message_text("وضعیت هر سرویس را می‌توانید تغییر دهید:", reply_markup=InlineKeyboardMarkup(keyboard))

async def toggle_service_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    service_key = query.data.replace('toggle_service_', '')
    setting_key = f'service_{service_key}_status'
    
    current_status = database.get_setting(setting_key, 'true') == 'true'
    new_status = 'false' if current_status else 'true'
    database.set_setting(setting_key, new_status)
    
    # رفرش کردن منو برای نمایش وضعیت جدید
    await manage_services_menu(update, context)


# ... (تمام توابع دیگر ادمین مثل قبل)


# ==============================================================================
# تابع اصلی و راه‌اندازی ربات
# ==============================================================================
def main() -> None:
    # ... (بخش database.init_db و application.builder مثل قبل)

    # ... (تعریف تمام ConversationHandler ها مثل قبل)

    # ثبت کنترلرها
    # ... (ثبت تمام کنترلرهای قبلی)

    # <<< NEW: ثبت کنترلرهای جدید برای مدیریت سرویس‌ها
    application.add_handler(CallbackQueryHandler(manage_services_menu, pattern='^admin_manage_services$'))
    application.add_handler(CallbackQueryHandler(toggle_service_status, pattern=r'^toggle_service_'))
    
    # ... (بقیه کنترلرها و اجرای ربات)
    application.run_polling()

if __name__ == "__main__":
    main()

