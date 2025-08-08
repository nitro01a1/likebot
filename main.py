# main.py (نسخه نهایی با قابلیت تنظیم هزینه برای تمام سرویس‌ها)

import logging
import os
import math
import random
import re
import asyncio
from datetime import datetime, timedelta, date

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler, MessageHandler,
    ContextTypes, ConversationHandler, filters
)
from telegram.constants import ParseMode
from telegram.error import Forbidden, TelegramError

# این دو فایل را باید در کنار این فایل داشته باشید
import config
import database

# --- تنظیمات و استیت‌ها ---
logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(name)

# استیت‌های مکالمه
(
    AWAITING_ID, AWAITING_STARS_DETAILS,
    AWAITING_USER_ID_MANAGE, AWAITING_COST_AMOUNT,
    AWAITING_RECIPIENT_ID, AWAITING_TRANSFER_AMOUNT,
    AWAITING_ADMIN_MESSAGE, AWAITING_GIFT_CODE_DETAILS,
    AWAITING_GIFT_CODE_INPUT, AWAITING_SECONDARY_ERROR_MESSAGE,
    AWAITING_BROADCAST_MESSAGE, AWAITING_BROADCAST_CONFIRMATION,
    AWAITING_VIP_DURATION, AWAITING_SERVICE_FOR_COST
) = range(14)


# دیکشنری سرویس‌ها برای مدیریت آسان‌تر
USER_SERVICES = {
    'free_like': 'لایک رایگان🔥', 'account_info': 'اطلاعات اکانت📄',
    'free_stars': 'استارز رایگان⭐', 'teddy_gift': 'گیفت تدی🗿',
    'daily_bonus': 'امتیاز روزانه🎁', 'transfer_points': 'انتقال امتیاز 🔄',
    'vip_shop': 'فروشگاه VIP 💎', 'lottery': 'قرعه‌کشی 🎟️'
}

# [جدید] دیکشنری سرویس‌هایی که هزینه قابل تنظیم دارند
COSTS_TO_SET = {
    'free_like': 'لایک رایگان🔥',
    'free_stars': 'استارز رایگان⭐',
    'account_info': 'اطلاعات اکانت📄',
    'teddy_gift': 'گیفت تدی🗿',
    'vip_30_day': 'عضویت VIP (۳۰ روز)',
    'lottery_ticket': 'بلیت قرعه‌کشی'
}


# =============================================================================
# توابع کمکی و کیبوردها
# =============================================================================

def get_main_reply_keyboard():
    """کیبورد اصلی کاربران با دکمه جدید."""
    return ReplyKeyboardMarkup([
        ['حساب کاربری👤', '🏆 نفرات برتر'],
        ['فروشگاه VIP 💎', 'قرعه‌کشی 🎟️'],
        ['لایک رایگان🔥', 'استارز رایگان⭐'],
        ['اطلاعات اکانت📄', 'گیفت تدی🗿'], # [جدید] دکمه‌های جدید اضافه شدند
        ['امتیاز روزانه🎁', 'انتقال امتیاز 🔄', 'کد هدیه 🎁'],
        ['پشتیبانی📞']
    ], resize_keyboard=True)

def calculate_transfer_tax(amount: int, is_vip: bool) -> int:
    """محاسبه مالیات انتقال با تخفیف برای کاربران VIP"""
    if is_vip:
        base_tax = calculate_transfer_tax(amount, False)
        return math.ceil(base_tax / 2)
    if 3 <= amount < 5: return 1
    if 5 <= amount < 10: return 2
    if 10 <= amount < 15: return 3
    if 15 <= amount < 20: return 4
    if amount >= 20: return 5
    return 0

async def check_user_preconditions(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """تمام پیش‌شرط‌های لازم برای اجرای دستورات کاربر را چک می‌کند."""
    user = update.effective_user
    if not user: return False

    bot_is_on = database.get_setting('bot_status', 'true') == 'true'
    if not bot_is_on and user.id != config.ADMIN_ID:
        await update.message.reply_text("🔴 ربات در حال حاضر در حال تعمیر و بروزرسانی است. لطفا بعدا تلاش کنید.")
        return False
        
    db_user = database.get_or_create_user(user.id, user.first_name)
    if not db_user:
        await update.message.reply_text("مشکلی در دسترسی به اطلاعات شما پیش آمد. لطفاً دوباره /start را بزنید.")
        return False
    if db_user.get('is_banned'):
        await update.message.reply_text("شما توسط ادمین مسدود شده‌اید.")
        return False

    for channel in config.FORCED_JOIN_CHANNELS:
        try:
            member = await context.bot.get_chat_member(chat_id=channel, user_id=user.id)
            if member.status not in ['member', 'administrator', 'creator']:
                join_links = "\n".join(f"➡️ {ch}" for ch in config.FORCED_JOIN_CHANNELS)
                await update.message.reply_text(f"برای استفاده از ربات، باید در کانال‌های زیر عضو شوید:\n{join_links}\n\nپس از عضویت، دوباره تلاش کنید.")
                return False
        except Exception as e:
            logger.error(f"Error checking membership for {channel} and user {user.id}: {e}")
            if "Chat not found" in str(e):
                await context.bot.send_message(chat_id=config.ADMIN_ID, text=f"خطای مهم: کانال {channel} پیدا نشد یا ربات ادمین نیست.")
            await update.message.reply_text("خطایی در بررسی عضویت کانال رخ داد. لطفاً با پشتیبانی تماس بگیرید.")
            return False
            
    return True


# =============================================================================
# کنترلرهای اصلی کاربران
# =============================================================================

# (این بخش‌ها بدون تغییر هستند)
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    # ...
    await update.message.reply_text(f"سلام {update.effective_user.first_name}! به ربات ما خوش آمدید.", reply_markup=get_main_reply_keyboard())

async def profile_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # ...
    pass

# ... سایر کنترلرها


# --- [جدید] کنترلر اصلی برای شروع تمام سرویس‌های مبتنی بر امتیاز ---
async def service_entry_point(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """یک ورودی یکپارچه برای تمام سرویس‌هایی که نیاز به امتیاز دارند."""
    
    # پیدا کردن کلید سرویس بر اساس متن دکمه
    service_key = None
    for key, name in USER_SERVICES.items():
        if name == update.message.text:
            service_key = key
            break
            
    if not service_key:
        return ConversationHandler.END

    # چک کردن اینکه سرویس فعال است یا خیر
    if database.get_setting(f'service_{service_key}_status', 'true') == 'false':
        await update.message.reply_text("❌ این سرویس در حال حاضر توسط مدیر غیرفعال شده است.")
        return ConversationHandler.END

    if not await check_user_preconditions(update, context): return ConversationHandler.END

    cost = int(database.get_setting(f'{service_key}_cost', '1')) # هزینه پیش‌فرض ۱
    user = update.effective_user
    db_user = database.get_or_create_user(user.id, user.first_name)

    if db_user['points'] < cost:
        await update.message.reply_text(f"❌ امتیاز شما برای «{update.message.text}» کافی نیست! (نیاز به {cost} امتیاز)")
        return ConversationHandler.END

    context.user_data['service_key'] = service_key
    context.user_data['cost'] = cost
    
    database.update_points(user.id, -cost)
    new_points = database.get_or_create_user(user.id, user.first_name)['points']
    
    # تعیین پیام مناسب برای هر سرویس
    prompt_message = ""
    next_state = AWAITING_ID
    
    if service_key == 'free_stars':
        prompt_message = "لطفا ایدی عددی حساب خود در ربات، لینک کانال و پستی که می\u200cخواهید برای آن استارز زده شود را در قالب یک متن واحد برای ما ارسال کنید."
        next_state = AWAITING_STARS_DETAILS
    elif service_key == 'teddy_gift':
        prompt_message = "لطفاً آیدی عددی و آیدی اکانت تلگرام خود (مثلا @username) را در یک پیام واحد وارد کنید."
    elif service_key == 'account_info':
        prompt_message = "لطفاً آیدی عددی بازی خود که می‌خواهید برای آن اطلاعات دریافت کنید را ارسال نمایید."
    else: # free_like
        prompt_message = "برای تکمیل سفارش، آیدی عددی بازی خود را ارسال کنید."
        
    await update.message.reply_text(
        f"✅ {cost} امتیاز از شما کسر شد. موجودی جدید: {new_points} امتیاز.\n\n"
        f"{prompt_message}\n\nبرای انصراف /cancel را بزنید."
    )
    return next_state


async def receive_id_and_process(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """اطلاعات دریافتی از کاربر را برای ادمین فوروارد می‌کند."""
    user = update.effective_user
    details_text = update.message.text
    service_key = context.user_data.get('service_key')
    
    service_display_name = USER_SERVICES.get(service_key, "سرویس نامشخص")
    forward_text = (
        f"📩 درخواست جدید\n"
        f"از کاربر: {user.first_name} ({user.id})\n"
        f"نوع سرویس: {service_display_name}\n\n"
        f"اطلاعات ارسالی:\n"
        f"{details_text}"
    )
    await context.bot.send_message(chat_id=config.ADMIN_ID, text=forward_text, parse_mode=ParseMode.MARKDOWN)
    
    await update.message.reply_text(
        "✅ درخواست شما با موفقیت ثبت و برای ادمین ارسال شد.",
        reply_markup=get_main_reply_keyboard()
    )
    
    context.user_data.clear()
    return ConversationHandler.END


# =============================================================================
# کنترلرهای پنل ادمین
# =============================================================================

async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    # ... (بدون تغییر)
    pass

# --- [اصلاح نهایی] مکالمه تنظیم هزینه ---
async def set_costs_entry(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """منوی تنظیمات هزینه را با تمام سرویس‌های جدید نمایش می‌دهد."""
    query = update.callback_query
    await query.answer()

    keyboard = []
    text = "هزینه کدام بخش را می‌خواهید تغییر دهید؟\n\n"
    
    for key, name in COSTS_TO_SET.items():
        # هزینه پیش‌فرض برای هر سرویس متفاوت است
        default_cost = '300' if key == 'vip_30_day' else '5' if key == 'lottery_ticket' else '1'
        cost = database.get_setting(f'{key}_cost', default_cost)
        text += f"▫️ {name}: {cost} امتیاز\n"
        keyboard.append([InlineKeyboardButton(f"تغییر هزینه {name}", callback_data=f'setcost_{key}')])

    keyboard.append([InlineKeyboardButton("بازگشت به پنل اصلی ↩️", callback_data='back_to_admin_panel')])
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.MARKDOWN)
    return AWAITING_SERVICE_FOR_COST

async def ask_for_new_cost(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """سرویس انتخاب شده را دریافت و هزینه جدید را میپرسد."""
    query = update.callback_query
    await query.answer()
    
    service_key = query.data.split('_', 1)[1]
    context.user_data['service_to_set_cost'] = service_key
    
    service_name_fa = COSTS_TO_SET.get(service_key, "این سرویس")
    
    await query.edit_message_text(f"لطفاً هزینه جدید را برای «{service_name_fa}» به صورت یک عدد ارسال کنید.\nبرای لغو /cancel را بزنید.")
    return AWAITING_COST_AMOUNT
    
async def set_new_cost(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """هزینه جدید را دریافت و ذخیره می‌کند."""
    try:
        new_cost = int(update.message.text)
        service_key = context.user_data.get('service_to_set_cost')
        
        if service_key and new_cost >= 0:
            database.set_setting(f"{service_key}_cost", str(new_cost))
            service_name_fa = COSTS_TO_SET.get(service_key, "سرویس")
            await update.message.reply_text(f"✅ هزینه «{service_name_fa}» با موفقیت به {new_cost} امتیاز تغییر یافت.")
        else:
            await update.message.reply_text("❌ خطایی رخ داده. لطفاً دوباره تلاش کنید.")
    except (ValueError, TypeError):
        await update.message.reply_text("❌ مقدار نامعتبر است. لطفاً فقط یک عدد وارد کنید.")
    
    context.user_data.clear()
    await admin_panel(update, context) # بازگشت به پنل اصلی
    return ConversationHandler.END


# --- مدیریت وضعیت سرویس‌ها ---
async def manage_services_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # ... (این بخش بدون تغییر است)
    pass
async def toggle_service_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # ... (این بخش بدون تغییر است)
    pass

# --- مکالمه اعطای VIP توسط ادمین ---
# ... (تمام کنترلرهای مربوط به مدیریت کاربر، VIP، بکاپ و پیام همگانی بدون تغییر اینجا قرار دارند)


# =============================================================================
# تابع اصلی و راه‌اندازی ربات
# =============================================================================

def main() -> None:
    database.init_db()
    
    # مقداردهی اولیه برای هزینه‌های جدید در صورت عدم وجود
    if not database.get_setting('teddy_gift_cost'): database.set_setting('teddy_gift_cost', '10')
    if not database.get_setting('account_info_cost'): database.set_setting('account_info_cost', '5')
    
    # مقداردهی اولیه برای وضعیت سرویس‌های جدید
    if not database.get_setting('service_teddy_gift_status'): database.set_setting('service_teddy_gift_status', 'true')
    if not database.get_setting('service_account_info_status'): database.set_setting('service_account_info_status', 'true')


    application = Application.builder().token(config.BOT_TOKEN).build()
    
    # [اصلاح شده] مکالمه یکپارچه برای تمام سرویس‌های کاربر
    service_conv = ConversationHandler(
        # ورودی: یک regex که تمام دکمه‌های سرویس را پوشش دهد
        entry_points=[MessageHandler(filters.Regex(f"^({'|'.join(USER_SERVICES.values())})$"), service_entry_point)],
        states={
            AWAITING_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_id_and_process)],
            AWAITING_STARS_DETAILS: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_id_and_process)] # از همان پردازشگر استفاده میکنیم
        },
        fallbacks=[CommandHandler('cancel', cancel_conversation)],
        per_user=True
    )
    
    # [اصلاح شده] مکالمه تنظیم هزینه
    set_cost_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(set_costs_entry, pattern='^admin_set_costs$')],
        states={
            AWAITING_SERVICE_FOR_COST: [CallbackQueryHandler(ask_for_new_cost, pattern='^setcost_')],
            AWAITING_COST_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, set_new_cost)]
        },
        fallbacks=[CommandHandler('cancel', cancel_conversation), CallbackQueryHandler(admin_panel, pattern='^back_to_admin_panel$')],
        per_user=True
    )

    # --- ثبت تمام کنترلرها ---
    application.add_handler(service_conv) # ثبت کنترلر یکپارچه سرویس
    application.add_handler(set_cost_conv) # ثبت کنترلر اصلاح شده تنظیم هزینه
    
    # (ثبت تمام کنترلرهای دیگر مثل start, admin_panel, vip, lottery, broadcast, backup, ...)
    # ...
    
    logger.info("ربات با تمام قابلیت‌های نهایی در حال اجراست...")
    application.run_polling()


if name == "main":
    main()
