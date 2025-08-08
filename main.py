# main.py (نسخه کامل و نهایی با پنل کد هدیه)

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

# --- تنظیمات اولیه و استیت‌ها ---
logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

# استیت‌های قبلی
AWAITING_ID, AWAITING_STARS_DETAILS = 0, 1
AWAITING_USER_ID_MANAGE, AWAITING_COST_AMOUNT = range(2, 4)
AWAITING_RECIPIENT_ID, AWAITING_TRANSFER_AMOUNT = range(4, 6)
AWAITING_ADMIN_MESSAGE = 7
# استیت جدید برای افزودن کد هدیه
AWAITING_GIFT_CODE_DETAILS = 8

# ... دیکشنری‌ها و توابع کمکی شما بدون تغییر اینجا قرار دارند ...
SERVICE_MAP = {'لایک رایگان🔥':'free_like','اطلاعات اکانت📄':'account_info','استارز رایگان⭐':'free_stars','گیفت تدی🗿':'teddy_gift'}
SERVICE_NAME_MAP_FA = {v: k for k, v in SERVICE_MAP.items()}
USER_SERVICES = {'free_like':'لایک رایگان🔥','account_info':'اطلاعات اکانت📄','free_stars':'استارز رایگان⭐','teddy_gift':'گیفت تدی🗿','daily_bonus':'امتیاز روزانه🎁','transfer_points':'انتقال امتیاز 🔄'}
def get_main_reply_keyboard():
    return ReplyKeyboardMarkup([['لایک رایگان🔥', 'اطلاعات اکانت📄', 'استارز رایگان⭐'],['گیفت تدی🗿', 'امتیاز روزانه🎁', 'انتقال امتیاز 🔄'],['حساب کاربری👤', '🏆 نفرات برتر', 'پشتیبانی📞']], resize_keyboard=True)
def calculate_transfer_tax(amount: int) -> int:
    if 3 <= amount < 5: return 1;
    if 5 <= amount < 7: return 2;
    if 7 <= amount < 10: return 3;
    if 10 <= amount < 15: return 4;
    if 15 <= amount < 20: return 5;
    if amount >= 20: return 7;
    return 0
async def check_user_preconditions(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    user = update.effective_user;
    if not user: return False;
    bot_is_on = database.get_setting('bot_status', 'true') == 'true';
    if not bot_is_on and user.id != config.ADMIN_ID:
        reply_text = "🔴 ربات در حال حاضر در حال تعمیر و بروزرسانی است. لطفا بعدا تلاش کنید.";
        if update.message: await update.message.reply_text(reply_text)
        elif update.callback_query: await update.callback_query.answer(reply_text, show_alert=True)
        return False
    db_user = database.get_or_create_user(user.id, user.first_name);
    if not db_user:
        if update.message: await update.message.reply_text("مشکلی در دسترسی به اطلاعات شما پیش آمد.");
        return False
    if db_user.get('is_banned'):
        if update.message: await update.message.reply_text("شما توسط ادمین مسدود شده‌اید.");
        return False
    for channel in config.FORCED_JOIN_CHANNELS:
        try:
            member = await context.bot.get_chat_member(chat_id=channel, user_id=user.id);
            if member.status not in ['member', 'administrator', 'creator']:
                join_links = "\n".join(f"➡️ {ch}" for ch in config.FORCED_JOIN_CHANNELS);
                if update.message: await update.message.reply_text(f"برای استفاده از ربات، باید در کانال‌های زیر عضو شوید:\n{join_links}");
                return False
        except Exception as e:
            logger.error(f"Error checking membership for {channel}: {e}");
            if update.message: await update.message.reply_text("خطایی در بررسی عضویت کانال رخ داد.");
            return False
    return True
# ... تمام کنترلرهای اصلی کاربران (start, profile, etc.) بدون تغییر اینجا قرار دارند ...
# ...
# ...

# --- دستور /gift بازنویسی شده ---
async def gift_code_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """دستور /gift برای استفاده کاربران با منطق جدید"""
    if not await check_user_preconditions(update, context): return
    user = update.effective_user
    if not context.args:
        await update.message.reply_text("استفاده صحیح: /gift <کد هدیه>")
        return
    
    code = context.args[0]
    # از تابع جدید دیتابیس استفاده می‌کنیم
    status, points_value = database.redeem_gift_code(user.id, code)

    if status == "success":
        db_user = database.get_or_create_user(user.id, user.first_name)
        await update.message.reply_text(f"🎁 تبریک! کد با موفقیت استفاده شد و {points_value} امتیاز دریافت کردید.\nموجودی جدید: {db_user['points']} امتیاز")
    elif status == "already_used":
        await update.message.reply_text("❌ شما قبلاً از این کد هدیه استفاده کرده‌اید.")
    elif status == "limit_reached":
        await update.message.reply_text("❌ متاسفانه ظرفیت استفاده از این کد هدیه به پایان رسیده است.")
    elif status == "not_found":
        await update.message.reply_text("❌ کد هدیه وارد شده نامعتبر است.")
    else: # "error"
        await update.message.reply_text("❌ خطایی در سیستم رخ داد. لطفاً با پشتیبانی تماس بگیرید.")


# ==============================================================================
# کنترلرهای پنل ادمین (بازنویسی شده و جدید)
# ==============================================================================
async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """پنل اصلی مدیریت"""
    if update.effective_user.id != config.ADMIN_ID: return
    
    keyboard = [
        [InlineKeyboardButton("پنل کد هدیه 🎁", callback_data='gift_code_panel')],
        [InlineKeyboardButton("مدیریت کاربر 👤", callback_data='admin_manage_user'), InlineKeyboardButton("تنظیم هزینه‌ها ⚙️", callback_data='admin_set_costs')],
        [InlineKeyboardButton("مدیریت وضعیت سرویس‌ها 🔧", callback_data='admin_manage_services')],
        [InlineKeyboardButton("تاریخچه انتقالات 📜", callback_data='admin_transfer_history_page_1')],
        [InlineKeyboardButton("لیست کاربران 👥", callback_data='list_users_page_1')],
        [InlineKeyboardButton("تغییر وضعیت ربات ⚙️", callback_data='toggle_bot_status')],
    ]
    text = "به پنل مدیریت خوش آمدید."
    if update.callback_query:
        await update.callback_query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
    else:
        await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

# --- توابع جدید پنل کد هدیه ---
async def gift_code_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """نمایش پنل مدیریت کدهای هدیه"""
    query = update.callback_query
    await query.answer()
    keyboard = [
        [InlineKeyboardButton("افزودن کد جدید ➕", callback_data='add_gift_code_entry')],
        [InlineKeyboardButton("لیست و حذف کدها 📋", callback_data='list_gift_codes')],
        [InlineKeyboardButton("بازگشت به پنل اصلی ↩️", callback_data='back_to_admin_panel')]
    ]
    text = "🎁 **پنل مدیریت کدهای هدیه** 🎁"
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.MARKDOWN)

async def add_gift_code_entry(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """شروع فرآیند افزودن کد هدیه"""
    query = update.callback_query
    await query.answer()
    text = "لطفاً اطلاعات کد جدید را به این صورت در یک پیام ارسال کنید:\n\n`CODE POINTS USES`\n\n**مثال:**\n`welcome1404 10 50`\n(کدی به نام `welcome1404` با ارزش ۱۰ امتیاز و ظرفیت استفاده برای ۵۰ نفر)\n\nبرای لغو /cancel را بزنید."
    await query.edit_message_text(text, parse_mode=ParseMode.MARKDOWN)
    return AWAITING_GIFT_CODE_DETAILS

async def process_new_gift_code(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """پردازش اطلاعات کد هدیه جدید"""
    try:
        code, points_str, limit_str = update.message.text.split()
        points = int(points_str)
        usage_limit = int(limit_str)
    except (ValueError, IndexError):
        await update.message.reply_text("❌ فرمت ورودی اشتباه است. لطفاً به شکل `CODE POINTS USES` ارسال کنید.\nمثال: `newyear 5 100`")
        return AWAITING_GIFT_CODE_DETAILS
    
    if database.add_gift_code(code, points, usage_limit):
        await update.message.reply_text(f"✅ کد هدیه `{code}` با ارزش {points} امتیاز و ظرفیت {usage_limit} نفر با موفقیت ساخته شد.", parse_mode=ParseMode.MARKDOWN)
    else:
        await update.message.reply_text(f"❌ کد هدیه `{code}` از قبل در سیستم وجود دارد.", parse_mode=ParseMode.MARKDOWN)
    
    await admin_panel(update, context)
    return ConversationHandler.END
    
async def list_gift_codes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """نمایش لیست کدهای هدیه موجود"""
    query = update.callback_query
    await query.answer()
    all_codes = database.get_all_gift_codes()

    if not all_codes:
        text = "هیچ کد هدیه‌ای در سیستم ثبت نشده است."
        keyboard = [[InlineKeyboardButton("بازگشت ↩️", callback_data='gift_code_panel')]]
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
        return

    text = "📋 **لیست کدهای هدیه** 📋\n\n"
    keyboard = []
    for code_data in all_codes:
        text += (f"🔹 **کد:** `{code_data['code']}`\n"
                 f"   - **امتیاز:** {code_data['points']} ⭐\n"
                 f"   - **استفاده شده:** {code_data['usage_count']} از {code_data['usage_limit']} نفر\n\n")
        keyboard.append([InlineKeyboardButton(f"حذف کد: {code_data['code']} 🗑️", callback_data=f"delete_gift_{code_data['code']}")])
    
    keyboard.append([InlineKeyboardButton("بازگشت ↩️", callback_data='gift_code_panel')])
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.MARKDOWN)

async def delete_gift_code_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """حذف یک کد هدیه از طریق دکمه در لیست"""
    query = update.callback_query
    await query.answer("در حال حذف...")
    code_to_delete = query.data.split('_')[-1]
    
    if database.delete_gift_code(code_to_delete):
        await query.edit_message_text(f"✅ کد هدیه `{code_to_delete}` با موفقیت حذف شد.", parse_mode=ParseMode.MARKDOWN)
    else:
        await query.edit_message_text(f"❌ خطایی در حذف کد `{code_to_delete}` رخ داد.", parse_mode=ParseMode.MARKDOWN)
    
    # برای نمایش لیست آپدیت شده، دوباره تابع لیست را صدا می‌زنیم
    await list_gift_codes(update, context)


# ==============================================================================
# تابع اصلی و راه‌اندازی ربات
# ==============================================================================
def main() -> None:
    database.init_db()
    # ... کدهای اولیه شما ...

    application = Application.builder().token(config.BOT_TOKEN).build()

    # --- مکالمات ---
    # مکالمه جدید برای افزودن کد هدیه
    add_gift_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(add_gift_code_entry, pattern='^add_gift_code_entry$')],
        states={AWAITING_GIFT_CODE_DETAILS: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_new_gift_code)]},
        fallbacks=[CommandHandler('cancel', cancel_conversation)]
    )
    
    # مکالمات قبلی شما
    service_conv = ConversationHandler(...)
    transfer_conv = ConversationHandler(...)
    manage_user_conv = ConversationHandler(...)
    set_cost_conv = ConversationHandler(...)

    # --- ثبت Handler ها ---
    # دستورات اصلی
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("admin", admin_panel))
    application.add_handler(CommandHandler("gift", gift_code_handler)) # دستور /gift با منطق جدید
    
    # ثبت مکالمات
    application.add_handler(add_gift_conv)
    # ... ثبت بقیه مکالمات شما ...

    # دکمه‌های پنل ادمین اصلی
    application.add_handler(CallbackQueryHandler(admin_panel, pattern='^back_to_admin_panel$'))
    # ... بقیه CallbackQueryHandler های پنل ادمین شما ...
    
    # دکمه‌های پنل کد هدیه
    application.add_handler(CallbackQueryHandler(gift_code_panel, pattern='^gift_code_panel$'))
    application.add_handler(CallbackQueryHandler(list_gift_codes, pattern='^list_gift_codes$'))
    application.add_handler(CallbackQueryHandler(delete_gift_code_callback, pattern=r'^delete_gift_'))

    # ... ثبت بقیه Handler های شما ...
    # دستورات قدیمی add/remove points
    application.add_handler(CommandHandler("addpoints", add_points))
    application.add_handler(CommandHandler("removepoints", remove_points))
    
    logger.info("Starting bot with polling...")
    application.run_polling()

if __name__ == "__main__":
    # به دلیل طولانی بودن کد، بخش‌های تکراری حذف شده‌اند.
    # شما باید این کد را با کد خودتان ادغام کنید.
    # main()
    print("لطفا کد کامل را در فایل خود جایگزین کرده و اجرا نمایید.")

