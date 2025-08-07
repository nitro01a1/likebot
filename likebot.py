import json
import random
import os
from functools import wraps
from telegram import (
    Update,
    ReplyKeyboardMarkup,
    ReplyKeyboardRemove,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
)
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
    ConversationHandler,
    CallbackQueryHandler,
)

# ====== تنظیمات اولیه ======
BOT_TOKEN = "7882319394:AAG-TFTzkcEccTbR3sEIOJ0I9StWJMhNeHc"
ADMINS = [1956250138, 8066854428]  # ایدی عددی ادمین‌ها
CHANNELS = ["@npvpnir", "@x7gap"]  # یوزرنیم چنل‌های جوین اجباری

DATA_FOLDER = "data"
USERS_FILE = os.path.join(DATA_FOLDER, "users.json")
SETTINGS_FILE = os.path.join(DATA_FOLDER, "settings.json")
CONFIG_FILE = os.path.join(DATA_FOLDER, "config.json")

# ====== ایجاد پوشه و فایل‌ها در صورت نبود ======
if not os.path.exists(DATA_FOLDER):
    os.mkdir(DATA_FOLDER)
if not os.path.exists(USERS_FILE):
    with open(USERS_FILE, "w") as f:
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
if not os.path.exists(CONFIG_FILE):
    config = {
        "bot_on": True
    }
    with open(CONFIG_FILE, "w") as f:
        json.dump(config, f)

# ====== بارگذاری داده‌ها ======
def load_json(filename):
    with open(filename, "r", encoding="utf-8") as f:
        return json.load(f)


def save_json(filename, data):
    with open(filename, "w", encoding="utf-8") as f:
        json.dump(data, f, ensure_ascii=False, indent=4)


users = load_json(USERS_FILE)
settings = load_json(SETTINGS_FILE)
config = load_json(CONFIG_FILE)

# ====== چک کردن عضویت در چنل‌ها ======
async def check_membership(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    for channel in CHANNELS:
        try:
            member = await context.bot.get_chat_member(channel, user_id)
            if member.status not in ["member", "administrator", "creator"]:
                await update.message.reply_text(
                    f"برای استفاده از ربات باید در کانال {channel} عضو باشید."
                )
                return False
        except Exception:
            await update.message.reply_text(
                f"لطفا ابتدا در کانال {channel} عضو شوید و سپس دوباره تلاش کنید."
            )
            return False
    return True


# ====== چک ادمین ======
def admin_only(func):
    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        user_id = update.effective_user.id
        if user_id not in ADMINS:
            await update.message.reply_text("⚠️ شما دسترسی ادمین ندارید.")
            return
        return await func(update, context)

    return wrapper


# ====== چک فعال بودن ربات ======
def bot_active_check(func):
    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        if not config.get("bot_on", True):
            await update.message.reply_text("ربات در حال حاضر خاموش است.")
            return
        return await func(update, context)

    return wrapper


# ====== ساخت لینک رفرال ======
def get_referral_link(user_id):
    return f"https://t.me/YourBotUserName?start={user_id}"


# ====== ثبت کاربر جدید ======
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
            # پیام دادن به رفرال که امتیاز گرفته
        save_json(USERS_FILE, users)


# ====== استارت و رفرال ======
@bot_active_check
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    user = update.effective_user
    user_id = user.id
    username = user.username
    fullname = user.full_name
    ref = None

    if args:
        try:
            ref = int(args[0])
        except Exception:
            ref = None

    add_new_user(user_id, username, fullname, ref)

    await update.message.reply_text(
        f"سلام {fullname}!\n"
        f"امتیاز شما: ({users[str(user_id)]['score']})\n"
        f"لینک رفرال شما: {get_referral_link(user_id)}\n"
        f"لطفا ابتدا در کانال‌های زیر عضو شوید:\n" + "\n".join(CHANNELS)
    )


# ====== بخش‌های امتیازی ======

# لیست بخش‌ها و اسم کلیدهای امتیازشون:
# like_freefire, account_info, sticker_account, free_stars

# ساخت صفحه کلید برای انتخاب بخش‌ها
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
async def menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    if str(user_id) not in users:
        await update.message.reply_text(
            "لطفا ابتدا /start را بزنید."
        )
        return
    markup = get_main_menu(user_id)
    await update.message.reply_text(
        f"سلام، امتیاز شما: ({users[str(user_id)]['score']})\n"
        f"لینک رفرال شما: {get_referral_link(user_id)}\n"
        "بخش مورد نظر را انتخاب کنید:",
        reply_markup=markup,
    )


# ====== هندلر کال‌بک دکمه‌ها ======

SECTION_WAITING_FOR_ID = {}

@bot_active_check
async def button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    user_id = query.from_user.id
    await query.answer()

    if str(user_id) not in users:
        await query.edit_message_text("لطفا ابتدا /start را بزنید.")
        return

    user_data = users[str(user_id)]
    section = query.data
    user_score = user_data.get("score", 0)

    # چک بن بودن
    if user_data.get("banned", False):
        await query.edit_message_text("شما توسط ادمین بن شده‌اید.")
        return

    # چک امتیاز لازم
    need_score = settings["sections"].get(section, 1)
    if user_score < need_score:
        await query.edit_message_text(
            f"برای دسترسی به این بخش به {need_score} امتیاز نیاز دارید.\n"
            f"امتیاز شما: ({user_score})\n"
            f"لینک رفرال شما: {get_referral_link(user_id)}\n"
            "برای جمع‌آوری امتیاز باید رفرال جمع کنید."
        )
        return

    # بخش‌های مختلف:

    if section in ["like_freefire", "account_info", "sticker_account"]:
        await query.edit_message_text(
            f"لطفا آیدی عددی گیم خود را وارد کنید تا به ادمین‌ها پیام داده شود.\n"
            f"امتیاز شما: ({user_score})\n"
            f"لینک رفرال شما: {get_referral_link(user_id)}"
        )
        SECTION_WAITING_FOR_ID[user_id] = section
        return

    if section == "free_stars":
        await query.edit_message_text(
            f"لطفا لینک چنل خود و آیدی تلگرام خود را ارسال کنید.\n"
            f"امتیاز شما: ({user_score})\n"
            f"لینک رفرال شما: {get_referral_link(user_id)}"
        )
        SECTION_WAITING_FOR_ID[user_id] = section
        return

    if section == "daily_score":
        # امتیاز روزانه 1 تا 4
        if user_data.get("daily_claimed", False):
            await query.edit_message_text("امتیاز روزانه خود را امروز گرفته‌اید.")
        else:
            add = random.randint(1, 4)
            user_data["score"] += add
            user_data["daily_claimed"] = True
            save_json(USERS_FILE, users)
            await query.edit_message_text(f"امتیاز روزانه شما {add} امتیاز افزوده شد.\nامتیاز کل: {user_data['score']}")

        return

    if section == "profile":
        txt = (
            f"حساب کاربری شما:\n"
            f"آیدی عددی: {user_id}\n"
            f"نام کاربری: @{user_data.get('username','-')}\n"
            f"نام کامل: {user_data.get('fullname','-')}\n"
            f"لینک رفرال: {get_referral_link(user_id)}\n"
            f"امتیاز: {user_data.get('score',0)}"
        )
        await query.edit_message_text(txt)
        return

    if section == "support":
        txt = (
            "پشتیبانی:\n"
            "ایدی مالک: @immmdold\n"
            "ایدی مدیر: @likeadminx7"
        )
        await query.edit_message_text(txt)
        return


# ====== دریافت آیدی یا لینک بعد از درخواست ======

@bot_active_check
async def message_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = update.effective_user.id
    text = update.message.text

    if user_id not in SECTION_WAITING_FOR_ID:
        return  # اگر کاربر توی حالت انتظار نباشد کاری نکن

    section = SECTION_WAITING_FOR_ID[user_id]
    user_data = users.get(str(user_id))
    if user_data is None:
        await update.message.reply_text("لطفا ابتدا /start را بزنید.")
        return

    # ارسال پیام به ادمین‌ها
    if section in ["like_freefire", "account_info", "sticker_account"]:
        # متن ایدی عددی
        for admin_id in ADMINS:
            try:
                await context.bot.send_message(
                    admin_id,
                    f"کاربر {user_data.get('fullname')} (آیدی: {user_id}) در بخش {section} پیام فرستاده:\n{text}",
                )
            except Exception:
                pass
        await update.message.reply_text(settings["auto_replies"]["default"])
        SECTION_WAITING_FOR_ID.pop(user_id)

    elif section == "free_stars":
        # انتظار لینک چنل و آیدی
        # فقط پیام رو فوروارد میکنیم به ادمین‌ها
        for admin_id in ADMINS:
            try:
                await context.bot.send_message(
                    admin_id,
                    f"کاربر {user_data.get('fullname')} (آیدی: {user_id}) درخواست استارز رایگان فرستاد:\n{text}",
                )
            except Exception:
                pass
        await update.message.reply_text("درخواست شما در حال بررسی است صبور باشید")
        SECTION_WAITING_FOR_ID.pop(user_id)


# ====== امتیاز روزانه ریست در نیمه شب ======

import asyncio
from datetime import datetime, time, timedelta

async def reset_daily_scores(app: Application):
    while True:
        now = datetime.now()
        next_reset = datetime.combine(now.date(), time(0, 0)) + timedelta(days=1)
        wait_seconds = (next_reset - now).total_seconds()
        await asyncio.sleep(wait_seconds)
        # ریست کردن فلگ دریافت امتیاز روزانه
        for user_id in users:
            users[user_id]["daily_claimed"] = False
        save_json(USERS_FILE, users)


# ====== پنل مدیریت ======

@admin_only
async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    keyboard = [
        [InlineKeyboardButton("🔴 خاموش کردن ربات", callback_data="bot_off")],
        [InlineKeyboardButton("🟢 روشن کردن ربات", callback_data="bot_on")],
        [InlineKeyboardButton("📊 آمار کاربران", callback_data="stats")],
        [InlineKeyboardButton("👥 لیست کاربران", callback_data="user_list")],
        [InlineKeyboardButton("⚙️ تنظیم امتیاز بخش‌ها", callback_data="settings")],
        [InlineKeyboardButton("🔧 مدیریت کاربران", callback_data="manage_users")],
    ]
    await update.message.reply_text("پنل مدیریت:", reply_markup=InlineKeyboardMarkup(keyboard))


@admin_only
async def admin_button_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    await query.answer()

    if data == "bot_off":
        config["bot_on"] = False
        save_json(CONFIG_FILE, config)
        await query.edit_message_text("ربات خاموش شد.")

    elif data == "bot_on":
        config["bot_on"] = True
        save_json(CONFIG_FILE, config)
        await query.edit_message_text("ربات روشن شد.")

    elif data == "stats":
        total_users = len(users)
        total_score = sum(user["score"] for user in users.values())
        banned_users = sum(1 for user in users.values() if user.get("banned", False))
        text = (
            f"آمار ربات:\n"
            f"تعداد کل کاربران: {total_users}\n"
            f"جمع کل امتیاز: {total_score}\n"
            f"تعداد کاربران بن شده: {banned_users}"
        )
        await query.edit_message_text(text)

    elif data == "user_list":
        # لیست کاربران با ایدی
        text = "لیست کاربران:\n"
        for uid, udata in users.items():
            text += f"{udata.get('fullname', '-')}\tID: {uid}\n"
        await query.edit_message_text(text)

    elif data == "manage_users":
        await query.edit_message_text("برای مدیریت کاربر، دستور زیر را بفرستید:\n"
                                      "/ban <id>\n/unban <id>\n/addscore <id> <num>\n/remscore <id> <num>")

    elif data == "settings":
        txt = "تنظیم امتیاز مورد نیاز هر بخش:\n"
        for section, score_needed in settings["sections"].items():
            txt += f"{section}: {score_needed} امتیاز\n"
        await query.edit_message_text(txt)


# ====== دستورات مدیریت کاربران ======

@admin_only
async def ban_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    if len(args) != 1:
        await update.message.reply_text("دستور اشتباه است. استفاده: /ban <id>")
        return
    uid = args[0]
    if uid in users:
        users[uid]["banned"] = True
        save_json(USERS_FILE, users)
        await update.message.reply_text(f"کاربر {uid} بن شد.")
    else:
        await update.message.reply_text("کاربر پیدا نشد.")


@admin_only
async def unban_user(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    if len(args) != 1:
        await update.message.reply_text("دستور اشتباه است. استفاده: /unban <id>")
        return
    uid = args[0]
    if uid in users:
        users[uid]["banned"] = False
        save_json(USERS_FILE, users)
        await update.message.reply_text(f"کاربر {uid} آنبن شد.")
    else:
        await update.message.reply_text("کاربر پیدا نشد.")


@admin_only
async def add_score(update: Update, context: ContextTypes.DEFAULT_TYPE):
    args = context.args
    if len(args) != 2:
        await update.message.reply_text("دستور اشتباه است. استفاده: /addscore <id> <num>")
        return
    uid, num = args[0], args[1]
    if uid in users:
        try:
            n = int(num)
        except ValueError:
            await update.message.reply_text
