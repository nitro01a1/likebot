import json
import os
import random
from functools import wraps

from flask import Flask, request, abort
import filetype  # جایگزین imghdr

from telegram import Bot, Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Dispatcher, CommandHandler, MessageHandler, Filters, CallbackQueryHandler

# ====== تنظیمات اولیه ======
BOT_TOKEN = "7882319394:AAG-TFTzkcEccTbR3sEIOJ0I9StWJMhNeHc"
ADMINS = [1956250138, 8066854428]  # ایدی عددی ادمین‌ها
CHANNELS = ["@npvpnir", "@x7gap"]  # یوزرنیم چنل‌های جوین اجباری
WEBHOOK_URL = "https://likebot-hxwc.onrender.com"  # آدرس وب‌سرویس رندر

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

# بارگذاری داده‌ها
def load_json(filename):
    with open(filename, "r", encoding="utf-8") as f:
        return json.load(f)

def save_json(filename, data):
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)

users = load_json(USERS_FILE)
settings = load_json(SETTINGS_FILE)

app = Flask(__name__)
bot = Bot(token=BOT_TOKEN)
dispatcher = Dispatcher(bot, None, workers=0)

# دکوراتورها
def admin_only(func):
    @wraps(func)
    def wrapped(update, context):
        user_id = update.effective_user.id
        if user_id not in ADMINS:
            if update.message:
                update.message.reply_text("⚠️ شما دسترسی ادمین ندارید.")
            elif update.callback_query:
                update.callback_query.answer("⚠️ شما دسترسی ادمین ندارید.", show_alert=True)
            return
        return func(update, context)
    return wrapped

def bot_active_check(func):
    @wraps(func)
    def wrapped(update, context):
        if not settings.get("bot_active", True):
            if update.message:
                update.message.reply_text("ربات در حال حاضر خاموش است.")
            elif update.callback_query:
                update.callback_query.answer("ربات در حال حاضر خاموش است.", show_alert=True)
            return
        return func(update, context)
    return wrapped

# لینک رفرال
def get_referral_link(user_id):
    return f"https://t.me/YourBotUserName?start={user_id}"

# ثبت کاربر جدید
def add_new_user(user_id, username, fullname, ref=None):
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
                    bot.send_message(admin_id, f"کاربر {users[str(user_id)]['fullname']} با لینک شما وارد شد و یک امتیاز به شما افزوده شد.")
                except:
                    pass
        save_json(USERS_FILE, users)

# چک عضویت در کانال‌ها
def is_member(user_id):
    for channel in CHANNELS:
        try:
            member = bot.get_chat_member(channel, user_id)
            if member.status not in ["member", "administrator", "creator"]:
                return False
        except:
            return False
    return True

# هندلر /start
@bot_active_check
def start(update, context):
    args = context.args
    user = update.effective_user
    user_id = user.id
    username = user.username
    fullname = user.full_name
    ref = None
    if args:
        try:
            ref = int(args[0])
        except:
            ref = None
    add_new_user(user_id, username, fullname, ref)
    text = (f"سلام {fullname}!\n"
            f"امتیاز شما: ({users[str(user_id)]['score']})\n"
            f"لینک رفرال شما: {get_referral_link(user_id)}\n"
            f"لطفا ابتدا در کانال‌های زیر عضو شوید:\n" + "\n".join(CHANNELS))
    update.message.reply_text(text)

# منو
def get_main_menu(user_id):
    score = users.get(str(user_id), {}).get("score", 0)
    menu = [
        [InlineKeyboardButton("لایک فری فایر", callback_data="like_freefire")],
        [InlineKeyboardButton("اطلاعات اکانت", callback_data="account_info")],
        [InlineKeyboardButton("استیکر اکانت", callback_data="sticker_account")],
        [InlineKeyboardButton("استارز رایگان", callback_data="free_stars")],
        [InlineKeyboardButton("امتیاز روزانه", callback_data="daily_score")],
        [InlineKeyboardButton("حساب کاربری", callback_data="profile")],
        [InlineKeyboardButton("پشتیبانی", callback_data="support")],
    ]
    return InlineKeyboardMarkup(menu)

@bot_active_check
def menu(update, context):
    user_id = update.effective_user.id
    if str(user_id) not in users:
        update.message.reply_text("لطفا ابتدا /start را بزنید.")
        return
    if not is_member(user_id):
        update.message.reply_text("برای استفاده از ربات باید در کانال‌های مربوطه عضو باشید.")
        return
    markup = get_main_menu(user_id)
    update.message.reply_text(f"سلام، امتیاز شما: ({users[str(user_id)]['score']})\nلینک رفرال شما: {get_referral_link(user_id)}\nبخش مورد نظر را انتخاب کنید:", reply_markup=markup)

SECTION_WAITING_FOR_ID = {}

@bot_active_check
def button_handler(update, context):
    query = update.callback_query
    user_id = query.from_user.id
    query.answer()
    if str(user_id) not in users:
        query.edit_message_text("لطفا ابتدا /start را بزنید.")
        return
    user_data = users[str(user_id)]
    section = query.data
    user_score = user_data.get("score", 0)

    if user_data.get("banned", False):
        query.edit_message_text("شما توسط ادمین بن شده‌اید.")
        return

    need_score = settings["sections"].get(section, 1)
    if user_score < need_score:
        query.edit_message_text(f"برای دسترسی به این بخش به {need_score} امتیاز نیاز دارید.\nامتیاز شما: ({user_score})\nلینک رفرال شما: {get_referral_link(user_id)}\nبرای جمع‌آوری امتیاز باید رفرال جمع کنید.")
        return

    if section in ["like_freefire", "account_info", "sticker_account"]:
        query.edit_message_text(f"لطفا آیدی عددی گیم خود را وارد کنید تا به ادمین‌ها پیام داده شود.\nامتیاز شما: ({user_score})\nلینک رفرال شما: {get_referral_link(user_id)}")
        SECTION_WAITING_FOR_ID[user_id] = section
        return

    if section == "free_stars":
        query.edit_message_text(f"لطفا لینک چنل خود و آیدی تلگرام خود را ارسال کنید.\nامتیاز شما: ({user_score})\nلینک رفرال شما: {get_referral_link(user_id)}")
        SECTION_WAITING_FOR_ID[user_id] = section
        return

    if section == "daily_score":
        if user_data.get("daily_claimed", False):
            query.edit_message_text("امتیاز روزانه خود را امروز گرفته‌اید.")
        else:
            add = random.randint(1, 4)
            user_data["score"] += add
            user_data["daily_claimed"] = True
            save_json(USERS_FILE, users)
            query.edit_message_text(f"امتیاز روزانه شما {add} امتیاز افزوده شد.\nامتیاز کل: {user_data['score']}")
        return

    if section == "profile":
        txt = (f"حساب کاربری شما:\n"
               f"آیدی عددی: {user_id}\n"
               f"نام کاربری: @{user_data.get('username','-')}\n"
               f"نام کامل: {user_data.get('fullname','-')}\n"
               f"لینک رفرال: {get_referral_link(user_id)}\n"
               f"امتیاز: {user_data.get('score',0)}")
        query.edit_message_text(txt)
        return

    if section == "support":
        txt = "پشتیبانی:\nایدی مالک: @immmdold\nایدی مدیر: @likeadminx7"
        query.edit_message_text(txt)
        return

@bot_active_check
def message_handler(update, context):
    user_id = update.effective_user.id
    text = update.message.text
    if user_id not in SECTION_WAITING_FOR_ID:
        return
    section = SECTION_WAITING_FOR_ID[user_id]
    user_data = users.get(str(user_id))
    if user_data is None:
        update.message.reply_text("لطفا ابتدا /start را بزنید.")
        return
    if section in ["like_freefire", "account_info", "sticker_account"]:
        for admin_id in ADMINS:
            try:
                bot.send_message(admin_id, f"کاربر {user_data.get('fullname')} (آیدی: {user_id}) در بخش {section} پیام فرستاده:\n{text}")
            except:
                pass
        update.message.reply_text(settings["auto_replies"]["default"])
        SECTION_WAITING_FOR_ID.pop(user_id)
    elif section == "free_stars":
        for admin_id in ADMINS:
            try:
                bot.send_message(admin_id, f"کاربر {user_data.get('fullname')} (آیدی: {user_id}) درخواست استارز رایگان فرستاد:\n{text}")
            except:
                pass
        update.message.reply_text("درخواست شما در حال بررسی است صبور باشید")
        SECTION_WAITING_FOR_ID.pop(user_id)

# پنل مدیریت

@admin_only
def admin_panel(update, context):
    keyboard = [
        [InlineKeyboardButton("🔴 خاموش کردن ربات", callback_data="bot_off")],
        [InlineKeyboardButton("🟢 روشن کردن ربات", callback_data="bot_on")],
        [InlineKeyboardButton("📊 آمار کاربران", callback_data="stats")],
        [InlineKeyboardButton("👥 لیست کاربران", callback_data="user_list")],
        [InlineKeyboardButton("⚙️ تنظیم امتیاز بخش‌ها", callback_data="settings")],
        [InlineKeyboardButton("🔧 مدیریت کاربران", callback_data="manage_users")],
    ]
    update.message.reply_text("پنل مدیریت:", reply_markup=InlineKeyboardMarkup(keyboard))

@admin_only
def admin_button_handler(update, context):
    query = update.callback_query
    data = query.data
    query.answer()
    if data == "bot_off":
        settings["bot_active"] = False
        save_json(SETTINGS_FILE, settings)
        query.edit_message_text("ربات خاموش شد.")
    elif data == "bot_on":
        settings["bot_active"] = True
        save_json(SETTINGS_FILE, settings)
        query.edit_message_text("ربات روشن شد.")
    elif data == "stats":
        total_users = len(users)
        total_score = sum(user["score"] for user in users.values())
        banned_users = sum(1 for user in users.values() if user.get("banned", False))
        text = f"آمار ربات:\nتعداد کل کاربران: {total_users}\nجمع کل امتیاز: {total_score}\nتعداد کاربران بن شده: {banned_users}"
        query.edit_message_text(text)
    elif data == "user_list":
        text = "لیست کاربران:\n"
        for uid, udata in users.items():
            text += f"{udata.get('fullname', '-')}\tID: {uid}\n"
        query.edit_message_text(text)
    elif data == "manage_users":
        query.edit_message_text("برای مدیریت کاربر، دستور زیر را بفرستید:\n/ban <id>\n/unban <id>\n/addscore <id> <num>\n/remscore <id> <num>")
    elif data == "settings":
        txt = "تنظیم امتیاز مورد نیاز هر بخش:\n"
        for section, score_needed in settings["sections"].items():
            txt += f"{section}: {score_needed} امتیاز\n"
        query.edit_message_text(txt)

# دستورات مدیریتی

@admin_only
def ban_user(update, context):
    args = context.args
    if len(args) != 1:
        update.message.reply_text("دستور اشتباه است. استفاده: /ban <id>")
        return
    uid = args[0]
    if uid in users:
        users[uid]["banned"] = True
        save_json(USERS_FILE, users)
        update.message.reply_text(f"کاربر {uid} بن شد.")
    else:
        update.message.reply_text("کاربر پیدا نشد.")

@admin_only
def unban_user(update, context):
    args = context.args
    if len(args) != 1:
        update.message.reply_text("دستور اشتباه است. استفاده: /unban <id>")
        return
    uid = args[0]
    if uid in users:
        users[uid]["banned"] = False
        save_json(USERS_FILE, users)
        update.message.reply_text(f"کاربر {uid} آنبن شد.")
    else:
        update.message.reply_text("کاربر پیدا نشد.")

@admin_only
def add_score(update, context):
    args = context.args
    if len(args) != 2:
        update.message.reply_text("دستور اشتباه است. استفاده: /addscore <id> <num>")
        return
    uid, num = args[0], args[1]
    if uid in users:
        try:
            n = int(num)
        except:
            update.message.reply_text("عدد وارد شده نامعتبر است.")
            return
        users[uid]["score"] += n
        save_json(USERS_FILE, users)
        update.message.reply_text(f"{n} امتیاز به کاربر {uid} افزوده شد.")
    else:
        update.message.reply_text("کاربر پیدا نشد.")

@admin_only
def rem_score(update, context):
    args = context.args
    if len(args) != 2:
        update.message.reply_text("دستور اشتباه است. استفاده: /remscore <id> <num>")
        return
    uid, num = args[0], args[1]
    if uid in users:
        try:
            n = int(num)
        except:
            update.message.reply_text("عدد وارد شده نامعتبر است.")
            return
        users[uid]["score"] -= n
        if users[uid]["score"] < 0:
            users[uid]["score"] = 0
        save_json(USERS_FILE, users)
        update.message.reply_text(f"{n} امتیاز از کاربر {uid} کسر شد.")
    else:
        update.message.reply_text("کاربر پیدا نشد.")

# ثبت هندلرها
dispatcher.add_handler(CommandHandler("start", start))
dispatcher.add_handler(CommandHandler("menu", menu))
dispatcher.add_handler(CallbackQueryHandler(button_handler))
dispatcher.add_handler(CommandHandler("admin", admin_panel))
dispatcher.add_handler(CallbackQueryHandler(admin_button_handler, pattern="^(bot_off|bot_on|stats|user_list|settings|manage_users)$"))
dispatcher.add_handler(CommandHandler("ban", ban_user))
dispatcher.add_handler(CommandHandler("unban", unban_user))
dispatcher.add_handler(CommandHandler("addscore", add_score))
dispatcher.add_handler(CommandHandler("remscore", rem_score))
dispatcher.add_handler(MessageHandler(Filters.text & (~Filters.command), message_handler))

# مسیر وبهوک
@app.route('/', methods=['POST'])
def webhook():
    if request.method == "POST":
        update = Update.de_json(request.get_json(force=True), bot)
        dispatcher.process_update(update)
        return 'ok'
    else:
        abort(403)

if __name__ == "__main__":
    bot.delete_webhook()
    bot.set_webhook(url=WEBHOOK_URL)
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)
