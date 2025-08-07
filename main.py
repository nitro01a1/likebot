import logging
import os
from datetime import datetime, timedelta
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

logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(name)

# --- تعریف استیت‌ها و دیکشنری‌ها ---
AWAITING_ID, AWAITING_STARS_DETAILS = 0, 1
AWAITING_USER_ID_MANAGE, AWAITING_COST_AMOUNT = range(2, 4)

SERVICE_MAP = {
    'لایک رایگان🔥': 'free_like',
    'اطلاعات اکانت📄': 'account_info',
    'استارز رایگان⭐': 'free_stars'
}
SERVICE_NAME_MAP_FA = {v: k for k, v in SERVICE_MAP.items()}

# ==============================================================================
# کیبورد و توابع کمکی
# ==============================================================================
def get_main_reply_keyboard():
    return ReplyKeyboardMarkup([['لایک رایگان🔥', 'اطلاعات اکانت📄'], ['استارز رایگان⭐', 'امتیاز روزانه🎁'], ['حساب کاربری👤', 'پشتیبانی📞']], resize_keyboard=True)

async def check_user_preconditions(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
    user = update.effective_user
    
    bot_is_on = database.get_setting('bot_status', 'true') == 'true'
    if not bot_is_on and user.id != config.ADMIN_ID:
        await update.message.reply_text("🔴 در حال حاضر ربات در حال تعمیر و بروزرسانی است. لطفا بعدا تلاش کنید.")
        return False

    db_user = database.get_or_create_user(user.id, user.first_name)
    if not db_user:
        await update.message.reply_text("مشکلی در دسترسی به اطلاعات شما پیش آمد. لطفاً دوباره /start را بزنید.")
        return False
    if db_user['is_banned']:
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

# ==============================================================================
# جریان اصلی کار کاربر
# ==============================================================================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    bot_is_on = database.get_setting('bot_status', 'true') == 'true'
    if not bot_is_on and user.id != config.ADMIN_ID:
        await update.message.reply_text("🔴 در حال حاضر ربات در حال تعمیر و بروزرسانی است. لطفا بعدا تلاش کنید.")
        return

    is_new_user = not database.get_or_create_user(user.id, user.first_name)
    if context.args and is_new_user:
        try:
            referrer_id = int(context.args[0])
            if referrer_id != user.id:
                database.get_or_create_user(user.id, user.first_name, referred_by=referrer_id)
                database.update_points(referrer_id, 1)
                await context.bot.send_message(chat_id=referrer_id, text="یک کاربر جدید از طریق لینک شما وارد ربات شد و ۱ امتیاز دریافت کردید!")
        except Exception as e:
            logger.error(f"Referral error: {e}")
    await update.message.reply_text(f"سلام {user.first_name}! به ربات ما خوش آمدید.", reply_markup=get_main_reply_keyboard())

async def service_entry_point(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not await check_user_preconditions(update, context): return ConversationHandler.END

    service_key = SERVICE_MAP.get(update.message.text)
    cost = int(database.get_setting(f'cost_{service_key}', '1'))
    user = update.effective_user
    db_user = database.get_or_create_user(user.id, user.first_name)

    if db_user['points'] < cost:
        await update.message.reply_text(f"❌ امتیاز شما برای «{update.message.text}» کافی نیست! (نیاز به {cost} امتیاز)")
        return ConversationHandler.END

    context.user_data['service_key'] = service_key
    context.user_data['cost'] = cost
    
    database.update_points(user.id, -cost)
    new_points = database.get_or_create_user(user.id, user.first_name)['points']

    if service_key == 'free_stars':
        await update.message.reply_text(
            f"✅ {cost} امتیاز از شما کسر شد. موجودی جدید: {new_points} امتیاز.\n\n"
            "لطفا ایدی عددی حساب کاربری خود در همین ربات، لینک کانال و پستی که می‌خواهید برای آن استارز زده شود را در قالب یک متن واحد برای ما ارسال کنید.\n\n"
            "⚠️ مهم: در صورت عدم ارسال صحیح اطلاعات، سفارش شما انجام نخواهد شد.\n\n"
            "برای انصراف /cancel را بزنید."
        )
        return AWAITING_STARS_DETAILS
    else:
        await update.message.reply_text(
            f"✅ {cost} امتیاز از شما کسر شد. موجودی جدید: {new_points} امتیاز.\n\n"
            f"برای تکمیل سفارش «{update.message.text}»، آیدی عددی خود را ارسال کنید. برای انصراف /cancel را بزنید."
        )
        return AWAITING_ID

async def receive_stars_details_and_process(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = update.effective_user; details_text = update.message.text
    service_key = context.user_data.get('service_key')
    service_display_name = SERVICE_NAME_MAP_FA.get(service_key, "سرویس نامشخص")

    forward_text = (f"درخواست جدید (استارز):\n" f"کاربر: {user.first_name} ({user.id})\n" f"نوع: {service_display_name}\n\n" f"جزئیات ارسالی:\n" f"{details_text}")
    await context.bot.send_message(chat_id=config.ADMIN_ID, text=forward_text)
    await update.message.reply_text("✅ سفارش شما با موفقیت ثبت و در صف بررسی قرار گرفت.", reply_markup=get_main_reply_keyboard())
    
    context.user_data.clear()
    return ConversationHandler.END

# <<< MODIFIED: این تابع برای اعتبارسنجی ورودی و تغییر پیام ثانویه آپدیت شد
async def receive_id_and_process(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = update.effective_user
    game_id = update.message.text
    service_key = context.user_data.get('service_key')

    # مرحله ۱: اعتبارسنجی ورودی
    if not game_id.isdigit():
        await update.message.reply_text("❌ ورودی نامعتبر است. لطفاً فقط عدد وارد کنید.")
        return AWAITING_ID # کاربر را در همین مرحله نگه می‌دارد تا دوباره تلاش کند

    if not (5 <= len(game_id) <= 14):
        await update.message.reply_text("❌ تعداد ارقام وارد شده باید بین ۵ تا ۱۴ رقم باشد. لطفاً مجدداً تلاش کنید.")
        return AWAITING_ID # کاربر را در همین مرحله نگه می‌دارد

    # مرحله ۲: ارسال به ادمین و ثبت نهایی
    service_display_name = SERVICE_NAME_MAP_FA.get(service_key, "سرویس نامشخص")
    forward_text = f"درخواست جدید:\n کاربر: {user.first_name} ({user.id})\n نوع: {service_display_name}\n آیدی ارسالی: {game_id}"
    await context.bot.send_message(chat_id=config.ADMIN_ID, text=forward_text)

    reply_text = "درخواست شما با موفقیت ثبت شد."
    sent_message = await update.message.reply_text(f"{reply_text}\nامتیاز شما: {database.get_or_create_user(user.id, user.first_name)['points']}")

    # مرحله ۳: ارسال خطای ثانویه فقط برای سرویس‌های مشخص شده
    is_secondary_error_enabled = database.get_setting('secondary_error_enabled', 'false') == 'true'
    if is_secondary_error_enabled and service_key in ['free_like', 'account_info']:
        error_message = database.get_setting('secondary_error_message')
        await sent_message.reply_text(error_message)

    context.user_data.clear()
    return ConversationHandler.END

# <<< MODIFIED: این تابع برای بازگرداندن امتیاز در صورت لغو آپدیت شد
async def cancel_conversation(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    cost = context.user_data.get('cost')
    if cost:
        user_id = update.effective_user.id
        database.update_points(user_id, cost)
        await update.message.reply_text(f"عملیات لغو شد و {cost} امتیاز به شما بازگردانده شد.", reply_markup=get_main_reply_keyboard())
    else:
        await update.message.reply_text("عملیات لغو شد.", reply_markup=get_main_reply_keyboard())
    
    context.user_data.clear()
    return ConversationHandler.END

async def profile_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_user_preconditions(update, context): return
    user = update.effective_user
    db_user = database.get_or_create_user(user.id, user.first_name)
    bot_username = (await context.bot.get_me()).username
    referral_link = f"https://t.me/{bot_username}?start={user.id}"
    profile_text = f"👤 حساب کاربری شما\n\n🏷️ نام: {db_user['first_name']}\n🆔 آیدی: {user.id}\n⭐️ امتیاز: {db_user['points']}\n\n🔗 لینک دعوت شما:\n{referral_link}"
    await update.message.reply_text(profile_text, parse_mode=ParseMode.MARKDOWN)

async def daily_bonus_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_user_preconditions(update, context): return
    user = update.effective_user; db_user = database.get_or_create_user(user.id, user.first_name)
    now = datetime.now()
    if db_user['last_daily_claim']:
        last_claim_time = datetime.fromisoformat(db_user['last_daily_claim'])
        if now - last_claim_time < timedelta(hours=24):
            remaining_time = (last_claim_time + timedelta(hours=24)) - now
            hours, rem = divmod(remaining_time.seconds, 3600); minutes, _ = divmod(rem, 60)
            await update.message.reply_text(f"شما قبلا امتیاز روزانه خود را دریافت کرده‌اید.\nزمان باقی‌مانده: {hours} ساعت و {minutes} دقیقه")
            return
    bonus_points = random.randint(1, 5)
    database.update_points(user.id, bonus_points); database.set_daily_claim(user.id)
    await update.message.reply_text(f"🎁 تبریک! شما {bonus_points} امتیاز روزانه دریافت کردید.\nموجودی فعلی: {db_user['points'] + bonus_points} امتیاز")

async def support_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_user_preconditions(update, context): return
    await update.message.reply_text(f"📞 پشتیبانی\n\n- مالک ربات: {config.OWNER_ID}\n- ادمین پشتیبانی: {config.SUPPORT_ID}")

# ==============================================================================
# جریان کار ادمین
# ==============================================================================
async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_user.id != config.ADMIN_ID: return

    is_bot_on = database.get_setting('bot_status', 'true') == 'true'
    bot_status_text = "روشن 🟢" if is_bot_on else "خاموش 🔴"
    
    is_error_enabled = database.get_setting('secondary_error_enabled', 'false') == 'true'
    error_status_text = "فعال 🟢" if is_error_enabled else "غیرفعال 🔴"
    
    keyboard = [
        [InlineKeyboardButton(f"وضعیت ربات: {bot_status_text}", callback_data='toggle_bot_status')],
        [InlineKeyboardButton(f"خطای ثانویه: {error_status_text}", callback_data='toggle_secondary_error')],
        [InlineKeyboardButton("مدیریت کاربر 👤", callback_data='admin_manage_user'), InlineKeyboardButton("تنظیم هزینه‌ها ⚙️", callback_data='admin_set_costs')],
        [InlineKeyboardButton("لیست کاربران 👥", callback_data='admin_list_users')]
    ]
    text = "به پنل مدیریت خوش آمدید.\n\nراهنمای امتیازدهی دستی:\n/addpoints <USER_ID> <AMOUNT>\n/removepoints <USER_ID> <AMOUNT>"
    
    if update.callback_query:
        await update.callback_query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.MARKDOWN)
    else:
        await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.MARKDOWN)

async def toggle_bot_status_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query; await query.answer()
    is_on = database.get_setting('bot_status', 'true') == 'true'
    new_status = 'false' if is_on else 'true'
    database.set_setting('bot_status', new_status)
    await admin_panel(update, context)

async def toggle_secondary_error_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query; await query.answer()
    is_enabled = database.get_setting('secondary_error_enabled', 'false') == 'true'
    new_status = 'false' if is_enabled else 'true'
    database.set_setting('secondary_error_enabled', new_status)
    await admin_panel(update, context)

# <<< MODIFIED: این تابع برای حذف متن اضافی از پاسخ ادمین آپدیت شد
async def admin_reply_to_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != config.ADMIN_ID or not update.message.reply_to_message: return
    replied_message_text = update.message.reply_to_message.text
    match = re.search(r"کاربر: .* \((\d+)\)", replied_message_text)
    if match:
        user_id_to_reply = int(match.group(1)); admin_text = update.message.text
        try:
            # فقط متن خود ادمین ارسال می‌شود
            await context.bot.send_message(chat_id=user_id_to_reply, text=admin_text)
            await update.message.reply_text("✅ پیام شما برای کاربر ارسال شد.")
        except Exception as e:
            await update.message.reply_text(f"❌ خطا در ارسال پیام به کاربر {user_id_to_reply}: {e}")

# ... (بقیه توابع ادمین بدون تغییر باقی می‌مانند) ...
async def manage_user_entry(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query; await query.answer()
    await query.edit_message_text("لطفاً آیدی عددی کاربری که می‌خواهید مدیریت کنید را ارسال نمایید. برای لغو /cancel را بزنید.")
    return AWAITING_USER_ID_MANAGE

async def show_user_manage_options(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    try: user_id_to_manage = int(update.message.text)
    except ValueError: await update.message.reply_text("آیدی نامعتبر است."); return AWAITING_USER_ID_MANAGE
    user_info = database.get_or_create_user(user_id_to_manage, "Unknown")
    if not user_info: await update.message.reply_text("کاربری با این آیدی یافت نشد."); return ConversationHandler.END
    status = "🔴 مسدود" if user_info['is_banned'] else "🟢 فعال"
    keyboard = [[InlineKeyboardButton("بن کردن 🚫", callback_data=f"ban_{user_id_to_manage}")], [InlineKeyboardButton("آنبن کردن ✅", callback_data=f"unban_{user_id_to_manage}")]]
    await update.message.reply_text(f"کاربر: {user_info['first_name']} ({user_id_to_manage})\nوضعیت: {status}\n\nچه کاری انجام شود؟", reply_markup=InlineKeyboardMarkup(keyboard))
    return ConversationHandler.END
    
async def perform_ban_unban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query; action, user_id = query.data.split('_'); user_id = int(user_id)
    if action == "ban": database.set_ban_status(user_id, True); await query.edit_message_text(f"کاربر {user_id} مسدود شد.")
    elif action == "unban": database.set_ban_status(user_id, False); await query.edit_message_text(f"کاربر {user_id} از مسدودیت خارج شد.")

async def set_costs_entry(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query; await query.answer()
    costs = {k: database.get_setting(f'cost_{k}', '1') for k in SERVICE_NAME_MAP_FA.keys()}
    keyboard = [[InlineKeyboardButton(f"{SERVICE_NAME_MAP_FA[k]} ({v} امتیاز)", callback_data=f'setcost_{k}')] for k, v in costs.items()]
    await query.edit_message_text("هزینه کدام بخش را می‌خواهید تغییر دهید؟", reply_markup=InlineKeyboardMarkup(keyboard))

async def ask_for_new_cost(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query; await query.answer()
    service_key = query.data.split('_')[1]
    context.user_data['service_to_set_cost'] = service_key
    service_name_fa = SERVICE_NAME_MAP_FA.get(service_key, "این سرویس")
    await query.edit_message_text(f"لطفاً هزینه جدید را برای «{service_name_fa}» به صورت یک عدد ارسال کنید. برای لغو /cancel را بزنید.")
    return AWAITING_COST_AMOUNT

async def set_new_cost(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    try:
        new_cost = int(update.message.text); service_key = context.user_data.get('service_to_set_cost')
        database.set_setting(f"cost_{service_key}", str(new_cost))
        await update.message.reply_text(f"هزینه با موفقیت به {new_cost} تغییر یافت.", reply_markup=get_main_reply_keyboard())
    except (ValueError, TypeError): await update.message.reply_text("مقدار نامعتبر است.")
    context.user_data.clear(); return ConversationHandler.END
    
async def add_points(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != config.ADMIN_ID: return
    try: user_id = int(context.args[0]); amount = int(context.args[1]); database.update_points(user_id, amount); await update.message.reply_text(f"{amount} امتیاز به کاربر {user_id} اضافه شد.")
    except (IndexError, ValueError): await update.message.reply_text("استفاده: /addpoints <USER_ID> <AMOUNT>")

async def remove_points(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != config.ADMIN_ID: return
    try: user_id = int(context.args[0]); amount = int(context.args[1]); database.update_points(user_id, -amount); await update.message.reply_text(f"{amount} امتیاز از کاربر {user_id} کسر شد.")
    except (IndexError, ValueError): await update.message.reply_text("استفاده: /removepoints <USER_ID> <AMOUNT>")

async def list_users_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query; await query.answer()
    users = database.get_all_users()
    if not users: await query.edit_message_text("هیچ کاربری ثبت‌نام نکرده است."); return
    user_list = "لیست کاربران:\n\n"
    for user_data in users: user_list += f"👤 نام: {user_data[1]}\n🆔 آیدی: {user_data[0]}\n⭐️ امتیاز: {user_data[2]}\n\n"
    await query.edit_message_text(user_list, parse_mode=ParseMode.MARKDOWN)

# ==============================================================================
# تابع اصلی و راه‌اندازی
# ==============================================================================
def main() -> None:
    database.init_db()
    if not database.get_setting('bot_status'):
        database.set_setting('bot_status', 'true')
    if not database.get_setting('secondary_error_enabled'):
        database.set_setting('secondary_error_enabled', 'false')
    # <<< MODIFIED: متن پیام ثانویه به درخواست شما تغییر کرد
    if not database.get_setting('secondary_error_message'):
        database.set_setting('secondary_error_message', "خطا❌در اتصال به سرور مشکلی پیش امد. با ادمین تماس بگیرید @likeadminx7")

    application = Application.builder().token(config.BOT_TOKEN).build()

    user_conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex(f"^({'|'.join(SERVICE_MAP.keys())})$"), service_entry_point)],
        states={
            AWAITING_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_id_and_process)],
            AWAITING_STARS_DETAILS: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_stars_details_and_process)]
        },
        fallbacks=[CommandHandler('cancel', cancel_conversation)], per_user=True)
    
    manage_user_conv = ConversationHandler(entry_points=[CallbackQueryHandler(manage_user_entry, pattern='^admin_manage_user$')], states={AWAITING_USER_ID_MANAGE: [MessageHandler(filters.TEXT & ~filters.COMMAND, show_user_manage_options)]}, fallbacks=[CommandHandler('cancel', cancel_conversation)], per_user=True)
    set_cost_conv = ConversationHandler(entry_points=[CallbackQueryHandler(ask_for_new_cost, pattern='^setcost_.*$')], states={AWAITING_COST_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, set_new_cost)]}, fallbacks=[CommandHandler('cancel', cancel_conversation)], per_user=True)

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("admin", admin_panel))
    application.add_handler(user_conv)
    application.add_handler(manage_user_conv)
    application.add_handler(set_cost_conv)
    application.add_handler(MessageHandler(filters.Regex('^حساب کاربری👤$'), profile_handler))
    application.add_handler(MessageHandler(filters.Regex('^امتیاز روزانه🎁$'), daily_bonus_handler))
    application.add_handler(MessageHandler(filters.Regex('^پشتیبانی📞$'), support_handler))
    
    application.add_handler(CallbackQueryHandler(toggle_bot_status_callback, pattern='^toggle_bot_status$'))
    application.add_handler(CallbackQueryHandler(toggle_secondary_error_callback, pattern='^toggle_secondary_error$'))
    application.add_handler(MessageHandler(filters.REPLY & filters.User(config.ADMIN_ID), admin_reply_to_user))
    
    application.add_handler(CallbackQueryHandler(perform_ban_unban, pattern=r'^(ban|unban)_'))
    application.add_handler(CallbackQueryHandler(set_costs_entry, pattern='^admin_set_costs$'))
    application.add_handler(CallbackQueryHandler(list_users_callback, pattern='^admin_list_users$'))
    application.add_handler(CommandHandler("addpoints", add_points))
    application.add_handler(CommandHandler("removepoints", remove_points))

    port = int(os.environ.get('PORT', 8443))
    logger.info(f"Starting webhook bot on port {port}")
    application.run_webhook(listen="0.0.0.0", port=port, url_path=config.BOT_TOKEN, webhook_url=f"{config.WEBHOOK_URL}/{config.BOT_TOKEN}")

if name == "main":
    main()
