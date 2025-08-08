# main.py (نسخه نهایی کامل با تمام توابع و اصلاحات)

import logging
import os
import math
from datetime import datetime, timedelta, date
import random
import re

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, ReplyKeyboardMarkup, ReplyKeyboardRemove
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

# استیت‌های مکالمه
AWAITING_ID, AWAITING_STARS_DETAILS = 0, 1
AWAITING_USER_ID_MANAGE, AWAITING_COST_AMOUNT = range(2, 4)
AWAITING_RECIPIENT_ID, AWAITING_TRANSFER_AMOUNT = range(4, 6)
AWAITING_ADMIN_MESSAGE = 7
AWAITING_GIFT_CODE_DETAILS = 8
AWAITING_GIFT_CODE_INPUT = 9
AWAITING_SECONDARY_ERROR_MESSAGE = 10

# دیکشنری سرویس‌ها
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
#                     بخش تنظیمات هزینه‌ها (اصلاح شده)
# ==============================================================================
SERVICE_COSTS = {
    'free_like': 2,
    'account_info': 1,
    'free_stars': 3,
    'teddy_gift': 35
}
# ==============================================================================


# ==============================================================================
# توابع کمکی و کیبورد
# ==============================================================================
def get_main_reply_keyboard():
    return ReplyKeyboardMarkup([
        ['لایک رایگان🔥', 'اطلاعات اکانت📄', 'استارز رایگان⭐'],
        ['گیفت تدی🗿', 'امتیاز روزانه🎁', 'انتقال امتیاز 🔄'],
        ['/profile', '🏆 نفرات برتر', 'پشتیبانی📞'],
        ['کد هدیه 🎁']
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
    if not user: return False
    bot_is_on = database.get_setting('bot_status', 'true') == 'true'
    if not bot_is_on and user.id != config.ADMIN_ID:
        reply_text = "🔴 ربات در حال حاضر در حال تعمیر و بروزرسانی است. لطفا بعدا تلاش کنید."
        if update.message: await update.message.reply_text(reply_text, reply_markup=ReplyKeyboardRemove())
        elif update.callback_query: await update.callback_query.answer(reply_text, show_alert=True)
        return False
    db_user = database.get_or_create_user(user.id, user.first_name)
    if not db_user:
        if update.message: await update.message.reply_text("مشکلی در دسترسی به اطلاعات شما پیش آمد.")
        return False
    if db_user.get('is_banned'):
        if update.message: await update.message.reply_text("شما توسط ادمین مسدود شده‌اید.", reply_markup=ReplyKeyboardRemove())
        return False
    for channel in config.FORCED_JOIN_CHANNELS:
        try:
            member = await context.bot.get_chat_member(chat_id=channel, user_id=user.id)
            if member.status not in ['member', 'administrator', 'creator']:
                join_links = "\n".join(f"➡️ {ch}" for ch in config.FORCED_JOIN_CHANNELS)
                if update.message: await update.message.reply_text(f"برای استفاده از ربات، باید در کانال‌های زیر عضو شوید:\n{join_links}")
                return False
        except Exception as e:
            logger.error(f"Error checking membership for {channel}: {e}")
            if update.message: await update.message.reply_text("خطایی در بررسی عضویت کانال رخ داد.")
            return False
    return True

# ==============================================================================
# کنترلرهای اصلی کاربران
# ==============================================================================
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    bot_is_on = database.get_setting('bot_status', 'true') == 'true'
    if not bot_is_on and user.id != config.ADMIN_ID:
        await update.message.reply_text("🔴 ربات در حال حاضر در حال تعمیر و بروزرسانی است. لطفا بعدا تلاش کنید.")
        return
    user_already_exists = database.user_exists(user.id)
    if not user_already_exists and context.args:
        try:
            referrer_id = int(context.args[0])
            if referrer_id != user.id:
                database.get_or_create_user(user.id, user.first_name, referred_by=referrer_id)
                database.update_points(referrer_id, 1)
                await context.bot.send_message(chat_id=referrer_id, text="یک کاربر جدید از طریق لینک شما وارد ربات شد و ۲ امتیاز دریافت کردید!")
        except (ValueError, IndexError):
            database.get_or_create_user(user.id, user.first_name)
    elif not user_already_exists:
        database.get_or_create_user(user.id, user.first_name)
    await update.message.reply_text(f"سلام {user.first_name}! به ربات ما خوش آمدید.", reply_markup=get_main_reply_keyboard())

async def show_profile(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_user_preconditions(update, context):
        return

    try:
        user = update.effective_user
        db_user = database.get_or_create_user(user.id, user.first_name)
        if not db_user:
            await update.message.reply_text("خطایی در بازیابی اطلاعات شما از پایگاه داده رخ داد.")
            return

        bot_username = (await context.bot.get_me()).username
        referral_link = f"https://t.me/{bot_username}?start={user.id}"
        referral_count = database.get_referral_count(user.id)

        profile_text = (
            f"👤 حساب کاربری شما\n\n"
            f"🏷️ نام: {db_user.get('first_name', 'کاربر')}\n"
            f"🆔 آیدی: {user.id}\n"
            f"⭐️ امتیاز: {db_user.get('points', 0)}\n"
            f"👥 تعداد زیرمجموعه: {referral_count} نفر\n\n"
            f"🔗 لینک دعوت شما:\n{referral_link}"
        )
        
        await update.message.reply_text(profile_text)

    except Exception as e:
        logger.error(f"Error in show_profile for user {update.effective_user.id}: {e}")
        await update.message.reply_text("خطایی در نمایش اطلاعات حساب رخ داد. لطفاً با پشتیبانی تماس بگیرید.")


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
    current_points = db_user.get('points', 0) + bonus_points
    await update.message.reply_text(f"🎁 تبریک! شما {bonus_points} امتیاز روزانه دریافت کردید.\nموجودی فعلی: {current_points} امتیاز")

async def support_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_user_preconditions(update, context): return
    await update.message.reply_text(f"📞 پشتیبانی\n\n- مالک ربات: {config.OWNER_ID}\n- ادمین پشتیبانی: {config.SUPPORT_ID}")

async def show_top_users(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_user_preconditions(update, context): return
    top_users = database.get_top_users(3)
    if not top_users:
        await update.message.reply_text("هنوز کاربری در ربات برای رتبه‌بندی وجود ندارد.")
        return
    text = "🏆 نفرات برتر ربات 🏆\n\n"
    emojis = ["🥇", "🥈", "🥉"]
    for i, user_data in enumerate(top_users):
        name, points, user_id = user_data
        text += f"{emojis[i]} نفر {'اول' if i==0 else 'دوم' if i==1 else 'سوم'}:\n"
        text += f"🏷️ نام: {name}\n"
        text += f"⭐️ امتیاز: {points}\n"
        text += f"🆔 آیدی: {user_id}\n\n"
    await update.message.reply_text(text)

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
    if not service_key: return ConversationHandler.END
    if database.get_setting(f'service_{service_key}_status', 'true') == 'false':
        await update.message.reply_text("❌ این سرویس در حال حاضر توسط مدیر غیرفعال شده است.")
        return ConversationHandler.END
    if not await check_user_preconditions(update, context): return ConversationHandler.END
    
    cost = SERVICE_COSTS.get(service_key, 1)
    
    user = update.effective_user
    db_user = database.get_or_create_user(user.id, user.first_name)
    if db_user.get('points', 0) < cost:
        await update.message.reply_text(f"❌ امتیاز شما برای «{update.message.text}» کافی نیست! (نیاز به {cost} امتیاز)")
        return ConversationHandler.END
    context.user_data['service_key'] = service_key; context.user_data['cost'] = cost
    database.update_points(user.id, -cost)
    new_points = database.get_or_create_user(user.id, user.first_name).get('points', 0)
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
    if not await check_user_preconditions(update, context): return ConversationHandler.END
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
    sent_message = await update.message.reply_text(f"{final_message}\nامتیاز شما: {database.get_or_create_user(user.id, user.first_name).get('points', 0)}")
    is_secondary_error_enabled = database.get_setting('secondary_error_enabled', 'false') == 'true'
    if is_secondary_error_enabled and service_key in ['free_like', 'account_info']:
        await sent_message.reply_text(database.get_setting('secondary_error_message'))
    context.user_data.clear(); return ConversationHandler.END

async def receive_stars_details_and_process(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not await check_user_preconditions(update, context): return ConversationHandler.END
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
    if not await check_user_preconditions(update, context): return ConversationHandler.END
    user = update.effective_user; db_user = database.get_or_create_user(user.id, user.first_name)
    today_str = date.today().isoformat()
    if db_user.get('last_transfer_date') == today_str:
        await update.message.reply_text("❌ شما امروز سهمیه انتقال امتیاز خود را استفاده کرده‌اید."); return ConversationHandler.END
    await update.message.reply_text("🔹 لطفاً آیدی عددی کاربر گیرنده را وارد کنید.\n\nبرای لغو /cancel را بزنید."); return AWAITING_RECIPIENT_ID

async def receive_recipient_id(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not await check_user_preconditions(update, context): return ConversationHandler.END
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
    if not await check_user_preconditions(update, context): return ConversationHandler.END
    sender = update.effective_user; amount_str = update.message.text
    if not amount_str.isdigit():
        await update.message.reply_text("❌ مبلغ نامعتبر است. لطفاً فقط عدد وارد کنید."); return AWAITING_TRANSFER_AMOUNT
    amount_to_send = int(amount_str)
    sender_db_user = database.get_or_create_user(sender.id, sender.first_name)
    if amount_to_send < 3:
        await update.message.reply_text("❌ حداقل امتیاز برای انتقال ۳ می‌باشد."); return AWAITING_TRANSFER_AMOUNT
    if sender_db_user.get('points', 0) < amount_to_send:
        await update.message.reply_text(f"❌ امتیاز شما کافی نیست! (موجودی: {sender_db_user.get('points', 0)})"); return ConversationHandler.END
    recipient_id = context.user_data['recipient_id']; recipient_name = context.user_data['recipient_name']
    tax = calculate_transfer_tax(amount_to_send); amount_received = amount_to_send - tax
    database.update_points(sender.id, -amount_to_send)
    database.update_points(recipient_id, amount_received)
    database.set_transfer_date(sender.id)
    database.log_transfer(sender_id=sender.id, sender_name=sender.first_name, recipient_id=recipient_id, recipient_name=recipient_name, amount_sent=amount_to_send, tax=tax, amount_received=amount_received)
    sender_new_balance = sender_db_user.get('points', 0) - amount_to_send
    recipient_new_balance = database.get_or_create_user(recipient_id, recipient_name).get('points', 0)
    await update.message.reply_text(f"✅ شما {amount_to_send} امتیاز به {recipient_name} انتقال دادید.\nموجودی شما: {sender_new_balance}", reply_markup=get_main_reply_keyboard())
    try:
        await context.bot.send_message(chat_id=recipient_id, text=(f"🎉 کاربر {sender.first_name} برای شما {amount_received} امتیاز انتقال داد.\nموجودی جدید: {recipient_new_balance}"))
    except Exception as e:
        logger.error(f"Could not send transfer notification to {recipient_id}: {e}")
    context.user_data.clear(); return ConversationHandler.END

# ==============================================================================
# مکالمه کد هدیه کاربر
# ==============================================================================
async def gift_code_button_entry(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not await check_user_preconditions(update, context): return ConversationHandler.END
    await update.message.reply_text(
        "🎁 لطفاً کد هدیه خود را وارد کنید.\n\nبرای لغو /cancel را بزنید.",
        reply_markup=ReplyKeyboardRemove()
    )
    return AWAITING_GIFT_CODE_INPUT

async def process_gift_code_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not await check_user_preconditions(update, context): return ConversationHandler.END
    user = update.effective_user
    code = update.message.text
    status, points_value = database.redeem_gift_code(user.id, code)
    reply_message = ""
    if status == "success":
        db_user = database.get_or_create_user(user.id, user.first_name)
        reply_message = f"✅ تبریک! کد با موفقیت استفاده شد و {points_value} امتیاز دریافت کردید.\nموجودی جدید: {db_user.get('points', 0)} امتیاز"
    elif status == "already_used":
        reply_message = "❌ شما قبلاً از این کد هدیه استفاده کرده‌اید."
    elif status == "limit_reached":
        reply_message = "❌ متاسفانه ظرفیت استفاده از این کد هدیه به پایان رسیده است."
    elif status == "not_found":
        reply_message = "❌ کد هدیه وارد شده نامعتبر است."
    else: # "error"
        reply_message = "❌ خطایی در سیستم رخ داد. لطفاً با پشتیبانی تماس بگیرید."
    await update.message.reply_text(reply_message, reply_markup=get_main_reply_keyboard())
    return ConversationHandler.END

# ==============================================================================
# کنترلرهای پنل ادمین
# ==============================================================================
async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    chat = update.effective_chat
    if chat.type != 'private':
        if update.callback_query:
            await update.callback_query.answer("این پنل فقط در چت خصوصی با ربات قابل استفاده است.", show_alert=True)
        return

    if update.effective_user.id != config.ADMIN_ID: return
    
    secondary_error_status = "🟢" if database.get_setting('secondary_error_enabled', 'false') == 'true' else "🔴"
    
    keyboard = [
        [InlineKeyboardButton("پنل کد هدیه 🎁", callback_data='gift_code_panel')],
        [InlineKeyboardButton("مدیریت کاربر 👤", callback_data='admin_manage_user')],
        [InlineKeyboardButton("مدیریت وضعیت سرویس‌ها 🔧", callback_data='admin_manage_services')],
        [InlineKeyboardButton("تاریخچه انتقالات 📜", callback_data='admin_transfer_history_page_1')],
        [InlineKeyboardButton("لیست کاربران 👥", callback_data='list_users_page_1')],
        [InlineKeyboardButton("تغییر وضعیت ربات ⚙️", callback_data='toggle_bot_status')],
        [InlineKeyboardButton(f"خطای ثانویه {secondary_error_status}", callback_data='secondary_error_panel')],
    ]
    text = "به پنل مدیریت خوش آمدید."
    if update.callback_query:
        await update.callback_query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
    else:
        await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

async def add_points(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.chat.type != 'private':
        await update.message.reply_text("این دستور فقط در چت خصوصی با ربات قابل استفاده است.")
        return
        
    if update.effective_user.id != config.ADMIN_ID: return
    try: 
        user_id = int(context.args[0]); amount = int(context.args[1])
        database.update_points(user_id, amount)
        await update.message.reply_text(f"{amount} امتیاز به کاربر {user_id} اضافه شد.")
    except: 
        await update.message.reply_text("استفاده: /addpoints <USER_ID> <AMOUNT>")

async def remove_points(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.message.chat.type != 'private':
        await update.message.reply_text("این دستور فقط در چت خصوصی با ربات قابل استفاده است.")
        return

    if update.effective_user.id != config.ADMIN_ID: return
    try: 
        user_id = int(context.args[0]); amount = int(context.args[1])
        database.update_points(user_id, -amount)
        await update.message.reply_text(f"{amount} امتیاز از کاربر {user_id} کسر شد.")
    except: 
        await update.message.reply_text("استفاده: /removepoints <USER_ID> <AMOUNT>")

async def secondary_error_panel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    
    is_enabled = database.get_setting('secondary_error_enabled', 'false') == 'true'
    status_text = "فعال 🟢" if is_enabled else "غیرفعال 🔴"
    current_message = database.get_setting('secondary_error_message', 'پیام پیش‌فرض خطای ثانویه')
    
    text = (f"⚠️ مدیریت خطای ثانویه ⚠️\n\n"
            f"وضعیت فعلی: {status_text}\n"
            f"پیام فعلی: {current_message}\n\n"
            f"لطفاً یکی از گزینه‌های زیر را انتخاب کنید:")
    
    keyboard = [
        [InlineKeyboardButton("فعال/غیرفعال کردن", callback_data='toggle_secondary_error')],
        [InlineKeyboardButton("تغییر پیام خطا", callback_data='change_secondary_error_message')],
        [InlineKeyboardButton("بازگشت به پنل اصلی ↩️", callback_data='back_to_admin_panel')]
    ]
    
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.MARKDOWN)

async def toggle_secondary_error(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    
    current_status = database.get_setting('secondary_error_enabled', 'false') == 'true'
    new_status = 'false' if current_status else 'true'
    database.set_setting('secondary_error_enabled', new_status)
    
    await query.answer(f"وضعیت خطای ثانویه به {'فعال' if new_status == 'true' else 'غیرفعال'} تغییر کرد.")
    await secondary_error_panel(update, context)

async def change_secondary_error_message_entry(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    await query.edit_message_text(
        "لطفاً پیام جدید خطای ثانویه را وارد کنید.\n\nبرای لغو /cancel را بزنید.",
        reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("لغو", callback_data='back_to_admin_panel')]])
    )
    return AWAITING_SECONDARY_ERROR_MESSAGE

async def process_new_error_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    new_message = update.message.text
    database.set_setting('secondary_error_message', new_message)
    await update.message.reply_text(
        f"✅ پیام خطای ثانویه با موفقیت به '{new_message}' تغییر یافت.",
        reply_markup=get_main_reply_keyboard()
    )
    context.user_data.clear()
    return ConversationHandler.END

async def toggle_bot_status_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query; await query.answer()
    is_on = database.get_setting('bot_status', 'true') == 'true'; new_status = 'false' if is_on else 'true'
    database.set_setting('bot_status', new_status)
    await query.answer(f"وضعیت ربات به {'روشن' if new_status == 'true' else 'خاموش'} تغییر کرد.")

async def admin_reply_to_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if update.effective_user.id != config.ADMIN_ID or not update.message.reply_to_message: return
    match = re.search(r"کاربر: .* \((\d+)\)", update.message.reply_to_message.text)
    if match:
        user_id_to_reply = int(match.group(1)); admin_text = update.message.text
        try: 
            await context.bot.send_message(chat_id=user_id_to_reply, text=f"پاسخ از طرف پشتیبانی:\n\n{admin_text}")
            await update.message.reply_text("✅ پیام شما برای کاربر ارسال شد.")
        except Exception as e: 
            await update.message.reply_text(f"❌ خطا در ارسال پیام: {e}")

async def list_users_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    page = 1
    if query.data and 'list_users_page_' in query.data:
        page = int(query.data.split('_')[-1])
    limit = 10
    offset = (page - 1) * limit
    users = database.get_all_users(limit=limit, offset=offset)
    total_users = database.get_user_count()
    total_pages = math.ceil(total_users / limit) if total_users > 0 else 1
    if not users:
        await query.edit_message_text("هیچ کاربری ثبت‌نام نکرده است.")
        return
    user_list = f"👥 لیست کاربران (صفحه {page}/{total_pages}):\n\n"
    for user_data in users:
        user_list += f"👤 {user_data[1]}\n🆔 {user_data[0]} | ⭐️ {user_data[2]}\n\n"
    keyboard = []
    row = []
    if page > 1:
        row.append(InlineKeyboardButton("⬅️ قبلی", callback_data=f'list_users_page_{page-1}'))
    row.append(InlineKeyboardButton(f"صفحه {page}", callback_data='noop'))
    if page < total_pages:
        row.append(InlineKeyboardButton("بعدی ➡️", callback_data=f'list_users_page_{page+1}'))
    keyboard.append(row)
    keyboard.append([InlineKeyboardButton(" بازگشت ↩️", callback_data='back_to_admin_panel')])
    await query.edit_message_text(user_list, reply_markup=InlineKeyboardMarkup(keyboard))

async def show_transfer_history(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query; await query.answer(); page = 1
    if query.data and 'transfer_history_page_' in query.data: page = int(query.data.split('_')[-1])
    limit = 10; offset = (page - 1) * limit; history = database.get_transfer_history(limit=limit, offset=offset)
    total_transfers = database.get_transfer_count(); total_pages = math.ceil(total_transfers / limit) if total_transfers > 0 else 1
    if not history: text = "هنوز هیچ انتقال امتیازی ثبت نشده است."
    else:
        text = f"📜 آخرین انتقالات (صفحه {page}/{total_pages}) 📜\n\n"
        for record in history: 
            text += (f"🗓 {record['timestamp']}\n" 
                     f"👤از: {record['sender_name']} ({record['sender_id']})\n" 
                     f"👥به: {record['recipient_name']} ({record['recipient_id']})\n" 
                     f"➖({record['amount_sent']})| مالیات({record['tax_amount']})| دریافتی({record['amount_received']})\n" 
                     "--------------------\n")
    keyboard = []; row = []
    if page > 1: row.append(InlineKeyboardButton("⬅️ قبلی", callback_data=f'transfer_history_page_{page-1}'))
    row.append(InlineKeyboardButton(f"صفحه {page}", callback_data='noop'))
    if page < total_pages: row.append(InlineKeyboardButton("بعدی ➡️", callback_data=f'transfer_history_page_{page+1}'))
    keyboard.append(row); keyboard.append([InlineKeyboardButton(" بازگشت ↩️", callback_data='back_to_admin_panel')])
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

async def manage_services_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query; await query.answer(); keyboard = []
    for service_key, service_name in USER_SERVICES.items():
        status = database.get_setting(f'service_{service_key}_status', 'true') == 'true'; status_text = "فعال 🟢" if status else "غیرفعال 🔴"
        keyboard.append([InlineKeyboardButton(f"{service_name}: {status_text}", callback_data=f'toggle_service_{service_key}')])
    keyboard.append([InlineKeyboardButton(" بازگشت ↩️", callback_data='back_to_admin_panel')])
    await query.edit_message_text("وضعیت هر سرویس را می‌توانید تغییر دهید:", reply_markup=InlineKeyboardMarkup(keyboard))

async def toggle_service_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query; await query.answer(); service_key = query.data.replace('toggle_service_', ''); setting_key = f'service_{service_key}_status'
    current_status = database.get_setting(setting_key, 'true') == 'true'; new_status = 'false' if current_status else 'true'
    database.set_setting(setting_key, new_status); await manage_services_menu(update, context)

async def manage_user_entry(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query; await query.answer()
    await query.edit_message_text("لطفاً آیدی عددی کاربری که می‌خواهید مدیریتش کنید را ارسال نمایید.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(" بازگشت ↩️", callback_data='back_to_admin_panel')]]))
    return AWAITING_USER_ID_MANAGE

async def show_user_manage_options(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    try: 
        user_id_to_manage = int(update.message.text)
    except ValueError: 
        await update.message.reply_text("آیدی نامعتبر است."); return AWAITING_USER_ID_MANAGE
    user_info = database.get_or_create_user(user_id_to_manage, "Unknown")
    if not user_info: 
        await update.message.reply_text("کاربری با این آیدی یافت نشد."); return ConversationHandler.END
    referral_count = database.get_referral_count(user_id_to_manage)
    status = "🔴 مسدود" if user_info.get('is_banned') else "🟢 فعال"
    profile_text = (f"👤 پروفایل: {user_info['first_name']}\n" 
                    f"🆔 آیدی: {user_info['user_id']}\n" 
                    f"⭐️ امتیاز: {user_info['points']}\n" 
                    f"👥 تعداد زیرمجموعه: {referral_count} نفر\n" 
                    f"🚦 وضعیت: {status}\n\n" 
                    f"🔗 معرف: {user_info.get('referred_by') or 'ندارد'}\n" 
                    f"🎁 آخرین جایزه: {user_info.get('last_daily_claim') or 'N/A'}\n" 
                    f"🔄 آخرین انتقال: {user_info.get('last_transfer_date') or 'N/A'}")
    keyboard = [[InlineKeyboardButton("بن کردن 🚫", callback_data=f"ban_{user_id_to_manage}"), 
                 InlineKeyboardButton("آنبن کردن ✅", callback_data=f"unban_{user_id_to_manage}")], 
                [InlineKeyboardButton("ارسال پیام 📨", callback_data=f"send_msg_{user_id_to_manage}")], 
                [InlineKeyboardButton(" بازگشت ↩️", callback_data='back_to_admin_panel')]]
    await update.message.reply_text(profile_text, reply_markup=InlineKeyboardMarkup(keyboard))
    return ConversationHandler.END

async def ask_for_admin_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query; await query.answer(); user_id = int(query.data.split('_')[2])
    user_info = database.get_or_create_user(user_id, "Unknown")
    context.user_data['recipient_id_admin_msg'] = user_id
    await query.edit_message_text(f"پیام خود را برای کاربر «{user_info['first_name']}» بنویسید:", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("لغو", callback_data='back_to_admin_panel')]]))
    return AWAITING_ADMIN_MESSAGE

async def send_message_from_admin(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    recipient_id = context.user_data.get('recipient_id_admin_msg')
    try:
        await context.bot.send_message(chat_id=recipient_id, text=f"📨 یک پیام از طرف مدیر برای شما:\n\n{update.message.text}", parse_mode=ParseMode.MARKDOWN)
        await update.message.reply_text("✅ پیام شما با موفقیت برای کاربر ارسال شد.")
    except Exception as e: 
        await update.message.reply_text(f"❌ ارسال پیام با خطا مواجه شد: {e}")
    context.user_data.clear(); await admin_panel(update, context); return ConversationHandler.END
    
async def perform_ban_unban(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query; await query.answer(); action, user_id = query.data.split('_'); user_id = int(user_id)
    if action == "ban": 
        database.set_ban_status(user_id, True)
        await query.edit_message_text(f"کاربر {user_id} مسدود شد.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(" بازگشت ↩️", callback_data='back_to_admin_panel')]]))
    elif action == "unban": 
        database.set_ban_status(user_id, False)
        await query.edit_message_text(f"کاربر {user_id} از مسدودیت خارج شد.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton(" بازگشت ↩️", callback_data='back_to_admin_panel')]]))

async def gift_code_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query; await query.answer()
    keyboard = [[InlineKeyboardButton("افزودن کد جدید ➕", callback_data='add_gift_code_entry')], 
                [InlineKeyboardButton("لیست کدها 📋", callback_data='list_gift_codes')], 
                [InlineKeyboardButton("بازگشت به پنل اصلی ↩️", callback_data='back_to_admin_panel')]]
    text = "🎁 پنل مدیریت کدهای هدیه 🎁"
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.MARKDOWN)

async def add_gift_code_entry(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query; await query.answer()
    text = "لطفاً اطلاعات کد جدید را به این صورت در یک پیام ارسال کنید:\n\nCODE POINTS USES\n\nمثال:\nwelcome1404 10 50\n\nبرای لغو /cancel را بزنید."
    await query.edit_message_text(text, parse_mode=ParseMode.MARKDOWN)
    return AWAITING_GIFT_CODE_DETAILS

async def process_new_gift_code(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    try: 
        code, points_str, limit_str = update.message.text.split(); points = int(points_str); usage_limit = int(limit_str)
    except (ValueError, IndexError): 
        await update.message.reply_text("❌ فرمت ورودی اشتباه است.\nدوباره تلاش کنید یا /cancel را بزنید."); return AWAITING_GIFT_CODE_DETAILS
    if database.add_gift_code(code, points, usage_limit): 
        await update.message.reply_text(f"✅ کد هدیه {code} با موفقیت ساخته شد.", parse_mode=ParseMode.MARKDOWN, reply_markup=get_main_reply_keyboard())
    else: 
        await update.message.reply_text(f"❌ کد هدیه {code} از قبل موجود است.", parse_mode=ParseMode.MARKDOWN, reply_markup=get_main_reply_keyboard())
    context.user_data.clear(); return ConversationHandler.END
    
async def list_gift_codes(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query; await query.answer(); all_codes = database.get_all_gift_codes()
    if not all_codes:
        text = "هیچ کد هدیه‌ای ثبت نشده است."; keyboard = [[InlineKeyboardButton("بازگشت ↩️", callback_data='gift_code_panel')]]
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard)); return
    text = "📋 لیست کدهای هدیه 📋\n\n"
    keyboard = []
    for code_data in all_codes:
        text += (f"🔹 کد: {code_data['code']}\n"
                 f"   - امتیاز: {code_data['points']} ⭐\n"
                 f"   - استفاده شده: {code_data['usage_count']} از {code_data['usage_limit']}\n\n")
        button_row = [InlineKeyboardButton(f"مشاهده کاربران 👥", callback_data=f"view_users_gift_{code_data['code']}_page_1"), 
                      InlineKeyboardButton(f"حذف 🗑️", callback_data=f"delete_gift_{code_data['code']}")]
        keyboard.append(button_row)
    keyboard.append([InlineKeyboardButton("بازگشت ↩️", callback_data='gift_code_panel')])
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.MARKDOWN)

async def delete_gift_code_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query; code_to_delete = query.data.split('_')[-1]
    if database.delete_gift_code(code_to_delete): 
        await query.answer(f"✅ کد {code_to_delete} حذف شد.", show_alert=False)
    else: 
        await query.answer(f"❌ خطا در حذف کد {code_to_delete}.", show_alert=True)
    await list_gift_codes(update, context)

async def show_gift_code_users(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query; await query.answer(); parts = query.data.split('_'); code = parts[3]; page = int(parts[5])
    users = database.get_users_of_gift_code(code)
    if not users:
        text = f"هنوز هیچ کاربری از کد {code} استفاده نکرده است."; 
        keyboard = [[InlineKeyboardButton(" بازگشت ↩️", callback_data='list_gift_codes')]]
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard)); return
    limit = 10; offset = (page - 1) * limit; total_users = len(users); total_pages = math.ceil(total_users / limit)
    paginated_users = users[offset : offset + limit]
    text = f"👥 **کاربران کد {code} (صفحه {page}/{total_pages})**\n\n"
    for user in paginated_users: text += f"👤 نام: {user['first_name']}\n   - آیدی: {user['user_id']}\n"
    keyboard_rows = []; pagination_row = []
    if page > 1: pagination_row.append(InlineKeyboardButton("⬅️ قبلی", callback_data=f"view_users_gift_{code}_page_{page-1}"))
    pagination_row.append(InlineKeyboardButton(f"{page}/{total_pages}", callback_data="noop"))
    if page < total_pages: pagination_row.append(InlineKeyboardButton("بعدی ➡️", callback_data=f"view_users_gift_{code}_page_{page+1}"))
    if pagination_row: keyboard_rows.append(pagination_row)
    keyboard_rows.append([InlineKeyboardButton(" بازگشت به لیست کدها ↩️", callback_data='list_gift_codes')])
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard_rows), parse_mode=ParseMode.MARKDOWN)

# ==============================================================================
# تابع اصلی و راه‌اندازی ربات
# ==============================================================================
def main() -> None:
    database.init_db()
    if not database.get_setting('bot_status'): database.set_setting('bot_status', 'true')
    if not database.get_setting('secondary_error_enabled'): database.set_setting('secondary_error_enabled', 'false')
    if not database.get_setting('secondary_error_message'): database.set_setting('secondary_error_message', "خطا❌در اتصال به سرور مشکلی پیش امد. با ادمین تماس بگیرید @likeadminx7")

    application = Application.builder().token(config.BOT_TOKEN).build()
    
    cancel_handler = CommandHandler('cancel', cancel_conversation)
    base_fallbacks = [cancel_handler]
    admin_base_conv_fallbacks = [cancel_handler, CallbackQueryHandler(admin_panel, pattern='^back_to_admin_panel$')]
    
    secondary_error_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(change_secondary_error_message_entry, pattern='^change_secondary_error_message$')],
        states={AWAITING_SECONDARY_ERROR_MESSAGE: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_new_error_message)]},
        fallbacks=admin_base_conv_fallbacks, per_user=True
    )
    gift_conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex('^کد هدیه 🎁$'), gift_code_button_entry)],
        states={AWAITING_GIFT_CODE_INPUT: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_gift_code_input)]},
        fallbacks=base_fallbacks
    )
    service_conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex(f"^({'|'.join(SERVICE_MAP.keys())})$"), service_entry_point)],
        states={
            AWAITING_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_id_and_process)],
            AWAITING_STARS_DETAILS: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_stars_details_and_process)]
        },
        fallbacks=base_fallbacks, per_user=True
    )
    transfer_conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex('^انتقال امتیاز 🔄$'), transfer_entry)],
        states={
            AWAITING_RECIPIENT_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_recipient_id)],
            AWAITING_TRANSFER_AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_transfer)]
        },
        fallbacks=base_fallbacks, per_user=True
    )
    add_gift_conv = ConversationHandler(
        entry_points=[CallbackQueryHandler(add_gift_code_entry, pattern='^add_gift_code_entry$')],
        states={AWAITING_GIFT_CODE_DETAILS: [MessageHandler(filters.TEXT & ~filters.COMMAND, process_new_gift_code)]},
        fallbacks=base_fallbacks
    )
    manage_user_conv = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(manage_user_entry, pattern='^admin_manage_user$'),
            CallbackQueryHandler(ask_for_admin_message, pattern=r'^send_msg_')
        ],
        states={
            AWAITING_USER_ID_MANAGE: [MessageHandler(filters.TEXT & ~filters.COMMAND, show_user_manage_options)],
            AWAITING_ADMIN_MESSAGE: [MessageHandler(filters.TEXT & ~filters.COMMAND, send_message_from_admin)]
        },
        fallbacks=admin_base_conv_fallbacks, per_user=True
    )
    
    # --- ثبت هندلرها ---
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("admin", admin_panel))
    application.add_handler(CommandHandler("profile", show_profile))
    application.add_handler(cancel_handler)

    application.add_handler(gift_conv)
    application.add_handler(service_conv)
    application.add_handler(transfer_conv)
    application.add_handler(add_gift_conv)
    application.add_handler(manage_user_conv)
    application.add_handler(secondary_error_conv)

    application.add_handler(MessageHandler(filters.Regex('^امتیاز روزانه🎁$'), daily_bonus_handler))
    application.add_handler(MessageHandler(filters.Regex('^پشتیبانی📞$'), support_handler))
    application.add_handler(MessageHandler(filters.Regex('^🏆 نفرات برتر$'), show_top_users))
    application.add_handler(MessageHandler(filters.REPLY & filters.User(config.ADMIN_ID), admin_reply_to_user))
    
    application.add_handler(CallbackQueryHandler(admin_panel, pattern='^back_to_admin_panel$'))
    application.add_handler(CallbackQueryHandler(toggle_bot_status_callback, pattern='^toggle_bot_status$'))
    application.add_handler(CallbackQueryHandler(show_transfer_history, pattern=r'^admin_transfer_history_page_'))
    application.add_handler(CallbackQueryHandler(list_users_callback, pattern=lambda data: data and data.startswith('list_users_page_')))
    application.add_handler(CallbackQueryHandler(perform_ban_unban, pattern=r'^(ban|unban)_'))
    application.add_handler(CallbackQueryHandler(manage_services_menu, pattern='^admin_manage_services$'))
    application.add_handler(CallbackQueryHandler(toggle_service_status, pattern=r'^toggle_service_'))
    application.add_handler(CallbackQueryHandler(gift_code_panel, pattern='^gift_code_panel$'))
    application.add_handler(CallbackQueryHandler(list_gift_codes, pattern='^list_gift_codes$'))
    application.add_handler(CallbackQueryHandler(delete_gift_code_callback, pattern=r'^delete_gift_'))
    application.add_handler(CallbackQueryHandler(show_gift_code_users, pattern=r'^view_users_gift_'))
    application.add_handler(CallbackQueryHandler(secondary_error_panel, pattern='^secondary_error_panel$'))
    application.add_handler(CallbackQueryHandler(toggle_secondary_error, pattern='^toggle_secondary_error$'))
    
    application.add_handler(CallbackQueryHandler(lambda u, c: u.callback_query.answer(), pattern='^noop$'))

    application.add_handler(CommandHandler("addpoints", add_points))
    application.add_handler(CommandHandler("removepoints", remove_points))
    
    logger.info("Starting bot with polling...")
    application.run_polling()

if __name__ == "__main__":
    main()
