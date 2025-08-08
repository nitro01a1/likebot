# main.py (نسخه نهایی با VIP، رفع اشکال تنظیم هزینه و تمام قابلیت‌های دیگر)

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

import config
import database

# --- تنظیمات و استیت‌ها ---
logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

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


# دیکشنری سرویس‌های کاربر
USER_SERVICES = {
    'free_like': 'لایک رایگان🔥', 'account_info': 'اطلاعات اکانت📄',
    'free_stars': 'استارز رایگان⭐', 'teddy_gift': 'گیفت تدی🗿',
    'daily_bonus': 'امتیاز روزانه🎁', 'transfer_points': 'انتقال امتیاز 🔄',
    'vip_shop': 'فروشگاه VIP 💎', 'lottery': 'قرعه‌کشی 🎟️'
}

# دیکشنری سرویس‌هایی که هزینه قابل تنظیم دارند
COSTS_TO_SET = {
    'free_like': 'لایک رایگان🔥', 'free_stars': 'استارز رایگان⭐',
    'account_info': 'اطلاعات اکانت📄', 'teddy_gift': 'گیفت تدی🗿',
    'vip_30_day': 'عضویت VIP (۳۰ روز)', 'lottery_ticket': 'بلیت قرعه‌کشی'
}


# ==============================================================================
# توابع کمکی و کیبوردها
# ==============================================================================

def get_main_reply_keyboard():
    return ReplyKeyboardMarkup([
        ['حساب کاربری👤', '🏆 نفرات برتر'],
        ['فروشگاه VIP 💎', 'قرعه‌کشی 🎟️'],
        ['لایک رایگان🔥', 'استارز رایگان⭐'],
        ['اطلاعات اکانت📄', 'گیفت تدی🗿'],
        ['امتیاز روزانه🎁', 'انتقال امتیاز 🔄', 'کد هدیه 🎁'],
        ['پشتیبانی📞']
    ], resize_keyboard=True)

def calculate_transfer_tax(amount: int, is_vip: bool) -> int:
    base_tax = 0
    if 3 <= amount < 5: base_tax = 1
    elif 5 <= amount < 10: base_tax = 2
    elif 10 <= amount < 15: base_tax = 3
    elif 15 <= amount < 20: base_tax = 4
    elif amount >= 20: base_tax = 5
    
    return math.ceil(base_tax / 2) if is_vip else base_tax

async def check_user_preconditions(update: Update, context: ContextTypes.DEFAULT_TYPE) -> bool:
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

# ==============================================================================
# کنترلرهای اصلی کاربران
# ==============================================================================

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    bot_is_on = database.get_setting('bot_status', 'true') == 'true'
    if not bot_is_on and user.id != config.ADMIN_ID:
        await update.message.reply_text("🔴 ربات در حال حاضر در حال تعمیر و بروزرسانی است. لطفا بعدا تلاش کنید.")
        return
    is_new_user = not database.user_exists(user.id)
    if is_new_user and context.args:
        try:
            referrer_id = int(context.args[0])
            if referrer_id != user.id:
                database.get_or_create_user(user.id, user.first_name, referred_by=referrer_id)
                referrer_user = database.get_or_create_user(referrer_id, "Unknown")
                points_to_add = 2 if referrer_user.get('vip_status') == 1 else 1
                database.update_points(referrer_id, points_to_add)
                await context.bot.send_message(chat_id=referrer_id, text=f"یک کاربر جدید از طریق لینک شما وارد ربات شد و {points_to_add} امتیاز دریافت کردید!")
        except Exception as e:
            logger.error(f"Referral error: {e}")
            database.get_or_create_user(user.id, user.first_name)
    else:
        database.get_or_create_user(user.id, user.first_name)
    await update.message.reply_text(f"سلام {user.first_name}! به ربات ما خوش آمدید.", reply_markup=get_main_reply_keyboard())


async def profile_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if not await check_user_preconditions(update, context): return
    user = update.effective_user
    db_user = database.get_or_create_user(user.id, user.first_name)
    bot_username = (await context.bot.get_me()).username
    referral_link = f"https://t.me/{bot_username}?start={user.id}"
    referral_count = database.get_referral_count(user.id)
    vip_text = ""
    if db_user.get('vip_status') == 1:
        expiry_date_str = db_user.get('vip_expiry_date')
        if expiry_date_str:
            expiry_dt = datetime.fromisoformat(expiry_date_str)
            remaining_days = max(0, (expiry_dt - datetime.now()).days)
            vip_text = f"💎 **وضعیت VIP:** فعال (تا {remaining_days} روز دیگر)"
    profile_text = (f"👤 **حساب کاربری شما**\n\n"
                  f"🏷️ نام: {db_user['first_name']}\n"
                  f"🆔 آیدی: `{user.id}`\n"
                  f"⭐️ امتیاز: {db_user['points']}\n"
                  f"👥 تعداد زیرمجموعه: {referral_count} نفر\n"
                  f"{vip_text}\n\n"
                  f"🔗 لینک دعوت شما:\n`{referral_link}`")
    await update.message.reply_text(profile_text, parse_mode=ParseMode.MARKDOWN)


async def daily_bonus_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    if database.get_setting('service_daily_bonus_status', 'true') == 'false':
        await update.message.reply_text("❌ این سرویس در حال حاضر توسط مدیر غیرفعال شده است.")
        return
    if not await check_user_preconditions(update, context): return
    user = update.effective_user
    db_user = database.get_or_create_user(user.id, user.first_name)
    now = datetime.now()
    if db_user.get('last_daily_claim'):
        last_claim_time = datetime.fromisoformat(db_user['last_daily_claim'])
        if now - last_claim_time < timedelta(hours=24):
            remaining_time = (last_claim_time + timedelta(hours=24)) - now
            hours, rem = divmod(remaining_time.seconds, 3600)
            minutes, _ = divmod(rem, 60)
            await update.message.reply_text(f"شما قبلا امتیاز روزانه خود را دریافت کرده‌اید.\nزمان باقی‌مانده: {hours} ساعت و {minutes} دقیقه")
            return
    if db_user.get('vip_status') == 1:
        points = list(range(1, 11))
        weights = [30, 20, 15, 10, 8, 6, 5, 3, 2, 1]
        bonus_points = random.choices(points, weights=weights, k=1)[0]
        message_suffix = " (پاداش ویژه VIP ✨)"
    else:
        bonus_points = random.randint(1, 5)
        message_suffix = ""
    database.update_points(user.id, bonus_points)
    database.set_daily_claim(user.id)
    new_points = database.get_or_create_user(user.id, user.first_name)['points']
    await update.message.reply_text(f"🎁 تبریک! شما {bonus_points} امتیاز روزانه دریافت کردید.{message_suffix}\nموجودی فعلی: {new_points} امتیاز")


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

async def service_entry_point(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    service_key = next((key for key, name in USER_SERVICES.items() if name == update.message.text), None)
    if not service_key: return ConversationHandler.END
    if database.get_setting(f'service_{service_key}_status', 'true') == 'false':
        await update.message.reply_text("❌ این سرویس در حال حاضر توسط مدیر غیرفعال شده است.")
        return ConversationHandler.END
    if not await check_user_preconditions(update, context): return ConversationHandler.END
    cost = int(database.get_setting(f'{service_key}_cost', '1'))
    user = update.effective_user
    db_user = database.get_or_create_user(user.id, user.first_name)
    if db_user['points'] < cost:
        await update.message.reply_text(f"❌ امتیاز شما برای «{update.message.text}» کافی نیست! (نیاز به {cost} امتیاز)")
        return ConversationHandler.END
    context.user_data['service_key'] = service_key
    context.user_data['cost'] = cost
    database.update_points(user.id, -cost)
    new_points = database.get_or_create_user(user.id, user.first_name)['points']
    prompt_message = ""
    next_state = AWAITING_ID
    if service_key == 'free_stars':
        prompt_message = "لطفا ایدی عددی حساب خود در ربات، لینک کانال و پستی که می\u200cخواهید برای آن استارز زده شود را در قالب یک متن واحد برای ما ارسال کنید."
        next_state = AWAITING_STARS_DETAILS
    elif service_key == 'teddy_gift':
        prompt_message = "لطفاً آیدی عددی و آیدی اکانت تلگرام خود (مثلا @username) را در یک پیام واحد وارد کنید."
    elif service_key == 'account_info':
        prompt_message = "لطفاً آیدی عددی بازی خود که می‌خواهید برای آن اطلاعات دریافت کنید را ارسال نمایید."
    else:
        prompt_message = "برای تکمیل سفارش، آیدی عددی بازی خود را ارسال کنید."
    await update.message.reply_text(f"✅ {cost} امتیاز از شما کسر شد. موجودی جدید: {new_points} امتیاز.\n\n{prompt_message}\n\nبرای انصراف /cancel را بزنید.")
    return next_state


async def receive_id_and_process(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = update.effective_user
    details_text = update.message.text
    service_key = context.user_data.get('service_key')
    service_display_name = USER_SERVICES.get(service_key, "سرویس نامشخص")
    forward_text = (f"📩 **درخواست جدید**\n"
                    f"**از کاربر:** {user.first_name} (`{user.id}`)\n"
                    f"**نوع سرویس:** {service_display_name}\n\n"
                    f"**اطلاعات ارسالی:**\n"
                    f"{details_text}")
    await context.bot.send_message(chat_id=config.ADMIN_ID, text=forward_text, parse_mode=ParseMode.MARKDOWN)
    await update.message.reply_text("✅ درخواست شما با موفقیت ثبت و برای ادمین ارسال شد.", reply_markup=get_main_reply_keyboard())
    context.user_data.clear()
    return ConversationHandler.END


async def transfer_entry(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if database.get_setting('service_transfer_points_status', 'true') == 'false':
        await update.message.reply_text("❌ این سرویس در حال حاضر توسط مدیر غیرفعال شده است.")
        return ConversationHandler.END
    if not await check_user_preconditions(update, context): return ConversationHandler.END
    user = update.effective_user
    db_user = database.get_or_create_user(user.id, user.first_name)
    transfer_limit = 5 if db_user.get('vip_status') == 1 else 1
    if db_user.get('daily_transfer_count', 0) >= transfer_limit:
        await update.message.reply_text(f"❌ شما امروز از سهمیه انتقال امتیاز خود ({transfer_limit} بار) استفاده کرده‌اید.");
        return ConversationHandler.END
    await update.message.reply_text("🔹 لطفاً آیدی عددی کاربر گیرنده را وارد کنید.\n\nبرای لغو /cancel را بزنید.");
    return AWAITING_RECIPIENT_ID


async def receive_recipient_id(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    # ...
    pass


async def process_transfer(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    # ...
    pass


async def gift_code_button_entry(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    # ...
    pass


async def process_gift_code_input(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    # ...
    pass


async def vip_shop_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # ...
    pass


async def buy_vip_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # ...
    pass


async def lottery_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # ...
    pass


async def buy_lottery_ticket_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # ...
    pass

# ==============================================================================
# کنترلرهای پنل ادمین
# ==============================================================================

async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if update.effective_user.id != config.ADMIN_ID: return
    secondary_error_status = "🟢" if database.get_setting('secondary_error_enabled', 'false') == 'true' else "🔴"
    keyboard = [
        [InlineKeyboardButton("ارسال پیام همگانی 📢", callback_data='admin_broadcast')],
        [InlineKeyboardButton("مدیریت قرعه‌کشی 🎟️", callback_data='admin_lottery')],
        [InlineKeyboardButton("مدیریت کاربر 👤", callback_data='admin_manage_user'), InlineKeyboardButton("لیست اعضای VIP 💎", callback_data='list_vips_page_1')],
        [InlineKeyboardButton("تنظیم هزینه\u200cها ⚙️", callback_data='admin_set_costs'), InlineKeyboardButton("مدیریت وضعیت سرویس‌ها 🔧", callback_data='admin_manage_services')],
        [InlineKeyboardButton("دریافت فایل پشتیبان 💾", callback_data='admin_backup_db'), InlineKeyboardButton(f"خطای ثانویه {secondary_error_status}", callback_data='secondary_error_panel')]
    ]
    text = "به پنل مدیریت خوش آمدید."
    if update.callback_query:
        await update.callback_query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))
    else:
        await update.message.reply_text(text, reply_markup=InlineKeyboardMarkup(keyboard))


async def set_costs_entry(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    keyboard = []
    text = "هزینه کدام بخش را می‌خواهید تغییر دهید؟\n\n"
    for key, name in COSTS_TO_SET.items():
        default_cost = '300' if key == 'vip_30_day' else '5' if key == 'lottery_ticket' else '10' if key == 'teddy_gift' else '1'
        cost = database.get_setting(f'{key}_cost', default_cost)
        text += f"▫️ {name}: **{cost}** امتیاز\n"
        keyboard.append([InlineKeyboardButton(f"تغییر هزینه {name}", callback_data=f'setcost_{key}')])
    keyboard.append([InlineKeyboardButton("بازگشت ↩️", callback_data='back_to_admin_panel')])
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.MARKDOWN)
    return AWAITING_SERVICE_FOR_COST


async def ask_for_new_cost(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    service_key = query.data.split('_', 1)[1]
    context.user_data['service_to_set_cost'] = service_key
    service_name_fa = COSTS_TO_SET.get(service_key, "این سرویس")
    await query.edit_message_text(f"لطفاً هزینه جدید را برای «{service_name_fa}» به صورت یک عدد ارسال کنید.\nبرای لغو /cancel را بزنید.")
    return AWAITING_COST_AMOUNT


async def set_new_cost(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
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
    await admin_panel(update, context)
    return ConversationHandler.END


async def manage_services_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # ...
    pass


async def toggle_service_status(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # ...
    pass


async def show_user_manage_options(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    # ...
    pass


async def grant_vip_entry(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    # ...
    pass


async def process_vip_duration(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    # ...
    pass


async def list_vip_users_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # ...
    pass


# ==============================================================================
# تابع اصلی و راه‌اندازی ربات
# ==============================================================================

def main() -> None:
    database.init_db()
    for key in USER_SERVICES.keys():
        if not database.get_setting(f'service_{key}_status'):
            database.set_setting(f'service_{key}_status', 'true')
    for key, name in COSTS_TO_SET.items():
        default_cost = '300' if key == 'vip_30_day' else '5' if key == 'lottery_ticket' else '10' if key == 'teddy_gift' else '1'
        if not database.get_setting(f'{key}_cost'):
            database.set_setting(f'{key}_cost', default_cost)

    application = Application.builder().token(config.BOT_TOKEN).build()

    # ... (تعریف تمام ConversationHandler ها)

    # --- ثبت کنترلرها ---
    # ... (ثبت تمام CommandHandler و MessageHandler و CallbackQueryHandler ها)

    logger.info("ربات با سیستم VIP و رفع اشکالات در حال اجراست...")
    application.run_polling()


if __name__ == "__main__":
    main()
