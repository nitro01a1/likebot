import json
import os
import random
from functools import wraps
from telegram import Bot, Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackQueryHandler

BOT_TOKEN = "YOUR_BOT_TOKEN_HERE"
ADMINS = [123456789, 987654321]
CHANNELS = ["@channel1", "@channel2"]

DATA_FOLDER = "data"
USERS_FILE = os.path.join(DATA_FOLDER, "users.json")
SETTINGS_FILE = os.path.join(DATA_FOLDER, "settings.json")

if not os.path.exists(DATA_FOLDER):
    os.mkdir(DATA_FOLDER)

if not os.path.exists(USERS_FILE):
    with open(USERS_FILE, "w", encoding="utf-8") as f:
        json.dump({}, f)

if not os.path.exists(SETTINGS_FILE):
    default_settings = {
        "sections": {
            "like_freefire": 1,
            "account_info": 1,
            "sticker_account": 1,
            "free_stars": 3
        },
        "auto_replies": {
            "default": "درخواست شما به سرور ارسال شد✅صبور باشید",
            "error": "خطا❌ لطفا با مدیریت تماس بگیرید."
        },
        "bot_active": True
    }
    with open(SETTINGS_FILE, "w", encoding="utf-8") as f:
        json.dump(default_settings, f, ensure_ascii=False, indent=4)

def load_json(filename):
    with open(filename, "r", encoding="utf-8") as f:
        return json.load(f)

def save_json(filename, data):
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

users = load_json(USERS_FILE)
settings = load_json(SETTINGS_FILE)

updater = Updater(token=BOT_TOKEN, use_context=True)
bot = updater.bot
dispatcher = updater.dispatcher

# بقیه کد و هندلرها مثل قبل...

# مثلا هندلر /start
def start(update, context):
    user = update.effective_user
    user_id = user.id
    username = user.username
    fullname = user.full_name
    args = context.args
    ref = None
    if args:
        try:
            ref = int(args[0])
        except:
            ref = None
    if str(user_id) not in users:
        users[str(user_id)] = {
            "username": username or "",
            "fullname": fullname or "",
            "score": 0,
            "ref": ref,
            "referrals": [],
            "banned": False,
            "daily_claimed": False,
        }
        if ref and str(ref) in users:
            users[str(ref)]["score"] += 1
            users[str(ref)]["referrals"].append(user_id)
            for admin_id in ADMINS:
                try:
                    bot.send_message(admin_id, f"کاربر {fullname} با لینک شما وارد شد و یک امتیاز به شما افزوده شد.")
                except:
                    pass
        save_json(USERS_FILE, users)
    update.message.reply_text(f"سلام {fullname}!\nامتیاز شما: ({users[str(user_id)]['score']})\nلینک رفرال شما: https://t.me/YourBotUserName?start={user_id}")

# ثبت هندلرها
dispatcher.add_handler(CommandHandler("start", start))

# سایر هندلرها رو مثل قبلی اضافه کن

if __name__ == "__main__":
    updater.start_polling()
    updater.idle()
