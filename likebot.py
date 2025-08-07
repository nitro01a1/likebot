import logging
import json
from datetime import datetime, timedelta
import random
import os  # <<< اضافه شده برای خواندن متغیرهای محیطی

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, Bot
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    MessageHandler,
    filters,
    ContextTypes,
    ConversationHandler,
)
from telegram.constants import ParseMode

# --- تنظیمات اولیه (خوانده شده از متغیرهای محیطی Render) ---
BOT_TOKEN = os.getenv("7882319394:AAG-TFTzkcEccTbR3sEIOJ0I9StWJMhNeHc")
ADMIN_IDS_STR = os.getenv("1956250138", "8066854428").split(',')
ADMIN_IDS = [int(admin_id) for admin_id in ADMIN_IDS_STR if admin_id]
FORCED_JOIN_CHANNELS = os.getenv("@x7gap", "@npvpnir").split(',')

# --- مسیر فایل دیتا روی حافظه دائمی Render Disk --- # <<< تغییر یافته
DATA_PATH = os.path.join(os.getenv("RENDER_DISK_PATH", "."), "data.json")

if not BOT_TOKEN or not ADMIN_IDS:
    raise ValueError("متغیرهای BOT_TOKEN و ADMIN_IDS باید در محیط Render تنظیم شوند!")

# --- لاگین برای دیباگ ---
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# --- متغیرهای سراسری برای ConversationHandler ---
(SELECTING_ACTION, GET_GAME_ID, GET_STARS_INFO, 
 ADMIN_PANEL, MANAGE_USER_ID, MANAGE_USER_ACTION, SET_COSTS, SET_REPLY) = range(8)

# --- توابع کار با پایگاه داده (JSON) --- # <<< تغییر یافته
def load_data():
    """خواندن اطلاعات از فایل JSON در مسیر دائمی"""
    try:
        with open(DATA_PATH, 'r', encoding='utf-8') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        # اگر فایل وجود نداشت یا خالی بود، ساختار اولیه را برمی‌گرداند
        logger.warning(f"فایل data.json در مسیر {DATA_PATH} یافت نشد. یک فایل جدید ایجاد می‌شود.")
        return {
            "bot_status": "on", "users": {}, "settings": {
                "costs": {"like_ff": 1, "account_info": 1, "account_sticker": 1, "free_stars": 3},
                "secondary_reply": {"like_ff": "خطا❌ لطفا با مدیریت تماس بگیرید", "account_info": "خطا❌ لطفا با مدیریت تماس بگیرید", "account_sticker": "خطا❌ لطفا با مدیریت تماس بگیرید", "free_stars": ""}
            }
        }

def save_data(data):
    """ذخیره اطلاعات در فایل JSON در مسیر دائمی"""
    try:
        with open(DATA_PATH, 'w', encoding='utf-8') as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
    except Exception as e:
        logger.error(f"خطا در ذخیره فایل data.json در مسیر {DATA_PATH}: {e}")

# ... (بقیه کد بدون هیچ تغییری از اینجا به بعد کپی می‌شود) ...
# (کد مربوط به is_member, start, show_main_menu و بقیه توابع را اینجا قرار دهید)
# برای جلوگیری از طولانی شدن بیش از حد، فقط بخش‌های تغییر یافته نمایش داده شد.
# شما باید کل کد ربات را که قبلا داشتم در اینجا کپی کنید. منطق اصلی ربات هیچ تغییری نکرده است.

# --- توابع کمکی ---
async def is_member(user_id: int, context: ContextTypes.DEFAULT_TYPE) -> bool:
    """بررسی عضویت کاربر در کانال‌های اجباری"""
    if not FORCED_JOIN_CHANNELS or FORCED_JOIN_CHANNELS == ['']:
        return True
    for channel in FORCED_JOIN_CHANNELS:
        try:
            member = await context.bot.get_chat_member(chat_id=channel, user_id=user_id)
            if member.status not in ['member', 'administrator', 'creator']:
                return False
        except Exception as e:
            logger.error(f"Error checking membership for {user_id} in {channel}: {e}")
            await context.bot.send_message(
                chat_id=ADMIN_IDS[0],
                text=f"خطا در بررسی عضویت کانال {channel}. ربات در کانال ادمین نیست یا آیدی اشتباه است."
            )
            return False
    return True

def generate_referral_link(user_id: int, bot_username: str) -> str:
    """ساخت لینک رفرال"""
    return f"https://t.me/{bot_username}?start={user_id}"

# --- کنترلرهای اصلی ربات ---
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """هنگام اجرای دستور /start"""
    user = update.effective_user
    user_id_str = str(user.id)
    data = load_data()

    # بررسی وضعیت ربات (خاموش/روشن)
    if data.get("bot_status", "on") == "off" and user.id not in ADMIN_IDS:
        await update.message.reply_text("🤖 ربات در حال حاضر خاموش است. لطفا بعدا تلاش کنید.")
        return

    # بررسی عضویت اجباری
    if not await is_member(user.id, context):
        keyboard = [[InlineKeyboardButton(f"عضویت در کانال {i+1}", url=f"https://t.me/{ch.lstrip('@')}") for i, ch in enumerate(FORCED_JOIN_CHANNELS)]]
        keyboard.append([InlineKeyboardButton("✅ عضو شدم", callback_data="check_join")])
        await update.message.reply_text(
            "👋 سلام! برای استفاده از ربات، لطفا ابتدا در کانال‌های زیر عضو شوید و سپس دکمه 'عضو شدم' را بزنید.",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return

    # ثبت کاربر جدید و مدیریت رفرال
    if user_id_str not in data["users"]:
        data["users"][user_id_str] = {
            "name": user.full_name,
            "points": 0,
            "last_daily_bonus": None
        }
        
        # بررسی کد رفرال
        if context.args and len(context.args) > 0:
            referrer_id = context.args[0]
            if referrer_id.isdigit() and referrer_id in data["users"] and referrer_id != user_id_str:
                data["users"][referrer_id]["points"] += 1
                try:
                    referrer_name = data["users"][user_id_str].get("name", "یک کاربر جدید")
                    await context.bot.send_message(
                        chat_id=int(referrer_id),
                        text=f"🎉 کاربر \"{referrer_name}\" با لینک شما وارد ربات شد و 1 امتیاز به شما اضافه شد!"
                    )
                except Exception as e:
                    logger.error(f"Failed to send referral notification to {referrer_id}: {e}")

    save_data(data)
    await show_main_menu(update, context)

async def show_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """نمایش منوی اصلی"""
    keyboard = [
        [InlineKeyboardButton("🔥 لایک فری فایر", callback_data="like_ff"), InlineKeyboardButton("ℹ️ اطلاعات اکانت", callback_data="account_info")],
        [InlineKeyboardButton("🎨 استیکر اکانت", callback_data="account_sticker"), InlineKeyboardButton("🌟 استارز رایگان", callback_data="free_stars")],
        [InlineKeyboardButton("🎁 امتیاز روزانه", callback_data="daily_bonus")],
        [InlineKeyboardButton("👤 حساب کاربری", callback_data="my_account"), InlineKeyboardButton("📞 پشتیبانی", callback_data="support")]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    message_text = " خوش آمدید! لطفا یکی از گزینه‌های زیر را انتخاب کنید:"
    if update.callback_query:
        await update.callback_query.edit_message_text(message_text, reply_markup=reply_markup)
    else:
        await update.message.reply_text(message_text, reply_markup=reply_markup)


async def callback_query_handler(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """مدیریت دکمه‌های شیشه‌ای"""
    query = update.callback_query
    await query.answer()
    user_id = query.from_user.id
    user_id_str = str(user_id)
    
    data = load_data()

    if data.get("bot_status", "on") == "off" and user_id not in ADMIN_IDS:
        await query.edit_message_text("🤖 ربات در حال حاضر خاموش است. لطفا بعدا تلاش کنید.")
        return

    if not await is_member(user_id, context):
        keyboard = [[InlineKeyboardButton(f"عضویت در کانال {i+1}", url=f"https://t.me/{ch.lstrip('@')}") for i, ch in enumerate(FORCED_JOIN_CHANNELS)]]
        keyboard.append([InlineKeyboardButton("✅ عضو شدم", callback_data="check_join")])
        await query.edit_message_text(
            "❌ شما هنوز در همه کانال‌ها عضو نیستید! لطفا عضو شوید و دوباره تلاش کنید.",
            reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return

    if query.data == "check_join":
        await start(query, context)
        return
    
    if query.data == "my_account":
        await my_account(query, context)
    elif query.data == "support":
        await support(query, context)
    elif query.data == "daily_bonus":
        await daily_bonus(query, context)
    elif query.data in ["like_ff", "account_info", "account_sticker", "free_stars"]:
        return await handle_service_request(query, context)
    elif query.data == "main_menu":
        await show_main_menu(update, context)

async def my_account(query: Update.callback_query, context: ContextTypes.DEFAULT_TYPE):
    user = query.from_user
    user_id_str = str(user.id)
    data = load_data()
    user_data = data["users"][user_id_str]
    bot_username = (await context.bot.get_me()).username
    
    text = f"""
    👤 **حساب کاربری شما**
    🔹 **نام:** {user_data.get('name', 'ثبت نشده')}
    🔹 **آیدی عددی:** `{user.id}`
    🔹 **امتیاز شما:** {user_data.get('points', 0)} امتیاز
    🔗 **لینک رفرال شما:**
    `{generate_referral_link(user.id, bot_username)}`
    """
    keyboard = [[InlineKeyboardButton("🔙 بازگشت به منوی اصلی", callback_data="main_menu")]]
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.MARKDOWN)

async def support(query: Update.callback_query, context: ContextTypes.DEFAULT_TYPE):
    text = """
    📞 **پشتیبانی ربات**
    در صورت وجود هرگونه مشکل، سوال یا پیشنهاد می‌توانید با ادمین‌های زیر در ارتباط باشید:
    🔸 **مالک ربات:** @immmdold
    🔸 **مدیر ربات:** @likeadminx7
    """
    keyboard = [[InlineKeyboardButton("🔙 بازگشت به منوی اصلی", callback_data="main_menu")]]
    await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard))

async def daily_bonus(query: Update.callback_query, context: ContextTypes.DEFAULT_TYPE):
    user_id_str = str(query.from_user.id)
    data = load_data()
    user_data = data["users"][user_id_str]
    
    last_bonus_str = user_data.get("last_daily_bonus")
    now = datetime.utcnow()

    if last_bonus_str:
        last_bonus_time = datetime.fromisoformat(last_bonus_str)
        if now < last_bonus_time + timedelta(hours=24):
            remaining_time = (last_bonus_time + timedelta(hours=24)) - now
            hours, remainder = divmod(remaining_time.seconds, 3600)
            minutes, _ = divmod(remainder, 60)
            await query.answer(f"❌ شما قبلا امتیاز روزانه خود را دریافت کرده‌اید. {hours} ساعت و {minutes} دقیقه دیگر تلاش کنید.", show_alert=True)
            return

    bonus = random.randint(1, 4)
    user_data["points"] += bonus
    user_data["last_daily_bonus"] = now.isoformat()
    save_data(data)

    await query.answer(f"🎉 تبریک! شما {bonus} امتیاز روزانه دریافت کردید.", show_alert=True)
    if query.message.text and "حساب کاربری شما" in query.message.text:
         await my_account(query, context)


async def handle_service_request(query: Update.callback_query, context: ContextTypes.DEFAULT_TYPE):
    service = query.data
    user_id_str = str(query.from_user.id)
    data = load_data()
    
    user_points = data["users"][user_id_str].get("points", 0)
    required_points = data["settings"]["costs"].get(service, 999)

    if user_points < required_points:
        bot_username = (await context.bot.get_me()).username
        referral_link = generate_referral_link(query.from_user.id, bot_username)
        text = f"""
        ⚠️ **امتیاز کافی نیست!**
        برای دسترسی به این بخش به [{required_points}] امتیاز نیاز دارید.
        امتیاز شما: [{user_points}]
        🔗 **لینک رفرال شما:**
        `{referral_link}`
        برای جمع آوری امتیاز باید رفرال جمع کنید.
        """
        keyboard = [[InlineKeyboardButton("🔙 بازگشت به منوی اصلی", callback_data="main_menu")]]
        await query.edit_message_text(text, reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.MARKDOWN)
        return ConversationHandler.END

    data["users"][user_id_str]["points"] -= required_points
    save_data(data)
    context.user_data['service_type'] = service

    if service == "free_stars":
        await query.edit_message_text("✅ امتیاز شما کسر شد.\n\nلطفا لینک کانال خود به همراه آیدی تلگرام خود را ارسال کنید:")
        return GET_STARS_INFO
    else:
        await query.edit_message_text("✅ امتیاز شما کسر شد.\n\nلطفا آیدی عددی گیم خود را وارد نمایید:")
        return GET_GAME_ID


async def get_game_id(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_message = update.message.text
    user = update.effective_user
    service = context.user_data.get('service_type', 'نامشخص')
    
    admin_message = f"""
    📬 **درخواست جدید**
    **از طرف:** {user.full_name} (`{user.id}`)
    **نوع سرویس:** {service}
    **محتوای پیام:**
    {user_message}
    """
    for admin_id in ADMIN_IDS:
        try:
            await context.bot.send_message(chat_id=admin_id, text=admin_message, parse_mode=ParseMode.MARKDOWN)
        except Exception as e:
            logger.error(f"Failed to send message to admin {admin_id}: {e}")

    await update.message.reply_text("✅ درخواست به سرور ارسال شد. صبور باشید.")

    data = load_data()
    secondary_reply = data["settings"]["secondary_reply"].get(service)
    if secondary_reply:
        await update.message.reply_text(secondary_reply)
        
    return ConversationHandler.END


async def get_stars_info(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    user_message = update.message.text
    user = update.effective_user
    
    admin_message = f"""
    🌟 **درخواست استارز رایگان**
    **از طرف:** {user.full_name} (`{user.id}`)
    **محتوای پیام:**
    {user_message}
    """
    for admin_id in ADMIN_IDS:
        try:
            await context.bot.send_message(chat_id=admin_id, text=admin_message, parse_mode=ParseMode.MARKDOWN)
        except Exception as e:
            logger.error(f"Failed to send message to admin {admin_id}: {e}")
            
    await update.message.reply_text("⏳ درخواست شما در حال بررسی است. صبور باشید.")
    
    data = load_data()
    secondary_reply = data["settings"]["secondary_reply"].get("free_stars")
    if secondary_reply:
        await update.message.reply_text(secondary_reply)

    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    await update.message.reply_text("عملیات لغو شد.")
    await show_main_menu(update, context)
    return ConversationHandler.END


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
        [InlineKeyboardButton("تنظیم هزینه بخش‌ها", callback_data="admin_set_costs")],
        [InlineKeyboardButton("تنظیم پاسخ ثانویه", callback_data="admin_set_reply")],
        [InlineKeyboardButton("لیست کاربران", callback_data="admin_user_list")],
        [InlineKeyboardButton("بازگشت به منوی کاربر", callback_data="main_menu")],
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    text = "به پنل مدیریت خوش آمدید."
    if update.callback_query:
        await update.callback_query.edit_message_text(text, reply_markup=reply_markup)
    else:
        await update.message.reply_text(text, reply_markup=reply_markup)
    
    return ADMIN_PANEL

async def handle_admin_callbacks(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    data = load_data()
    action = query.data

    if action == "admin_toggle_bot":
        data['bot_status'] = 'off' if data.get('bot_status', 'on') == 'on' else 'on'
        save_data(data)
        await admin_panel(query, context)

    elif action == "admin_stats":
        user_count = len(data.get("users", {}))
        await query.answer(f"تعداد کل کاربران: {user_count} نفر", show_alert=True)
    
    elif action == "admin_user_list":
        users = data.get("users", {})
        if not users:
            await query.edit_message_text("هیچ کاربری ثبت نشده است.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("بازگشت", callback_data="admin_panel_back")]]))
            return ADMIN_PANEL

        user_list_text = "لیست کاربران:\n\n"
        for uid, udata in users.items():
            user_list_text += f"👤 نام: {udata.get('name', 'N/A')}\n🆔 آیدی: `{uid}`\n\n"
        
        if len(user_list_text) > 4000:
            user_list_text = "تعداد کاربران زیاد است. لیست در فایل زیر:"
            with open("user_list.txt", "w", encoding="utf-8") as f:
                f.write(user_list_text)
            await context.bot.send_document(chat_id=query.from_user.id, document=open("user_list.txt", "rb"))
        else:
             await query.edit_message_text(user_list_text, parse_mode=ParseMode.MARKDOWN, reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("بازگشت", callback_data="admin_panel_back")]]))

    elif action == "admin_manage_user":
        await query.edit_message_text("لطفا آیدی عددی کاربری که می‌خواهید مدیریتش کنید را ارسال نمایید:")
        return MANAGE_USER_ID
    
    elif action == "admin_set_costs":
        await query.edit_message_text("این بخش در دست توسعه است. لطفا فایل data.json را مستقیما ویرایش کنید.")
        return ADMIN_PANEL
    
    elif action == "admin_set_reply":
        await query.edit_message_text("این بخش در دست توسعه است. لطفا فایل data.json را مستقیما ویرایش کنید.")
        return ADMIN_PANEL

    elif action == "admin_panel_back":
        await admin_panel(query, context)
        return ADMIN_PANEL
    
    return ADMIN_PANEL

async def get_user_id_for_manage(update: Update, context: ContextTypes.DEFAULT_TYPE):
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

    is_banned = user_info.get("banned", False)
    ban_text = "رفع بن" if is_banned else "بن کردن"

    keyboard = [
        [InlineKeyboardButton("افزودن امتیاز", callback_data="manage_add"), InlineKeyboardButton("کسر امتیاز", callback_data="manage_sub")],
        [InlineKeyboardButton(ban_text, callback_data="manage_ban")],
        [InlineKeyboardButton("بازگشت", callback_data="admin_panel_back")]
    ]
    await update.message.reply_text(f"مدیریت کاربر `{target_user_id}`\nامتیاز فعلی: {points}\n\nچه کاری می‌خواهید انجام دهید؟", 
                                    reply_markup=InlineKeyboardMarkup(keyboard), parse_mode=ParseMode.MARKDOWN)
    
    return MANAGE_USER_ACTION

async def manage_user_action(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    
    action = query.data.split('_')[-1]
    target_user_id = context.user_data.get('target_user_id')
    
    if not target_user_id:
        await query.edit_message_text("خطا! آیدی کاربر مشخص نیست. لطفا از اول شروع کنید.", reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("بازگشت به پنل", callback_data="admin_panel_back")]]))
        return ADMIN_PANEL
    
    data = load_data()
    amount_text = ""
    if action == "add":
        data["users"][target_user_id]["points"] += 1
        amount_text = "1 امتیاز اضافه شد."
    elif action == "sub":
        data["users"][target_user_id]["points"] -= 1
        amount_text = "1 امتیاز کسر شد."
    elif action == "ban":
        current_ban_status = data["users"][target_user_id].get("banned", False)
        data["users"][target_user_id]["banned"] = not current_ban_status
        amount_text = "کاربر بن شد." if not current_ban_status else "کاربر از بن خارج شد."

    save_data(data)
    
    new_points = data["users"][target_user_id]["points"]
    await query.edit_message_text(f"انجام شد! {amount_text}\nامتیاز جدید کاربر `{target_user_id}`: {new_points}", parse_mode=ParseMode.MARKDOWN,
                                  reply_markup=InlineKeyboardMarkup([[InlineKeyboardButton("بازگشت به پنل", callback_data="admin_panel_back")]]))

    return ADMIN_PANEL


# --- Main ---
def main() -> None:
    """Run the bot."""
    application = Application.builder().token(BOT_TOKEN).build()

    service_conv_handler = ConversationHandler(
        entry_points=[CallbackQueryHandler(handle_service_request, pattern='^(like_ff|account_info|account_sticker|free_stars)$')],
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
        fallbacks=[CommandHandler('cancel', cancel), CallbackQueryHandler(admin_panel, pattern='admin_panel_back')],
    )

    application.add_handler(CommandHandler("start", start))
    application.add_handler(service_conv_handler)
    application.add_handler(admin_conv_handler)
    application.add_handler(CallbackQueryHandler(callback_query_handler))

    logger.info("ربات در حال اجرا است...")
    application.run_polling()


if __name__ == "__main__":
    main()

