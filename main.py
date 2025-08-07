# main.py (نسخه نهایی و اصلاح شده)

import logging
import asyncio
from datetime import datetime, timedelta
import random
import os

from flask import Flask, request as flask_request
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler, MessageHandler,
    ContextTypes, ConversationHandler, filters
)
from telegram.constants import ParseMode

# وارد کردن فایل‌های کمکی
import config
import database

# تنظیمات لاگ‌گیری برای دیباگ
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logging.getLogger("httpx").setLevel(logging.WARNING)
logger = logging.getLogger(__name__)

# تعریف استیت‌های مکالمه
AWAITING_ID_LIKE, AWAITING_ID_INFO, AWAITING_ID_STARS = range(3)

# ==============================================================================
# راه‌اندازی اولیه برنامه
# ==============================================================================

# ساخت دیتابیس در اولین اجرا
database.init_db()

# ساخت اپلیکیشن تلگرام
application = (
    Application.builder()
    .token(config.BOT_TOKEN)
    .build()
)

# ساخت اپلیکیشن فلسک
app = Flask(__name__)

# ==============================================================================
# توابع کمکی و منوها (بدون تغییر)
# ==============================================================================
async def is_user_member_of_channels(user_id: int, context: ContextTypes.DEFAULT_TYPE) -> bool:
    for channel in config.FORCED_JOIN_CHANNELS:
        try:
            member = await context.bot.get_chat_member(chat_id=channel, user_id=user_id)
            if member.status not in ['member', 'administrator', 'creator']: return False
        except Exception as e:
            logger.error(f"Error checking membership for {channel}: {e}")
            await context.bot.send_message(chat_id=config.ADMIN_ID, text=f"خطا در بررسی عضویت کانال {channel}. مطمئن شوید ربات در این کانال ادمین است.")
            return False
    return True

def get_main_menu_keyboard():
    keyboard = [
        [InlineKeyboardButton("لایک رایگان🔥", callback_data='free_like')],
        [InlineKeyboardButton("اطلاعات اکانت📄", callback_data='account_info')],
        [InlineKeyboardButton("استارز رایگان⭐", callback_data='free_stars')],
        [InlineKeyboardButton("امتیاز روزانه🎁", callback_data='daily_bonus')],
        [InlineKeyboardButton("حساب کاربری👤", callback_data='user_profile')],
        [InlineKeyboardButton("پشتیبانی📞", callback_data='support')],
    ]
    return InlineKeyboardMarkup(keyboard)

# ==============================================================================
# Handlers (بدون تغییر)
# ==============================================================================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    referred_by_id = None
    if context.args:
        try:
            referred_by_id = int(context.args[0])
            if referred_by_id == user.id: referred_by_id = None
        except (ValueError, IndexError): referred_by_id = None
    
    db_user = database.get_or_create_user(user.id, user.first_name, referred_by=referred_by_id)

    if referred_by_id and db_user.get('referred_by') == referred_by_id:
        is_new_referral = not context.bot_data.get(f'referred_{user.id}')
        if is_new_referral:
            database.update_points(referred_by_id, 1)
            context.bot_data[f'referred_{user.id}'] = True
            try:
                referrer_db_user = database.get_or_create_user(referred_by_id, "")
                await context.bot.send_message(
                    chat_id=referred_by_id,
                    text=f"کاربر جدیدی با نام «{user.first_name}» با لینک شما وارد ربات شد و ۱ امتیاز دریافت کردید. ✅\nمجموع امتیاز شما: {referrer_db_user['points'] + 1}"
                )
            except Exception as e:
                logger.error(f"Could not send referral notification to {referred_by_id}: {e}")

    if not await is_user_member_of_channels(user.id, context):
        join_links = "\n".join(f"➡️ {ch}" for ch in config.FORCED_JOIN_CHANNELS)
        await update.message.reply_text(
            f"👋 سلام {user.first_name}!\n\n"
            f"برای استفاده از ربات، ابتدا باید در کانال‌های زیر عضو شوید:\n{join_links}\n\n"
            "پس از عضویت، دوباره دستور /start را بزنید."
        )
        return
    await update.message.reply_text("خوش آمدید! لطفا یکی از گزینه‌های زیر را انتخاب کنید:", reply_markup=get_main_menu_keyboard())

async def main_menu_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    user = query.from_user
    db_user = database.get_or_create_user(user.id, user.first_name)
    if db_user['is_banned']:
        await query.edit_message_text("شما توسط ادمین مسدود شده‌اید و امکان استفاده از ربات را ندارید.")
        return
    if not await is_user_member_of_channels(user.id, context):
        join_links = "\n".join(f"➡️ {ch}" for ch in config.FORCED_JOIN_CHANNELS)
        await query.edit_message_text(f"برای ادامه، لطفا ابتدا در کانال‌های زیر عضو شوید:\n{join_links}\n\nپس از عضویت، دوباره /start را بزنید.")
        return
    data = query.data
    if data == 'main_menu': await query.edit_message_text("منوی اصلی:", reply_markup=get_main_menu_keyboard())
    elif data == 'user_profile': await profile_handler(update, context)
    elif data == 'daily_bonus': await daily_bonus_handler(update, context)
    elif data == 'support': await support_handler(update, context)
    elif data in ['free_like', 'account_info', 'free_stars']: await service_confirmation(update, context)

async def service_confirmation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    user = query.from_user
    service = query.data
    service_map = {'free_like': {'cost': 1, 'name': 'لایک رایگان🔥'}, 'account_info': {'cost': 1, 'name': 'اطلاعات اکانت📄'}, 'free_stars': {'cost': 3, 'name': 'استارز رایگان⭐'}}
    cost = service_map[service]['cost']
    name = service_map[service]['name']
    db_user = database.get_or_create_user(user.id, user.first_name)
    if db_user['points'] < cost:
        bot_username = (await context.bot.get_me()).username
        referral_link = f"https://t.me/{bot_username}?start={user.id}"
        await query.edit_message_text(f"❌ امتیاز شما کافی نیست!\n\nبرای دسترسی به بخش «{name}» به {cost} امتیاز نیاز دارید.\nامتیاز فعلی شما: {db_user['points']}\n\nبا استفاده از لینک زیر و دعوت دوستانتان، به ازای هر نفر ۱ امتیاز بگیرید:\n`{referral_link}`", parse_mode=ParseMode.MARKDOWN, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("بازگشت", callback_data='main_menu')]]))
    else:
        keyboard = [[InlineKeyboardButton("✅ تایید و کسر امتیاز", callback_data=f'confirm_{service}')], [InlineKeyboardButton("بازگشت ↪️", callback_data='main_menu')]]
        await query.edit_message_text(f"شما در حال استفاده از بخش «{name}» هستید.\nهزینه این بخش {cost} امتیاز است. آیا مطمئن هستید؟", reply_markup=InlineKeyboardMarkup(keyboard))

async def start_service_conversation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    user = query.from_user
    service = query.data.split('_')[1]
    service_map = {'free_like': {'cost': 1, 'state': AWAITING_ID_LIKE, 'name': 'لایک رایگان🔥'}, 'account_info': {'cost': 1, 'state': AWAITING_ID_INFO, 'name': 'اطلاعات اکانت📄'}, 'free_stars': {'cost': 3, 'state': AWAITING_ID_STARS, 'name': 'استارز رایگان⭐'}}
    cost = service_map[service]['cost']
    state = service_map[service]['state']
    context.user_data['conversation_state'] = service_map[service]['name']
    database.update_points(user.id, -cost)
    await query.edit_message_text("لطفا آیدی عددی بازی خود را ارسال کنید:")
    return state

async def receive_game_id(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = update.effective_user
    game_id = update.message.text
    state_name = context.user_data.get('conversation_state', 'نا مشخص')
    forward_text = f"درخواست جدید دریافت شد:\nکاربر: {user.first_name} ({user.id})\nآیدی ارسال شده: {game_id}\nنوع درخواست: {state_name}"
    await context.bot.send_message(chat_id=config.ADMIN_ID, text=forward_text)
    reply_text = "سفارش شما در حال بررسی است. صبور باشید. ⏳" if state_name == 'استارز رایگان⭐' else "درخواست به سرور ارسال شد✅ صبور باشید."
    sent_message = await update.message.reply_text(reply_text)
    if config.SECONDARY_ERROR_ENABLED and state_name != 'استارز رایگان⭐':
        await asyncio.sleep(1)
        await sent_message.reply_text(config.SECONDARY_ERROR_MESSAGE)
    context.user_data.clear()
    return ConversationHandler.END

async def profile_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user = query.from_user if query else update.effective_user
    if query: await query.answer()
    db_user = database.get_or_create_user(user.id, user.first_name)
    bot_username = (await context.bot.get_me()).username
    referral_link = f"https://t.me/{bot_username}?start={user.id}"
    profile_text = f"👤 **حساب کاربری شما**\n\n🏷️ نام: {db_user['first_name']}\n🆔 آیدی عددی: `{user.id}`\n⭐️ امتیاز: {db_user['points']}\n\n🔗 لینک دعوت شما:\n`{referral_link}`"
    keyboard = [[InlineKeyboardButton("بازگشت ↪️", callback_data='main_menu')]]
    if query: await query.edit_message_text(profile_text, parse_mode=ParseMode.MARKDOWN, reply_markup=InlineKeyboardMarkup(keyboard))
    else: await update.message.reply_text(profile_text, parse_mode=ParseMode.MARKDOWN, reply_markup=InlineKeyboardMarkup(keyboard))

async def daily_bonus_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    user = query.from_user
    db_user = database.get_or_create_user(user.id, user.first_name)
    now = datetime.now()
    if db_user['last_daily_claim']:
        last_claim_time = datetime.fromisoformat(db_user['last_daily_claim'])
        if now - last_claim_time < timedelta(hours=24):
            remaining_time = (last_claim_time + timedelta(hours=24)) - now
            hours, rem = divmod(remaining_time.seconds, 3600)
            minutes, _ = divmod(rem, 60)
            await query.edit_message_text(f"شما قبلا امتیاز روزانه خود را دریافت کرده‌اید.\nزمان باقی‌مانده تا دریافت بعدی: {hours} ساعت و {minutes} دقیقه", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("بازگشت", callback_data='main_menu')]]))
            return
    bonus_points = random.randint(1, 5)
    database.update_points(user.id, bonus_points)
    database.set_daily_claim(user.id)
    await query.edit_message_text(f"🎁 تبریک! شما {bonus_points} امتیاز روزانه دریافت کردید.\nموجودی فعلی: {db_user['points'] + bonus_points} امتیاز", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("بازگشت", callback_data='main_menu')]]))

async def support_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    support_text = f"📞 **بخش پشتیبانی**\n\nدر صورت بروز هرگونه مشکل یا سوال، می‌توانید با آیدی‌های زیر در تماس باشید:\n\n- مالک ربات: {config.OWNER_ID}\n- ادمین پشتیبانی: {config.SUPPORT_ID}"
    keyboard = [[InlineKeyboardButton("بازگشت ↪️", callback_data='main_menu')]]
    await query.edit_message_text(support_text, reply_markup=InlineKeyboardMarkup(keyboard))

async def cancel_conversation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("عملیات لغو شد.", reply_markup=get_main_menu_keyboard())
    context.user_data.clear()
    return ConversationHandler.END

# Admin Handlers (بدون تغییر)
async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_user.id != config.ADMIN_ID: return
    error_status = "فعال ✅" if config.SECONDARY_ERROR_ENABLED else "غیرفعال ❌"
    keyboard = [[InlineKeyboardButton("آمار ربات 📊", callback_data='admin_stats')], [InlineKeyboardButton("لیست کاربران 👥", callback_data='admin_users')], [InlineKeyboardButton(f"پیام خطای ثانویه ({error_status})", callback_data='admin_toggle_error')]]
    text = "به پنل مدیریت خوش آمدید.\nدستورات مدیریتی:\n/ban `USER_ID`\n/unban `USER_ID`\n/addpoints `USER_ID` `AMOUNT`\n/removepoints `USER_ID` `AMOUNT`"
    await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.MARKDOWN)

async def admin_callback_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != config.ADMIN_ID: return
    query = update.callback_query
    await query.answer()
    data = query.data
    if data == 'admin_stats':
        count = database.get_user_count()
        await query.edit_message_text(f"تعداد کل کاربران ربات: {count} نفر")
    elif data == 'admin_users':
        users = database.get_all_users()
        if not users: await query.edit_message_text("هیچ کاربری در ربات ثبت‌نام نکرده است."); return
        user_list = "لیست کاربران:\n\n"
        for user_data in users: user_list += f"👤 نام: {user_data[1]}\n🆔 آیدی: `{user_data[0]}`\n⭐️ امتیاز: {user_data[2]}\n\n"
        if len(user_list) > 4000:
            with open("user_list.txt", "w", encoding="utf-8") as f: f.write(user_list)
            await context.bot.send_document(chat_id=config.ADMIN_ID, document=open("user_list.txt", "rb"))
        else: await query.edit_message_text(user_list, parse_mode=ParseMode.MARKDOWN)
    elif data == 'admin_toggle_error':
        config.SECONDARY_ERROR_ENABLED = not config.SECONDARY_ERROR_ENABLED
        await query.message.delete()
        await admin_panel(update, context)

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
        await update.message.reply_text(f"کاربر با آیدی {user_id} با موفقیت از مسدودیت خارج شد.")
    except (IndexError, ValueError): await update.message.reply_text("استفاده صحیح: /unban <USER_ID>")
async def add_points(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != config.ADMIN_ID: return
    try:
        user_id = int(context.args[0]); amount = int(context.args[1])
        database.update_points(user_id, amount)
        await update.message.reply_text(f"{amount} امتیاز به کاربر {user_id} اضافه شد.")
    except (IndexError, ValueError): await update.message.reply_text("استفاده صحیح: /addpoints <USER_ID> <AMOUNT>")
async def remove_points(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != config.ADMIN_ID: return
    try:
        user_id = int(context.args[0]); amount = int(context.args[1])
        database.update_points(user_id, -amount)
        await update.message.reply_text(f"{amount} امتیاز از کاربر {user_id} کسر شد.")
    except (IndexError, ValueError): await update.message.reply_text("استفاده صحیح: /removepoints <USER_ID> <AMOUNT>")

# ==============================================================================
# ثبت Handler ها و Webhook
# ==============================================================================

# مکالمه برای دریافت آیدی بازی
service_conv_handler = ConversationHandler(
    entry_points=[CallbackQueryHandler(start_service_conversation, pattern='^confirm_.*')],
    states={
        AWAITING_ID_LIKE: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_game_id)],
        AWAITING_ID_INFO: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_game_id)],
        AWAITING_ID_STARS: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_game_id)],
    },
    fallbacks=[CommandHandler('cancel', cancel_conversation)],
    per_message=False,
)

# ثبت Handler ها در اپلیکیشن تلگرام
application.add_handler(CommandHandler("start", start))
application.add_handler(CallbackQueryHandler(main_menu_callback, pattern='^(?!admin_).*$'))
application.add_handler(service_conv_handler)
application.add_handler(CommandHandler("admin", admin_panel))
application.add_handler(CallbackQueryHandler(admin_callback_handler, pattern='^admin_.*'))
application.add_handler(CommandHandler("ban", ban_user))
application.add_handler(CommandHandler("unban", unban_user))
application.add_handler(CommandHandler("addpoints", add_points))
application.add_handler(CommandHandler("removepoints", remove_points))

# مسیر Flask برای دریافت آپدیت‌ها از تلگرام
@app.route(f"/{config.BOT_TOKEN}", methods=["POST"])
async def telegram_webhook():
    update_json = flask_request.get_json(force=True)
    update = Update.de_json(update_json, application.bot)
    await application.process_update(update)
    return {"ok": True}

# مسیر ساده برای بررسی سلامت سرویس
@app.route("/")
def index():
    return "Bot is running!"

# این تابع در زمان استقرار، ربات را آماده و وب‌هوک را تنظیم می‌کند
async def setup_bot():
    logger.info("Initializing application...")
    await application.initialize()  # <--- **خط مهم و اصلاح شده**
    
    logger.info("Setting webhook...")
    await application.bot.set_webhook(
        url=f"{config.WEBHOOK_URL}/{config.BOT_TOKEN}",
        allowed_updates=Update.ALL_TYPES
    )
    logger.info("Webhook set successfully")

# در زمان شروع برنامه، یکبار تابع setup_bot را اجرا می‌کنیم
with app.app_context():
    loop = asyncio.get_event_loop()
    if loop.is_running():
        loop.create_task(setup_bot())
    else:
        asyncio.run(setup_bot())

