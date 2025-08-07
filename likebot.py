import logging
import json
import os
from telegram import Update, ReplyKeyboardMarkup, ReplyKeyboardRemove
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters,
    ContextTypes,
    ConversationHandler,
)

# ------------------- تنظیمات اولیه (بسیار مهم) -------------------
BOT_TOKEN = "7882319394:AAG-TFTzkcEccTbR3sEIOJ0I9StWJMhNeHc"
ADMIN_CHAT_ID = 8066854428  # آیدی عددی ادمین
DATA_FILE = "referral_data.json"  # فایل ذخیره اطلاعات
# -----------------------------------------------------------------

# تعریف مراحل برای ConversationHandler
AWAITING_LIKE_ID, AWAITING_STAR_INFO = range(2)

# تنظیمات لاگ
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)

# --- توابع مربوط به ذخیره و بازیابی اطلاعات ---
def load_data():
    if os.path.exists(DATA_FILE):
        with open(DATA_FILE, 'r') as f:
            return json.load(f)
    return {"users": {}, "referral_counts": {}}

def save_data(data):
    with open(DATA_FILE, 'w') as f:
        json.dump(data, f, indent=4)

# --- توابع اصلی ربات ---

async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """دستور /start را مدیریت می‌کند، رفرال‌ها را ثبت کرده و کیبورد اصلی را نمایش می‌دهد."""
    user = update.effective_user
    data = load_data()

    # --- بخش ثبت رفرال ---
    if context.args:
        try:
            referrer_id = int(context.args[0])
            if str(user.id) not in data["users"] and user.id != referrer_id:
                data["users"][str(user.id)] = {"referred_by": referrer_id}
                referrer_id_str = str(referrer_id)
                data["referral_counts"][referrer_id_str] = data["referral_counts"].get(referrer_id_str, 0) + 1
                save_data(data)
                await context.bot.send_message(
                    chat_id=referrer_id,
                    text=f"🎉 تبریک! یک کاربر جدید ({user.first_name}) با لینک شما وارد ربات شد."
                )
        except (ValueError, IndexError):
            logger.warning("Invalid referral link used.")

    # --- بخش خوشامدگویی و نمایش کیبورد ---
    keyboard = [
        ["لایک رایگان🤠", "استارز رایگان⭐"],
        ["اطلاعات اکانت 👤"]
    ]
    reply_markup = ReplyKeyboardMarkup(keyboard, resize_keyboard=True)
    welcome_text = "به ربات لایک رایگان x7 خوش آمدید!"
    await update.message.reply_text(welcome_text, reply_markup=reply_markup)

async def account_info(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """اطلاعات اکانت کاربر را نمایش می‌دهد."""
    user = update.effective_user
    data = load_data()
    score = data["referral_counts"].get(str(user.id), 0)
    bot_username = (await context.bot.get_me()).username
    referral_link = f"https://t.me/{bot_username}?start={user.id}"

    info_text = (
        f"👤 **اطلاعات اکانت شما**\n\n"
        f"▫️ **آیدی عددی:** `{user.id}`\n"
        f"▫️ **امتیاز شما:** **{score}** (تعداد افراد دعوت شده)\n\n"
        f"🔗 **لینک دعوت اختصاصی شما:**\n`{referral_link}`"
    )
    await update.message.reply_text(info_text, parse_mode='Markdown')

async def free_like_request(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """شروع فرآیند درخواست لایک رایگان."""
    await update.message.reply_text(
        "لطفا آیدی خود را در قالب یک متن ارسال کنید.",
        reply_markup=ReplyKeyboardRemove() # کیبورد را موقتا مخفی میکند
    )
    return AWAITING_LIKE_ID

async def free_star_request(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """شروع فرآیند درخواست استارز رایگان و بررسی امتیاز."""
    user = update.effective_user
    data = load_data()
    score = data["referral_counts"].get(str(user.id), 0)

    if score < 2:
        bot_username = (await context.bot.get_me()).username
        referral_link = f"https://t.me/{bot_username}?start={user.id}"
        await update.message.reply_text(
            f"❌ امتیاز شما کافی نیست!\n\n"
            f"برای دریافت یک استارز، باید حداقل ۲ نفر را به ربات دعوت کنید (امتیاز شما: {score}).\n\n"
            f"لینک دعوت شما:\n`{referral_link}`"
            , parse_mode='Markdown'
        )
        return ConversationHandler.END # پایان مکالمه
    else:
        # کسر امتیاز
        data["referral_counts"][str(user.id)] = score - 2
        save_data(data)
        await update.message.reply_text(
            "✅ امتیاز از شما کسر شد.\n"
            "لطفا آیدی عددی خود (که از بخش اطلاعات اکانت بدست میاد) و آیدی چنلتون را در قالب یک متن ارسال کنید.",
            reply_markup=ReplyKeyboardRemove()
        )
        return AWAITING_STAR_INFO

async def forward_like_id(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """پیام آیدی لایک را برای ادمین فوروارد می‌کند."""
    user = update.effective_user
    text = update.message.text
    header = f"📩 **درخواست لایک جدید**\nاز: {user.first_name} (ID: `{user.id}`)\n\n**آیدی ارسالی:**\n{text}"
    await context.bot.send_message(chat_id=ADMIN_CHAT_ID, text=header, parse_mode='Markdown')
    await update.message.reply_text("✅ درخواست شما برای ادمین ارسال شد. به منوی اصلی بازگشتید.")
    await start(update, context) # نمایش مجدد کیبورد اصلی
    return ConversationHandler.END

async def forward_star_info(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """پیام اطلاعات استارز را برای ادمین فوروارد می‌کند."""
    user = update.effective_user
    text = update.message.text
    header = f"⭐ **درخواست استارز جدید**\nاز: {user.first_name} (ID: `{user.id}`)\n\n**اطلاعات ارسالی:**\n{text}"
    await context.bot.send_message(chat_id=ADMIN_CHAT_ID, text=header, parse_mode='Markdown')
    await update.message.reply_text("✅ درخواست شما برای ادمین ارسال شد. به منوی اصلی بازگشتید.")
    await start(update, context) # نمایش مجدد کیبورد اصلی
    return ConversationHandler.END

async def cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    """فرآیند را لغو کرده و به منوی اصلی برمیگردد."""
    await update.message.reply_text("عملیات لغو شد.")
    await start(update, context)
    return ConversationHandler.END

async def handle_admin_reply(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """پاسخ ادمین را به کاربر مربوطه ارسال می‌کند."""
    if update.message.chat_id == ADMIN_CHAT_ID and update.message.reply_to_message:
        try:
            # استخراج آیدی کاربر از پیام ریپلای شده
            replied_text = update.message.reply_to_message.text
            original_user_id = int(replied_text.split('(ID: `')[1].split('`)')[0])
            await context.bot.send_message(chat_id=original_user_id, text=f"🗣️ پاسخ ادمین:\n\n{update.message.text}")
            await update.message.reply_text("✅ پاسخ شما برای کاربر ارسال شد.")
        except (IndexError, ValueError):
            # اگر فرمت پیام برای ریپلای مناسب نبود
            await update.message.reply_text("خطا: این پیام قابل پاسخگویی نیست. لطفاً فقط به پیام‌های درخواست کاربران ریپلای کنید.")

def main() -> None:
    """شروع به کار ربات."""
    application = Application.builder().token(BOT_TOKEN).build()

    # ConversationHandler برای مدیریت فرآیندهای چند مرحله‌ای
    conv_handler = ConversationHandler(
        entry_points=[
            MessageHandler(filters.Regex("^لایک رایگان🤠$"), free_like_request),
            MessageHandler(filters.Regex("^استارز رایگان⭐$"), free_star_request),
        ],
        states={
            AWAITING_LIKE_ID: [MessageHandler(filters.TEXT & ~filters.COMMAND, forward_like_id)],
            AWAITING_STAR_INFO: [MessageHandler(filters.TEXT & ~filters.COMMAND, forward_star_info)],
        },
        fallbacks=[CommandHandler("cancel", cancel)],
    )

    application.add_handler(conv_handler)
    application.add_handler(CommandHandler("start", start))
    application.add_handler(MessageHandler(filters.Regex("^اطلاعات اکانت 👤$"), account_info))
    # این هندلر باید بعد از بقیه باشد تا در کار آنها اختلال ایجاد نکند
    application.add_handler(MessageHandler(filters.REPLY, handle_admin_reply))


    print("ربات با تمام قابلیت‌های جدید در حال اجراست...")
    application.run_polling()

if __name__ == "__main__":
    main()
            # فرمت ما: "پیام جدید از ... (ID: 12345)"
            original_user_id_str = update.message.reply_to_message.text.split('(ID: ')[1].split(')')[0]
            original_user_id = int(original_user_id_str)
            
            # پیام ادمین را به کاربر اصلی ارسال می‌کنیم
            await context.bot.send_message(chat_id=original_user_id, text=update.message.text)
            await update.message.reply_text("✅ پاسخ شما برای کاربر ارسال شد.")
        except (IndexError, ValueError):
            await update.message.reply_text("خطا: نتوانستم کاربر اصلی را برای ارسال پاسخ پیدا کنم. لطفاً فقط به پیام‌های فوروارد شده از ربات ریپلای کنید.")
        return

    # ---- اگر پیام از طرف یک کاربر عادی باشد ----
    if chat_id != ADMIN_CHAT_ID:
        # ساخت یک هدر برای پیام فورواردی جهت شناسایی راحت‌تر کاربر
        forward_header = f"پیام جدید از {user.first_name} (ID: {user.id}):"
        
        # ارسال هدر و سپس فوروارد کردن پیام اصلی کاربر به ادمین
        await context.bot.send_message(chat_id=ADMIN_CHAT_ID, text=forward_header)
        await context.bot.forward_message(chat_id=ADMIN_CHAT_ID, from_chat_id=user.id, message_id=update.message.message_id)


def main() -> None:
    """شروع به کار ربات."""
    # ساخت اپلیکیشن ربات
    application = Application.builder().token(BOT_TOKEN).build()

    # تعریف دستورات و هندلرها
    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(button_callback))
    application.add_handler(MessageHandler(filters.TEXT & ~filters.COMMAND, handle_message))

    # اجرای ربات
    print("ربات در حال اجراست...")
    application.run_polling()


if __name__ == "__main__":
    main()

