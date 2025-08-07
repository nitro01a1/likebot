import logging
import json
import os
from functools import wraps
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
    ConversationHandler,
)
from telegram.constants import ChatMemberStatus

# ------------------- تنظیمات اولیه (بسیار مهم) -------------------
BOT_TOKEN = "7882319394:AAG-TFTzkcEccTbR3sEIOJ0I9StWJMhNeHc"
ADMIN_IDS = [1956250138, 8066854428]  # آیدی عددی تمام ادمین‌ها
DATA_FILE = "referral_data.json"
SETTINGS_FILE = "settings.json"  # فایل جدید برای تنظیمات
REQUIRED_CHANNELS = ["@x7gap", "@npvpnir"]
# -----------------------------------------------------------------

# مراحل کاربر
AWAITING_LIKE_ID, AWAITING_STAR_INFO = range(2)
# مراحل ادمین
AWAITING_USER_ID_FOR_MGMT, AWAITING_ACTION_FOR_USER, AWAITING_POINTS_TO_ADD, AWAITING_POINTS_TO_SUBTRACT = range(2, 6)

logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

# --- توابع داده‌ها و تنظیمات ---
def load_data(file_path, default_data):
    if os.path.exists(file_path):
        with open(file_path, 'r') as f:
            return json.load(f)
    return default_data

def save_data(data, file_path):
    with open(file_path, 'w') as f:
        json.dump(data, f, indent=4)

# --- دکوریتورهای دسترسی ---
def user_check(func):
    @wraps(func)
    async def wrapped(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        user = update.effective_user
        user_data = load_data(DATA_FILE, {"users": {}})
        if user_data.get("users", {}).get(str(user.id), {}).get("is_banned", False):
            await update.message.reply_text("❌ شما توسط ادمین از استفاده از خدمات ربات محروم شده‌اید.")
            return

        not_joined_channels = []
        for channel_id in REQUIRED_CHANNELS:
            try:
                member = await context.bot.get_chat_member(chat_id=channel_id, user_id=user.id)
                if member.status not in [ChatMemberStatus.MEMBER, ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.CREATOR]:
                    not_joined_channels.append(channel_id)
            except Exception as e:
                logger.error(f"Error checking channel {channel_id}: {e}")
                await context.bot.send_message(ADMIN_IDS[0], f"⚠️ خطا در بررسی عضویت کانال `{channel_id}`.")
                return

        if not_joined_channels:
            keyboard = []
            for i, channel_id in enumerate(not_joined_channels, 1):
                channel_info = await context.bot.get_chat(channel_id)
                invite_link = channel_info.invite_link or f"https://t.me/{channel_info.username}"
                title = "کانال" if channel_info.type == 'channel' else "گروه"
                keyboard.append([InlineKeyboardButton(f"عضویت در {title} {i}", url=invite_link)])
            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.message.reply_text("❌ برای استفاده از ربات، ابتدا باید در کانال(های) زیر عضو شوید:", reply_markup=reply_markup)
            return
        
        return await func(update, context, *args, **kwargs)
    return wrapped

def admin_only(func):
    @wraps(func)
    async def wrapped(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        if update.effective_user.id not in ADMIN_IDS:
            await update.message.reply_text("❌ شما دسترسی لازم برای اجرای این دستور را ندارید.")
            return
        return await func(update, context, *args, **kwargs)
    return wrapped

# --- توابع کاربران ---
@user_check
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    data = load_data(DATA_FILE, {"users": {}, "referral_counts": {}})
    if str(user.id) not in data.get("users", {}):
        data.setdefault("users", {})[str(user.id)] = {"is_banned": False}
    if context.args:
        try:
            referrer_id = int(context.args[0])
            if str(user.id) not in data["users"] and user.id != referrer_id:
                data["users"][str(user.id)]["referred_by"] = referrer_id
                referrer_id_str = str(referrer_id)
                data["referral_counts"][referrer_id_str] = data["referral_counts"].get(referrer_id_str, 0) + 1
                save_data(data, DATA_FILE)
                await context.bot.send_message(chat_id=referrer_id, text=f"🎉 یک کاربر جدید ({user.first_name}) با لینک شما وارد ربات شد.")
        except (ValueError, IndexError):
            pass
    save_data(data, DATA_FILE)
    
    keyboard = [["لایک رایگان🔥", "استارز رایگان⭐"], ["اطلاعات اکانت 👤", "پشتیبانی📱"]]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.message.reply_text("به ربات لایک رایگان x7 خوش آمدید!", reply_markup=reply_markup)

@user_check
async def support(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    support_text = "📱 **پشتیبانی ربات**\n\n▫️ **مالک ربات:** @immmdold\n▫️ **پشتیبانی:** @likeadminx7"
    await update.message.reply_text(support_text)

@user_check
async def account_info(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    data = load_data(DATA_FILE, {"referral_counts": {}})
    score = data["referral_counts"].get(str(user.id), 0)
    bot_username = (await context.bot.get_me()).username
    referral_link = f"https://t.me/{bot_username}?start={user.id}"
    info_text = (f"👤 **اطلاعات اکانت شما**\n\n▫️ **آیدی عددی:** `{user.id}`\n▫️ **امتیاز شما:** **{score}**\n\n🔗 **لینک دعوت شما:**\n`{referral_link}`")
    await update.message.reply_text(info_text, parse_mode='Markdown')

@user_check
async def free_like_request(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = update.effective_user
    user_data = load_data(DATA_FILE, {"referral_counts": {}})
    settings = load_data(SETTINGS_FILE, {"like_cost": 1})
    like_cost = settings.get("like_cost", 1)
    user_score = user_data["referral_counts"].get(str(user.id), 0)

    if user_score < like_cost:
        await update.message.reply_text(f"❌ امتیاز شما برای دریافت لایک رایگان کافی نیست. (نیازمند: {like_cost} امتیاز، امتیاز شما: {user_score})")
        return ConversationHandler.END
    
    # کسر امتیاز
    user_data["referral_counts"][str(user.id)] = user_score - like_cost
    save_data(user_data, DATA_FILE)
    
    await update.message.reply_text(f"✅ {like_cost} امتیاز از شما کسر شد.\nلطفا آیدی خود را در قالب یک متن ارسال کنید.", reply_markup=ReplyKeyboardRemove())
    return AWAITING_LIKE_ID

@user_check
async def free_star_request(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = update.effective_user
    data = load_data(DATA_FILE, {"referral_counts": {}})
    score = data["referral_counts"].get(str(user.id), 0)
    if score < 2:
        bot_username = (await context.bot.get_me()).username
        referral_link = f"https://t.me/{bot_username}?start={user.id}"
        await update.message.reply_text(f"❌ امتیاز شما کافی نیست! (امتیاز شما: {score})\nبرای دریافت یک استارز، باید ۲ نفر را دعوت کنید.\n\nلینک دعوت شما:\n`{referral_link}`", parse_mode='Markdown')
        return ConversationHandler.END
    else:
        data["referral_counts"][str(user.id)] = score - 2
        save_data(data, DATA_FILE)
        await update.message.reply_text("✅ امتیاز از شما کسر شد.\nلطفا آیدی عددی خود و آیدی چنلتون را در قالب یک متن ارسال کنید.", reply_markup=ReplyKeyboardRemove())
        return AWAITING_STAR_INFO

async def forward_like_id(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = update.effective_user
    text = update.message.text
    header = f"📩 **درخواست لایک جدید**\nاز: {user.first_name} (ID: `{user.id}`)\n\n**آیدی ارسالی:**\n{text}"
    for admin_id in ADMIN_IDS:
        await context.bot.send_message(chat_id=admin_id, text=header, parse_mode='Markdown')
    await update.message.reply_text("✅ درخواست شما ارسال شد.")
    await start(update, context)
    return ConversationHandler.END

async def forward_star_info(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = update.effective_user
    text = update.message.text
    header = f"⭐ **درخواست استارز جدید**\nاز: {user.first_name} (ID: `{user.id}`)\n\n**اطلاعات ارسالی:**\n{text}"
    for admin_id in ADMIN_IDS:
        await context.bot.send_message(chat_id=admin_id, text=header, parse_mode='Markdown')
    await update.message.reply_text("✅ درخواست شما ارسال شد.")
    await start(update, context)
    return ConversationHandler.END

# --- توابع پنل ادمین ---
@admin_only
async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    keyboard = [["آمار ربات 📊", "مدیریت کاربر 🛠"], ["تنظیمات ربات ⚙️", "بازگشت به منوی کاربر"]]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.message.reply_text("به پنل مدیریت خوش آمدید.", reply_markup=reply_markup)

@admin_only
async def bot_stats(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    data = load_data(DATA_FILE, {"users": {}})
    total_users = len(data.get("users", {}))
    await update.message.reply_text(f"📊 **آمار ربات**\n\n▫️ تعداد کل کاربران ثبت شده: **{total_users}** نفر")

@admin_only
async def bot_settings(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    settings = load_data(SETTINGS_FILE, {"like_cost": 1})
    like_cost = settings.get("like_cost", 1)
    button_text = f"نیازمندی لایک (فعلی: {like_cost} امتیاز)"
    keyboard = [[button_text], ["بازگشت به پنل ادمین"]]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.message.reply_text("تنظیمات ربات:", reply_markup=reply_markup)

@admin_only
async def toggle_like_cost(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    settings = load_data(SETTINGS_FILE, {"like_cost": 1})
    current_cost = settings.get("like_cost", 1)
    new_cost = 0 if current_cost == 1 else 1
    settings["like_cost"] = new_cost
    save_data(settings, SETTINGS_FILE)
    await update.message.reply_text(f"✅ نیازمندی امتیاز برای لایک رایگان به **{new_cost}** تغییر یافت.")
    await bot_settings(update, context) # نمایش مجدد منوی تنظیمات

@admin_only
async def manage_user_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("لطفا آیدی عددی کاربری که قصد مدیریت آن را دارید، وارد کنید:", reply_markup=ReplyKeyboardRemove())
    return AWAITING_USER_ID_FOR_MGMT

async def get_user_id_for_mgmt(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    try:
        user_id = int(update.message.text)
        context.user_data['user_to_manage'] = user_id
        data = load_data(DATA_FILE, {"users": {}, "referral_counts": {}})
        user_info = data.get("users", {}).get(str(user_id))
        if not user_info:
            await update.message.reply_text("❌ کاربری با این آیدی یافت نشد.")
            return ConversationHandler.END
        
        score = data.get("referral_counts", {}).get(str(user_id), 0)
        is_banned = user_info.get("is_banned", False)
        ban_status_text = "✅ (بن نیست)" if not is_banned else "🚫 (بن است)"
        
        text = f"👤 **مدیریت کاربر:** `{user_id}`\n▫️ **امتیاز فعلی:** {score}\n▫️ **وضعیت بن:** {ban_status_text}"
        keyboard = [["بن / آنبن کردن 🚫"], ["افزودن امتیاز ✨", "کاهش امتیاز 🔻"], ["لغو"]]
        reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
        await update.message.reply_text(text, reply_markup=reply_markup, parse_mode='Markdown')
        return AWAITING_ACTION_FOR_USER
    except ValueError:
        await update.message.reply_text("❌ ورودی نامعتبر است. لطفا فقط آیدی عددی کاربر را وارد کنید.")
        return ConversationHandler.END

async def toggle_ban_user(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_id = context.user_data['user_to_manage']
    data = load_data(DATA_FILE, {"users": {}})
    user_info = data["users"][str(user_id)]
    current_status = user_info.get("is_banned", False)
    user_info["is_banned"] = not current_status
    save_data(data, DATA_FILE)
    new_status_text = "🚫 کاربر با موفقیت **بن** شد." if not current_status else "✅ کاربر با موفقیت **آنبن** شد."
    await update.message.reply_text(new_status_text, parse_mode='Markdown')
    await admin_panel(update, context)
    return ConversationHandler.END

async def add_points_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("چه تعداد امتیاز می‌خواهید به این کاربر اضافه کنید؟ لطفا عدد را وارد کنید:")
    return AWAITING_POINTS_TO_ADD

async def subtract_points_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("چه تعداد امتیاز می‌خواهید از این کاربر کم کنید؟ لطفا عدد را وارد کنید:")
    return AWAITING_POINTS_TO_SUBTRACT

async def add_points_to_user(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    try:
        points_to_add = int(update.message.text)
        user_id = context.user_data['user_to_manage']
        data = load_data(DATA_FILE, {"referral_counts": {}})
        user_id_str = str(user_id)
        data["referral_counts"][user_id_str] = data["referral_counts"].get(user_id_str, 0) + points_to_add
        save_data(data, DATA_FILE)
        new_score = data["referral_counts"][user_id_str]
        await update.message.reply_text(f"✅ **{points_to_add}** امتیاز با موفقیت اضافه شد.\nامتیاز جدید کاربر: **{new_score}**")
        await admin_panel(update, context)
        return ConversationHandler.END
    except ValueError:
        await update.message.reply_text("❌ ورودی نامعتبر است. لطفا فقط یک عدد وارد کنید.")
        return AWAITING_POINTS_TO_ADD
        
async def subtract_points_from_user(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    try:
        points_to_subtract = int(update.message.text)
        user_id = context.user_data['user_to_manage']
        data = load_data(DATA_FILE, {"referral_counts": {}})
        user_id_str = str(user_id)
        current_score = data["referral_counts"].get(user_id_str, 0)
        # جلوگیری از منفی شدن امتیاز
        new_score = max(0, current_score - points_to_subtract)
        data["referral_counts"][user_id_str] = new_score
        save_data(data, DATA_FILE)
        
        await update.message.reply_text(f"✅ **{points_to_subtract}** امتیاز با موفقیت کسر شد.\nامتیاز جدید کاربر: **{new_score}**")
        await admin_panel(update, context)
        return ConversationHandler.END
    except ValueError:
        await update.message.reply_text("❌ ورودی نامعتبر است. لطفا فقط یک عدد وارد کنید.")
        return AWAITING_POINTS_TO_SUBTRACT

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("عملیات لغو شد.")
    if update.effective_user.id in ADMIN_IDS:
        await admin_panel(update, context)
    else:
        await start(update, context)
    return ConversationHandler.END

def main() -> None:
    application = Application.builder().token(BOT_TOKEN).build()

    user_conv_handler = ConversationHandler(
        entry_points=[
            MessageHandler(filters.Regex("^لایک رایگان🔥$"), free_like_request),
            MessageHandler(filters.Regex("^استارز رایگان⭐$"), free_star_request),
        ],
        states={
            AWAITING_LIKE_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, forward_like_id)],
            AWAITING_STAR_INFO: [MessageHandler(filters.TEXT & ~filters.COMMAND, forward_star_info)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    admin_conv_handler = ConversationHandler(
        entry_points=[MessageHandler(filters.Regex("^مدیریت کاربر 🛠$"), manage_user_start)],
        states={
            AWAITING_USER_ID_FOR_MGMT: [MessageHandler(filters.TEXT & ~filters.COMMAND, get_user_id_for_mgmt)],
            AWAITING_ACTION_FOR_USER: [
                MessageHandler(filters.Regex("^بن / آنبن کردن 🚫$"), toggle_ban_user),
                MessageHandler(filters.Regex("^افزودن امتیاز ✨$"), add_points_start),
                MessageHandler(filters.Regex("^کاهش امتیاز 🔻$"), subtract_points_start),
            ],
            AWAITING_POINTS_TO_ADD: [MessageHandler(filters.TEXT & ~filters.COMMAND, add_points_to_user)],
            AWAITING_POINTS_TO_SUBTRACT: [MessageHandler(filters.TEXT & ~filters.COMMAND, subtract_points_from_user)],
        },
        fallbacks=[CommandHandler("cancel", cancel), MessageHandler(filters.Regex("^لغو$"), cancel)],
    )

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CommandHandler("admin", admin_panel))
    
    application.add_handler(MessageHandler(filters.Regex("^اطلاعات اکانت 👤$"), account_info))
    application.add_handler(MessageHandler(filters.Regex("^پشتیبانی📱$"), support))
    
    application.add_handler(MessageHandler(filters.Regex("^آمار ربات 📊$"), bot_stats))
    application.add_handler(MessageHandler(filters.Regex("^تنظیمات ربات ⚙️$"), bot_settings))
    application.add_handler(MessageHandler(filters.Regex(r"^نیازمندی لایک \(فعلی: \d+ امتیاز\)$"), toggle_like_cost))
    application.add_handler(MessageHandler(filters.Regex("^بازگشت به پنل ادمین$"), admin_panel))
    application.add_handler(MessageHandler(filters.Regex("^بازگشت به منوی کاربر$"), start))

    application.add_handler(user_conv_handler)
    application.add_handler(admin_conv_handler)

    print("ربات با تمام قابلیت‌های پیشرفته در حال اجراست...")
    application.run_polling()

if __name__ == "__main__":
    main()
