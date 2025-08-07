import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import Application, CommandHandler, MessageHandler, filters, ContextTypes, CallbackQueryHandler

# ------------------- تنظیمات اولیه -------------------
# توکن ربات خود را که از BotFather گرفته‌اید، اینجا قرار دهید
BOT_TOKEN = "7611590415:AAENMu67exAyMlVrLXwT7W4vQ2NZr9L7U3g"

# آیدی عددی اکانت ادمین (خودتان) را که از @userinfobot گرفتید، اینجا قرار دهید
ADMIN_CHAT_ID = 8066854428  # حتما این عدد را با آیدی خودتان جایگزین کنید
# ----------------------------------------------------

# تنظیمات لاگ برای دیباگ کردن راحت‌تر
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO
)
logger = logging.getLogger(__name__)


# تابع برای دستور /start
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """این تابع به دستور /start پاسخ می‌دهد."""
    # ساخت دکمه
    keyboard = [
        [InlineKeyboardButton("لایک رایگان🤠", callback_data='free_like_button')]
    ]
    reply_markup = InlineKeyboardMarkup(keyboard)

    # متن خوشامدگویی
    welcome_text = (
        "به ربات لایک رایگان x7 خوش آمدید!\n"
        "لطفا جهت دریافت، قسمت لایک رایگان را انتخاب کنید."
    )
    
    await update.message.reply_text(welcome_text, reply_markup=reply_markup)


# تابع برای مدیریت کلیک روی دکمه‌ها
async def button_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """این تابع کلیک روی دکمه‌های شیشه‌ای را مدیریت می‌کند."""
    query = update.callback_query
    await query.answer()  # به تلگرام پاسخ می‌دهد که کلیک دریافت شد

    if query.data == 'free_like_button':
        # متنی که بعد از کلیک روی دکمه نمایش داده می‌شود
        response_text = (
            "لطفا آیدی خود را در قالب یک متن ارسال کنید.\n"
            "و لطفا اسپم ندهید در غیر اینصورت واریز نمیشود."
        )
        await query.message.reply_text(response_text)


# تابع برای مدیریت پیام‌های متنی کاربران و پاسخ ادمین
async def handle_message(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """پیام کاربر را به ادمین فوروارد کرده و پاسخ ادمین را به کاربر برمی‌گرداند."""
    user = update.message.from_user
    chat_id = update.message.chat_id

    # ---- اگر پیام از طرف ادمین و در پاسخ به پیام کاربر باشد ----
    if chat_id == ADMIN_CHAT_ID and update.message.reply_to_message:
        # در متن پیام فوروارد شده، آیدی کاربر اصلی وجود دارد. آن را استخراج می‌کنیم.
        try:
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

