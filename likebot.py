import logging
import json
import os
from functools import wraps
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import (
    Application, CommandHandler, MessageHandler, filters, ContextTypes,
    ConversationHandler
)
from telegram.constants import ChatMemberStatus

# --- تنظیمات ---
BOT_TOKEN = "7882319394:AAG-TFTzkcEccTbR3sEIOJ0I9StWJMhNeHc"  
ADMIN_IDS = [1956250138, 8066854428]  
DATA_FILE = "referral_data.json"  
SETTINGS_FILE = "settings.json"  
REQUIRED_CHANNELS = ["@npvpnir", "@x7gap"]  
USERS_PER_PAGE = 10  
DEFAULT_AUTOREPLY_MSG = "خطا در اتصال به سرور❌ لطفا با مدیریت تماس بگیرید @likeadminx7"  

AWAITING_LIKE_ID = 1
AWAITING_FF_INFO = 2
AWAITING_STICKER_INFO = 3
AWAITING_NEW_COST = 4
AWAITING_AUTOREPLY_MSG = 5

logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

# --- داده‌ها ---
def load_data(file_path, default):
    if os.path.exists(file_path):
        with open(file_path, 'r') as f:
            try: return json.load(f)
            except json.JSONDecodeError: return default
    return default

def save_data(data, file_path):
    with open(file_path, 'w') as f:
        json.dump(data, f, indent=4)

# --- دکوراتور ادمین ---
def admin_only(func):
    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        if user_id not in ADMIN_IDS:
            await update.message.reply_text("⛔️ شما دسترسی لازم را ندارید.")
            return ConversationHandler.END
        return await func(update, context)
    return wrapper

# --- start ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [["درخواست لایک رایگان"], ["درخواست فری فایر"], ["درخواست استیکر"], ["تنظیمات ربات ⚙️"]]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.message.reply_text("به ربات خوش آمدید!", reply_markup=reply_markup)

# --- توابع عمومی ---
async def generic_request_start(update: Update, context: ContextTypes.DEFAULT_TYPE, service_key: str, prompt_message: str, next_state: int) -> int:
    user = update.effective_user
    user_data = load_data(DATA_FILE, {})
    settings = load_data(SETTINGS_FILE, {})

    cost_key = f"{service_key}_cost"
    cost = settings.get(cost_key, 1)
    user_score = user_data.get("referral_counts", {}).get(str(user.id), 0)

    if user_score < cost:
        await update.message.reply_text("❌ امتیاز شما کافی نیست.")
        return ConversationHandler.END

    user_data.setdefault("referral_counts", {})[str(user.id)] = user_score - cost
    save_data(user_data, DATA_FILE)

    await update.message.reply_text(f"✅ {cost} امتیاز از شما کسر شد.\n{prompt_message}", reply_markup=ReplyKeyboardRemove())
    return next_state

async def generic_forwarder(update: Update, context: ContextTypes.DEFAULT_TYPE, request_title: str, service_key: str) -> int:
    user = update.effective_user
    text = update.message.text
    header = f"{request_title}\nاز: {user.first_name} (ID: `{user.id}`)\n\n**اطلاعات ارسالی:**\n{text}"

    for admin_id in ADMIN_IDS:
        await context.bot.send_message(chat_id=admin_id, text=header, parse_mode='Markdown')

    settings = load_data(SETTINGS_FILE, {})
    autoreply_info = settings.get(f"{service_key}_autoreply", {"enabled": False, "message": DEFAULT_AUTOREPLY_MSG})
    if autoreply_info.get("enabled", False):
        await update.message.reply_text(autoreply_info.get("message", DEFAULT_AUTOREPLY_MSG))

    await start(update, context)
    return ConversationHandler.END

# --- درخواست‌ها ---
async def free_like_request(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    return await generic_request_start(update, context, "like", "آیدی خود را ارسال کنید:", AWAITING_LIKE_ID)

async def forward_like_id(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    return await generic_forwarder(update, context, "📩 درخواست لایک", "like")

async def free_fire_request(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    return await generic_request_start(update, context, "ff", "اطلاعات اکانت خود را ارسال کنید:", AWAITING_FF_INFO)

async def forward_ff_info(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    return await generic_forwarder(update, context, "🔥 فری فایر جدید", "ff")

async def account_sticker_request(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    return await generic_request_start(update, context, "sticker", "لطفا اطلاعات استیکر را ارسال کنید:", AWAITING_STICKER_INFO)

async def forward_sticker_info(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    return await generic_forwarder(update, context, "🎨 درخواست استیکر", "sticker")

# --- پنل ادمین ---
@admin_only
async def bot_settings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [["تنظیمات بخش لایک 🔥"], ["تنظیمات بخش فری فایر 💻"], ["تنظیمات بخش استیکر 📷"]]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.message.reply_text("بخش مورد نظر را انتخاب کنید:", reply_markup=reply_markup)

async def set_new_cost_end(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    service_key = context.user_data.pop('current_service_key', None)
    if not service_key:
        return ConversationHandler.END
    try:
        new_cost = int(update.message.text)
    except ValueError:
        await update.message.reply_text("لطفاً یک عدد معتبر وارد کنید.")
        return AWAITING_NEW_COST

    settings = load_data(SETTINGS_FILE, {})
    settings[f"{service_key}_cost"] = new_cost
    save_data(settings, SETTINGS_FILE)
    await update.message.reply_text("✅ هزینه جدید ذخیره شد.")
    await bot_settings(update, context)
    return ConversationHandler.END

# --- main ---
def main():
    application = Application.builder().token(BOT_TOKEN).build()

    conv_handler = ConversationHandler(
        entry_points=[CommandHandler("start", start),
                      MessageHandler(filters.Regex("^درخواست لایک رایگان$"), free_like_request),
                      MessageHandler(filters.Regex("^درخواست فری فایر$"), free_fire_request),
                      MessageHandler(filters.Regex("^درخواست استیکر$"), account_sticker_request),
                      MessageHandler(filters.Regex("^تنظیمات ربات ⚙️$"), bot_settings)],
        states={
            AWAITING_LIKE_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, forward_like_id)],
            AWAITING_FF_INFO: [MessageHandler(filters.TEXT & ~filters.COMMAND, forward_ff_info)],
            AWAITING_STICKER_INFO: [MessageHandler(filters.TEXT & ~filters.COMMAND, forward_sticker_info)],
            AWAITING_NEW_COST: [MessageHandler(filters.TEXT & ~filters.COMMAND, set_new_cost_end)],
        },
        fallbacks=[CommandHandler("start", start)],
    )

    application.add_handler(conv_handler)
    application.run_polling()

if __name__ == '__main__':
    main()
