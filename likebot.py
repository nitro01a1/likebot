import logging
import json
from datetime import datetime, timedelta
import random
import os

from telegram import Update, ReplyKeyboardMarkup, KeyboardButton, ReplyKeyboardRemove, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
    ConversationHandler,
    CallbackQueryHandler,
)
from telegram.constants import ParseMode

# --- تنظیمات اولیه (خوانده شده از متغیرهای محیطی Render) ---
BOT_TOKEN = os.getenv("BOT_TOKEN")
ADMIN_IDS_STR = os.getenv("ADMIN_IDS", "").split(',')
ADMIN_IDS = [int(admin_id) for admin_id in ADMIN_IDS_STR if admin_id]
FORCED_JOIN_CHANNELS = os.getenv("FORCED_JOIN_CHANNELS", "").split(',')

# --- مسیر فایل دیتا روی حافظه دائمی Render Disk ---
DATA_PATH = os.path.join(os.getenv("RENDER_DISK_PATH", "."), "data.json")

if not BOT_TOKEN or not ADMIN_IDS:
    raise ValueError("متغیرهای BOT_TOKEN و ADMIN_IDS باید در محیط Render تنظیم شوند!")

# --- لاگین برای دیباگ ---
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# --- متغیرهای ConversationHandler ---
(GET_GAME_ID, GET_STARS_INFO, ADMIN_PANEL, MANAGE_USER_ID, MANAGE_USER_ACTION) = range(5)

# --- ثابت‌های متنی برای دکمه‌ها (برای جلوگیری از خطای تایپی) ---
BTN_LIKE_FF = "🔥 لایک فری فایر"
BTN_ACC_INFO = "ℹ️ اطلاعات اکانت"
BTN_ACC_STICKER = "🎨 استیکر اکانت"
BTN_FREE_STARS = "🌟 استارز رایگان"
BTN_DAILY_BONUS = "🎁 امتیاز روزانه"
BTN_MY_ACCOUNT = "👤 حساب کاربری"
BTN_SUPPORT = "📞 پشتیبانی"


# --- توابع کار با پایگاه داده (JSON) ---
def load_data():
    try:
        with open(DATA_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        logger.warning(f"فایل data.json یافت نشد. یک فایل جدید ایجاد می‌شود.")
        return {
            "bot_status": "on", "users": {}, "settings": {
                "costs": {"like_ff": 1, "account_info": 1, "account_sticker": 1, "free_stars": 3},
                "secondary_reply": {"like_ff": "خطا❌ لطفا با مدیریت تماس بگیرید", "account_info": "خطا❌ لطفا با مدیریت تماس بگیرید", "account_sticker": "خطا❌ لطفا با مدیریت تماس بگیرید", "free_stars": ""}
            }
        }

def save_data(data):
    with open(DATA_PATH, 'w', encoding='utf-8') as f:
        json.dump(data, f, indent=2, ensure_ascii=False)


# --- توابع کمکی ---
async def is_member(user_id: int, context: ContextTypes.DEFAULT_TYPE) -> bool:
    if not FORCED_JOIN_CHANNELS or FORCED_JOIN_CHANNELS == ['']:
        return True
    for channel in FORCED_JOIN_CHANNELS:
        try:
            member = await context.bot.get_chat_member(chat_id=channel, user_id=user_id)
            if member.status not in ['member', 'administrator', 'creator']:
                return False
        except Exception as e:
            logger.error(f"Error checking membership for {user_id} in {channel}: {e}")
            return False
    return True

def generate_referral_link(user_id: int, bot_username: str) -> str:
    return f"https://t.me/{bot_username}?start={user_id}"


# --- نمایش منوی اصلی با کیبورد ---
async def show_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard_buttons = [
        [KeyboardButton(BTN_LIKE_FF), KeyboardButton(BTN_ACC_INFO)],
        [KeyboardButton(BTN_ACC_STICKER), KeyboardButton(BTN_FREE_STARS)],
        [KeyboardButton(BTN_DAILY_BONUS)],
        [KeyboardButton(BTN_MY_ACCOUNT), KeyboardButton(BTN_SUPPORT)]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard_buttons, resize_keyboard=True)
    await update.message.reply_text("خوش آمدید! لطفا یکی از گزینه‌ها را انتخاب کنید:", reply_markup=reply_markup)


# --- کنترلر دستورات اصلی ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_id_str = str(user.id)
    data = load_data()

    if data.get("bot_status", "on") == "off" and user.id not in ADMIN_IDS:
        await update.message.reply_text("🤖 ربات در حال حاضر خاموش است.")
        return

    # ثبت کاربر جدید و مدیریت رفرال
    if user_id_str not in data["users"]:
        data["users"][user_id_str] = {"name": user.full_name, "points": 0, "last_daily_bonus": None}
        if context.args and len(context.args) > 0:
            referrer_id = context.args[0]
            if referrer_id.isdigit() and referrer_id in data["users"] and referrer_id != user_id_str:
                data["users"][referrer_id]["points"] += 1
                try:
                    await context.bot.send_message(
                        chat_id=int(referrer_id),
                        text=f"🎉 کاربر \"{user.full_name}\" با لینک شما وارد ربات شد و 1 امتیاز به شما اضافه شد!"
                    )
                except Exception as e:
                    logger.error(f"Failed to send referral notification to {referrer_id}: {e}")
    save_data(data)
    await show_main_menu(update, context)


# --- مدیریت پیام‌های متنی (برای دکمه‌های کیبورد) ---
async def handle_text_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_text = update.message.text
    user_id = update.effective_user.id
    
    if not await is_member(user_id, context):
        await update.message.reply_text("❌ شما هنوز در همه کانال‌ها عضو نیستید! لطفا عضو شوید و دوباره تلاش کنید.")
        return

    # مسیردهی بر اساس متن دکمه
    if user_text == BTN_MY_ACCOUNT:
        await my_account(update, context)
    elif user_text == BTN_SUPPORT:
        await support(update, context)
    elif user_text == BTN_DAILY_BONUS:
        await daily_bonus(update, context)


# --- کنترلرهای بخش‌های کاربری ---
async def my_account(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    data = load_data()
    user_data = data["users"][str(user.id)]
    bot_username = (await context.bot.get_me()).username
    text = (
        f"👤 **حساب کاربری شما**\n\n"
        f"🔹 **نام:** {user_data.get('name', 'ثبت نشده')}\n"
        f"🔹 **آیدی عددی:** `{user.id}`\n"
        f"🔹 **امتیاز شما:** {user_data.get('points', 0)} امتیاز\n\n"
        f"🔗 **لینک رفرال شما:**\n`{generate_referral_link(user.id, bot_username)}`"
    )
    await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)

async def support(update: Update, context: ContextTypes.DEFAULT_TYPE):
    text = (
        "📞 **پشتیبانی ربات**\n\n"
        "در صورت وجود هرگونه مشکل، سوال یا پیشنهاد می‌توانید با ادمین‌های زیر در ارتباط باشید:\n\n"
        "🔸 **مالک ربات:** @immmdold\n"
        "🔸 **مدیر ربات:** @likeadminx7"
    )
    await update.message.reply_text(text)

async def daily_bonus(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id_str = str(update.effective_user.id)
    data = load_data()
    user_data = data["users"][user_id_str]
    last_bonus_str = user_data.get("last_daily_bonus")
    now = datetime.utcnow()

    if last_bonus_str:
        last_bonus_time = datetime.fromisoformat(last_bonus_str)
        if now < last_bonus_time + timedelta(hours=24):
            remaining_time = (last_bonus_time + timedelta(hours=24)) - now
            hours, remainder = divmod(remaining_time.total_seconds(), 3600)
            minutes, _ = divmod(remainder, 60)
            await update.message.reply_text(f"❌ شما قبلا امتیاز روزانه خود را دریافت کرده‌اید. {int(hours)} ساعت و {int(minutes)} دقیقه دیگر تلاش کنید.")
            return

    bonus = random.randint(1, 4)
    user_data["points"] += bonus
    user_data["last_daily_bonus"] = now.isoformat()
    save_data(data)
    await update.message.reply_text(f"🎉 تبریک! شما {bonus} امتیاز روزانه دریافت کردید.")


# --- مدیریت درخواست‌های سرویس (ConversationHandler) ---
async def handle_service_request(update: Update, context: ContextTypes.DEFAULT_TYPE):
    service_map = {
        BTN_LIKE_FF: "like_ff", BTN_ACC_INFO: "account_info",
        BTN_ACC_STICKER: "account_sticker", BTN_FREE_STARS: "free_stars"
    }
    service_key = service_map.get(update.message.text)
    context.user_data['service_key'] = service_key

    data = load_data()
    user_points = data["users"][str(update.effective_user.id)].get("points", 0)
    required_points = data["settings"]["costs"].get(service_key, 999)

    if user_points < required_points:
        bot_username = (await context.bot.get_me()).username
        referral_link = generate_referral_link(update.effective_user.id, bot_username)
        text = (
            f"⚠️ **امتیاز کافی نیست!**\n\n"
            f"برای دسترسی به این بخش به [{required_points}] امتیاز نیاز دارید.\n"
            f"امتیاز شما: [{user_points}]\n\n"
            f"🔗 **لینک رفرال شما:**\n`{referral_link}`\n\n"
            "برای جمع آوری امتیاز باید رفرال جمع کنید."
        )
        await update.message.reply_text(text, parse_mode=ParseMode.MARKDOWN)
        return ConversationHandler.END

    data["users"][str(update.effective_user.id)]["points"] -= required_points
    save_data(data)
    
    if service_key == "free_stars":
        await update.message.reply_text(
            "✅ امتیاز شما کسر شد.\n\nلطفا لینک کانال خود به همراه آیدی تلگرام خود را ارسال کنید:",
            reply_markup=ReplyKeyboardRemove()
        )
        return GET_STARS_INFO
    else:
        await update.message.reply_text(
            "✅ امتیاز شما کسر شد.\n\nلطفا آیدی عددی گیم خود را وارد نمایید:",
            reply_markup=ReplyKeyboardRemove()
        )
        return GET_GAME_ID

async def process_user_input_and_forward(update: Update, context: ContextTypes.DEFAULT_TYPE, success_message: str, admin_title: str):
    user_message = update.message.text
    user = update.effective_user
    service_key = context.user_data.get('service_key', 'نامشخص')
    
    admin_message = f"📬 **{admin_title}**\n\n**از طرف:** {user.full_name} (`{user.id}`)\n**نوع سرویس:** {service_key}\n\n**محتوای پیام:**\n{user_message}"
    
    for admin_id in ADMIN_IDS:
        try:
            await context.bot.send_message(chat_id=admin_id, text=admin_message, parse_mode=ParseMode.MARKDOWN)
        except Exception as e:
            logger.error(f"Failed to send message to admin {admin_id}: {e}")

    await update.message.reply_text(success_message)
    
    data = load_data()
    secondary_reply = data["settings"]["secondary_reply"].get(service_key)
    if secondary_reply:
        await update.message.reply_text(secondary_reply)
        
    await show_main_menu(update, context)
    return ConversationHandler.END

async def get_game_id(update: Update, context: ContextTypes.DEFAULT_TYPE):
    return await process_user_input_and_forward(update, context, "✅ درخواست به سرور ارسال شد. صبور باشید.", "درخواست جدید")

async def get_stars_info(update: Update, context: ContextTypes.DEFAULT_TYPE):
    return await process_user_input_and_forward(update, context, "⏳ درخواست شما در حال بررسی است. صبور باشید.", "درخواست استارز رایگان")

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text("عملیات لغو شد.")
    await show_main_menu(update, context)
    return ConversationHandler.END


# --- پنل مدیریت ---
async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if user_id not in ADMIN_IDS:
        await update.message.reply_text("شما دسترسی به این بخش را ندارید.")
        return

    data = load_data()
    bot_status = "روشن ✅" if data.get("bot_status", "on") == "on" else "خاموش ❌"
    user_count = len(data.get("users", {}))

    keyboard = [
        [InlineKeyboardButton(f"وضعیت ربات: {bot_status}", callback_data="admin_toggle_bot")],
        [InlineKeyboardButton(f"آمار کاربران: {user_count} نفر", callback_data="admin_stats")],
        [InlineKeyboardButton("مدیریت کاربر", callback_data="admin_manage_user")],
        [InlineKeyboardButton("لیست کاربران", callback_data="admin_user_list")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    await update.message.reply_text("به پنل مدیریت خوش آمدید.", reply_markup=reply_markup)
    return ADMIN_PANEL

async def handle_admin_callbacks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = load_data()

    if query.data == "admin_toggle_bot":
        data['bot_status'] = 'off' if data.get('bot_status', 'on') == 'on' else 'on'
        save_data(data)
        await admin_panel(query, context) # Refresh panel

    elif query.data == "admin_stats":
        user_count = len(data.get("users", {}))
        await query.answer(f"تعداد کل کاربران: {user_count} نفر", show_alert=True)
    
    elif query.data == "admin_user_list":
        users = data.get("users", {})
        if not users:
            text = "هیچ کاربری ثبت نشده است."
        else:
            text = "لیست کاربران:\n\n"
            for uid, udata in users.items():
                text += f"👤 نام: {udata.get('name', 'N/A')}\n🆔 آیدی: `{uid}`\n\n"
        
        keyboard = [[InlineKeyboardButton("بازگشت", callback_data="admin_panel_back")]]
        await query.edit_message_text(text, parse_mode=ParseMode.MARKDOWN, reply_markup=InlineKeyboardMarkup(keyboard))

    elif query.data == "admin_manage_user":
        await query.edit_message_text("لطفا آیدی عددی کاربری که می‌خواهید مدیریتش کنید را ارسال نمایید:")
        return MANAGE_USER_ID

    elif query.data == "admin_panel_back":
        await query.delete_message()
        await admin_panel(update, context)
        return ADMIN_PANEL
    
    return ADMIN_PANEL


async def get_user_id_for_manage(update: Update, context: ContextTypes.DEFAULT_TYPE):
    # This is now part of a conversation, so it expects a message
    target_user_id = update.message.text
    if not target_user_id.isdigit():
        await update.message.reply_text("آیدی نامعتبر است. لطفا یک آیدی عددی صحیح وارد کنید.")
        return MANAGE_USER_ID

    data = load_data()
    if target_user_id not in data["users"]:
        await update.message.reply_text("کاربری با این آیدی یافت نشد.")
        return MANAGE_USER_ID
    
    context.user_data['target_user_id'] = target_user_id
    user_info = data["users"][target_user_id]
    points = user_info.get("points", 0)
    ban_text = "رفع بن" if user_info.get("banned", False) else "بن کردن"

    keyboard = [
        [InlineKeyboardButton("➕ افزودن امتیاز", callback_data=f"manage_add_{target_user_id}")],
        [InlineKeyboardButton("➖ کسر امتیاز", callback_data=f"manage_sub_{target_user_id}")],
        [InlineKeyboardButton(f"🚫 {ban_text}", callback_data=f"manage_ban_{target_user_id}")],
        [InlineKeyboardButton("بازگشت", callback_data="admin_panel_back")]
    ]
    await update.message.reply_text(f"مدیریت کاربر `{target_user_id}`\nامتیاز فعلی: {points}\n\nچه کاری می‌خواهید انجام دهید؟", 
                                    reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.MARKDOWN)
    
    return MANAGE_USER_ACTION


async def manage_user_action(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    parts = query.data.split('_')
    action = parts[1]
    target_user_id = parts[2]
    
    data = load_data()
    user_data = data["users"][target_user_id]
    
    if action == "add":
        user_data["points"] = user_data.get("points", 0) + 1
        await query.answer("1 امتیاز اضافه شد.")
    elif action == "sub":
        user_data["points"] = user_data.get("points", 0) - 1
        await query.answer("1 امتیاز کسر شد.")
    elif action == "ban":
        current_status = user_data.get("banned", False)
        user_data["banned"] = not current_status
        await query.answer(f"کاربر {'از بن خارج شد' if current_status else 'بن شد'}.")

    save_data(data)
    
    # Refresh the management message
    points = user_data.get("points", 0)
    ban_text = "رفع بن" if user_data.get("banned", False) else "بن کردن"
    keyboard = [
        [InlineKeyboardButton("➕ افزودن امتیاز", callback_data=f"manage_add_{target_user_id}")],
        [InlineKeyboardButton("➖ کسر امتیاز", callback_data=f"manage_sub_{target_user_id}")],
        [InlineKeyboardButton(f"🚫 {ban_text}", callback_data=f"manage_ban_{target_user_id}")],
        [InlineKeyboardButton("بازگشت", callback_data="admin_panel_back")]
    ]
    await query.edit_message_text(f"مدیریت کاربر `{target_user_id}`\nامتیاز فعلی: {points}", 
                                  reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.MARKDOWN)
    return MANAGE_USER_ACTION


# --- تابع اصلی ---
def main() -> None:
    """Run the bot."""
    application = Application.builder().token(BOT_TOKEN).build()

    # فیلتر برای دکمه‌های سرویس
    service_entry_filter = (
        filters.Text([BTN_LIKE_FF]) | filters.Text([BTN_ACC_INFO]) |
        filters.Text([BTN_ACC_STICKER]) | filters.Text([BTN_FREE_STARS])
    )

    service_conv_handler = ConversationHandler(
        entry_points=[MessageHandler(service_entry_filter, handle_service_request)],
        states={
            GET_GAME_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_game_id)],
            GET_STARS_INFO: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_stars_info)],
        },
        fallbacks=[CommandHandler('cancel', cancel)],
    )

    admin_conv_handler = ConversationHandler(
        entry_points=[CommandHandler('admin', admin_panel)],
        states={
            ADMIN_PANEL: [CallbackQueryHandler(handle_admin_callbacks, pattern='^admin_')],
            MANAGE_USER_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_user_id_for_manage)],
            MANAGE_USER_ACTION: [CallbackQueryHandler(manage_user_action, pattern='^manage_')]
        },
        fallbacks=[CommandHandler('cancel', cancel), CallbackQueryHandler(handle_admin_callbacks, pattern='admin_panel_back')],
    )

    application.add_handler(CommandHandler("start", start))
    application.add_handler(service_conv_handler)
    application.add_handler(admin_conv_handler)
    
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_text_message))

    logger.info("ربات در حال اجرا است...")
    application.run_polling()


if __name__ == "__main__":
    main()
