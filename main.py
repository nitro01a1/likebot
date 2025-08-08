# main.py (نسخه نهایی با تمام تغییرات درخواستی شما)

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
    'اطلاعات اکانت📄': 'account_info',  # ✅ اضافه شد
    'استارز رایگان⭐': 'free_stars',
    'گیفت تدی🗿': 'teddy_gift'
}
SERVICE_NAME_MAP_FA = {v: k for k, v in SERVICE_MAP.items()}
USER_SERVICES = {
    'free_like': 'لایک رایگان🔥',
    'account_info': 'اطلاعات اکانت📄', # ✅ اضافه شد
    'free_stars': 'استارز رایگان⭐',
    'teddy_gift': 'گیفت تدی🗿',
    'daily_bonus': 'امتیاز روزانه🎁',
    'transfer_points': 'انتقال امتیاز 🔄'
}

# ==============================================================================
#                     ✅ بخش تنظیمات هزینه‌ها (اصلاح شده) ✅
# ==============================================================================
SERVICE_COSTS = {
    'free_like': 2,         # ✅ تغییر کرد
    'account_info': 2,      # ✅ اضافه شد (هزینه مشابه لایک)
    'free_stars': 5,        # ✅ تغییر کرد
    'teddy_gift': 35        # ✅ تغییر کرد
}
# ==============================================================================


# ==============================================================================
# توابع کمکی و کیبورد
# ==============================================================================
def get_main_reply_keyboard():
    return ReplyKeyboardMarkup([
        ['لایک رایگان🔥', 'اطلاعات اکانت📄', 'استارز رایگان⭐'], # ✅ دکمه اضافه شد
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
                # ✅ پاداش رفرال به ۲ تغییر کرد
                database.update_points(referrer_id, 2)
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
        
        await update.message.reply_text(profile_text, parse_mode=ParseMode.MARKDOWN)

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
    # ✅ امتیاز روزانه حداکثر ۳ شد
    bonus_points = random.randint(1, 3)
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

# ... (بقیه توابع بدون تغییر تا تابع main) ...
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

# ... (بقیه توابع تا آخر بدون تغییر) ...

# ==============================================================================
# تابع اصلی و راه‌اندازی ربات
# ==============================================================================
def main() -> None:
    database.init_db()
    if not database.get_setting('bot_status'): database.set_setting('bot_status', 'true')
    # ... بقیه تنظیمات اولیه ...

    application = Application.builder().token(config.BOT_TOKEN).build()
    
    cancel_handler = CommandHandler('cancel', cancel_conversation)
    base_fallbacks = [cancel_handler]
    
    service_conv = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex(f"^({'|'.join(SERVICE_MAP.keys())})$"), service_entry_point)],
        states={
            AWAITING_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_id_and_process)],
            AWAITING_STARS_DETAILS: [MessageHandler(filters.TEXT & ~filters.COMMAND, receive_stars_details_and_process)]
        },
        fallbacks=base_fallbacks,
        per_user=True
    )
    # ... بقیه ConversationHandler ها ...

    # --- ثبت هندلرها ---
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("admin", admin_panel))
    application.add_handler(CommandHandler("profile", show_profile))
    application.add_handler(cancel_handler)

    application.add_handler(service_conv)
    # ... بقیه ...

    application.add_handler(MessageHandler(filters.Regex('^امتیاز روزانه🎁$'), daily_bonus_handler))
    application.add_handler(MessageHandler(filters.Regex('^پشتیبانی📞$'), support_handler))
    application.add_handler(MessageHandler(filters.Regex('^🏆 نفرات برتر$'), show_top_users))
    application.add_handler(MessageHandler(filters.REPLY & filters.User(config.ADMIN_ID), admin_reply_to_user))
    
    # ... بقیه هندلرها بدون تغییر ...

    logger.info("Starting bot with polling...")
    application.run_polling()

if __name__ == "__main__":
    main()
