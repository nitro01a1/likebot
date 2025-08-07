import logging
from functools import wraps
from telegram import Update
from telegram.ext import Application, CommandHandler, ContextTypes
from telegram.constants import ChatMemberStatus

# --- تنظیمات خود را اینجا وارد کنید ---
BOT_TOKEN = "7882319394:AAG-TFTzkcEccTbR3sEIOJ0I9StWJMhNeHc"
ADMIN_IDS = [1956250138] # آیدی عددی خودتان
REQUIRED_CHANNELS = ["@x7gap", "@npvpnir"] # آیدی کانال و گروه
# ------------------------------------

logging.basicConfig(format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=logging.INFO)

def check_join(func):
    @wraps(func)
    async def wrapped(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        user = update.effective_user
        for channel_id in REQUIRED_CHANNELS:
            try:
                member = await context.bot.get_chat_member(chat_id=channel_id, user_id=user.id)
                if member.status not in [ChatMemberStatus.MEMBER, ChatMemberStatus.ADMINISTRATOR, ChatMemberStatus.OWNER]:
                    await update.message.reply_text(f"❌ برای تست، ابتدا باید در کانال/گروه {channel_id} عضو شوید.")
                    return
            except Exception as e:
                await update.message.reply_text(f"⚠️ خطا در بررسی عضویت {channel_id}. آیا ربات در آن ادمین است؟")
                logging.error(f"Error checking {channel_id}: {e}")
                return
        return await func(update, context, *args, **kwargs)
    return wrapped

@check_join
async def test_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """یک دستور تست ساده که فقط در صورت عضویت اجرا می‌شود."""
    await update.message.reply_text("✅ تست موفق بود! سیستم عضویت اجباری شما به درستی کار می‌کند.")

def main() -> None:
    application = Application.builder().token(BOT_TOKEN).build()
    application.add_handler(CommandHandler("test", test_command))
    print("ربات تست در حال اجراست...")
    application.run_polling()

if __name__ == "__main__":
    main()
