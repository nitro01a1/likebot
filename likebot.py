import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Updater,
    CommandHandler,
    MessageHandler,
    Filters,
    CallbackContext,
    CallbackQueryHandler,
    ConversationHandler
)
import random
import sqlite3
from uuid import uuid4

# تنظیمات لاگ
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s', level=logging.INFO
)
logger = logging.getLogger(__name__)

# تنظیمات دیتابیس
DB_NAME = 'bot_database.db'

# حالت‌های گفتگو
LIKE_FREE_FIRE, ACCOUNT_INFO, ACCOUNT_STICKER, FREE_STARS = range(4)
INPUT_GAME_ID, INPUT_CHANNEL_LINK = range(2)

# تنظیمات ربات
ADMINS = [123456789, 987654321]  # جایگزین کنید با آیدی عددی ادمین‌ها
REQUIRED_CHANNELS = ['@channel1', '@channel2']  # جایگزین کنید با چنل‌های واقعی
BOT_TOKEN = 'YOUR_BOT_TOKEN'  # جایگزین کنید با توکن ربات
OWNER_USERNAME = '@immmdold'
ADMIN_USERNAME = '@likeadminx7'

# اتصال به دیتابیس
def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    # ایجاد جدول کاربران
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY,
        username TEXT,
        first_name TEXT,
        last_name TEXT,
        referral_code TEXT UNIQUE,
        points INTEGER DEFAULT 0,
        referred_by INTEGER,
        banned INTEGER DEFAULT 0
    )
    ''')
    
    # ایجاد جدول درخواست‌ها
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS requests (
        request_id INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id INTEGER,
        request_type TEXT,
        content TEXT,
        status TEXT DEFAULT 'pending',
        timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
        FOREIGN KEY(user_id) REFERENCES users(user_id)
    )
    ''')
    
    # ایجاد جدول تنظیمات
    cursor.execute('''
    CREATE TABLE IF NOT EXISTS settings (
        setting_name TEXT PRIMARY KEY,
        setting_value TEXT
    )
    ''')
    
    # تنظیمات پیش‌فرض
    settings = [
        ('bot_active', '1'),
        ('like_free_fire_points', '1'),
        ('account_info_points', '1'),
        ('account_sticker_points', '1'),
        ('free_stars_points', '3'),
        ('like_free_fire_reply', 'درخواست به سرور ارسال شد✅صبور باشید'),
        ('account_info_reply', 'درخواست به سرور ارسال شد✅صبور باشید'),
        ('account_sticker_reply', 'درخواست به سرور ارسال شد✅صبور باشید'),
        ('free_stars_reply', 'درخواست شما در حال بررسی است صبور باشید'),
        ('error_reply', 'خطا❌ لطفا با مدیریت تماس بگیرید')
    ]
    
    cursor.executemany('''
    INSERT OR IGNORE INTO settings (setting_name, setting_value) VALUES (?, ?)
    ''', settings)
    
    conn.commit()
    conn.close()

init_db()

# توابع کمکی
def get_user(user_id):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('SELECT * FROM users WHERE user_id = ?', (user_id,))
    user = cursor.fetchone()
    conn.close()
    return user

def create_user(user_id, username, first_name, last_name, referred_by=None):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    referral_code = str(uuid4())[:8]
    
    cursor.execute('''
    INSERT OR IGNORE INTO users 
    (user_id, username, first_name, last_name, referral_code, referred_by) 
    VALUES (?, ?, ?, ?, ?, ?)
    ''', (user_id, username, first_name, last_name, referral_code, referred_by))
    
    if referred_by:
        cursor.execute('''
        UPDATE users SET points = points + 1 WHERE user_id = ?
        ''', (referred_by,))
        
        # اطلاع به کاربری که رفرال داده
        try:
            context.bot.send_message(
                chat_id=referred_by,
                text=f'کاربر {first_name} با لینک شما وارد شد و یک امتیاز به شما افزوده شد!'
            )
        except:
            pass
    
    conn.commit()
    conn.close()

def get_setting(setting_name):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('SELECT setting_value FROM settings WHERE setting_name = ?', (setting_name,))
    result = cursor.fetchone()
    conn.close()
    return result[0] if result else None

def update_setting(setting_name, setting_value):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('''
    INSERT OR REPLACE INTO settings (setting_name, setting_value) 
    VALUES (?, ?)
    ''', (setting_name, setting_value))
    conn.commit()
    conn.close()

def add_request(user_id, request_type, content):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('''
    INSERT INTO requests (user_id, request_type, content) 
    VALUES (?, ?, ?)
    ''', (user_id, request_type, content))
    conn.commit()
    conn.close()

def get_all_users():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('SELECT user_id, username, first_name, last_name, points FROM users')
    users = cursor.fetchall()
    conn.close()
    return users

def update_user_points(user_id, points_change):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('''
    UPDATE users SET points = points + ? WHERE user_id = ?
    ''', (points_change, user_id))
    conn.commit()
    conn.close()

def toggle_user_ban(user_id):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute('''
    UPDATE users SET banned = NOT banned WHERE user_id = ?
    ''', (user_id,))
    conn.commit()
    conn.close()

def check_user_in_channels(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    for channel in REQUIRED_CHANNELS:
        try:
            member = context.bot.get_chat_member(channel, user_id)
            if member.status in ['left', 'kicked']:
                return False
        except:
            return False
    return True

# دستورات کاربران عادی
def start(update: Update, context: CallbackContext):
    user = update.effective_user
    referred_by = None
    
    # بررسی رفرال
    if context.args:
        referred_by = int(context.args[0]) if context.args[0].isdigit() else None
    
    create_user(user.id, user.username, user.first_name, user.last_name, referred_by)
    
    if not check_user_in_channels(update, context):
        channels_text = "\n".join(REQUIRED_CHANNELS)
        update.message.reply_text(
            f"⚠️ برای استفاده از ربات باید در چنل‌های زیر عضو باشید:\n{channels_text}\n\n"
            "پس از عضویت /start را دوباره بزنید."
        )
        return
    
    show_main_menu(update, context)

def show_main_menu(update: Update, context: CallbackContext):
    user = get_user(update.effective_user.id)
    keyboard = [
        [InlineKeyboardButton("لایک فری فایر", callback_data='like_free_fire')],
        [InlineKeyboardButton("اطلاعات اکانت", callback_data='account_info')],
        [InlineKeyboardButton("استیکر اکانت", callback_data='account_sticker')],
        [InlineKeyboardButton("استارز رایگان", callback_data='free_stars')],
        [InlineKeyboardButton("امتیاز روزانه", callback_data='daily_points')],
        [InlineKeyboardButton("حساب کاربری", callback_data='user_account')],
        [InlineKeyboardButton("پشتیبانی", callback_data='support')]
    ]
    
    if update.effective_user.id in ADMINS:
        keyboard.append([InlineKeyboardButton("پنل مدیریت", callback_data='admin_panel')])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    update.message.reply_text(
        "🏠 منوی اصلی:",
        reply_markup=reply_markup
    )

def button_handler(update: Update, context: CallbackContext):
    query = update.callback_query
    query.answer()
    
    user = get_user(query.from_user.id)
    
    if query.data == 'like_free_fire':
        handle_like_free_fire(query, context)
    elif query.data == 'account_info':
        handle_account_info(query, context)
    elif query.data == 'account_sticker':
        handle_account_sticker(query, context)
    elif query.data == 'free_stars':
        handle_free_stars(query, context)
    elif query.data == 'daily_points':
        handle_daily_points(query, context)
    elif query.data == 'user_account':
        handle_user_account(query, context)
    elif query.data == 'support':
        handle_support(query, context)
    elif query.data == 'admin_panel':
        handle_admin_panel(query, context)
    elif query.data == 'back_to_main':
        show_main_menu_from_query(query, context)
    elif query.data == 'bot_toggle':
        handle_bot_toggle(query, context)
    elif query.data == 'user_stats':
        handle_user_stats(query, context)
    elif query.data == 'user_list':
        handle_user_list(query, context)
    elif query.data == 'ban_user':
        query.edit_message_text("لطفا آیدی عددی کاربر را برای بن/آنبن ارسال کنید:")
        return 'ban_user'
    elif query.data == 'manage_points':
        query.edit_message_text("لطفا آیدی عددی کاربر و مقدار امتیاز را به فرمت زیر ارسال کنید:\n12345 +10 (برای افزودن)\n12345 -5 (برای کسر)")
        return 'manage_points'
    elif query.data == 'settings_menu':
        handle_settings_menu(query, context)
    elif query.data.startswith('setting_'):
        handle_setting_change(query, context)

def handle_like_free_fire(query, context):
    user = get_user(query.from_user.id)
    required_points = int(get_setting('like_free_fire_points'))
    
    if user[5] < required_points:
        query.edit_message_text(
            f"برای دسترسی به این بخش به {required_points} امتیاز نیاز دارید. [{user[5]} امتیاز شما]\n"
            f"لینک رفرال شما: https://t.me/{context.bot.username}?start={user[0]}\n"
            "برای جمع آوری امتیاز باید رفرال جمع کنید."
        )
    else:
        query.edit_message_text("لطفا آیدی عددی بازی خود را ارسال کنید:")
        return INPUT_GAME_ID

def handle_account_info(query, context):
    user = get_user(query.from_user.id)
    required_points = int(get_setting('account_info_points'))
    
    if user[5] < required_points:
        query.edit_message_text(
            f"برای دسترسی به این بخش به {required_points} امتیاز نیاز دارید. [{user[5]} امتیاز شما]\n"
            f"لینک رفرال شما: https://t.me/{context.bot.username}?start={user[0]}\n"
            "برای جمع آوری امتیاز باید رفرال جمع کنید."
        )
    else:
        query.edit_message_text("لطفا آیدی عددی بازی خود را ارسال کنید:")
        return INPUT_GAME_ID

def handle_account_sticker(query, context):
    user = get_user(query.from_user.id)
    required_points = int(get_setting('account_sticker_points'))
    
    if user[5] < required_points:
        query.edit_message_text(
            f"برای دسترسی به این بخش به {required_points} امتیاز نیاز دارید. [{user[5]} امتیاز شما]\n"
            f"لینک رفرال شما: https://t.me/{context.bot.username}?start={user[0]}\n"
            "برای جمع آوری امتیاز باید رفرال جمع کنید."
        )
    else:
        query.edit_message_text("لطفا آیدی عددی بازی خود را ارسال کنید:")
        return INPUT_GAME_ID

def handle_free_stars(query, context):
    user = get_user(query.from_user.id)
    required_points = int(get_setting('free_stars_points'))
    
    if user[5] < required_points:
        query.edit_message_text(
            f"برای دسترسی به این بخش به {required_points} امتیاز نیاز دارید. [{user[5]} امتیاز شما]\n"
            f"لینک رفرال شما: https://t.me/{context.bot.username}?start={user[0]}\n"
            "برای جمع آوری امتیاز باید رفرال جمع کنید."
        )
    else:
        query.edit_message_text("لطفا لینک چنل خود به همراه آیدی تلگرام خود را ارسال کنید:")
        return INPUT_CHANNEL_LINK

def handle_daily_points(query, context):
    user = get_user(query.from_user.id)
    points = random.randint(1, 4)
    
    update_user_points(user[0], points)
    
    query.edit_message_text(f"🎉 شما {points} امتیاز روزانه دریافت کردید!")

def handle_user_account(query, context):
    user = get_user(query.from_user.id)
    query.edit_message_text(
        f"👤 حساب کاربری:\n\n"
        f"🆔 آیدی عددی: {user[0]}\n"
        f"👤 نام: {user[2]} {user[3] if user[3] else ''}\n"
        f"🔗 لینک رفرال: https://t.me/{context.bot.username}?start={user[0]}\n"
        f"⭐ امتیاز: {user[5]}"
    )

def handle_support(query, context):
    query.edit_message_text(
        f"📞 پشتیبانی:\n\n"
        f"👤 ایدی مالک: {OWNER_USERNAME}\n"
        f"👥 ایدی مدیر: {ADMIN_USERNAME}"
    )

def input_game_id(update: Update, context: CallbackContext):
    user = get_user(update.message.from_user.id)
    request_type = context.user_data.get('current_request_type')
    
    add_request(user[0], request_type, update.message.text)
    
    reply_text = get_setting(f'{request_type}_reply')
    update.message.reply_text(reply_text)
    
    # ارسال به ادمین‌ها
    for admin in ADMINS:
        try:
            context.bot.send_message(
                chat_id=admin,
                text=f"درخواست جدید از کاربر {user[2]} ({user[0]}):\n"
                     f"نوع: {request_type}\n"
                     f"محتوا: {update.message.text}"
            )
        except:
            pass
    
    # ارسال پیام خطا بعد از 5 ثانیه
    context.job_queue.run_once(
        send_error_message, 
        5, 
        context=update.message.chat_id
    )
    
    return ConversationHandler.END

def input_channel_link(update: Update, context: CallbackContext):
    user = get_user(update.message.from_user.id)
    request_type = 'free_stars'
    
    add_request(user[0], request_type, update.message.text)
    
    reply_text = get_setting(f'{request_type}_reply')
    update.message.reply_text(reply_text)
    
    # ارسال به ادمین‌ها
    for admin in ADMINS:
        try:
            context.bot.send_message(
                chat_id=admin,
                text=f"درخواست جدید از کاربر {user[2]} ({user[0]}):\n"
                     f"نوع: استارز رایگان\n"
                     f"محتوا: {update.message.text}"
            )
        except:
            pass
    
    # ارسال پیام خطا بعد از 5 ثانیه
    context.job_queue.run_once(
        send_error_message, 
        5, 
        context=update.message.chat_id
    )
    
    return ConversationHandler.END

def send_error_message(context: CallbackContext):
    job = context.job
    error_reply = get_setting('error_reply')
    context.bot.send_message(
        chat_id=job.context,
        text=error_reply
    )

# پنل مدیریت
def handle_admin_panel(query, context):
    if query.from_user.id not in ADMINS:
        query.answer("شما دسترسی ندارید!", show_alert=True)
        return
    
    bot_status = "🟢 روشن" if get_setting('bot_active') == '1' else "🔴 خاموش"
    
    keyboard = [
        [InlineKeyboardButton(f"وضعیت ربات: {bot_status}", callback_data='bot_toggle')],
        [InlineKeyboardButton("آمار کاربران", callback_data='user_stats')],
        [InlineKeyboardButton("لیست کاربران", callback_data='user_list')],
        [InlineKeyboardButton("مدیریت بن کاربران", callback_data='ban_user')],
        [InlineKeyboardButton("مدیریت امتیاز کاربران", callback_data='manage_points')],
        [InlineKeyboardButton("تنظیمات امتیازها", callback_data='settings_menu')],
        [InlineKeyboardButton("بازگشت به منوی اصلی", callback_data='back_to_main')]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    query.edit_message_text(
        "👨‍💻 پنل مدیریت:",
        reply_markup=reply_markup
    )

def handle_bot_toggle(query, context):
    if query.from_user.id not in ADMINS:
        query.answer("شما دسترسی ندارید!", show_alert=True)
        return
    
    current_status = get_setting('bot_active')
    new_status = '0' if current_status == '1' else '1'
    update_setting('bot_active', new_status)
    
    bot_status = "🟢 روشن" if new_status == '1' else "🔴 خاموش"
    query.edit_message_text(
        f"وضعیت ربات به {bot_status} تغییر یافت.",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("بازگشت به پنل مدیریت", callback_data='admin_panel')]
        ])
    )

def handle_user_stats(query, context):
    if query.from_user.id not in ADMINS:
        query.answer("شما دسترسی ندارید!", show_alert=True)
        return
    
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    
    # تعداد کل کاربران
    cursor.execute('SELECT COUNT(*) FROM users')
    total_users = cursor.fetchone()[0]
    
    # کاربران فعال
    cursor.execute('SELECT COUNT(*) FROM users WHERE banned = 0')
    active_users = cursor.fetchone()[0]
    
    # کاربران بن شده
    cursor.execute('SELECT COUNT(*) FROM users WHERE banned = 1')
    banned_users = cursor.fetchone()[0]
    
    # مجموع امتیازات
    cursor.execute('SELECT SUM(points) FROM users')
    total_points = cursor.fetchone()[0] or 0
    
    conn.close()
    
    query.edit_message_text(
        f"📊 آمار کاربران:\n\n"
        f"👥 تعداد کل کاربران: {total_users}\n"
        f"🟢 کاربران فعال: {active_users}\n"
        f"🔴 کاربران بن شده: {banned_users}\n"
        f"⭐ مجموع امتیازات: {total_points}",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("بازگشت به پنل مدیریت", callback_data='admin_panel')]
        ])
    )

def handle_user_list(query, context):
    if query.from_user.id not in ADMINS:
        query.answer("شما دسترسی ندارید!", show_alert=True)
        return
    
    users = get_all_users()
    users_text = "\n\n".join(
        f"🆔 {user[0]} | 👤 {user[2]} {user[3] if user[3] else ''} | ⭐ {user[4]}"
        for user in users[:50]  # نمایش 50 کاربر اول برای جلوگیری از پیام طولانی
    )
    
    if len(users) > 50:
        users_text += f"\n\nو {len(users)-50} کاربر دیگر..."
    
    query.edit_message_text(
        f"📋 لیست کاربران:\n\n{users_text}",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("بازگشت به پنل مدیریت", callback_data='admin_panel')]
        ])
    )

def ban_user(update: Update, context: CallbackContext):
    if update.message.from_user.id not in ADMINS:
        update.message.reply_text("شما دسترسی ندارید!")
        return ConversationHandler.END
    
    try:
        user_id = int(update.message.text)
        toggle_user_ban(user_id)
        
        user = get_user(user_id)
        status = "بن شد" if user[6] == 1 else "آنبن شد"
        
        update.message.reply_text(
            f"کاربر {user[2]} ({user_id}) {status}.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("بازگشت به پنل مدیریت", callback_data='admin_panel')]
            ])
        )
    except ValueError:
        update.message.reply_text("آیدی کاربر باید عددی باشد. لطفا دوباره تلاش کنید.")
        return 'ban_user'
    except:
        update.message.reply_text("خطا در پردازش درخواست. لطفا دوباره تلاش کنید.")
        return 'ban_user'
    
    return ConversationHandler.END

def manage_points(update: Update, context: CallbackContext):
    if update.message.from_user.id not in ADMINS:
        update.message.reply_text("شما دسترسی ندارید!")
        return ConversationHandler.END
    
    try:
        parts = update.message.text.split()
        user_id = int(parts[0])
        points_change = int(parts[1])
        
        update_user_points(user_id, points_change)
        user = get_user(user_id)
        
        update.message.reply_text(
            f"{points_change} امتیاز به کاربر {user[2]} ({user_id}) اضافه شد.\n"
            f"امتیاز جدید: {user[5]}",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("بازگشت به پنل مدیریت", callback_data='admin_panel')]
            ])
        )
    except:
        update.message.reply_text("فرمت ورودی نادرست است. لطفا به فرمت گفته شده ارسال کنید.")
        return 'manage_points'
    
    return ConversationHandler.END

def handle_settings_menu(query, context):
    if query.from_user.id not in ADMINS:
        query.answer("شما دسترسی ندارید!", show_alert=True)
        return
    
    keyboard = [
        [
            InlineKeyboardButton(f"لایک فری فایر: {get_setting('like_free_fire_points')}", 
                                callback_data='setting_like_free_fire_points')
        ],
        [
            InlineKeyboardButton(f"اطلاعات اکانت: {get_setting('account_info_points')}", 
                                callback_data='setting_account_info_points')
        ],
        [
            InlineKeyboardButton(f"استیکر اکانت: {get_setting('account_sticker_points')}", 
                                callback_data='setting_account_sticker_points')
        ],
        [
            InlineKeyboardButton(f"استارز رایگان: {get_setting('free_stars_points')}", 
                                callback_data='setting_free_stars_points')
        ],
        [InlineKeyboardButton("بازگشت به پنل مدیریت", callback_data='admin_panel')]
    ]
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    query.edit_message_text(
        "⚙️ تنظیمات امتیازهای مورد نیاز برای هر بخش:",
        reply_markup=reply_markup
    )

def handle_setting_change(query, context):
    if query.from_user.id not in ADMINS:
        query.answer("شما دسترسی ندارید!", show_alert=True)
        return
    
    setting_name = query.data.replace('setting_', '')
    current_value = get_setting(setting_name)
    
    query.edit_message_text(
        f"لطفا مقدار جدید را برای {setting_name.replace('_', ' ')} (فعلی: {current_value}) ارسال کنید:"
    )
    
    context.user_data['editing_setting'] = setting_name
    return 'update_setting'

def update_setting_value(update: Update, context: CallbackContext):
    if update.message.from_user.id not in ADMINS:
        update.message.reply_text("شما دسترسی ندارید!")
        return ConversationHandler.END
    
    setting_name = context.user_data.get('editing_setting')
    new_value = update.message.text
    
    if not new_value.isdigit():
        update.message.reply_text("مقدار باید عددی باشد. لطفا دوباره تلاش کنید.")
        return 'update_setting'
    
    update_setting(setting_name, new_value)
    
    update.message.reply_text(
        f"تنظیمات با موفقیت به روز شد.\n\n{setting_name.replace('_', ' ')}: {new_value}",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("بازگشت به تنظیمات", callback_data='settings_menu')],
            [InlineKeyboardButton("بازگشت به پنل مدیریت", callback_data='admin_panel')]
        ])
    )
    
    return ConversationHandler.END

def show_main_menu_from_query(query, context):
    keyboard = [
        [InlineKeyboardButton("لایک فری فایر", callback_data='like_free_fire')],
        [InlineKeyboardButton("اطلاعات اکانت", callback_data='account_info')],
        [InlineKeyboardButton("استیکر اکانت", callback_data='account_sticker')],
        [InlineKeyboardButton("استارز رایگان", callback_data='free_stars')],
        [InlineKeyboardButton("امتیاز روزانه", callback_data='daily_points')],
        [InlineKeyboardButton("حساب کاربری", callback_data='user_account')],
        [InlineKeyboardButton("پشتیبانی", callback_data='support')]
    ]
    
    if query.from_user.id in ADMINS:
        keyboard.append([InlineKeyboardButton("پنل مدیریت", callback_data='admin_panel')])
    
    reply_markup = InlineKeyboardMarkup(keyboard)
    
    query.edit_message_text(
        "🏠 منوی اصلی:",
        reply_markup=reply_markup
    )

def cancel(update: Update, context: CallbackContext):
    update.message.reply_text('عملیات لغو شد.')
    return ConversationHandler.END

def error_handler(update: Update, context: CallbackContext):
    logger.error(msg="Exception while handling an update:", exc_info=context.error)
    
    try:
        update.message.reply_text('خطایی رخ داد. لطفا دوباره تلاش کنید.')
    except:
        pass

def main():
    updater = Updater(BOT_TOKEN)
    dispatcher = updater.dispatcher

    # دستورات
    dispatcher.add_handler(CommandHandler('start', start))
    
    # مدیریت گفتگوها
    conv_handler = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(button_handler, pattern='^like_free_fire$'),
            CallbackQueryHandler(button_handler, pattern='^account_info$'),
            CallbackQueryHandler(button_handler, pattern='^account_sticker$'),
            CallbackQueryHandler(button_handler, pattern='^free_stars$')
        ],
        states={
            INPUT_GAME_ID: [MessageHandler(Filters.text & ~Filters.command, input_game_id)],
            INPUT_CHANNEL_LINK: [MessageHandler(Filters.text & ~Filters.command, input_channel_link)],
            'ban_user': [MessageHandler(Filters.text & ~Filters.command, ban_user)],
            'manage_points': [MessageHandler(Filters.text & ~Filters.command, manage_points)],
            'update_setting': [MessageHandler(Filters.text & ~Filters.command, update_setting_value)]
        },
        fallbacks=[CommandHandler('cancel', cancel)],
    )
    
    dispatcher.add_handler(conv_handler)
    dispatcher.add_handler(CallbackQueryHandler(button_handler))
    
    # مدیریت خطاها
    dispatcher.add_error_handler(error_handler)
    
    # شروع ربات
    updater.start_polling()
    updater.idle()

if __name__ == '__main__':
    main()
