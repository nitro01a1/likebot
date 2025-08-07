import logging
import json
import os
import random
from datetime import datetime, timedelta
from functools import wraps
from flask import Flask
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
    ConversationHandler,
    CallbackQueryHandler,
)

# تنظیمات اولیه
app = Flask(__name__)
BOT_TOKEN = "7882319394:AAG-TFTzkcEccTbR3sEIOJ0I9StWJMhNeHc"
ADMIN_IDS = [1956250138, 8066854428]
DATA_FILE = "referral_data.json"
SETTINGS_FILE = "settings.json"
REQUIRED_CHANNELS = ["@npvpnir", "@x7gap"]
USERS_PER_PAGE = 10
DEFAULT_AUTOREPLY_MSG = "خطا در اتصال به سرور❌ لطفا با مدیریت تماس بگیرید @likeadminx7"

# مراحل کاربر
AWAITING_LIKE_ID, AWAITING_STAR_INFO, AWAITING_FF_INFO, AWAITING_STICKER_INFO = range(4)

# مراحل ادمین
AWAITING_USER_ID_FOR_MGMT, AWAITING_ACTION_FOR_USER, AWAITING_POINTS_TO_ADD, AWAITING_POINTS_TO_SUBTRACT, \
AWAITING_NEW_COST, AWAITING_AUTOREPLY_MSG = range(4, 10)

logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

# توابع داده‌ها و تنظیمات
def load_data(file_path, default_data):
    if os.path.exists(file_path):
        with open(file_path, 'r') as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                logger.error(f"Error loading {file_path}: Invalid JSON")
                return default_data
    return default_data

def save_data(data, file_path):
    try:
        with open(file_path, 'w') as f:
            json.dump(data, f, indent=4)
    except Exception as e:
        logger.error(f"Error saving {file_path}: {e}")

# دکوریتورهای دسترسی
def user_check(func):
    @wraps(func)
    async def wrapped(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        user = update.effective_user
        if not user:
            return

        settings = load_data(SETTINGS_FILE, {"is_bot_active": True})
        if not settings.get("is_bot_active", True) and user.id not in ADMIN_IDS:
            await update.message.reply_text("🔴 ربات خاموشه.")
            return

        user_data = load_data(DATA_FILE, {"users": {}, "referral_counts": {}})
        if user_data.get("users", {}).get(str(user.id), {}).get("is_banned", False):
            await update.message.reply_text("❌ بن شدی.")
            return

        not_joined_channels = []
        for channel_id in REQUIRED_CHANNELS:
            try:
                member = await context.bot.get_chat_member(chat_id=channel_id, user_id=user.id)
                if member.status not in ["member", "administrator", "owner"]:
                    not_joined_channels.append(channel_id)
            except Exception as e:
                logger.error(f"Channel check error for {channel_id}: {e}")
                return

        if not_joined_channels:
            keyboard = [[InlineKeyboardButton(f"عضویت", url=f"https://t.me/{channel_id[1:]}")] for channel_id in not_joined_channels]
            reply_markup = InlineKeyboardMarkup(keyboard)
            await update.message.reply_text("❌ عضو کانال شو:", reply_markup=reply_markup)
            return

        user_info = user_data.get("users", {}).get(str(user.id), {})
        if "pending_referrer" in user_info:
            referrer_id = user_info["pending_referrer"]
            user_data.setdefault("referral_counts", {})[str(referrer_id)] = user_data.get("referral_counts", {}).get(str(referrer_id), 0) + 1
            del user_data["users"][str(user.id)]["pending_referrer"]
            save_data(user_data, DATA_FILE)
            try:
                await context.bot.send_message(chat_id=referrer_id, text="✅ کاربر جدید با لینکت.")
            except Exception as e:
                logger.warning(f"Referral notify failed for {referrer_id}: {e}")

        return await func(update, context, *args, **kwargs)
    return wrapped

def admin_only(func):
    @wraps(func)
    async def wrapped(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        if update.effective_user.id not in ADMIN_IDS:
            await update.message.reply_text("❌ دسترسی نداری.")
            return
        return await func(update, context, *args, **kwargs)
    return wrapped

# توابع اصلی کاربران
@user_check
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    data = load_data(DATA_FILE, {"users": {}, "referral_counts": {}})
    user_id_str = str(user.id)

    if user_id_str not in data.get("users", {}):
        data.setdefault("users", {})[user_id_str] = {"is_banned": False, "last_bonus": None}

    if context.args:
        try:
            referrer_id = int(context.args[0])
            if str(referrer_id) != user_id_str and "referred_by" not in data["users"].get(user_id_str, {}):
                data["users"][user_id_str]["pending_referrer"] = referrer_id
                save_data(data, DATA_FILE)
        except (ValueError, IndexError):
            pass

    save_data(data, DATA_FILE)
    keyboard = [["لایک رایگان🔥", "استارز رایگان⭐"], ["امتیاز روزانه🎁", "اطلاعات اکانت 👤"], ["پشتیبانی📱"]]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.message.reply_text("خوش اومدی!", reply_markup=reply_markup)

@user_check
async def daily_bonus(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    data = load_data(DATA_FILE, {"users": {}, "referral_counts": {}})
    user_id_str = str(user.id)
    user_info = data.get("users", {}).get(user_id_str, {"last_bonus": None})

    last_bonus = user_info.get("last_bonus")
    if last_bonus and datetime.fromisoformat(last_bonus) > datetime.now() - timedelta(hours=24):
        await update.message.reply_text("❌ ۲۴ ساعت صبر کن.")
        return

    points = random.randint(1, 5)
    data.setdefault("referral_counts", {})[user_id_str] = data.get("referral_counts", {}).get(user_id_str, 0) + points
    data["users"][user_id_str]["last_bonus"] = datetime.now().isoformat()
    save_data(data, DATA_FILE)
    await update.message.reply_text(f"🎉 {points} امتیاز گرفتی!", parse_mode='Markdown')

@user_check
async def account_info(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    data = load_data(DATA_FILE, {"referral_counts": {}})
    score = data.get("referral_counts", {}).get(str(user.id), 0)
    bot_username = (await context.bot.get_me()).username
    referral_link = f"https://t.me/{bot_username}?start={user.id}"
    await update.message.reply_text(f"👤 آیدی: {user.id}\nامتیاز: {score}\nلینک: {referral_link}", parse_mode='Markdown')

@user_check
async def support(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await update.message.reply_text("📱 پشتیبانی: @likeadminx7")

async def generic_request_start(update: Update, context: ContextTypes.DEFAULT_TYPE, service_key: str, prompt: str, next_state: int) -> int:
    user = update.effective_user
    user_data = load_data(DATA_FILE, {"referral_counts": {}})
    settings = load_data(SETTINGS_FILE, {"like_cost": 1, "star_cost": 1, "ff_cost": 1, "sticker_cost": 1})

    cost = settings.get(f"{service_key}_cost", 1)
    score = user_data.get("referral_counts", {}).get(str(user.id), 0)
    if score < cost:
        bot_username = (await context.bot.get_me()).username
        await update.message.reply_text(f"❌ امتیاز کمه ({cost} نیازه، تو {score} داری).")
        return ConversationHandler.END

    user_data.setdefault("referral_counts", {})[str(user.id)] = score - cost
    save_data(user_data, DATA_FILE)
    await update.message.reply_text(f"✅ {cost} امتیاز کسر شد.\n{prompt}")
    return next_state

async def free_like_request(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    return await generic_request_start(update, context, "like", "آیدی رو بفرست:", AWAITING_LIKE_ID)

async def free_star_request(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    return await generic_request_start(update, context, "star", "آیدی و چنل رو بفرست:", AWAITING_STAR_INFO)

async def forward_like_id(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = update.effective_user
    text = update.message.text
    for admin_id in ADMIN_IDS:
        await context.bot.send_message(chat_id=admin_id, text=f"📩 لایک از {user.id}: {text}")
    await update.message.reply_text("✅ درخواستت رفت.")
    await start(update, context)
    return ConversationHandler.END

async def forward_star_info(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user = update.effective_user
    text = update.message.text
    for admin_id in ADMIN_IDS:
        await context.bot.send_message(chat_id=admin_id, text=f"⭐ استار از {user.id}: {text}")
    await update.message.reply_text("✅ درخواستت رفت.")
    await start(update, context)
    return ConversationHandler.END

# توابع پنل ادمین
@admin_only
async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    keyboard = [["آمار ربات 📊", "مدیریت کاربر 🛠"], ["لیست کاربران 👥", "تنظیمات ربات ⚙️"], ["بازگشت"]]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.message.reply_text("پنل ادمین:", reply_markup=reply_markup)
    return AWAITING_ACTION_FOR_USER

@admin_only
async def bot_stats(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    data = load_data(DATA_FILE, {"users": {}})
    await update.message.reply_text(f"📊 کاربران: {len(data.get('users', {}))}")

@admin_only
async def list_users(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await send_user_list_page(update, context, page=0)

async def send_user_list_page(update: Update, context: ContextTypes.DEFAULT_TYPE, page: int):
    data = load_data(DATA_FILE, {"users": {}, "referral_counts": {}})
    users = list(data.get("users", {}).keys())
    start_idx = page * USERS_PER_PAGE
    end_idx = start_idx + USERS_PER_PAGE
    paginated_users = users[start_idx:end_idx]

    if not paginated_users:
        await update.message.reply_text("📋 کاربری نیست.")
        return

    text = "👥 لیست کاربران:\n"
    for user_id in paginated_users:
        score = data.get("referral_counts", {}).get(user_id, 0)
        banned = data.get("users", {}).get(user_id, {}).get("is_banned", False)
        text += f"{user_id} - امتیاز: {score} - {'بن‌شده' if banned else 'فعال'}\n"

    keyboard = []
    if page > 0:
        keyboard.append([InlineKeyboardButton("قبل", callback_data=f"user_list_{page-1}")])
    if end_idx < len(users):
        keyboard.append([InlineKeyboardButton("بعد", callback_data=f"user_list_{page+1}")])
    reply_markup = InlineKeyboardMarkup(keyboard) if keyboard else None

    if update.callback_query:
        await update.callback_query.edit_message_text(text, reply_markup=reply_markup)
    else:
        await update.message.reply_text(text, reply_markup=reply_markup)

async def user_list_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    page = int(query.data.split("_")[-1])
    await send_user_list_page(update, context, page=page)

@admin_only
async def manage_user_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("آیدی کاربر را وارد کن:")
    return AWAITING_USER_ID_FOR_MGMT

async def manage_user_action(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_id = update.message.text
    if not user_id.isdigit():
        await update.message.reply_text("❌ آیدی معتبر نیست.")
        return AWAITING_USER_ID_FOR_MGMT
    context.user_data['target_user_id'] = user_id
    keyboard = [["اضافه امتیاز", "کم کردن امتیاز"], ["بن کردن", "حذف کاربر"], ["بازگشت"]]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.message.reply_text(f"برای {user_id}:", reply_markup=reply_markup)
    return AWAITING_ACTION_FOR_USER

async def add_points(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("مقدار امتیاز را وارد کن:")
    return AWAITING_POINTS_TO_ADD

async def subtract_points(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("مقدار امتیاز را وارد کن:")
    return AWAITING_POINTS_TO_SUBTRACT

async def ban_user(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_id = context.user_data['target_user_id']
    data = load_data(DATA_FILE, {"users": {}})
    data.setdefault("users", {})[user_id] = data.get("users", {}).get(user_id, {})
    data["users"][user_id]["is_banned"] = True
    save_data(data, DATA_FILE)
    await update.message.reply_text(f"✅ {user_id} بن شد.")
    await admin_panel(update, context)
    return ConversationHandler.END

async def delete_user(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_id = context.user_data['target_user_id']
    data = load_data(DATA_FILE, {"users": {}, "referral_counts": {}})
    if user_id in data.get("users", {}):
        del data["users"][user_id]
    if user_id in data.get("referral_counts", {}):
        del data["referral_counts"][user_id]
    save_data(data, DATA_FILE)
    await update.message.reply_text(f"✅ {user_id} حذف شد.")
    await admin_panel(update, context)
    return ConversationHandler.END

async def process_points(update: Update, context: ContextTypes.DEFAULT_TYPE, action: str) -> int:
    try:
        points = int(update.message.text)
        user_id = context.user_data['target_user_id']
        data = load_data(DATA_FILE, {"referral_counts": {}})
        current_points = data.get("referral_counts", {}).get(user_id, 0)
        if action == "add":
            data.setdefault("referral_counts", {})[user_id] = current_points + points
        else:
            data.setdefault("referral_counts", {})[user_id] = max(0, current_points - points)
        save_data(data, DATA_FILE)
        await update.message.reply_text(f"✅ {points} {'اضافه' if action == 'add' else 'کم'} شد.")
    except ValueError:
        await update.message.reply_text("❌ عدد وارد کن.")
    await admin_panel(update, context)
    return ConversationHandler.END

@admin_only
async def bot_settings(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    keyboard = [["تنظیم هزینه لایک", "تنظیم هزینه استار"], ["تنظیم هزینه فری فایر", "تنظیم هزینه استیکر"], ["پاسخ خودکار", "خاموش/روشن"], ["بازگشت"]]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.message.reply_text("تنظیمات را انتخاب کن:", reply_markup=reply_markup)
    return AWAITING_ACTION_FOR_USER

async def set_cost_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    service_map = {
        "تنظیم هزینه لایک": "like_cost",
        "تنظیم هزینه استار": "star_cost",
        "تنظیم هزینه فری فایر": "ff_cost",
        "تنظیم هزینه استیکر": "sticker_cost"
    }
    service_key = service_map.get(update.message.text)
    if not service_key:
        await update.message.reply_text("❌ گزینه نامعتبر.")
        return AWAITING_ACTION_FOR_USER
    context.user_data['current_setting'] = service_key
    await update.message.reply_text("مقدار جدید را وارد کن:")
    return AWAITING_NEW_COST

async def set_autoreply_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data['current_setting'] = "autoreply"
    await update.message.reply_text("متن پاسخ خودکار را وارد کن:")
    return AWAITING_AUTOREPLY_MSG

async def toggle_bot_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    settings = load_data(SETTINGS_FILE, {"is_bot_active": True})
    settings["is_bot_active"] = not settings.get("is_bot_active", True)
    save_data(settings, SETTINGS_FILE)
    await update.message.reply_text(f"✅ ربات {'روشن' if settings['is_bot_active'] else 'خاموش'} شد.")
    await admin_panel(update, context)
    return ConversationHandler.END

async def set_new_cost_end(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    try:
        new_cost = int(update.message.text)
        if new_cost < 0:
            raise ValueError
        settings = load_data(SETTINGS_FILE, {})
        settings[context.user_data['current_setting']] = new_cost
        save_data(settings, SETTINGS_FILE)
        await update.message.reply_text(f"✅ هزینه به {new_cost} تغییر کرد.")
    except ValueError:
        await update.message.reply_text("❌ عدد مثبت وارد کن.")
    await bot_settings(update, context)
    return ConversationHandler.END

async def set_autoreply_end(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    settings = load_data(SETTINGS_FILE, {})
    settings.setdefault("autoreply", {})["message"] = update.message.text
    settings["autoreply"]["enabled"] = True
    save_data(settings, SETTINGS_FILE)
    await update.message.reply_text("✅ پاسخ خودکار تنظیم شد.")
    await bot_settings(update, context)
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("❌ لغو شد.")
    if update.effective_user.id in ADMIN_IDS:
        await admin_panel(update, context)
    else:
        await start(update, context)
    return ConversationHandler.END

# سرور وب برای Render
@app.route('/')
def health_check():
    return "OK", 200

def main() -> None:
    application = Application.builder().token(BOT_TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('start', start), CommandHandler('admin', admin_panel)],
        states={
            AWAITING_LIKE_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, forward_like_id)],
            AWAITING_STAR_INFO: [MessageHandler(filters.TEXT & ~filters.COMMAND, forward_star_info)],
            AWAITING_USER_ID_FOR_MGMT: [MessageHandler(filters.TEXT & ~filters.COMMAND, manage_user_action)],
            AWAITING_ACTION_FOR_USER: [
                MessageHandler(filters.Regex(r"^(آمار ربات|مدیریت کاربر|لیست کاربران|تنظیمات ربات|بازگشت)$"), lambda u, c: globals()[u.message.text.replace(" ", "_")] if u.message.text in ["آمار ربات", "مدیریت کاربر", "لیست کاربران", "تنظیمات ربات"] else start(u, c)),
                MessageHandler(filters.Regex(r"^(اضافه امتیاز|کم کردن امتیاز|بن کردن|حذف کاربر)$"), lambda u, c: globals()[u.message.text.replace(" ", "_")] if u.message.text in ["اضافه امتیاز", "کم کردن امتیاز", "بن کردن", "حذف کاربر"] else admin_panel(u, c)),
                MessageHandler(filters.Regex(r"^(تنظیم هزینه (لایک|استار|فری فایر|استیکر)|پاسخ خودکار|خاموش/روشن)$"), lambda u, c: set_cost_start(u, c) if "تنظیم هزینه" in u.message.text else set_autoreply_start(u, c) if u.message.text == "پاسخ خودکار" else toggle_bot_status(u, c))
            ],
            AWAITING_POINTS_TO_ADD: [MessageHandler(filters.TEXT & ~filters.COMMAND, lambda u, c: process_points(u, c, "add"))],
            AWAITING_POINTS_TO_SUBTRACT: [MessageHandler(filters.TEXT & ~filters.COMMAND, lambda u, c: process_points(u, c, "subtract"))],
            AWAITING_NEW_COST: [MessageHandler(filters.TEXT & ~filters.COMMAND, set_new_cost_end)],
            AWAITING_AUTOREPLY_MSG: [MessageHandler(filters.TEXT & ~filters.COMMAND, set_autoreply_end)],
        },
        fallbacks=[CommandHandler('cancel', cancel)]
    )

    application.add_handler(conv_handler)
    application.add_handler(CommandHandler("stats", bot_stats))
    application.add_handler(CommandHandler("users", list_users))
    application.add_handler(CallbackQueryHandler(user_list_callback, pattern=r'^user_list_\d+$'))
    application.add_handler(MessageHandler(filters.Regex(r"^لایک رایگان🔥$"), free_like_request))
    application.add_handler(MessageHandler(filters.Regex(r"^استارز رایگان⭐$"), free_star_request))
    application.add_handler(MessageHandler(filters.Regex(r"^امتیاز روزانه🎁$"), daily_bonus))
    application.add_handler(MessageHandler(filters.Regex(r"^اطلاعات اکانت 👤$"), account_info))
    application.add_handler(MessageHandler(filters.Regex(r"^پشتیبانی📱$"), support))

    application.run_polling(allowed_updates=Update.ALL_TYPES)

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))
    main()
    app.run(host="0.0.0.0", port=port)
