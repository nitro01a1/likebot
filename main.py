# main.py (نسخه کامل و نهایی با رفع باگ زیرمجموعه‌گیری)

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
        await update.message.reply_text("🔴 در حال حاضر ربات در حال تعمیر و بروزرسانی است. لطفا بعدا تلاش کنید.")
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

# ==============================================================================
# کنترلرهای اصلی کاربران
# ==============================================================================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    bot_is_on = database.get_setting('bot_status', 'true') == 'true'
    if not bot_is_on and user.id != config.ADMIN_ID:
        await update.message.reply_text("🔴 در حال حاضر ربات در حال تعمیر و بروزرسانی است. لطفا بعدا تلاش کنید.")
        return

    user_already_exists = database.user_exists(user.id)

    if not user_already_exists and context.args:
        try:
            referrer_id = int(context.args[0])
            if referrer_id != user.id:
                database.get_or_create_user(user.id, user.first_name, referred_by=referrer_id)
                database.update_points(referrer_id, 1)
                await context.bot.send_message(chat_id=referrer_id, text="یک کاربر جدید از طریق لینک شما وارد ربات شد و ۱ امتیاز دریافت کردید!")
                logger.info(f"User {user.id} joined with referral from {referrer_id}.")
            else:
                database.get_or_create_user(user.id, user.first_name)
        except (ValueError, IndexError):
            database.get_or_create_user(user.id, user.first_name)
    elif not user_already_exists:
        database.get_or_create_user(user.id, user.first_name)
        logger.info(f"New user {user.id} joined without referral.")
        
    await update.message.reply_text(f"سلام {user.first_name}! به ربات ما خوش آمدید.", reply_markup=get_main_reply_keyboard())

async def profile_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_user_preconditions(update, context): return
    user = update.effective_user
    db_user = database.get_or_create_user(user.id, user.first_name)
    bot_username = (await context.bot.get_me()).username
    referral_link = f"https://t.me/{bot_username}?start={user.id}"
    profile_text = f"👤 **حساب کاربری شما**\n\n🏷️ نام: {db_user['first_name']}\n🆔 آیدی: `{user.id}`\n⭐️ امتیاز: {db_user['points']}\n\n🔗 لینک دعوت شما:\n`{referral_link}`"
    await update.message.reply_text(profile_text, parse_mode=ParseMode.MARKDOWN)

async def daily_bonus_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if database.get_setting('service_daily_bonus_status', 'true') == 'false':
        await update.message.reply_text("❌ این سرویس در حال حاضر توسط مدیر غیرفعال شده است.")
        return
    if not await check_user_preconditions(update, context): return
    user = update.effective_user; db_user = database.get_or_create_user(user.id, user.first_name)
    now = datetime.now()
    if db_user.get('last_daily_claim'):
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

async def show_top_users(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_user_preconditions(update, context): return
    top_users = database.get_top_users(3)
    if not top_users:
        await update.message.reply_text("هنوز کاربری در ربات برای رتبه‌بندی وجود ندارد.")
        return
    text = "🏆 **نفرات برتر ربات** 🏆\n\n"
    emojis = ["🥇", "🥈", "🥉"]
    for i, user_data in enumerate(top_users):
        name, points, user_id = user_data
        text += f"{emojis[i]} نفر {'اول' if i==0 else 'دوم' if i==1 else 'سوم'}:\n"
        text += f"🏷️ **نام:** {name}\n"
        text += f"⭐️ **امتیاز:** {points}\n"
        text += f"🆔 **آیدی:** `{user_id}`\n\n"
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)

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

# ==============================================================================
# گفتگوی دریافت خدمات
# ==============================================================================
async def service_entry_point(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    service_key = SERVICE_MAP.get(update.message.text)
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

async def receive_stars_details_and_process(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = update.effective_user; details_text = update.message.text; service_key = context.user_data.get('service_key')
    service_display_name = SERVICE_NAME_MAP_FA.get(service_key, "سرویس نامشخص")
    forward_text = (f"درخواست (استارز):\n کاربر: {user.first_name} ({user.id})\n نوع: {service_display_name}\n\nجزئیات:\n{details_text}")
    await context.bot.send_message(chat_id=config.ADMIN_ID, text=forward_text)
    await update.message.reply_text("✅ سفارش شما ثبت و در صف بررسی قرار گرفت.", reply_markup=get_main_reply_keyboard())
    context.user_data.clear(); return ConversationHandler.END

# ==============================================================================
# گفتگوی انتقال امتیاز
# ==============================================================================
async def transfer_entry(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if database.get_setting('service_transfer_points_status', 'true') == 'false':
        await update.message.reply_text("❌ این سرویس در حال حاضر توسط مدیر غیرفعال شده است.")
        return ConversationHandler.END
    user = update.effective_user; db_user = database.get_or_create_user(user.id, user.first_name)
    today_str = date.today().isoformat()
    if db_user.get('last_transfer_date') == today_str:
        await update.message.reply_text("❌ شما امروز سهمیه انتقال امتیاز خود را استفاده کرده‌اید."); return ConversationHandler.END
    await update.message.reply_text("🔹 لطفاً آیدی عددی کاربر گیرنده را وارد کنید.\n\nبرای لغو /cancel را بزنید."); return AWAITING_RECIPIENT_ID

async def receive_recipient_id(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    recipient_id_str = update.message.text; sender_id = update.effective_user.id
    if not recipient_id_str.isdigit():
        await update.message.reply_text("❌ آیدی نامعتبر است. لطفاً فقط آیدی عددی ارسال کنید."); return AWAITING_RECIPIENT_ID
    recipient_id = int(recipient_id_str)
    if recipient_id == sender_id:
        await update.message.reply_text("❌ شما نمی‌توانید به خودتان امتیاز انتقال دهید!"); return AWAITING_RECIPIENT_ID
    recipient_user = database.get_or_create_user(recipient_id, "Unknown")
    if not recipient_user:
        await update.message.reply_text("❌ کاربری با این آیدی یافت نشد."); return AWAITING_RECIPIENT_ID
    context.user_data['recipient_id'] = recipient_id; context.user_data['recipient_name'] = recipient_user.get('first_name')
    await update.message.reply_text(f"✅ کاربر «{recipient_user.get('first_name')}» یافت شد.\n\n🔹 لطفاً تعداد امتیاز انتقالی را وارد کنید (حداقل ۳)."); return AWAITING_TRANSFER_AMOUNT

async def process_transfer(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    sender = update.effective_user; amount_str = update.message.text
    if not amount_str.isdigit():
        await update.message.reply_text("❌ مبلغ نامعتبر است. لطفاً فقط عدد وارد کنید."); return AWAITING_TRANSFER_AMOUNT
    amount_to_send = int(amount_str)
    sender_db_user = database.get_or_create_user(sender.id, sender.first_name)
    if amount_to_send < 3:
        await update.message.reply_text("❌ حداقل امتیاز برای انتقال ۳ می‌باشد."); return AWAITING_TRANSFER_AMOUNT
    if sender_db_user['points'] < amount_to_send:
        await update.message.reply_text(f"❌ امتیاز شما کافی نیست! (موجودی: {sender_db_user['points']})"); return ConversationHandler.END
    recipient_id = context.user_data['recipient_id']; recipient_name = context.user_data['recipient_name']
    tax = calculate_transfer_tax(amount_to_send); amount_received = amount_to_send - tax
    database.update_points(sender.id, -amount_to_send)
    database.update_points(recipient_id, amount_received)
    database.set_transfer_date(sender.id)
    database.log_transfer(sender_id=sender.id, sender_name=sender.first_name, recipient_id=recipient_id, recipient_name=recipient_name, amount_sent=amount_to_send, tax=tax, amount_received=amount_received)
    sender_new_balance = sender_db_user['points'] - amount_to_send
    recipient_new_balance = database.get_or_create_user(recipient_id, recipient_name)['points']
    await update.message.reply_text(f"✅ شما {amount_to_send} امتیاز به {recipient_name} انتقال دادید.\nموجودی شما: {sender_new_balance}", reply_markup=get_main_reply_keyboard())
    try:
        await context.bot.send_message(chat_id=recipient_id, text=(f"🎉 کاربر {sender.first_name} برای شما {amount_received} امتیاز انتقال داد.\nموجودی جدید: {recipient_new_balance}"))
    except Exception as e:
        logger.error(f"Could not send transfer notification to {recipient_id}: {e}")
    context.user_data.clear(); return ConversationHandler.END

# ==============================================================================
# کنترلرهای ادمین و گفتگوهای مربوطه
# ==============================================================================
async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_user.id != config.ADMIN_ID: return
    is_bot_on = database.get_setting('bot_status', 'true') == 'true'; bot_status_text = "روشن 🟢" if is_bot_on else "خاموش 🔴"
    is_error_enabled = database.get_setting('secondary_error_enabled', 'false') == 'true'; error_status_text = "فعال 🟢" if is_error_enabled else "غیرفعال 🔴"
    keyboard = [[InlineKeyboardButton(f"وضعیت ربات: {bot_status_text}", callback_data='toggle_bot_status')], [InlineKeyboardButton(f"خطای ثانویه: {error_status_text}", callback_data='toggle_secondary_error')], [InlineKeyboardButton("مدیریت کاربر 👤", callback_data='admin_manage_user'), InlineKeyboardButton("تنظیم هزینه‌ها ⚙️", callback_data='admin_set_costs')], [InlineKeyboardButton("مدیریت وضعیت سرویس‌ها 🔧", callback_data='admin_manage_services')], [InlineKeyboardButton("تاریخچه انتقالات 📜", callback_data='admin_transfer_history')], [InlineKeyboardButton("لیست کاربران 👥", callback_data='admin_list_users')]]
    text = "به پنل مدیریت خوش آمدید.\n\n**راهنمای امتیازدهی دستی:**\n`/addpoints <USER_ID> <AMOUNT>`\n`/removepoints <USER_ID> <AMOUNT>`"
    if update.callback_query:
        await update.callback_query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.MARKDOWN)
    else:
        await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.MARKDOWN)

async def toggle_bot_status_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query; await query.answer()
    is_on = database.get_setting('bot_status', 'true') == 'true'; new_status = 'false' if is_on else 'true'
    database.set_setting('bot_status', new_status); await admin_panel(update, context)

async def toggle_secondary_error_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query; await query.answer()
    is_enabled = database.get_setting('secondary_error_enabled', 'false') == 'true'; new_status = 'false' if is_enabled else 'true'
    database.set_setting('secondary_error_enabled', new_status); await admin_panel(update, context)

async def show_transfer_history(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query; await query.answer()
    history = database.get_transfer_history(limit=20)
    if not history: text = "هنوز هیچ انتقال امتیازی ثبت نشده است."
    else:
        text = "📜 **آخرین انتقالات امتیاز** 📜\n\n"
        for record in history:
            text += (f"🗓 **زمان:** `{record['timestamp']}`\n"
                     f"👤 **از:** {record['sender_name']} (`{record['sender_id']}`)\n"
                     f"👥 **به:** {record['recipient_name']} (`{record['recipient_id']}`)\n"
                     f"➖ **ارسالی:** {record['amount_sent']} | **مالیات:** {record['tax_amount']} | **دریافتی:** {record['amount_received']}\n"
                     "--------------------\n")
    keyboard = [[InlineKeyboardButton(" بازگشت به پنل مدیریت ↩️", callback_data='back_to_admin_panel')]]
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.MARKDOWN)

async def manage_services_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query; await query.answer()
    keyboard = []
    for service_key, service_name in USER_SERVICES.items():
        status = database.get_setting(f'service_{service_key}_status', 'true') == 'true'
        status_text = "فعال 🟢" if status else "غیرفعال 🔴"
        keyboard.append([InlineKeyboardButton(f"{service_name}: {status_text}", callback_data=f'toggle_service_{service_key}')])
    keyboard.append([InlineKeyboardButton(" بازگشت به پنل اصلی ↩️", callback_data='back_to_admin_panel')])
    await query.edit_message_text("وضعیت هر سرویس را می‌توانید تغییر دهید:", reply_markup=InlineKeyboardMarkup(keyboard))

async def toggle_service_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query; await query.answer()
    service_key = query.data.replace('toggle_service_', ''); setting_key = f'service_{service_key}_status'
    current_status = database.get_setting(setting_key, 'true') == 'true'
    new_status = 'false' if current_status else 'true'
    database.set_setting(setting_key, new_status); await manage_services_menu(update, context)

async def admin_reply_to_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != config.ADMIN_ID or not update.message.reply_to_message: return
    match = re.search(r"کاربر: .* \((\d+)\)", update.message.reply_to_message.text)
    if match:
        user_id_to_reply = int(match.group(1)); admin_text = update.message.text
        try:
            await context.bot.send_message(chat_id=user_id_to_reply, text=admin_text)
            await update.message.reply_text("✅ پیام شما برای کاربر ارسال شد.")
        except Exception as e:
            await update.message.reply_text(f"❌ خطا در ارسال پیام: {e}")

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
    for user_data in users: user_list += f"👤 نام: {user_data[1]}\n🆔 آیدی: `{user_data[0]}`\n⭐️ امتیاز: {user_data[2]}\n\n"
    keyboard = [[InlineKeyboardButton(" بازگشت به پنل مدیریت ↩️", callback_data='back_to_admin_panel')]]
    await query.edit_message_text(user_list, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.MARKDOWN)

async def manage_user_entry(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query; await query.answer()
    await query.edit_message_text("لطفاً آیدی عددی کاربری که می‌خواهید مدیریت کنید را ارسال نمایید.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(" بازگشت ↩️", callback_data='back_to_admin_panel')]]))
    return AWAITING_USER_ID_MANAGE

async def show_user_manage_options(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    try: user_id_to_manage = int(update.message.text)
    except ValueError: await update.message.reply_text("آیدی نامعتبر است."); return AWAITING_USER_ID_MANAGE
    user_info = database.get_or_create_user(user_id_to_manage, "Unknown")
    if not user_info: await update.message.reply_text("کاربری با این آیدی یافت نشد."); return ConversationHandler.END
    status = "🔴 مسدود" if user_info.get('is_banned') else "🟢 فعال"
    keyboard = [[InlineKeyboardButton("بن کردن 🚫", callback_data=f"ban_{user_id_to_manage}"), InlineKeyboardButton("آنبن کردن ✅", callback_data=f"unban_{user_id_to_manage}")], [InlineKeyboardButton(" بازگشت ↩️", callback_data='back_to_admin_panel')]]
    await update.message.reply_text(f"کاربر: {user_info['first_name']} ({user_id_to_manage})\nوضعیت: {status}\n\nچه کاری انجام شود؟", reply_markup=InlineKeyboardMarkup(keyboard))
    return ConversationHandler.END

async def perform_ban_unban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query; await query.answer(); action, user_id = query.data.split('_'); user_id = int(user_id)
    if action == "ban": database.set_ban_status(user_id, True); await query.edit_message_text(f"کاربر {user_id} مسدود شد.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(" بازگشت ↩️", callback_data='back_to_admin_panel')]]))
    elif action == "unban": database.set_ban_status(user_id, False); await query.edit_message_text(f"کاربر {user_id} از مسدودیت خارج شد.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(" بازگشت ↩️", callback_data='back_to_admin_panel')]]))

async def set_costs_entry(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query; await query.answer()
    costs = {k: database.get_setting(f'cost_{k}', '1') for k in SERVICE_NAME_MAP_FA.keys()}
    keyboard_list = [[InlineKeyboardButton(f"{SERVICE_NAME_MAP_FA[k]} ({v} امتیاز)", callback_data=f'setcost_{k}')] for k, v in costs.items()]
    keyboard_list.append([InlineKeyboardButton(" بازگشت ↩️", callback_data='back_to_admin_panel')])
    await query.edit_message_text("هزینه کدام بخش را می‌خواهید تغییر دهید؟", reply_markup=InlineKeyboardMarkup(keyboard_list))

async def ask_for_new_cost(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query; await query.answer()
    context.user_data['service_to_set_cost'] = query.data.split('_')[1]
    service_name_fa = SERVICE_NAME_MAP_FA.get(context.user_data['service_to_set_cost'], "این سرویس")
    await query.edit_message_text(f"لطفاً هزینه جدید را برای «{service_name_fa}» به صورت یک عدد ارسال کنید.")
    return AWAITING_COST_AMOUNT

async def set_new_cost(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    try:
        new_cost = int(update.message.text); service_key = context.user_data.get('service_to_set_cost')
        database.set_setting(f"cost_{service_key}", str(new_cost))
        await update.message.reply_text(f"هزینه با موفقیت به {new_cost} تغییر یافت.", reply_markup=get_main_reply_keyboard())
    except (ValueError, TypeError): await update.message.reply_text("مقدار نامعتبر است.")
    context.user_data.clear(); return ConversationHandler.END

# ==============================================================================
# تابع اصلی و راه‌اندازی ربات
# ==============================================================================
def main() -> None:
    database.init_db()
    if not database.get_setting('bot_status'): database.set_setting('bot_status', 'true')
    if not database.get_setting('secondary_error_enabled'): database.set_setting('secondary_error_enabled', 'false')
    if not database.get_setting('secondary_error_message'): database.set_setting('secondary_error_message', "خطا❌در اتصال به سرور مشکلی پیش امد. با ادمین تماس بگیرید @likeadminx7")

    application = Application.builder().token(config.BOT_TOKEN).build()

    service_conv = ConversationHandler(entry_points=[MessageHandler(filters.Regex(f"^({'|'.join(SERVICE_MAP.keys())})$"), service_entry_point)], states={AWAITING_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_id_and_process)], AWAITING_STARS_DETAILS: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_stars_details_and_process)]}, fallbacks=[CommandHandler('cancel', cancel_conversation)], per_user=True)
    transfer_conv = ConversationHandler(entry_points=[MessageHandler(filters.Regex('^انتقال امتیاز 🔄$'), transfer_entry)], states={AWAITING_RECIPIENT_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_recipient_id)], AWAITING_TRANSFER_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_transfer)]}, fallbacks=[CommandHandler('cancel', cancel_conversation)], per_user=True)
    manage_user_conv = ConversationHandler(entry_points=[CallbackQueryHandler(manage_user_entry, pattern='^admin_manage_user$')], states={AWAITING_USER_ID_MANAGE: [MessageHandler(filters.TEXT & ~filters.COMMAND, show_user_manage_options)]}, fallbacks=[CommandHandler('cancel', cancel_conversation)], per_user=True)
    set_cost_conv = ConversationHandler(entry_points=[CallbackQueryHandler(ask_for_new_cost, pattern='^setcost_.*$')], states={AWAITING_COST_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, set_new_cost)]}, fallbacks=[CommandHandler('cancel', cancel_conversation)], per_user=True)

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("admin", admin_panel))
    application.add_handler(service_conv)
    application.add_handler(transfer_conv)
    application.add_handler(manage_user_conv)
    application.add_handler(set_cost_conv)

    application.add_handler(MessageHandler(filters.Regex('^حساب کاربری👤$'), profile_handler))
    application.add_handler(MessageHandler(filters.Regex('^امتیاز روزانه🎁$'), daily_bonus_handler))
    application.add_handler(MessageHandler(filters.Regex('^پشتیبانی📞$'), support_handler))
    application.add_handler(MessageHandler(filters.Regex('^🏆 نفرات برتر$'), show_top_users))
    application.add_handler(MessageHandler(filters.REPLY & filters.User(config.ADMIN_ID), admin_reply_to_user))
    
    application.add_handler(CallbackQueryHandler(toggle_bot_status_callback, pattern='^toggle_bot_status$'))
    application.add_handler(CallbackQueryHandler(toggle_secondary_error_callback, pattern='^toggle_secondary_error$'))
    application.add_handler(CallbackQueryHandler(show_transfer_history, pattern='^admin_transfer_history$'))
    application.add_handler(CallbackQueryHandler(list_users_callback, pattern='^admin_list_users$'))
    application.add_handler(CallbackQueryHandler(set_costs_entry, pattern='^admin_set_costs$'))
    application.add_handler(CallbackQueryHandler(perform_ban_unban, pattern=r'^(ban|unban)_'))
    application.add_handler(CallbackQueryHandler(manage_services_menu, pattern='^admin_manage_services$'))
    application.add_handler(CallbackQueryHandler(toggle_service_status, pattern=r'^toggle_service_'))
    application.add_handler(CallbackQueryHandler(admin_panel, pattern='^back_to_admin_panel$'))
    
    application.add_handler(CommandHandler("addpoints", add_points))
    application.add_handler(CommandHandler("removepoints", remove_points))

    logger.info("Starting bot with polling...")
    application.run_polling()

if __name__ == "__main__":
    main()
