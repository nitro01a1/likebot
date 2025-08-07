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
from telegram.constants import ChatMemberStatus

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
AWAITING_USER_ID_FOR_MGMT, AWAITING_ACTION_FOR_USER, AWAITING_POINTS_TO_ADD, AWAITING_POINTS_TO_SUBTRACT, AWAITING_NEW_LIKE_COST, AWAITING_NEW_STAR_COST, AWAITING_NEW_FF_COST, AWAITING_NEW_STICKER_COST, AWAITING_AUTOREPLY_MSG = range(4, 13)

logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)
logger = logging.getLogger(__name__)

# توابع داده‌ها و تنظیمات
def load_data(file_path, default_data):
    if os.path.exists(file_path):
        with open(file_path, 'r') as f:
            try:
                return json.load(f)
            except json.JSONDecodeError:
                return default_data
    return default_data

def save_data(data, file_path):
    with open(file_path, 'w') as f:
        json.dump(data, f, indent=4)

# دکوریتورهای دسترسی
def user_check(func):
    @wraps(func)
    async def wrapped(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        user = update.effective_user
        if not user:
            return

        settings = load_data(SETTINGS_FILE, {"is_bot_active": True})
        if not settings.get("is_bot_active", True) and user.id not in ADMIN_IDS:
            await update.message.reply_text("🔴 ربات در حال حاضر خاموش است. لطفا دقایقی دیگر مجدد به ربات سر بزنید.")
            return

        user_data = load_data(DATA_FILE, {"users": {}})
        if user_data.get("users", {}).get(str(user.id), {}).get("is_banned", False):
            await update.message.reply_text("❌ شما توسط ادمین از استفاده از خدمات ربات محروم شده‌اید.")
            return

        not_joined_channels = []
        for channel_id in REQUIRED_CHANNELS:
            try:
                member = await context.bot.get_chat_member(chat_id=channel_id, user_id=user.id)
                if member.status not in [ChatMemberStatus.MEMBER, ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER]:
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

        user_info = user_data.get("users", {}).get(str(user.id), {})
        if "pending_referrer" in user_info:
            referrer_id = user_info["pending_referrer"]
            referrer_id_str = str(referrer_id)
            user_data.setdefault("referral_counts", {})[referrer_id_str] = user_data.get("referral_counts", {}).get(referrer_id_str, 0) + 1
            del user_data["users"][str(user.id)]["pending_referrer"]
            save_data(user_data, DATA_FILE)
            try:
                await context.bot.send_message(chat_id=referrer_id, text=f"✅ کاربر {user.first_name} با لینک شما وارد ربات شد و ۱ امتیاز به شما افزوده شد.")
            except error.Forbidden:
                logger.warning(f"Could not send referral notification to {referrer_id}.")

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

# توابع اصلی کاربران
@user_check
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    data = load_data(DATA_FILE, {"users": {}, "referral_counts": {}})
    user_id_str = str(user.id)

    if user_id_str not in data.get("users", {}):
        data.setdefault("users", {})[user_id_str] = {"is_banned": False}

    if context.args:
        try:
            referrer_id = int(context.args[0])
            user_info = data.get("users", {}).get(user_id_str, {})
            if "referred_by" not in user_info and "pending_referrer" not in user_info and user.id != referrer_id:
                data["users"][user_id_str]["pending_referrer"] = referrer_id
        except (ValueError, IndexError):
            pass
    save_data(data, DATA_FILE)

    keyboard = [
        ["لایک رایگان🔥", "استارز رایگان⭐"],
        ["اطلاعات اکانت فری فایر💻", "استیکر اکانت📷"],
        ["امتیاز روزانه🎁", "اطلاعات اکانت 👤"],
        ["پشتیبانی📱"]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.message.reply_text("به ربات لایک رایگان x7 خوش آمدید!", reply_markup=reply_markup)

@user_check
async def daily_bonus(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    data = load_data(DATA_FILE, {"users": {}, "referral_counts": {}})
    user_id_str = str(user.id)

    user_info = data.get("users", {}).get(user_id_str, {})
    last_bonus_str = user_info.get("last_bonus")

    if last_bonus_str:
        last_bonus_time = datetime.fromisoformat(last_bonus_str)
        if datetime.now() < last_bonus_time + timedelta(hours=24):
            await update.message.reply_text("❌ شما قبلاً امتیاز روزانه خود را دریافت کرده‌اید. لطفاً ۲۴ ساعت دیگر دوباره تلاش کنید.")
            return

    points = [1, 2, 3, 4, 5]
    weights = [50, 25, 15, 7, 3]
    bonus_points = random.choices(points, weights=weights, k=1)[0]

    data.setdefault("referral_counts", {})[user_id_str] = data.get("referral_counts", {}).get(user_id_str, 0) + bonus_points
    data["users"][user_id_str]["last_bonus"] = datetime.now().isoformat()
    save_data(data, DATA_FILE)

    await update.message.reply_text(f"🎉 تبریک! شما **{bonus_points}** امتیاز روزانه دریافت کردید.")

@user_check
async def support(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    support_text = "📱 پشتیبانی ربات\n\n▫️ مالک ربات: @immmdold\n▫️ پشتیبانی: @likeadminx7"
    await update.message.reply_text(support_text)

@user_check
async def account_info(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    user = update.effective_user
    data = load_data(DATA_FILE, {"referral_counts": {}})
    score = data.get("referral_counts", {}).get(str(user.id), 0)
    bot_username = (await context.bot.get_me()).username
    referral_link = f"https://t.me/{bot_username}?start={user.id}"
    info_text = (f"👤 اطلاعات اکانت شما\n\n▫️ آیدی عددی: {user.id}\n▫️ امتیاز شما: {score}\n\n🔗 لینک دعوت شما:\n{referral_link}")
    await update.message.reply_text(info_text, parse_mode='Markdown')

async def generic_request_start(update: Update, context: ContextTypes.DEFAULT_TYPE, service_key: str, prompt_message: str, next_state: int) -> int:
    user = update.effective_user
    user_data = load_data(DATA_FILE, {})
    settings = load_data(SETTINGS_FILE, {})

    cost_key = f"{service_key}_cost"
    cost = settings.get(cost_key, 1)
    user_score = user_data.get("referral_counts", {}).get(str(user.id), 0)

    if user_score < cost:
        bot_username = (await context.bot.get_me()).username
        referral_link = f"https://t.me/{bot_username}?start={user.id}"
        await update.message.reply_text(f"❌ امتیاز شما کافی نیست! (نیازمند: {cost} امتیاز، امتیاز شما: {user_score})\n\nبا لینک زیر دوستان خود را دعوت کنید:\n`{referral_link}`", parse_mode='Markdown')
        return ConversationHandler.END

    user_data.setdefault("referral_counts", {})[str(user.id)] = user_score - cost
    save_data(user_data, DATA_FILE)

    await update.message.reply_text(f"✅ {cost} امتیاز از شما کسر شد.\n{prompt_message}", reply_markup=ReplyKeyboardRemove())
    return next_state

async def free_like_request(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    return await generic_request_start(update, context, "like", "لطفا آیدی خود را ارسال کنید.", AWAITING_LIKE_ID)

async def free_star_request(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    return await generic_request_start(update, context, "star", "لطفا آیدی عددی و آیدی چنل خود را ارسال کنید.", AWAITING_STAR_INFO)

async def free_fire_request(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    return await generic_request_start(update, context, "ff", "لطفا اطلاعات اکانت فری فایر خود را ارسال کنید.", AWAITING_FF_INFO)

async def account_sticker_request(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    return await generic_request_start(update, context, "sticker", "لطفا اطلاعات لازم برای ساخت استیکر را ارسال کنید.", AWAITING_STICKER_INFO)

async def generic_forwarder(update: Update, context: ContextTypes.DEFAULT_TYPE, request_title: str, service_key: str) -> int:
    user = update.effective_user
    text = update.message.text
    header = f"{request_title}\nاز: {user.first_name} (ID: {user.id})\n\nاطلاعات ارسالی:\n{text}"

    for admin_id in ADMIN_IDS:
        await context.bot.send_message(chat_id=admin_id, text=header, parse_mode='Markdown')

    await update.message.reply_text("✅ درخواست شما با موفقیت برای ادمین ارسال شد.")

    settings = load_data(SETTINGS_FILE, {})
    autoreply_info = settings.get(f"{service_key}_autoreply", {"enabled": False, "message": ""})
    if autoreply_info.get("enabled", False):
        await update.message.reply_text(autoreply_info.get("message", DEFAULT_AUTOREPLY_MSG))

    await start(update, context)
    return ConversationHandler.END

async def forward_like_id(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    return await generic_forwarder(update, context, "📩 درخواست لایک جدید", "like")

async def forward_star_info(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    return await generic_forwarder(update, context, "⭐ درخواست استارز جدید", "star")

async def forward_ff_info(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    return await generic_forwarder(update, context, "💻 درخواست اکانت فری فایر", "ff")

async def forward_sticker_info(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    return await generic_forwarder(update, context, "📷 درخواست استیکر اکانت", "sticker")

# توابع پنل ادمین
@admin_only
async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    keyboard = [["آمار ربات 📊", "مدیریت کاربر 🛠"], ["لیست کاربران 👥", "تنظیمات ربات ⚙️"], ["بازگشت به منوی کاربر"]]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.message.reply_text("به پنل مدیریت خوش آمدید.", reply_markup=reply_markup)

@admin_only
async def bot_stats(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    data = load_data(DATA_FILE, {"users": {}})
    total_users = len(data.get("users", {}))
    await update.message.reply_text(f"📊 آمار ربات\n\n▫️ تعداد کل کاربران ثبت شده: {total_users} نفر")

@admin_only
async def list_users(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    await send_user_list_page(update, context, page=0)

async def send_user_list_page(update: Update, context: ContextTypes.DEFAULT_TYPE, page: int):
    data = load_data(DATA_FILE, {"users": {}})
    users = list(data.get("users", {}).keys())

    start_index = page * USERS_PER_PAGE
    end_index = start_index + USERS_PER_PAGE
    paginated_users = users[start_index:end_index]

    if not paginated_users:
        if update.callback_query:
            await update.callback_query.answer("صفحه دیگری وجود ندارد.", show_alert=True)
        return

    text = f"👥 **لیست کاربران (صفحه {page + 1})**\n\n"
    for user_id in paginated_users:
        text += f"`{user_id}`\n"

    keyboard = []
    nav_buttons = []
    if page > 0:
        nav_buttons.append(InlineKeyboardButton("◀️ قبل", callback_data=f"user_list_{page - 1}"))
    if end_index < len(users):
        nav_buttons.append(InlineKeyboardButton("بعد ▶️", callback_data=f"user_list_{page + 1}"))

    if nav_buttons:
        keyboard.append(nav_buttons)
    reply_markup = InlineKeyboardMarkup(keyboard)

    if update.callback_query:
        await update.callback_query.edit_message_text(text, reply_markup=reply_markup, parse_mode='Markdown')
    else:
        await update.message.reply_text(text, reply_markup=reply_markup, parse_mode='Markdown')

async def user_list_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    page = int(query.data.split("_")[-1])
    await send_user_list_page(update, context, page=page)

@admin_only
async def bot_settings(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    keyboard = [["تنظیمات بخش لایک 🔥"], ["تنظیمات بخش استارز ⭐"], ["تنظیمات بخش فری فایر 💻"], ["تنظیمات بخش استیکر 📷"], ["خاموش/روشن کردن ربات"], ["بازگشت به پنل ادمین"]]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.message.reply_text("لطفا بخشی که قصد تنظیم آن را دارید انتخاب کنید:", reply_markup=reply_markup)

async def show_service_settings(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    service_map = {
        "تنظیمات بخش لایک 🔥": ("like", "لایک رایگان🔥"),
        "تنظیمات بخش استارز ⭐": ("star", "استارز رایگان⭐"),
        "تنظیمات بخش فری فایر 💻": ("ff", "فری فایر💻"),
        "تنظیمات بخش استیکر 📷": ("sticker", "استیکر📷")
    }
    service_key, service_name = service_map[update.message.text]
    context.user_data['current_service_key'] = service_key

    settings = load_data(SETTINGS_FILE, {})
    cost = settings.get(f"{service_key}_cost", 1)
    autoreply_info = settings.get(f"{service_key}_autoreply", {"enabled": False})
    autoreply_status = "🟢 فعال" if autoreply_info.get("enabled", False) else "🔴 غیرفعال"

    keyboard = [
        [f"تغییر هزینه (فعلی: {cost})"],
        ["تنظیم متن پاسخ خودکار"],
        [f"پاسخ خودکار (وضعیت: {autoreply_status})"],
        ["بازگشت به تنظیمات"]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    await update.message.reply_text(f"⚙️ **تنظیمات بخش {service_name}**", reply_markup=reply_markup, parse_mode='Markdown')
    return AWAITING_ACTION_FOR_USER

async def set_cost_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("لطفا عدد جدید برای نیازمندی امتیاز را وارد کنید:", reply_markup=ReplyKeyboardRemove())
    return AWAITING_NEW_COST

async def set_autoreply_message_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("لطفا متن جدید برای پاسخ خودکار را ارسال کنید:", reply_markup=ReplyKeyboardRemove())
    return AWAITING_AUTOREPLY_MSG

async def toggle_autoreply_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    service_key = context.user_data.get('current_service_key')
    if not service_key:
        return ConversationHandler.END

    settings = load_data(SETTINGS_FILE, {})
    autoreply_key = f"{service_key}_autoreply"
    settings.setdefault(autoreply_key, {"enabled": False, "message": DEFAULT_AUTOREPLY_MSG})
    settings[autoreply_key]["enabled"] = not settings[autoreply_key].get("enabled", False)
    save_data(settings, SETTINGS_FILE)

    await update.message.reply_text("وضعیت با موفقیت تغییر کرد.")
    await bot_settings(update, context)
    return ConversationHandler.END

async def set_new_cost_end(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    try:
        new_cost = int(update.message.text)
        service_key = context.user_data.get('current_service_key')
        if new_cost < 0 or not service_key:
            raise ValueError("Invalid")

        settings = load_data(SETTINGS_FILE, {})
        settings[f"{service_key}_cost"] = new_cost
        save_data(settings, SETTINGS_FILE)
        await update.message.reply_text(f"✅ هزینه با موفقیت به **{new_cost}** تغییر یافت.", parse_mode='Markdown')
    except (ValueError, KeyError):
        await update.message.reply_text("❌ عملیات ناموفق بود.")
    await bot_settings(update, context)
    return ConversationHandler.END

async def set_autoreply_message_end(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    service_key = context.user_data.get('current_service_key')
    if not service_key:
        return ConversationHandler.END

    new_message = update.message.text
    settings = load_data(SETTINGS_FILE, {})
    autoreply_key = f"{service_key}_autoreply"
    settings.setdefault(autoreply_key, {"enabled": False})
    settings[autoreply_key]["message"] = new_message
    save_data(settings, SETTINGS_FILE)

    await update.message.reply_text("✅ متن پاسخ خودکار با موفقیت ذخیره شد.")
    await bot_settings(update, context)
    return ConversationHandler.END

@admin_only
async def toggle_bot_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    settings = load_data(SETTINGS_FILE, {"is_bot_active": True})
    current_status = settings.get("is_bot_active", True)
    settings["is_bot_active"] = not current_status
    save_data(settings, SETTINGS_FILE)
    new_status_text = "🟢 روشن" if not current_status else "🔴 خاموش"
    await update.message.reply_text(f"✅ وضعیت ربات با موفقیت به {new_status_text} تغییر یافت.", parse_mode='Markdown')

@admin_only
async def manage_user_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    pass

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("عملیات لغو شد.")
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
    """Start the bot."""
    application = Application.builder().token(BOT_TOKEN).build()

    # ثبت هندلرها
    conv_handler = ConversationHandler(
        entry_points=[CommandHandler('start', start)],
        states={
            AWAITING_LIKE_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, forward_like_id)],
            AWAITING_STAR_INFO: [MessageHandler(filters.TEXT & ~filters.COMMAND, forward_star_info)],
            AWAITING_FF_INFO: [MessageHandler(filters.TEXT & ~filters.COMMAND, forward_ff_info)],
            AWAITING_STICKER_INFO: [MessageHandler(filters.TEXT & ~filters.COMMAND, forward_sticker_info)],
            AWAITING_ACTION_FOR_USER: [
                MessageHandler(filters.Regex(f"^{r'تغییر هزینه \(فعلی: \d+\)'}$"), set_cost_start),
                MessageHandler(filters.Regex("^تنظیم متن پاسخ خودکار$"), set_autoreply_message_start),
                MessageHandler(filters.Regex("^پاسخ خودکار \(وضعیت: .+\)$"), toggle_autoreply_status),
                MessageHandler(filters.Regex("^بازگشت به تنظیمات$"), bot_settings)
            ],
            AWAITING_NEW_COST: [MessageHandler(filters.TEXT & ~filters.COMMAND, set_new_cost_end)],
            AWAITING_AUTOREPLY_MSG: [MessageHandler(filters.TEXT & ~filters.COMMAND, set_autoreply_message_end)],
        },
        fallbacks=[CommandHandler('cancel', cancel)]
    )

    application.add_handler(conv_handler)
    application.add_handler(CommandHandler("daily", daily_bonus))
    application.add_handler(CommandHandler("support", support))
    application.add_handler(CommandHandler("info", account_info))
    application.add_handler(CommandHandler("admin", admin_panel))
    application.add_handler(CommandHandler("stats", bot_stats))
    application.add_handler(CommandHandler("users", list_users))
    application.add_handler(CommandHandler("settings", bot_settings))
    application.add_handler(CallbackQueryHandler(user_list_callback, pattern=r'^user_list_\d+$'))
    application.add_handler(MessageHandler(filters.Regex("^لایک رایگان🔥$"), free_like_request))
    application.add_handler(MessageHandler(filters.Regex("^استارز رایگان⭐$"), free_star_request))
    application.add_handler(MessageHandler(filters.Regex("^اطلاعات اکانت فری فایر💻$"), free_fire_request))
    application.add_handler(MessageHandler(filters.Regex("^استیکر اکانت📷$"), account_sticker_request))
    application.add_handler(MessageHandler(filters.Regex("^آمار ربات 📊$"), bot_stats))
    application.add_handler(MessageHandler(filters.Regex("^مدیریت کاربر 🛠$"), manage_user_start))
    application.add_handler(MessageHandler(filters.Regex("^لیست کاربران 👥$"), list_users))
    application.add_handler(MessageHandler(filters.Regex("^تنظیمات ربات ⚙️$"), bot_settings))
    application.add_handler(MessageHandler(filters.Regex("^خاموش/روشن کردن ربات$"), toggle_bot_status))
    application.add_handler(MessageHandler(filters.Regex("^بازگشت به منوی کاربر$"), start))
    application.add_handler(MessageHandler(filters.Regex("^تنظیمات بخش .+$"), show_service_settings))

    # اجرای ربات
    application.run_polling()

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 10000))  # پورت پیش‌فرض Render
    main()  # اجرای ربات
    app.run(host="0.0.0.0", port=port)  # اجرای سرور وب
