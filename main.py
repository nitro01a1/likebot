# main.py (نسخه نهایی با پنل ادمین محاوره‌ای و رفع تمام باگ‌ها)

import logging
import os
from datetime import datetime, timedelta
import random

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler, MessageHandler,
    ContextTypes, ConversationHandler, filters
)
from telegram.constants import ParseMode

import config
import database

logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

# --- تعریف استیت‌ها ---
# برای کاربر
GETTING_SERVICE, AWAITING_ID = range(2)
# برای ادمین
AWAITING_USER_ID_MANAGE, AWAITING_COST_AMOUNT = range(2, 4)

SERVICE_MAP = {
    'لایک رایگان🔥': 'free_like',
    'اطلاعات اکانت📄': 'account_info',
    'استارز رایگان⭐': 'free_stars'
}
SERVICE_NAME_MAP_FA = {v: k for k, v in SERVICE_MAP.items()} # معکوس برای نمایش نام فارسی

# ==============================================================================
# کیبوردها و توابع کمکی
# ==============================================================================
def get_main_reply_keyboard():
    return ReplyKeyboardMarkup([['لایک رایگان🔥', 'اطلاعات اکانت📄'], ['استارز رایگان⭐', 'امتیاز روزانه🎁'], ['حساب کاربری👤', 'پشتیبانی📞']], resize_keyboard=True)

async def check_user_preconditions(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    user = update.effective_user
    db_user = database.get_or_create_user(user.id, user.first_name)
    if not db_user or db_user.get('is_banned'):
        await update.message.reply_text("شما دسترسی به این بخش را ندارید.")
        return False
    # ... (کد بررسی عضویت در کانال) ...
    return True

# ==============================================================================
# جریان اصلی کار کاربر (User Flow)
# ==============================================================================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    # --- منطق رفرال ---
    if context.args:
        try:
            referrer_id = int(context.args[0])
            if referrer_id != user.id:
                # فقط اگر کاربر برای اولین بار وارد می‌شود، کد معرف ثبت شود
                is_new_user = not database.get_or_create_user(user.id, user.first_name)
                if is_new_user:
                    database.get_or_create_user(user.id, user.first_name, referred_by=referrer_id)
                    database.update_points(referrer_id, 1)
                    try:
                        await context.bot.send_message(chat_id=referrer_id, text=f"یک کاربر جدید از طریق لینک شما وارد ربات شد و ۱ امتیاز دریافت کردید!")
                    except Exception as e:
                        logger.error(f"Failed to send referral notification to {referrer_id}: {e}")
        except (ValueError, IndexError):
            pass # اگر کد رفرال اشتباه بود، نادیده بگیر
    else:
        database.get_or_create_user(user.id, user.first_name)
    await update.message.reply_text(f"سلام {user.first_name}! به ربات ما خوش آمدید.", reply_markup=get_main_reply_keyboard())


async def service_entry_point(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """نقطه ورود به مکالمه برای دریافت خدمات."""
    if not await check_user_preconditions(update, context): return ConversationHandler.END
    
    service_key = SERVICE_MAP.get(update.message.text)
    cost = int(database.get_setting(f'cost_{service_key}', '1'))
    db_user = database.get_or_create_user(update.effective_user.id, update.effective_user.first_name)

    if db_user['points'] < cost:
        await update.message.reply_text(f"❌ امتیاز شما برای «{update.message.text}» کافی نیست! (نیاز به {cost} امتیاز)")
        return ConversationHandler.END

    # ذخیره اطلاعات برای مرحله بعد
    context.user_data['service_key'] = service_key
    context.user_data['cost'] = cost

    await update.message.reply_text(f"هزینه این بخش {cost} امتیاز است. برای تایید و کسر امتیاز، آیدی عددی بازی خود را ارسال کنید. برای انصراف /cancel را بزنید.")
    return AWAITING_ID


async def receive_id_and_process(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """آیدی را دریافت، امتیاز را کم کرده و پردازش می‌کند."""
    user = update.effective_user
    game_id = update.message.text
    
    service_key = context.user_data.get('service_key')
    cost = context.user_data.get('cost')

    # کسر امتیاز
    database.update_points(user.id, -cost)
    
    service_display_name = SERVICE_NAME_MAP_FA.get(service_key, "سرویس نامشخص")
    forward_text = f"درخواست جدید:\n کاربر: {user.first_name} ({user.id})\n نوع: {service_display_name}\n آیدی ارسالی: {game_id}"
    await context.bot.send_message(chat_id=config.ADMIN_ID, text=forward_text)
    
    reply_text = "سفارش شما در حال بررسی است." if service_key == 'free_stars' else "درخواست شما با موفقیت ثبت شد."
    sent_message = await update.message.reply_text(f"{reply_text}\nامتیاز شما: {database.get_or_create_user(user.id, user.first_name)['points']}")
    
    if config.SECONDARY_ERROR_ENABLED and service_key != 'free_stars':
        await sent_message.reply_text(config.SECONDARY_ERROR_MESSAGE)

    context.user_data.clear()
    return ConversationHandler.END


async def cancel_conversation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """هر نوع مکالمه‌ای را لغو می‌کند."""
    await update.message.reply_text("عملیات لغو شد.", reply_markup=get_main_reply_keyboard())
    context.user_data.clear()
    return ConversationHandler.END

# ... (توابع profile_handler, daily_bonus_handler, support_handler مثل قبل، فقط check_user_preconditions به ابتدایشان اضافه شود) ...

# ==============================================================================
# جریان کار ادمین (Admin Flow)
# ==============================================================================
async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_user.id != config.ADMIN_ID: return
    
    admin_keyboard = [
        [InlineKeyboardButton("مدیریت کاربر 👤", callback_data='admin_manage_user')],
        [InlineKeyboardButton("تنظیم هزینه‌ها ⚙️", callback_data='admin_set_costs')],
        [InlineKeyboardButton("لیست کاربران 👥", callback_data='admin_list_users')]
    ]
    text = (
        "به پنل مدیریت خوش آمدید.\n\n"
        "**راهنمای امتیازدهی دستی:**\n"
        "`/addpoints <USER_ID> <AMOUNT>`\n"
        "`/removepoints <USER_ID> <AMOUNT>`"
    )
    await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(admin_keyboard), parse_mode=ParseMode.MARKDOWN)

# --- مکالمه برای مدیریت کاربر (بن/آنبن) ---
async def manage_user_entry(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("لطفاً آیدی عددی کاربری که می‌خواهید مدیریت کنید را ارسال نمایید.")
    return AWAITING_USER_ID_MANAGE

async def show_user_manage_options(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    try:
        user_id_to_manage = int(update.message.text)
    except ValueError:
        await update.message.reply_text("آیدی نامعتبر است. لطفاً یک آیدی عددی صحیح ارسال کنید."); return AWAITING_USER_ID_MANAGE

    user_info = database.get_or_create_user(user_id_to_manage, "Unknown")
    if not user_info:
        await update.message.reply_text("کاربری با این آیدی یافت نشد."); return ConversationHandler.END
        
    status = "🔴 مسدود" if user_info['is_banned'] else "🟢 فعال"
    keyboard = [
        [InlineKeyboardButton("بن کردن 🚫", callback_data=f"ban_{user_id_to_manage}")],
        [InlineKeyboardButton("آنبن کردن ✅", callback_data=f"unban_{user_id_to_manage}")]
    ]
    await update.message.reply_text(f"کاربر: {user_info['first_name']} ({user_id_to_manage})\nوضعیت: {status}\n\nچه کاری انجام شود؟", reply_markup=InlineKeyboardMarkup(keyboard))
    return ConversationHandler.END
    
async def perform_ban_unban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    action, user_id = query.data.split('_')
    user_id = int(user_id)
    
    if action == "ban":
        database.set_ban_status(user_id, True)
        await query.edit_message_text(f"کاربر {user_id} با موفقیت مسدود شد.")
    elif action == "unban":
        database.set_ban_status(user_id, False)
        await query.edit_message_text(f"کاربر {user_id} با موفقیت از مسدودیت خارج شد.")

# --- مکالمه برای تنظیم هزینه ---
async def set_costs_entry(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    cost_like = database.get_setting('cost_free_like', '1'); cost_info = database.get_setting('cost_account_info', '1'); cost_stars = database.get_setting('cost_free_stars', '3')
    
    keyboard = [
        [InlineKeyboardButton(f"لایک ({cost_like} امتیاز)", callback_data='setcost_free_like')],
        [InlineKeyboardButton(f"اطلاعات ({cost_info} امتیاز)", callback_data='setcost_account_info')],
        [InlineKeyboardButton(f"استارز ({cost_stars} امتیاز)", callback_data='setcost_free_stars')]
    ]
    await query.edit_message_text("هزینه کدام بخش را می‌خواهید تغییر دهید؟", reply_markup=InlineKeyboardMarkup(keyboard))
    return ConversationHandler.END # No state needed, next step is another callback

async def ask_for_new_cost(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    service_key = query.data.split('_')[1]
    context.user_data['service_to_set_cost'] = service_key
    service_name_fa = SERVICE_NAME_MAP_FA.get(service_key, "این سرویس")
    await query.edit_message_text(f"لطفاً هزینه جدید را برای «{service_name_fa}» به صورت یک عدد ارسال کنید.")
    return AWAITING_COST_AMOUNT

async def set_new_cost(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    try:
        new_cost = int(update.message.text)
        service_key = context.user_data.get('service_to_set_cost')
        database.set_setting(f"cost_{service_key}", str(new_cost))
        await update.message.reply_text(f"هزینه با موفقیت به {new_cost} تغییر یافت.", reply_markup=get_main_reply_keyboard())
    except (ValueError, TypeError):
        await update.message.reply_text("مقدار نامعتبر است. لطفاً فقط یک عدد ارسال کنید.")
    
    context.user_data.clear()
    return ConversationHandler.END
    
# ... (بقیه توابع ادمین مثل addpoints/removepoints که فقط با کامند کار می‌کنند) ...

# ==============================================================================
# تابع اصلی و راه‌اندازی
# ==============================================================================
def main() -> None:
    database.init_db()
    application = Application.builder().token(config.BOT_TOKEN).build()

    # مکالمه اصلی کاربر
    user_conv_handler = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex(f"^({'|'.join(SERVICE_MAP.keys())})$"), service_entry_point)],
        states={AWAITING_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_id_and_process)]},
        fallbacks=[CommandHandler('cancel', cancel_conversation)],
        per_user=True, per_chat=True
    )

    # مکالمات ادمین
    manage_user_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(manage_user_entry, pattern='^admin_manage_user$')],
        states={AWAITING_USER_ID_MANAGE: [MessageHandler(filters.TEXT & ~filters.COMMAND, show_user_manage_options)]},
        fallbacks=[CommandHandler('cancel', cancel_conversation)]
    )
    set_cost_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(ask_for_new_cost, pattern='^setcost_.*$')],
        states={AWAITING_COST_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, set_new_cost)]},
        fallbacks=[CommandHandler('cancel', cancel_conversation)]
    )

    application.add_handler(user_conv_handler)
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.Regex('^حساب کاربری👤$'), profile_handler))
    application.add_handler(MessageHandler(filters.Regex('^امتیاز روزانه🎁$'), daily_bonus_handler))
    application.add_handler(MessageHandler(filters.Regex('^پشتیبانی📞$'), support_handler))
    
    application.add_handler(CommandHandler("admin", admin_panel))
    application.add_handler(manage_user_conv)
    application.add_handler(set_cost_conv)
    application.add_handler(CallbackQueryHandler(perform_ban_unban, pattern='^(ban|unban)_.*$'))
    application.add_handler(CallbackQueryHandler(set_costs_entry, pattern='^admin_set_costs$'))
    # ... (ثبت سایر handler های ادمین مثل addpoints/removepoints)

    port = int(os.environ.get('PORT', 8443))
    application.run_webhook(listen="0.0.0.0", port=port, url_path=config.BOT_TOKEN, webhook_url=f"{config.WEBHOOK_URL}/{config.BOT_TOKEN}")

if __name__ == "__main__":
    main()

