# main.py (نسخه نهایی کامل - با تمام دستورات ادمین)

import logging
import asyncio
from datetime import datetime, timedelta
import random
import os

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

AWAITING_ID_LIKE, AWAITING_ID_INFO, AWAITING_ID_STARS = range(3)

SERVICE_NAMES = {'like': 'free_like', 'info': 'account_info', 'stars': 'free_stars'}

# ==============================================================================
# کیبوردها
# ==============================================================================
def get_main_reply_keyboard():
    keyboard = [
        ['لایک رایگان🔥', 'اطلاعات اکانت📄'],
        ['استارز رایگان⭐', 'امتیاز روزانه🎁'],
        ['حساب کاربری👤', 'پشتیبانی📞']
    ]
    return ReplyKeyboardMarkup(keyboard, resize_keyboard=True)

# ==============================================================================
# توابع کمکی
# ==============================================================================
async def check_user_preconditions(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    user = update.effective_user
    db_user = database.get_or_create_user(user.id, user.first_name)
    if db_user['is_banned']:
        await update.message.reply_text("شما توسط ادمین مسدود شده‌اید و امکان استفاده از ربات را ندارید.")
        return False
    
    for channel in config.FORCED_JOIN_CHANNELS:
        try:
            member = await context.bot.get_chat_member(chat_id=channel, user_id=user.id)
            if member.status not in ['member', 'administrator', 'creator']:
                join_links = "\n".join(f"➡️ {ch}" for ch in config.FORCED_JOIN_CHANNELS)
                await update.message.reply_text(f"برای استفاده از ربات، ابتدا باید در کانال‌های زیر عضو شوید:\n{join_links}\n\nپس از عضویت، دوباره تلاش کنید.")
                return False
        except Exception as e:
            logger.error(f"Error checking membership for {channel} and user {user.id}: {e}")
            if "Chat not found" in str(e):
                await context.bot.send_message(chat_id=config.ADMIN_ID, text=f"خطا: کانال {channel} پیدا نشد یا ربات در آن ادمین نیست.")
            await update.message.reply_text("خطایی در بررسی عضویت کانال رخ داد. لطفاً با پشتیبانی تماس بگیرید.")
            return False
    return True

# ==============================================================================
# Handlers - بخش اصلی منطق ربات
# ==============================================================================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    # کد رفرال ...
    database.get_or_create_user(user.id, user.first_name)
    await update.message.reply_text(
        f"سلام {user.first_name}! به ربات ما خوش آمدید.",
        reply_markup=get_main_reply_keyboard()
    )

async def handle_service_request(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await check_user_preconditions(update, context): return
    
    service_map = {
        'لایک رایگان🔥': 'free_like',
        'اطلاعات اکانت📄': 'account_info',
        'استارز رایگان⭐': 'free_stars'
    }
    service_key = service_map.get(update.message.text)
    
    cost = int(database.get_setting(f'cost_{service_key}', '1'))
    
    keyboard = [
        [InlineKeyboardButton(f"✅ تایید و کسر {cost} امتیاز", callback_data=f'confirm_{service_key}')],
        [InlineKeyboardButton("انصراف ↪️", callback_data='cancel_service')]
    ]
    await update.message.reply_text(
        f"شما در حال استفاده از بخش «{update.message.text}» هستید.\n"
        f"هزینه این بخش {cost} امتیاز است. آیا مطمئن هستید؟",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )

async def start_service_conversation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    user = query.from_user
    
    service_key = query.data.split('_')[1]
    cost = int(database.get_setting(f'cost_{service_key}', '1'))
    db_user = database.get_or_create_user(user.id, user.first_name)

    if db_user['points'] < cost:
        bot_username = (await context.bot.get_me()).username
        referral_link = f"https://t.me/{bot_username}?start={user.id}"
        await query.edit_message_text(
            f"❌ امتیاز شما کافی نیست!\n\n"
            f"امتیاز فعلی شما: {db_user['points']}\n"
            f"با استفاده از لینک زیر و دعوت دوستانتان، به ازای هر نفر ۱ امتیاز بگیرید:\n`{referral_link}`",
            parse_mode=ParseMode.MARKDOWN
        )
        return ConversationHandler.END

    database.update_points(user.id, -cost)
    await query.edit_message_text(f"امتیاز شما کسر شد. لطفاً آیدی عددی بازی خود را ارسال کنید:")
    
    state_map = {'free_like': AWAITING_ID_LIKE, 'account_info': AWAITING_ID_INFO, 'free_stars': AWAITING_ID_STARS}
    context.user_data['service_name'] = service_key
    return state_map[service_key]

async def cancel_service(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    await query.edit_message_text("عملیات لغو شد.")

async def receive_game_id(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = update.effective_user
    game_id = update.message.text
    service_name_map = {'free_like': 'لایک رایگان🔥', 'account_info': 'اطلاعات اکانت📄', 'free_stars': 'استارز رایگان⭐'}
    service_display_name = service_name_map.get(context.user_data.get('service_name', 'نا مشخص'))
    
    forward_text = f"درخواست جدید:\n کاربر: {user.first_name} ({user.id})\n آیدی ارسالی: {game_id}\n نوع: {service_display_name}"
    await context.bot.send_message(chat_id=config.ADMIN_ID, text=forward_text)
    
    reply_text = "سفارش شما در حال بررسی است. صبور باشید." if context.user_data.get('service_name') == 'free_stars' else "درخواست به سرور ارسال شد. صبور باشید."
    await update.message.reply_text(reply_text)
    
    if config.SECONDARY_ERROR_ENABLED and context.user_data.get('service_name') != 'free_stars':
        await update.message.reply_text(config.SECONDARY_ERROR_MESSAGE)

    context.user_data.clear()
    return ConversationHandler.END

async def profile_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_user_preconditions(update, context): return
    user = update.effective_user
    db_user = database.get_or_create_user(user.id, user.first_name)
    bot_username = (await context.bot.get_me()).username
    referral_link = f"https://t.me/{bot_username}?start={user.id}"
    profile_text = f"👤 **حساب کاربری شما**\n\n🏷️ نام: {db_user['first_name']}\n🆔 آیدی عددی: `{user.id}`\n⭐️ امتیاز: {db_user['points']}\n\n🔗 لینک دعوت شما:\n`{referral_link}`"
    await update.message.reply_text(profile_text, parse_mode=ParseMode.MARKDOWN)

async def daily_bonus_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_user_preconditions(update, context): return
    user = update.effective_user
    db_user = database.get_or_create_user(user.id, user.first_name)
    now = datetime.now()
    if db_user['last_daily_claim']:
        last_claim_time = datetime.fromisoformat(db_user['last_daily_claim'])
        if now - last_claim_time < timedelta(hours=24):
            remaining_time = (last_claim_time + timedelta(hours=24)) - now
            hours, rem = divmod(remaining_time.seconds, 3600)
            minutes, _ = divmod(rem, 60)
            await update.message.reply_text(f"شما قبلا امتیاز روزانه خود را دریافت کرده‌اید.\nزمان باقی‌مانده: {hours} ساعت و {minutes} دقیقه")
            return
    bonus_points = random.randint(1, 5)
    database.update_points(user.id, bonus_points)
    database.set_daily_claim(user.id)
    await update.message.reply_text(f"🎁 تبریک! شما {bonus_points} امتیاز روزانه دریافت کردید.\nموجودی فعلی: {db_user['points'] + bonus_points} امتیاز")

async def support_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(f"📞 پشتیبانی\n\n- مالک ربات: {config.OWNER_ID}\n- ادمین پشتیبانی: {config.SUPPORT_ID}")

# ==============================================================================
# Admin Handlers
# ==============================================================================
async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_user.id != config.ADMIN_ID: return
    admin_keyboard = [[InlineKeyboardButton("آمار ربات 📊", callback_data='admin_stats')], [InlineKeyboardButton("تنظیم هزینه‌ها ⚙️", callback_data='admin_costs')]]
    await update.message.reply_text("به پنل مدیریت خوش آمدید.", reply_markup=InlineKeyboardMarkup(admin_keyboard))

async def admin_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != config.ADMIN_ID: return
    query = update.callback_query
    await query.answer()
    if query.data == 'admin_stats':
        await query.edit_message_text(f"تعداد کل کاربران ربات: {database.get_user_count()} نفر")
    elif query.data == 'admin_costs':
        cost_like = database.get_setting('cost_free_like', '1')
        cost_info = database.get_setting('cost_account_info', '1')
        cost_stars = database.get_setting('cost_free_stars', '3')
        text = f"⚙️ **تنظیمات هزینه‌ها**\n\n- لایک رایگان: {cost_like}\n- اطلاعات اکانت: {cost_info}\n- استارز رایگان: {cost_stars}\n\nبرای تغییر: `/setcost <service> <amount>`\nمثال: `/setcost like 2`\nسرویس‌ها: `like`, `info`, `stars`"
        await query.edit_message_text(text, parse_mode=ParseMode.MARKDOWN)

async def set_cost(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != config.ADMIN_ID: return
    try:
        service_short_name = context.args[0].lower()
        amount = int(context.args[1])
        if service_short_name not in SERVICE_NAMES:
            await update.message.reply_text("نام سرویس نامعتبر است. از `like`, `info`, `stars` استفاده کنید.")
            return
        db_key = f"cost_{SERVICE_NAMES[service_short_name]}"
        database.set_setting(db_key, str(amount))
        await update.message.reply_text(f"✅ هزینه «{service_short_name}» با موفقیت به {amount} امتیاز تغییر کرد.")
    except (IndexError, ValueError):
        await update.message.reply_text("استفاده صحیح: `/setcost <service> <amount>`")

async def ban_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != config.ADMIN_ID: return
    try:
        user_id = int(context.args[0])
        database.set_ban_status(user_id, True)
        await update.message.reply_text(f"کاربر با آیدی {user_id} با موفقیت مسدود شد.")
    except (IndexError, ValueError): await update.message.reply_text("استفاده صحیح: /ban <USER_ID>")

async def unban_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != config.ADMIN_ID: return
    try:
        user_id = int(context.args[0])
        database.set_ban_status(user_id, False)
        await update.message.reply_text(f"کاربر با آیدی {user_id} از مسدودیت خارج شد.")
    except (IndexError, ValueError): await update.message.reply_text("استفاده صحیح: /unban <USER_ID>")

async def add_points(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != config.ADMIN_ID: return
    try:
        user_id = int(context.args[0])
        amount = int(context.args[1])
        database.update_points(user_id, amount)
        await update.message.reply_text(f"{amount} امتیاز به کاربر {user_id} اضافه شد.")
    except (IndexError, ValueError): await update.message.reply_text("استفاده صحیح: /addpoints <USER_ID> <AMOUNT>")

async def remove_points(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != config.ADMIN_ID: return
    try:
        user_id = int(context.args[0])
        amount = int(context.args[1])
        database.update_points(user_id, -amount)
        await update.message.reply_text(f"{amount} امتیاز از کاربر {user_id} کسر شد.")
    except (IndexError, ValueError): await update.message.reply_text("استفاده صحیح: /removepoints <USER_ID> <AMOUNT>")

# ==============================================================================
# تابع اصلی و راه‌اندازی
# ==============================================================================
def main() -> None:
    database.init_db()
    application = Application.builder().token(config.BOT_TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(start_service_conversation, pattern='^confirm_.*')],
        states={
            AWAITING_ID_LIKE: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_game_id)],
            AWAITING_ID_INFO: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_game_id)],
            AWAITING_ID_STARS: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_game_id)],
        },
        fallbacks=[CallbackQueryHandler(cancel_service, pattern='^cancel_service$')],
    )
    
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.Regex('^لایک رایگان🔥$|^اطلاعات اکانت📄$|^استارز رایگان⭐$'), handle_service_request))
    application.add_handler(MessageHandler(filters.Regex('^حساب کاربری👤$'), profile_handler))
    application.add_handler(MessageHandler(filters.Regex('^امتیاز روزانه🎁$'), daily_bonus_handler))
    application.add_handler(MessageHandler(filters.Regex('^پشتیبانی📞$'), support_handler))
    
    application.add_handler(conv_handler)
    application.add_handler(CallbackQueryHandler(cancel_service, pattern='^cancel_service$'))

    # ثبت دستورات ادمین
    application.add_handler(CommandHandler("admin", admin_panel))
    application.add_handler(CallbackQueryHandler(admin_callback_handler, pattern='^admin_.*'))
    application.add_handler(CommandHandler("setcost", set_cost))
    
    # ******** این خطوط در نسخه قبل فراموش شده بود ********
    application.add_handler(CommandHandler("ban", ban_user))
    application.add_handler(CommandHandler("unban", unban_user))
    application.add_handler(CommandHandler("addpoints", add_points))
    application.add_handler(CommandHandler("removepoints", remove_points))
    # ******************************************************

    port = int(os.environ.get('PORT', 8443))
    application.run_webhook(
        listen="0.0.0.0",
        port=port,
        url_path=config.BOT_TOKEN,
        webhook_url=f"{config.WEBHOOK_URL}/{config.BOT_TOKEN}"
    )

if __name__ == "__main__":
    main()
