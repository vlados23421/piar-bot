import logging
import sqlite3
import telebot
import threading
import time
import random
from datetime import datetime, timedelta
from flask import Flask, request

# === НАСТРОЙКИ ===
BOT_TOKEN = "8337839229:AAH7EuRNbQK2xn74o1WiDa-TxZHdDA795tg"
WEBHOOK_URL = "https://piar-bot-5zlx.onrender.com"
ADMIN_ID = 8718572838
CHANNEL_ID = -1004373056046
CHANNEL_LINK = "https://t.me/PiarSampCrmpQ"

# === ЛОГИ ===
logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)

bot = telebot.TeleBot(BOT_TOKEN, threaded=True)
app = Flask(__name__)
app.logger.disabled = True
logging.getLogger('werkzeug').disabled = True


# === ДЕКОРАТОР ===
def admin_only(func):
    def wrapper(message):
        if message.from_user.id != ADMIN_ID:
            msg = bot.reply_to(message, "⛔ <b>Отказано в доступе</b>", parse_mode='HTML')
            threading.Timer(5.0, lambda: delete_messages(message.chat.id, message.message_id, msg.message_id)).start()
            return
        return func(message)
    return wrapper


def delete_messages(chat_id, *message_ids):
    try:
        bot.delete_messages(chat_id, list(message_ids))
    except Exception:
        pass


# === БАЗА ===
DB_PATH = "/tmp/users.db"


def get_db():
    return sqlite3.connect(DB_PATH, timeout=5)


def init_db():
    conn = get_db()
    c = conn.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY, username TEXT, first_name TEXT,
        joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, last_bonus TIMESTAMP, ref_by INTEGER, ref_code TEXT)""")
    c.execute("""CREATE TABLE IF NOT EXISTS orders (
        id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, username TEXT,
        service TEXT, price INTEGER, status TEXT DEFAULT 'pending',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, reminder_sent INTEGER DEFAULT 0)""")
    c.execute("""CREATE TABLE IF NOT EXISTS settings (key TEXT PRIMARY KEY, value TEXT)""")
    c.execute("""CREATE TABLE IF NOT EXISTS services (
        key TEXT PRIMARY KEY, name TEXT, price INTEGER, enabled INTEGER DEFAULT 1)""")
    c.execute("""CREATE TABLE IF NOT EXISTS promos (
        code TEXT PRIMARY KEY, discount INTEGER, max_uses INTEGER, uses INTEGER DEFAULT 0,
        active INTEGER DEFAULT 1, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""")
    c.execute("""CREATE TABLE IF NOT EXISTS punishments (
        id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, username TEXT,
        type TEXT, reason TEXT, until TIMESTAMP, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
        active INTEGER DEFAULT 1)""")
    c.execute("""CREATE TABLE IF NOT EXISTS reviews (
        id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, username TEXT,
        text TEXT, rating INTEGER DEFAULT 5, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""")
    c.execute("""CREATE TABLE IF NOT EXISTS bookings (
        id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, username TEXT,
        date TEXT, time TEXT, service TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""")
    c.execute("""CREATE TABLE IF NOT EXISTS messages (
        id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, username TEXT,
        text TEXT, created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""")
    c.execute("""CREATE TABLE IF NOT EXISTS portfolio (
        id INTEGER PRIMARY KEY AUTOINCREMENT, title TEXT, url TEXT,
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""")
    c.execute("""CREATE TABLE IF NOT EXISTS bonuses (
        user_id INTEGER PRIMARY KEY, points INTEGER DEFAULT 0)""")
    default_services = [
        ("post_chat", "📢 Пост в чате", 20, 1),
        ("post_channel", "📺 Пост в канале", 100, 1),
        ("pin", "📌 Закреп на 24 часа", 150, 1),
        ("autopost", "🤖 Авторассылка", 200, 1),
        ("posts3", "🔥 3 поста подряд", 400, 1),
        ("package", "👑 Полный пакет", 500, 1),
        ("posts5", "💎 5 постов подряд", 600, 1),
    ]
    for key, name, price, enabled in default_services:
        c.execute("INSERT OR IGNORE INTO services VALUES (?, ?, ?, ?)", (key, name, price, enabled))
    default_settings = [
        ("schedule_enabled", "0"), ("schedule_open", "09:00"),
        ("schedule_close", "23:00"), ("schedule_days", "1,2,3,4,5,6,7"),
        ("bot_status", "open"), ("autopost_enabled", "1"),
    ]
    for key, value in default_settings:
        c.execute("INSERT OR IGNORE INTO settings VALUES (?, ?)", (key, value))
    conn.commit()
    conn.close()


def set_setting(key, value):
    conn = get_db(); c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO settings VALUES (?, ?)", (key, str(value)))
    conn.commit(); conn.close()


def get_setting(key, default=None):
    conn = get_db(); c = conn.cursor()
    c.execute("SELECT value FROM settings WHERE key = ?", (key,))
    row = c.fetchone(); conn.close()
    return row[0] if row else default


def get_services():
    conn = get_db(); c = conn.cursor()
    c.execute("SELECT key, name, price, enabled FROM services")
    rows = c.fetchall(); conn.close()
    return {r[0]: {"name": r[1], "price": r[2], "enabled": r[3]} for r in rows}


def update_service_price(key, price):
    conn = get_db(); c = conn.cursor()
    c.execute("UPDATE services SET price = ? WHERE key = ?", (price, key))
    conn.commit(); conn.close()


def toggle_service(key):
    conn = get_db(); c = conn.cursor()
    c.execute("UPDATE services SET enabled = 1 - enabled WHERE key = ?", (key,))
    conn.commit(); conn.close()


def add_user(user):
    try:
        conn = get_db(); c = conn.cursor()
        c.execute("""INSERT OR IGNORE INTO users (user_id, username, first_name, ref_code)
                     VALUES (?, ?, ?, ?)""",
                  (user.id, user.username or "", user.first_name or "", f"ref{user.id}"))
        conn.commit(); conn.close()
    except Exception as e:
        logger.error(f"Ошибка: {e}")


def get_user(user_id):
    conn = get_db(); c = conn.cursor()
    c.execute("SELECT user_id, username, first_name, joined_at, last_bonus, ref_by, ref_code FROM users WHERE user_id = ?",
              (user_id,))
    r = c.fetchone(); conn.close()
    return r


def get_all_users():
    conn = get_db(); c = conn.cursor()
    c.execute("SELECT user_id FROM users")
    users = [r[0] for r in c.fetchall()]; conn.close()
    return users


def get_users_count():
    conn = get_db(); c = conn.cursor()
    c.execute("SELECT COUNT(*) FROM users")
    n = c.fetchone()[0]; conn.close()
    return n


def create_order(user_id, username, service, price):
    conn = get_db(); c = conn.cursor()
    c.execute("INSERT INTO orders (user_id, username, service, price) VALUES (?, ?, ?, ?)",
              (user_id, username, service, price))
    oid = c.lastrowid; conn.commit(); conn.close()
    return oid


def get_orders(limit=20):
    conn = get_db(); c = conn.cursor()
    c.execute("SELECT id, user_id, username, service, price, status, created_at FROM orders ORDER BY id DESC LIMIT ?",
              (limit,))
    r = c.fetchall(); conn.close()
    return r


def get_user_orders(user_id, limit=10):
    conn = get_db(); c = conn.cursor()
    c.execute("""SELECT id, service, price, status, created_at FROM orders 
                 WHERE user_id = ? ORDER BY id DESC LIMIT ?""", (user_id, limit))
    r = c.fetchall(); conn.close()
    return r


def update_order_status(oid, status):
    conn = get_db(); c = conn.cursor()
    c.execute("UPDATE orders SET status = ? WHERE id = ?", (status, oid))
    conn.commit(); conn.close()


def get_order(oid):
    conn = get_db(); c = conn.cursor()
    c.execute("SELECT id, user_id, username, service, price, status FROM orders WHERE id = ?", (oid,))
    r = c.fetchone(); conn.close()
    return r


def create_promo(code, discount, max_uses):
    try:
        conn = get_db(); c = conn.cursor()
        c.execute("INSERT INTO promos (code, discount, max_uses) VALUES (?, ?, ?)",
                  (code.upper(), discount, max_uses))
        conn.commit(); conn.close()
        return True
    except sqlite3.IntegrityError:
        return False


def get_promos():
    conn = get_db(); c = conn.cursor()
    c.execute("SELECT code, discount, max_uses, uses, active FROM promos ORDER BY created_at DESC")
    r = c.fetchall(); conn.close()
    return r


def check_promo(code):
    conn = get_db(); c = conn.cursor()
    c.execute("SELECT discount, max_uses, uses, active FROM promos WHERE code = ?", (code.upper(),))
    r = c.fetchone(); conn.close()
    if not r:
        return None
    discount, max_uses, uses, active = r
    if not active or uses >= max_uses:
        return None
    return discount


def use_promo(code):
    conn = get_db(); c = conn.cursor()
    c.execute("UPDATE promos SET uses = uses + 1 WHERE code = ?", (code.upper(),))
    conn.commit(); conn.close()


def add_punishment(user_id, username, ptype, reason, until=None):
    conn = get_db(); c = conn.cursor()
    c.execute("INSERT INTO punishments (user_id, username, type, reason, until) VALUES (?, ?, ?, ?, ?)",
              (user_id, username, ptype, reason, until))
    conn.commit(); conn.close()


def get_active_punishment(user_id):
    conn = get_db(); c = conn.cursor()
    c.execute("""SELECT id, type, reason, until FROM punishments 
                 WHERE user_id = ? AND active = 1 ORDER BY id DESC LIMIT 1""", (user_id,))
    r = c.fetchone(); conn.close()
    if not r:
        return None
    pid, ptype, reason, until_str = r
    if until_str:
        try:
            until = datetime.strptime(until_str, "%Y-%m-%d %H:%M:%S")
            if datetime.now() > until:
                conn = get_db(); c = conn.cursor()
                c.execute("UPDATE punishments SET active = 0 WHERE id = ?", (pid,))
                conn.commit(); conn.close()
                return None
        except Exception:
            pass
    return {"id": pid, "type": ptype, "reason": reason, "until": until_str}


def remove_punishment(user_id, ptype=None):
    conn = get_db(); c = conn.cursor()
    if ptype:
        c.execute("UPDATE punishments SET active = 0 WHERE user_id = ? AND type = ?", (user_id, ptype))
    else:
        c.execute("UPDATE punishments SET active = 0 WHERE user_id = ?", (user_id,))
    conn.commit(); conn.close()


def get_all_punishments(limit=30):
    conn = get_db(); c = conn.cursor()
    c.execute("""SELECT id, user_id, username, type, reason, until, created_at, active 
                 FROM punishments ORDER BY id DESC LIMIT ?""", (limit,))
    r = c.fetchall(); conn.close()
    return r


def is_muted(user_id):
    p = get_active_punishment(user_id)
    return p and p["type"] == "mute"


def is_banned(user_id):
    p = get_active_punishment(user_id)
    return p and p["type"] in ("ban", "permban")


def parse_duration(duration):
    try:
        unit = duration[-1].lower()
        value = int(duration[:-1])
        if unit == 'm': delta = timedelta(minutes=value)
        elif unit == 'h': delta = timedelta(hours=value)
        elif unit == 'd': delta = timedelta(days=value)
        else: delta = timedelta(hours=1)
        return (datetime.now() + delta).strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        return (datetime.now() + timedelta(hours=1)).strftime("%Y-%m-%d %H:%M:%S")


def add_review(user_id, username, text, rating=5):
    conn = get_db(); c = conn.cursor()
    c.execute("INSERT INTO reviews (user_id, username, text, rating) VALUES (?, ?, ?, ?)",
              (user_id, username, text, rating))
    conn.commit(); conn.close()


def get_reviews(limit=10):
    conn = get_db(); c = conn.cursor()
    c.execute("SELECT user_id, username, text, rating, created_at FROM reviews ORDER BY id DESC LIMIT ?", (limit,))
    r = c.fetchall(); conn.close()
    return r


def add_booking(user_id, username, date, time_str, service):
    conn = get_db(); c = conn.cursor()
    c.execute("INSERT INTO bookings (user_id, username, date, time, service) VALUES (?, ?, ?, ?, ?)",
              (user_id, username, date, time_str, service))
    conn.commit(); conn.close()


def add_message(user_id, username, text):
    conn = get_db(); c = conn.cursor()
    c.execute("INSERT INTO messages (user_id, username, text) VALUES (?, ?, ?)",
              (user_id, username, text))
    conn.commit(); conn.close()


def add_portfolio(title, url):
    conn = get_db(); c = conn.cursor()
    c.execute("INSERT INTO portfolio (title, url) VALUES (?, ?)", (title, url))
    conn.commit(); conn.close()


def get_portfolio(limit=10):
    conn = get_db(); c = conn.cursor()
    c.execute("SELECT id, title, url FROM portfolio ORDER BY id DESC LIMIT ?", (limit,))
    r = c.fetchall(); conn.close()
    return r


def add_bonus_point(user_id, points=1):
    conn = get_db(); c = conn.cursor()
    c.execute("INSERT OR IGNORE INTO bonuses (user_id, points) VALUES (?, 0)", (user_id,))
    c.execute("UPDATE bonuses SET points = points + ? WHERE user_id = ?", (points, user_id))
    conn.commit(); conn.close()


def get_bonus_points(user_id):
    conn = get_db(); c = conn.cursor()
    c.execute("SELECT points FROM bonuses WHERE user_id = ?", (user_id,))
    r = c.fetchone(); conn.close()
    return r[0] if r else 0


def get_top_clients(limit=10):
    conn = get_db(); c = conn.cursor()
    c.execute("""SELECT u.user_id, u.username, u.first_name, COUNT(o.id) as cnt, SUM(o.price) as total
                 FROM users u LEFT JOIN orders o ON u.user_id = o.user_id
                 WHERE o.status = 'done'
                 GROUP BY u.user_id ORDER BY cnt DESC LIMIT ?""", (limit,))
    r = c.fetchall(); conn.close()
    return r


# === ПУБЛИКАЦИЯ В ТГК ===
def post_to_channel(text, photo=None):
    """Публикует пост в ТГК."""
    try:
        if photo:
            bot.send_photo(CHANNEL_ID, photo, caption=text, parse_mode='HTML')
        else:
            bot.send_message(CHANNEL_ID, text, parse_mode='HTML')
        return True
    except Exception as e:
        logger.error(f"Ошибка публикации: {e}")
        return False


# === ГРАФИК ===
def is_working_hours():
    if get_setting("schedule_enabled", "0") != "1":
        return True
    now = datetime.now()
    weekday = now.isoweekday()
    allowed_days = [int(d) for d in get_setting("schedule_days", "1,2,3,4,5,6,7").split(",")]
    if weekday not in allowed_days:
        return False
    try:
        open_time = datetime.strptime(get_setting("schedule_open", "09:00"), "%H:%M").time()
        close_time = datetime.strptime(get_setting("schedule_close", "23:00"), "%H:%M").time()
        current = now.time()
        if open_time <= close_time:
            return open_time <= current <= close_time
        else:
            return current >= open_time or current <= close_time
    except Exception:
        return True


def get_bot_status():
    if not is_working_hours():
        return "closed"
    return get_setting("bot_status", "open")


def set_bot_status(status):
    set_setting("bot_status", status)


def scheduler():
    last_status = None
    while True:
        try:
            if get_setting("schedule_enabled", "0") == "1":
                should_work = is_working_hours()
                current_status = "open" if should_work else "closed"
                if current_status != last_status:
                    set_setting("bot_status", current_status)
                    last_status = current_status
            time.sleep(60)
        except Exception:
            time.sleep(60)


def reminder_scheduler():
    while True:
        try:
            conn = get_db(); c = conn.cursor()
            c.execute("""SELECT id, user_id, service FROM orders 
                         WHERE status = 'pending' AND reminder_sent = 0 
                         AND datetime(created_at) < datetime('now', '-2 hours')""")
            rows = c.fetchall()
            for oid, uid, service in rows:
                try:
                    bot.send_message(uid,
                        f"⏰ <b>Напоминание</b>\n\n"
                        f"Заявка №{oid} ({service}) ждёт подтверждения.\n\n"
                        f"📩 @MaleficentR7",
                        parse_mode='HTML')
                    c.execute("UPDATE orders SET reminder_sent = 1 WHERE id = ?", (oid,))
                except Exception:
                    pass
            conn.commit(); conn.close()
            time.sleep(3600)
        except Exception:
            time.sleep(3600)


def auto_poster():
    """Автопостинг в ТГК раз в 24 часа."""
    # Ждём 6 часов перед первым постом, чтобы бот запустился
    time.sleep(21600)
    while True:
        try:
            if get_setting("autopost_enabled", "1") == "1":
                posts = [
                    "🔥 <b>ПИАР ЧАТ | SAMP • CRMP • MTA</b>\n\n"
                    "Закажи пиар своего проекта!\n\n"
                    "📢 Пост в чате — 20₽\n"
                    "📺 Пост в канале — 100₽\n"
                    "👑 Полный пакет — 500₽\n\n"
                    "📩 @MaleficentR7",

                    "💰 <b>АКЦИЯ!</b>\n\n"
                    "Скидка 10% на первый заказ!\n\n"
                    "🎁 Промокод: <b>START</b>\n\n"
                    "📩 @MaleficentR7",

                    "📢 <b>ПИАР ЧАТ</b>\n\n"
                    "Поможем продвинуть твой проект на SAMP, CRMP, MTA.\n\n"
                    "✅ Быстро\n✅ Качественно\n✅ Недорого\n\n"
                    "📩 @MaleficentR7",

                    "🎯 <b>УСЛУГИ ПИАР ЧАТА</b>\n\n"
                    "📢 Пост в чате — 20₽\n"
                    "📺 Пост в канале — 100₽\n"
                    "📌 Закреп — 150₽\n"
                    "🤖 Авторассылка — 200₽\n"
                    "👑 Полный пакет — 500₽\n\n"
                    "📩 @MaleficentR7",
                ]
                post_to_channel(random.choice(posts))
            time.sleep(86400)  # 24 часа
        except Exception as e:
            logger.error(f"Автопостер: {e}")
            time.sleep(86400)


def start_scheduler():
    threading.Thread(target=scheduler, daemon=True).start()
    threading.Thread(target=reminder_scheduler, daemon=True).start()
    threading.Thread(target=auto_poster, daemon=True).start()


# === ТЕКСТЫ ===
def get_text(key, default=""): return get_setting(f"text_{key}", default)
def set_text(key, value): set_setting(f"text_{key}", value)


def article_about():
    return get_text("about",
        "📖 <b>О ПРОЕКТЕ ПИАР ЧАТ</b>\n\n━━━━━━━━━━━━━━━━━━━━\n\n"
        "ПИАР ЧАТ — сервис продвижения проектов на SAMP, CRMP и MTA.\n\n"
        f"📢 Канал: {CHANNEL_LINK}\n"
        "📩 Админ: @MaleficentR7"
    )


def article_rules():
    return get_text("rules",
        "📜 <b>ПРАВИЛА ПИАР ЧАТА</b>\n\n━━━━━━━━━━━━━━━━━━━━\n\n"
        "1️⃣ Уважение\n2️⃣ Без спама\n3️⃣ Без 18+\n4️⃣ Без сторонних ссылок\n5️⃣ Подчиняйся админам\n\n"
        "📩 @MaleficentR7"
    )


def article_faq():
    return get_text("faq",
        "❓ <b>ЧАСТЫЕ ВОПРОСЫ</b>\n\n━━━━━━━━━━━━━━━━━━━━\n\n"
        "❓ <b>Как заказать?</b>\n1. Напиши @MaleficentR7\n2. Выбери услугу\n3. Оплати\n4. Получи результат\n\n"
        "❓ <b>Сколько ждать?</b>\nОт 1 до 24 часов.\n\n"
        "❓ <b>Как оплатить?</b>\nЮMoney, карта, СБП.\n\n"
        "❓ <b>Есть возврат?</b>\nДа, если услуга не выполнена.\n\n"
        "❓ <b>Что запрещено?</b>\n18+, скам, читы.\n\n"
        "📩 @MaleficentR7"
    )


def article_contact():
    return get_text("contact",
        "📞 <b>КОНТАКТЫ</b>\n\n━━━━━━━━━━━━━━━━━━━━\n\n"
        "🛡 <b>Админ:</b> @MaleficentR7\n"
        f"📢 <b>Канал:</b> {CHANNEL_LINK}\n"
        "💬 <b>Чат ВК:</b> vk.me/join/kuBhzS34RI7dc8140qevGBk11iBjwb8mcGk=\n\n"
        "📩 Пиши — ответим в течение 1-2 часов!"
    )


def article_price():
    services = get_services()
    text = "💰 <b>ПРАЙС НА ПИАР</b>\n\n━━━━━━━━━━━━━━━━━━━━\n\n"
    for key, s in services.items():
        if s["enabled"]:
            text += f"{s['name']} — <b>{s['price']}₽</b>\n"
    text += "\n━━━━━━━━━━━━━━━━━━━━\n\n🎁 Есть промокод?\n\n📩 Заказать: /order"
    return text


def article_order():
    return "📩 <b>ЗАКАЗ ПИАРА</b>\n\n━━━━━━━━━━━━━━━━━━━━\n\nВыбери услугу ниже 👇"


# === КЛАВИАТУРЫ ===
def menu_after_article():
    m = telebot.types.InlineKeyboardMarkup(row_width=2)
    m.add(
        telebot.types.InlineKeyboardButton("📖 О проекте", callback_data="about"),
        telebot.types.InlineKeyboardButton("📜 Правила", callback_data="rules"),
    )
    m.add(
        telebot.types.InlineKeyboardButton("💰 Прайс", callback_data="price"),
        telebot.types.InlineKeyboardButton("❓ FAQ", callback_data="faq"),
    )
    m.add(
        telebot.types.InlineKeyboardButton("📩 Заказать", callback_data="order"),
        telebot.types.InlineKeyboardButton("📞 Контакты", callback_data="contact"),
    )
    m.add(telebot.types.InlineKeyboardButton("🏠 Главная", callback_data="back"))
    return m


def services_menu():
    services = get_services()
    m = telebot.types.InlineKeyboardMarkup(row_width=1)
    for key, s in services.items():
        if s["enabled"]:
            m.add(telebot.types.InlineKeyboardButton(
                f"{s['name']} — {s['price']}₽",
                callback_data=f"buy_{key}"))
    m.add(telebot.types.InlineKeyboardButton("🎁 Ввести промокод", callback_data="enter_promo"))
    m.add(telebot.types.InlineKeyboardButton("⬅️ Назад", callback_data="back"))
    return m


def main_menu(user_id):
    m = telebot.types.InlineKeyboardMarkup(row_width=1)
    m.add(
        telebot.types.InlineKeyboardButton("📖 О проекте", callback_data="about"),
        telebot.types.InlineKeyboardButton("💰 Прайс", callback_data="price"),
        telebot.types.InlineKeyboardButton("📩 Заказать пиар", callback_data="order"),
        telebot.types.InlineKeyboardButton("👤 Личный кабинет", callback_data="my"),
        telebot.types.InlineKeyboardButton("⭐ Отзывы", callback_data="reviews"),
        telebot.types.InlineKeyboardButton("📸 Портфолио", callback_data="portfolio"),
        telebot.types.InlineKeyboardButton("🎁 Ежедневный бонус", callback_data="daily_bonus"),
        telebot.types.InlineKeyboardButton("📅 Записаться", callback_data="book"),
        telebot.types.InlineKeyboardButton("📢 Наш канал", url=CHANNEL_LINK),
        telebot.types.InlineKeyboardButton("📞 Контакты", callback_data="contact"),
    )
    if user_id == ADMIN_ID:
        m.add(telebot.types.InlineKeyboardButton("⚙️ Админ-панель", callback_data="admin_panel"))
    return m


def admin_menu():
    status = get_bot_status()
    status_text = "🔓 Открыт" if status == "open" else "🔒 Закрыт"
    schedule_enabled = get_setting("schedule_enabled", "0") == "1"
    schedule_text = "🟢 Вкл" if schedule_enabled else "🔴 Выкл"
    autopost_enabled = get_setting("autopost_enabled", "1") == "1"
    autopost_text = "🟢 Вкл" if autopost_enabled else "🔴 Выкл"
    m = telebot.types.InlineKeyboardMarkup(row_width=1)
    m.add(
        telebot.types.InlineKeyboardButton(f"📊 Статус: {status_text}", callback_data="admin_status"),
        telebot.types.InlineKeyboardButton(f"⏰ График: {schedule_text}", callback_data="admin_schedule"),
        telebot.types.InlineKeyboardButton(f"📢 Автопост: {autopost_text}", callback_data="admin_autopost"),
        telebot.types.InlineKeyboardButton("💰 Цены", callback_data="admin_prices"),
        telebot.types.InlineKeyboardButton("🛠 Услуги", callback_data="admin_services"),
        telebot.types.InlineKeyboardButton("🎁 Промокоды", callback_data="admin_promos"),
        telebot.types.InlineKeyboardButton("🚫 Наказания", callback_data="admin_punishments"),
        telebot.types.InlineKeyboardButton("📝 Тексты", callback_data="admin_texts"),
        telebot.types.InlineKeyboardButton("📸 Портфолио", callback_data="admin_portfolio"),
        telebot.types.InlineKeyboardButton("💬 Сообщения", callback_data="admin_messages"),
        telebot.types.InlineKeyboardButton("📊 Статистика", callback_data="admin_stats"),
        telebot.types.InlineKeyboardButton("📋 Заказы", callback_data="admin_orders"),
        telebot.types.InlineKeyboardButton("⬅️ Назад", callback_data="back"),
    )
    return m


# === КОМАНДЫ ===
@bot.message_handler(commands=['start'])
def start_command(message):
    args = message.text.split()
    if len(args) > 1 and args[1].startswith("ref"):
        try:
            ref_by = int(args[1].replace("ref", ""))
            if ref_by != message.from_user.id:
                conn = get_db(); c = conn.cursor()
                c.execute("UPDATE users SET ref_by = ? WHERE user_id = ? AND ref_by IS NULL",
                          (ref_by, message.from_user.id))
                conn.commit(); conn.close()
                add_bonus_point(ref_by, 5)
        except Exception:
            pass

    if message.from_user.id != ADMIN_ID:
        p = get_active_punishment(message.from_user.id)
        if p and p["type"] in ("ban", "permban"):
            until = p["until"] or "навсегда"
            bot.send_message(message.chat.id,
                f"🚫 <b>Вы забанены</b>\n\n{p['reason']}\n⏰ До: {until}\n\n📩 @MaleficentR7",
                parse_mode='HTML')
            return

    if get_bot_status() == "closed" and message.from_user.id != ADMIN_ID:
        if get_setting("schedule_enabled", "0") == "1":
            open_t = get_setting("schedule_open", "09:00")
            close_t = get_setting("schedule_close", "23:00")
            bot.send_message(message.chat.id,
                f"🔒 <b>Бот закрыт</b>\n\n⏰ {open_t} – {close_t}\n\n📩 @MaleficentR7",
                parse_mode='HTML')
        else:
            bot.send_message(message.chat.id, "🔒 <b>Бот закрыт</b>", parse_mode='HTML')
        return

    add_user(message.from_user)
    text = (
        "👋 <b>Добро пожаловать в ПИАР ЧАТ!</b>\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "📌 Заказать пиар твоего проекта.\n\n"
        "👇 <b>Выбери действие:</b>"
    )
    bot.send_message(message.chat.id, text, parse_mode='HTML', reply_markup=main_menu(message.from_user.id))


@bot.message_handler(commands=['help'])
def help_command(message):
    bot.send_message(message.chat.id,
        "🆘 <b>КОМАНДЫ</b>\n\n"
        "/start — меню\n/about — о проекте\n/price — прайс\n/order — заказать\n"
        "/my — личный кабинет\n/reviews — отзывы\n/portfolio — портфолио\n"
        "/book — записаться\n/chat — написать админу\n/bonus — бонус\n"
        "/rules — правила\n/faq — FAQ\n/contact — контакты",
        parse_mode='HTML')


@bot.message_handler(commands=['about'])
def about_command(message):
    bot.send_message(message.chat.id, article_about(), parse_mode='HTML', reply_markup=menu_after_article())


@bot.message_handler(commands=['rules'])
def rules_command(message):
    bot.send_message(message.chat.id, article_rules(), parse_mode='HTML', reply_markup=menu_after_article())


@bot.message_handler(commands=['price'])
def price_command(message):
    bot.send_message(message.chat.id, article_price(), parse_mode='HTML', reply_markup=menu_after_article())


@bot.message_handler(commands=['order'])
def order_command(message):
    if is_banned(message.from_user.id):
        bot.reply_to(message, "🚫 Вы забанены.")
        return
    bot.send_message(message.chat.id, article_order(), parse_mode='HTML', reply_markup=services_menu())


@bot.message_handler(commands=['faq'])
def faq_command(message):
    bot.send_message(message.chat.id, article_faq(), parse_mode='HTML', reply_markup=menu_after_article())


@bot.message_handler(commands=['contact'])
def contact_command(message):
    bot.send_message(message.chat.id, article_contact(), parse_mode='HTML', reply_markup=menu_after_article())


@bot.message_handler(commands=['my'])
def my_command(message):
    show_my(message.chat.id, message.from_user.id, message.from_user.first_name)


def show_my(chat_id, user_id, first_name):
    orders = get_user_orders(user_id, 5)
    points = get_bonus_points(user_id)
    user = get_user(user_id)
    ref_code = user[6] if user else f"ref{user_id}"

    text = (
        f"👤 <b>ЛИЧНЫЙ КАБИНЕТ</b>\n\n━━━━━━━━━━━━━━━━━━━━\n\n"
        f"👋 Привет, <b>{first_name}</b>!\n\n"
        f"🎁 Баллов: <b>{points}</b>\n"
        f"🔗 Рефералка:\n<code>https://t.me/{(bot.get_me()).username}?start={ref_code}</code>\n\n"
        f"━━━━━━━━━━━━━━━━━━━━\n\n📋 <b>ПОСЛЕДНИЕ ЗАКАЗЫ:</b>\n\n"
    )
    if not orders:
        text += "Пока нет заказов."
    else:
        for o in orders:
            oid, service, price, status, date = o
            em = "⏳" if status == "pending" else ("✅" if status == "confirmed" else "🎉")
            text += f"{em} №{oid} | {service}\n   {price}₽ | {date[:10]}\n\n"

    m = telebot.types.InlineKeyboardMarkup(row_width=1)
    m.add(
        telebot.types.InlineKeyboardButton("📩 Заказать", callback_data="order"),
        telebot.types.InlineKeyboardButton("🏆 Топ клиентов", callback_data="top"),
        telebot.types.InlineKeyboardButton("⬅️ Главная", callback_data="back"),
    )
    bot.send_message(chat_id, text, parse_mode='HTML', reply_markup=m)


@bot.message_handler(commands=['reviews'])
def reviews_command(message):
    show_reviews(message.chat.id)


def show_reviews(chat_id, edit=False, message_id=None):
    rows = get_reviews(10)
    text = "⭐ <b>ОТЗЫВЫ КЛИЕНТОВ</b>\n\n━━━━━━━━━━━━━━━━━━━━\n\n"
    if not rows:
        text += "Отзывов пока нет."
    else:
        for r in rows:
            uid, uname, txt, rating, date = r
            stars = "⭐" * rating
            text += f"{stars}\n<i>{txt}</i>\n— @{uname or uid}\n\n"

    m = telebot.types.InlineKeyboardMarkup(row_width=1)
    m.add(
        telebot.types.InlineKeyboardButton("✍️ Оставить отзыв", callback_data="add_review"),
        telebot.types.InlineKeyboardButton("⬅️ Назад", callback_data="back"),
    )
    if edit:
        bot.edit_message_text(text, chat_id, message_id, parse_mode='HTML', reply_markup=m)
    else:
        bot.send_message(chat_id, text, parse_mode='HTML', reply_markup=m)


@bot.message_handler(commands=['portfolio'])
def portfolio_command(message):
    show_portfolio(message.chat.id)


def show_portfolio(chat_id, edit=False, message_id=None):
    rows = get_portfolio(10)
    text = "📸 <b>ПОРТФОЛИО</b>\n\n━━━━━━━━━━━━━━━━━━━━\n\n"
    if not rows:
        text += "Скоро добавим примеры работ!"
    else:
        for r in rows:
            pid, title, url = r
            text += f"📌 <b>{title}</b>\n🔗 {url}\n\n"

    m = telebot.types.InlineKeyboardMarkup(row_width=1)
    m.add(telebot.types.InlineKeyboardButton("⬅️ Назад", callback_data="back"))
    if edit:
        bot.edit_message_text(text, chat_id, message_id, parse_mode='HTML', reply_markup=m)
    else:
        bot.send_message(chat_id, text, parse_mode='HTML', reply_markup=m)


@bot.message_handler(commands=['book'])
def book_command(message):
    bot.send_message(message.chat.id,
        "📅 <b>ЗАПИСЬ</b>\n\nОтправьте:\n<code>ДД.ММ.ГГГГ ЧЧ:ММ Услуга</code>\n\nПример:\n<code>15.10.2026 14:00 Пост в чате</code>",
        parse_mode='HTML')
    set_setting(f"waiting_booking_{message.from_user.id}", "yes")


@bot.message_handler(commands=['chat'])
def chat_command(message):
    bot.send_message(message.chat.id, "💬 Напишите сообщение — админ ответит.")
    set_setting(f"waiting_message_{message.from_user.id}", "yes")


@bot.message_handler(commands=['bonus'])
def bonus_command(message):
    give_daily_bonus(message.chat.id, message.from_user.id)


def give_daily_bonus(chat_id, user_id):
    user = get_user(user_id)
    if not user:
        return
    last_bonus = user[4]
    now = datetime.now()
    if last_bonus:
        try:
            last = datetime.strptime(last_bonus, "%Y-%m-%d %H:%M:%S")
            if (now - last).total_seconds() < 86400:
                left = 86400 - int((now - last).total_seconds())
                h, m = left // 3600, (left % 3600) // 60
                bot.send_message(chat_id, f"⏰ Бонус уже получен! Следующий через <b>{h}ч {m}мин</b>", parse_mode='HTML')
                return
        except Exception:
            pass
    add_bonus_point(user_id, 1)
    conn = get_db(); c = conn.cursor()
    c.execute("UPDATE users SET last_bonus = CURRENT_TIMESTAMP WHERE user_id = ?", (user_id,))
    conn.commit(); conn.close()
    points = get_bonus_points(user_id)
    bot.send_message(chat_id, f"🎁 <b>+1 балл!</b>\n\n💎 Всего: <b>{points}</b>", parse_mode='HTML')


@bot.message_handler(commands=['top'])
def top_command(message):
    show_top(message.chat.id)


def show_top(chat_id, edit=False, message_id=None):
    rows = get_top_clients(10)
    text = "🏆 <b>ТОП КЛИЕНТОВ</b>\n\n━━━━━━━━━━━━━━━━━━━━\n\n"
    if not rows:
        text += "Пока нет выполненных заказов."
    else:
        medals = ["🥇", "🥈", "🥉"]
        for i, r in enumerate(rows):
            uid, uname, fname, cnt, total = r
            medal = medals[i] if i < 3 else "🔸"
            text += f"{medal} <b>{fname or uname or uid}</b>\n   Заказов: {cnt} | {total or 0}₽\n\n"

    m = telebot.types.InlineKeyboardMarkup(row_width=1)
    m.add(telebot.types.InlineKeyboardButton("⬅️ Назад", callback_data="back"))
    if edit:
        bot.edit_message_text(text, chat_id, message_id, parse_mode='HTML', reply_markup=m)
    else:
        bot.send_message(chat_id, text, parse_mode='HTML', reply_markup=m)


# === ПОЛЬЗОВАТЕЛЬСКИЕ ОБРАБОТЧИКИ ===
@bot.message_handler(func=lambda m: m.from_user.id != ADMIN_ID and
                                   get_setting(f"waiting_promo_{m.from_user.id}") == "yes")
def handle_promo_apply(message):
    code = message.text.strip().upper()
    discount = check_promo(code)
    if discount:
        set_setting(f"promo_{message.from_user.id}", code)
        bot.reply_to(message, f"✅ Промокод <b>{code}</b> применён! Скидка <b>{discount}%</b>", parse_mode='HTML')
    else:
        bot.reply_to(message, f"❌ Промокод не найден.", parse_mode='HTML')
    set_setting(f"waiting_promo_{message.from_user.id}", "no")


@bot.message_handler(func=lambda m: m.from_user.id != ADMIN_ID and
                                   get_setting(f"waiting_review_{m.from_user.id}") == "yes")
def handle_review_input(message):
    add_review(message.from_user.id, message.from_user.username or message.from_user.first_name,
               message.text, 5)
    bot.reply_to(message, "⭐ Спасибо за отзыв!")
    set_setting(f"waiting_review_{message.from_user.id}", "no")


@bot.message_handler(func=lambda m: m.from_user.id != ADMIN_ID and
                                   get_setting(f"waiting_booking_{m.from_user.id}") == "yes")
def handle_booking(message):
    try:
        parts = message.text.split(maxsplit=2)
        add_booking(message.from_user.id, message.from_user.username or "",
                    parts[0], parts[1], parts[2] if len(parts) > 2 else "Не указано")
        bot.reply_to(message, "✅ Заявка на запись принята!")
        set_setting(f"waiting_booking_{message.from_user.id}", "no")
        try:
            bot.send_message(ADMIN_ID,
                f"📅 <b>ЗАПИСЬ</b>\n@{message.from_user.username or message.from_user.id}\n{message.text}",
                parse_mode='HTML')
        except Exception:
            pass
    except Exception:
        bot.reply_to(message, "❌ Формат: ДД.ММ.ГГГГ ЧЧ:ММ Услуга")


@bot.message_handler(func=lambda m: m.from_user.id != ADMIN_ID and
                                   get_setting(f"waiting_message_{m.from_user.id}") == "yes")
def handle_message_to_admin(message):
    add_message(message.from_user.id, message.from_user.username or "", message.text)
    bot.reply_to(message, "✅ Сообщение отправлено!")
    set_setting(f"waiting_message_{message.from_user.id}", "no")
    try:
        bot.send_message(ADMIN_ID,
            f"💬 <b>СООБЩЕНИЕ</b>\n@{message.from_user.username or message.from_user.id}\n🆔 <code>{message.from_user.id}</code>\n\n{message.text}",
            parse_mode='HTML')
    except Exception:
        pass


@bot.message_handler(func=lambda m: m.from_user.id == ADMIN_ID and
                                   get_setting(f"waiting_portfolio_{m.from_user.id}") == "yes")
def handle_portfolio_input(message):
    try:
        parts = message.text.split("|")
        add_portfolio(parts[0].strip(), parts[1].strip())
        bot.reply_to(message, "✅ Добавлено!")
    except Exception:
        bot.reply_to(message, "❌ Формат: Название | URL")
    set_setting(f"waiting_portfolio_{message.from_user.id}", "no")


# === АДМИН-КОМАНДЫ ===
@bot.message_handler(commands=['post'])
@admin_only
def post_command(message):
    text = message.text.replace('/post ', '', 1)
    if not text or text == '/post':
        bot.reply_to(message, "📝 /post [текст]")
        return
    if post_to_channel(text):
        bot.reply_to(message, "✅ Пост опубликован!")
    else:
        bot.reply_to(message, "❌ Ошибка. Бот админ канала?")


@bot.message_handler(content_types=['photo'])
def handle_photo(message):
    if message.from_user.id != ADMIN_ID:
        return
    if message.caption and message.caption.startswith('/post'):
        text = message.caption.replace('/post ', '', 1)
        photo_id = message.photo[-1].file_id
        if post_to_channel(text, photo_id):
            bot.reply_to(message, "✅ Пост с фото в ТГК!")
        else:
            bot.reply_to(message, "❌ Ошибка.")


@bot.message_handler(commands=['stats'])
@admin_only
def stats_command(message):
    count = get_users_count()
    bot.reply_to(message, f"📊 Пользователей: <b>{count}</b>", parse_mode='HTML')


@bot.message_handler(commands=['close'])
@admin_only
def close_command(message):
    set_bot_status("closed")
    bot.reply_to(message, "🔒 Бот закрыт.")


@bot.message_handler(commands=['open'])
@admin_only
def open_command(message):
    set_bot_status("open")
    bot.reply_to(message, "🔓 Бот открыт.")


@bot.message_handler(commands=['broadcast'])
@admin_only
def broadcast_command(message):
    text = message.text.replace('/broadcast ', '', 1)
    if not text or text == '/broadcast':
        bot.reply_to(message, "📝 /broadcast [текст]")
        return
    users = get_all_users()
    success = 0
    for uid in users:
        try:
            bot.send_message(uid, text, parse_mode='HTML')
            success += 1
        except Exception:
            pass
    bot.reply_to(message, f"📢 Отправлено: {success}")


@bot.message_handler(commands=['mute'])
@admin_only
def mute_command(message):
    try:
        parts = message.text.split(maxsplit=3)
        user_id = int(parts[1])
        until = parse_duration(parts[2])
        reason = parts[3] if len(parts) > 3 else "Без причины"
        add_punishment(user_id, "", "mute", reason, until)
        bot.reply_to(message, f"🔇 <code>{user_id}</code> замучен до {until}", parse_mode='HTML')
    except Exception:
        bot.reply_to(message, "📝 /mute [ID] [время] [причина]")


@bot.message_handler(commands=['ban'])
@admin_only
def ban_command(message):
    try:
        parts = message.text.split(maxsplit=3)
        user_id = int(parts[1])
        until = parse_duration(parts[2])
        reason = parts[3] if len(parts) > 3 else "Без причины"
        add_punishment(user_id, "", "ban", reason, until)
        bot.reply_to(message, f"🚫 <code>{user_id}</code> забанен до {until}", parse_mode='HTML')
    except Exception:
        bot.reply_to(message, "📝 /ban [ID] [время] [причина]")


@bot.message_handler(commands=['permban'])
@admin_only
def permban_command(message):
    try:
        parts = message.text.split(maxsplit=2)
        user_id = int(parts[1])
        reason = parts[2] if len(parts) > 2 else "Без причины"
        add_punishment(user_id, "", "permban", reason, None)
        bot.reply_to(message, f"⛔ <code>{user_id}</code> перм. бан", parse_mode='HTML')
    except Exception:
        bot.reply_to(message, "📝 /permban [ID] [причина]")


@bot.message_handler(commands=['unban'])
@admin_only
def unban_command(message):
    try:
        user_id = int(message.text.split()[1])
        remove_punishment(user_id)
        bot.reply_to(message, f"✅ <code>{user_id}</code> разбанен", parse_mode='HTML')
    except Exception:
        bot.reply_to(message, "📝 /unban [ID]")


@bot.message_handler(commands=['check'])
@admin_only
def check_command(message):
    try:
        user_id = int(message.text.split()[1])
        p = get_active_punishment(user_id)
        if not p:
            bot.reply_to(message, f"✅ <code>{user_id}</code> чист.", parse_mode='HTML')
        else:
            bot.reply_to(message, f"⚠️ {p['type']}\n📝 {p['reason']}\n⏰ {p['until'] or 'навсегда'}", parse_mode='HTML')
    except Exception:
        bot.reply_to(message, "📝 /check [ID]")


@bot.message_handler(commands=['confirm'])
@admin_only
def confirm_command(message):
    try:
        oid = int(message.text.split()[1])
        order = get_order(oid)
        if order:
            update_order_status(oid, "confirmed")
            bot.reply_to(message, f"✅ Заказ №{oid} подтверждён.")
            try:
                bot.send_message(order[1], f"✅ <b>Заказ №{oid} подтверждён!</b>", parse_mode='HTML')
            except Exception:
                pass
    except Exception:
        bot.reply_to(message, "📝 /confirm [id]")


@bot.message_handler(commands=['done'])
@admin_only
def done_command(message):
    try:
        oid = int(message.text.split()[1])
        order = get_order(oid)
        if order:
            update_order_status(oid, "done")
            bot.reply_to(message, f"🎉 Заказ №{oid} выполнен.")
            try:
                bot.send_message(order[1], f"🎉 <b>Заказ №{oid} выполнен!</b>", parse_mode='HTML')
            except Exception:
                pass
    except Exception:
        bot.reply_to(message, "📝 /done [id]")


# === РЕДАКТИРОВАНИЕ ===
@bot.message_handler(func=lambda m: m.from_user.id == ADMIN_ID and m.reply_to_message and
                                   m.reply_to_message.text and "Введите новую цену" in m.reply_to_message.text)
def handle_price_input(message):
    try:
        price = int(message.text.strip())
        for line in message.reply_to_message.text.split("\n"):
            if line.startswith("KEY:"):
                update_service_price(line.replace("KEY:", "").strip(), price)
                bot.reply_to(message, f"✅ Цена: <b>{price}₽</b>", parse_mode='HTML')
                return
    except Exception:
        bot.reply_to(message, "❌ Введите число.")


@bot.message_handler(func=lambda m: m.from_user.id == ADMIN_ID and m.reply_to_message and
                                   m.reply_to_message.text and "Введите новый текст" in m.reply_to_message.text)
def handle_text_input(message):
    for line in message.reply_to_message.text.split("\n"):
        if line.startswith("KEY:"):
            set_text(line.replace("KEY:", "").strip(), message.text)
            bot.reply_to(message, "✅ Обновлено.")
            return


@bot.message_handler(func=lambda m: m.from_user.id == ADMIN_ID and m.reply_to_message and
                                   m.reply_to_message.text and "Введите промокод" in m.reply_to_message.text)
def handle_promo_input(message):
    try:
        parts = message.text.split()
        code, discount, max_uses = parts[0], int(parts[1]), int(parts[2])
        if create_promo(code, discount, max_uses):
            bot.reply_to(message, f"✅ Промокод <b>{code.upper()}</b> создан!", parse_mode='HTML')
        else:
            bot.reply_to(message, "❌ Уже существует.")
    except Exception:
        bot.reply_to(message, "❌ Формат: КОД СКИДКА ЛИМИТ")


@bot.message_handler(func=lambda m: m.from_user.id == ADMIN_ID and m.reply_to_message and
                                   m.reply_to_message.text and "Введите график" in m.reply_to_message.text)
def handle_schedule_input(message):
    try:
        parts = message.text.strip().split()
        set_setting("schedule_open", parts[0])
        set_setting("schedule_close", parts[1])
        set_setting("schedule_days", parts[2] if len(parts) > 2 else "1,2,3,4,5,6,7")
        set_setting("schedule_enabled", "1")
        bot.reply_to(message, f"✅ График: {parts[0]} – {parts[1]}")
    except Exception:
        bot.reply_to(message, "❌ Формат: 09:00 23:00 1,2,3,4,5")


# === CALLBACK ===
@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    try:
        bot.answer_callback_query(call.id)

        if call.data.startswith("admin_") and call.from_user.id != ADMIN_ID:
            bot.answer_callback_query(call.id, "⛔ Отказано в доступе", show_alert=True)
            return

        if call.from_user.id != ADMIN_ID:
            if is_banned(call.from_user.id):
                bot.answer_callback_query(call.id, "🚫 Вы забанены.", show_alert=True)
                return
            if is_muted(call.from_user.id):
                bot.answer_callback_query(call.id, "🔇 Вы замучены.", show_alert=True)
                return

        if get_bot_status() == "closed" and call.from_user.id != ADMIN_ID:
            bot.answer_callback_query(call.id, "🔒 Бот закрыт.", show_alert=True)
            return

        if call.data == "about":
            bot.edit_message_text(article_about(), call.message.chat.id, call.message.message_id,
                                  parse_mode='HTML', reply_markup=menu_after_article())
        elif call.data == "rules":
            bot.edit_message_text(article_rules(), call.message.chat.id, call.message.message_id,
                                  parse_mode='HTML', reply_markup=menu_after_article())
        elif call.data == "price":
            bot.edit_message_text(article_price(), call.message.chat.id, call.message.message_id,
                                  parse_mode='HTML', reply_markup=menu_after_article())
        elif call.data == "order":
            bot.edit_message_text(article_order(), call.message.chat.id, call.message.message_id,
                                  parse_mode='HTML', reply_markup=services_menu())
        elif call.data == "faq":
            bot.edit_message_text(article_faq(), call.message.chat.id, call.message.message_id,
                                  parse_mode='HTML', reply_markup=menu_after_article())
        elif call.data == "contact":
            bot.edit_message_text(article_contact(), call.message.chat.id, call.message.message_id,
                                  parse_mode='HTML', reply_markup=menu_after_article())
        elif call.data == "back":
            text = "👋 <b>ПИАР ЧАТ</b>\n\n👇 Выбери действие:"
            bot.edit_message_text(text, call.message.chat.id, call.message.message_id,
                                  parse_mode='HTML', reply_markup=main_menu(call.from_user.id))
        elif call.data == "my":
            show_my(call.message.chat.id, call.from_user.id, call.from_user.first_name)
        elif call.data == "reviews":
            show_reviews(call.message.chat.id, edit=True, message_id=call.message.message_id)
        elif call.data == "portfolio":
            show_portfolio(call.message.chat.id, edit=True, message_id=call.message.message_id)
        elif call.data == "top":
            show_top(call.message.chat.id, edit=True, message_id=call.message.message_id)
        elif call.data == "daily_bonus":
            give_daily_bonus(call.message.chat.id, call.from_user.id)
        elif call.data == "book":
            bot.send_message(call.message.chat.id, "📅 Отправьте: <code>15.10.2026 14:00 Пост в чате</code>", parse_mode='HTML')
            set_setting(f"waiting_booking_{call.from_user.id}", "yes")
        elif call.data == "add_review":
            bot.send_message(call.message.chat.id, "✍️ Напишите отзыв:")
            set_setting(f"waiting_review_{call.from_user.id}", "yes")
        elif call.data == "enter_promo":
            bot.send_message(call.message.chat.id, "🎁 Введите промокод:")
            set_setting(f"waiting_promo_{call.from_user.id}", "yes")
        elif call.data.startswith("buy_"):
            key = call.data.replace("buy_", "")
            services = get_services()
            service = services.get(key)
            if not service:
                return
            promo_code = get_setting(f"promo_{call.from_user.id}")
            price = service["price"]
            promo_text = ""
            if promo_code:
                discount = check_promo(promo_code)
                if discount:
                    price = int(price * (100 - discount) / 100)
                    promo_text = f"\n🎁 Промокод: {promo_code} (-{discount}%)"
                    use_promo(promo_code)
                    set_setting(f"promo_{call.from_user.id}", "")
            order_id = create_order(call.from_user.id,
                                    call.from_user.username or call.from_user.first_name,
                                    service["name"], price)
            text = (
                f"📩 <b>ЗАЯВКА №{order_id}</b>\n\n━━━━━━━━━━━━━━━━━━━━\n\n"
                f"🛠 {service['name']}\n💰 <b>{price}₽</b>{promo_text}\n\n"
                f"📋 Напиши @MaleficentR7 с №{order_id}"
            )
            m = telebot.types.InlineKeyboardMarkup(row_width=1)
            m.add(
                telebot.types.InlineKeyboardButton("📩 Написать", url="https://t.me/MaleficentR7"),
                telebot.types.InlineKeyboardButton("⬅️ Назад", callback_data="order"),
            )
            bot.edit_message_text(text, call.message.chat.id, call.message.message_id,
                                  parse_mode='HTML', reply_markup=m)
            try:
                bot.send_message(ADMIN_ID,
                    f"🆕 <b>ЗАЯВКА №{order_id}</b>\n@{call.from_user.username or 'без ника'}\n{service['name']}\n{price}₽\n\n/confirm {order_id}",
                    parse_mode='HTML')
            except Exception:
                pass

        # АДМИН-ПАНЕЛЬ
        elif call.data == "admin_panel":
            bot.edit_message_text("⚙️ <b>АДМИН-ПАНЕЛЬ</b>", call.message.chat.id, call.message.message_id,
                                  parse_mode='HTML', reply_markup=admin_menu())
        elif call.data == "admin_status":
            status = get_bot_status()
            text = f"🔓 Открыт" if status == "open" else f"🔒 Закрыт"
            bot.edit_message_text(text, call.message.chat.id, call.message.message_id,
                                  parse_mode='HTML', reply_markup=admin_menu())
        elif call.data == "admin_schedule":
            enabled = get_setting("schedule_enabled", "0") == "1"
            open_t = get_setting("schedule_open", "09:00")
            close_t = get_setting("schedule_close", "23:00")
            days = get_setting("schedule_days", "1,2,3,4,5,6,7")
            status = "🟢 Вкл" if enabled else "🔴 Выкл"
            text = f"⏰ <b>ГРАФИК</b>\n\nСтатус: {status}\nОткрытие: <b>{open_t}</b>\nЗакрытие: <b>{close_t}</b>\nДни: {days}\n\nФормат: <code>09:00 23:00 1,2,3,4,5</code>"
            m = telebot.types.InlineKeyboardMarkup(row_width=1)
            m.add(
                telebot.types.InlineKeyboardButton("✏️ Изменить", callback_data="edit_schedule"),
                telebot.types.InlineKeyboardButton("🔴 Выключить", callback_data="disable_schedule"),
                telebot.types.InlineKeyboardButton("⬅️ Назад", callback_data="admin_panel"),
            )
            bot.edit_message_text(text, call.message.chat.id, call.message.message_id,
                                  parse_mode='HTML', reply_markup=m)
        elif call.data == "edit_schedule":
            bot.edit_message_text(
                "⏰ Введите график:\n<code>09:00 23:00 1,2,3,4,5</code>",
                call.message.chat.id, call.message.message_id, parse_mode='HTML')
        elif call.data == "disable_schedule":
            set_setting("schedule_enabled", "0")
            bot.edit_message_text("🔴 Выключено.", call.message.chat.id, call.message.message_id,
                                  parse_mode='HTML', reply_markup=admin_menu())
        elif call.data == "admin_autopost":
            enabled = get_setting("autopost_enabled", "1") == "1"
            new = "0" if enabled else "1"
            set_setting("autopost_enabled", new)
            status = "🟢 Включён" if new == "1" else "🔴 Выключен"
            bot.edit_message_text(f"📢 Автопост: {status}", call.message.chat.id, call.message.message_id,
                                  parse_mode='HTML', reply_markup=admin_menu())
        elif call.data == "admin_prices":
            services = get_services()
            m = telebot.types.InlineKeyboardMarkup(row_width=1)
            for key, s in services.items():
                m.add(telebot.types.InlineKeyboardButton(f"{s['name']} — {s['price']}₽", callback_data=f"editprice_{key}"))
            m.add(telebot.types.InlineKeyboardButton("⬅️ Назад", callback_data="admin_panel"))
            bot.edit_message_text("💰 <b>ЦЕНЫ</b>", call.message.chat.id, call.message.message_id,
                                  parse_mode='HTML', reply_markup=m)
        elif call.data.startswith("editprice_"):
            key = call.data.replace("editprice_", "")
            s = get_services().get(key)
            if s:
                bot.edit_message_text(
                    f"💰 <b>{s['name']}</b>\nТекущая: <b>{s['price']}₽</b>\n\n📝 Введите новую цену:\nKEY:{key}",
                    call.message.chat.id, call.message.message_id, parse_mode='HTML')
        elif call.data == "admin_services":
            services = get_services()
            m = telebot.types.InlineKeyboardMarkup(row_width=1)
            for key, s in services.items():
                st = "✅" if s["enabled"] else "❌"
                m.add(telebot.types.InlineKeyboardButton(f"{st} {s['name']}", callback_data=f"toggle_{key}"))
            m.add(telebot.types.InlineKeyboardButton("⬅️ Назад", callback_data="admin_panel"))
            bot.edit_message_text("🛠 <b>УСЛУГИ</b>", call.message.chat.id, call.message.message_id,
                                  parse_mode='HTML', reply_markup=m)
        elif call.data.startswith("toggle_"):
            toggle_service(call.data.replace("toggle_", ""))
            services = get_services()
            m = telebot.types.InlineKeyboardMarkup(row_width=1)
            for k, s in services.items():
                st = "✅" if s["enabled"] else "❌"
                m.add(telebot.types.InlineKeyboardButton(f"{st} {s['name']}", callback_data=f"toggle_{k}"))
            m.add(telebot.types.InlineKeyboardButton("⬅️ Назад", callback_data="admin_panel"))
            bot.edit_message_text("🛠 <b>УСЛУГИ</b>", call.message.chat.id, call.message.message_id,
                                  parse_mode='HTML', reply_markup=m)
        elif call.data == "admin_promos":
            promos = get_promos()
            text = "🎁 <b>ПРОМОКОДЫ</b>\n\n"
            if promos:
                for p in promos:
                    text += f"{'✅' if p[4] else '❌'} <b>{p[0]}</b> — {p[1]}% ({p[3]}/{p[2]})\n"
            else:
                text += "Пусто."
            m = telebot.types.InlineKeyboardMarkup(row_width=1)
            m.add(telebot.types.InlineKeyboardButton("➕ Создать", callback_data="create_promo"))
            m.add(telebot.types.InlineKeyboardButton("⬅️ Назад", callback_data="admin_panel"))
            bot.edit_message_text(text, call.message.chat.id, call.message.message_id,
                                  parse_mode='HTML', reply_markup=m)
        elif call.data == "create_promo":
            bot.edit_message_text(
                "🎁 Введите промокод:\n\n<code>КОД СКИДКА ЛИМИТ</code>\n\nПример: <code>START 10 100</code>",
                call.message.chat.id, call.message.message_id, parse_mode='HTML')
        elif call.data == "admin_texts":
            m = telebot.types.InlineKeyboardMarkup(row_width=1)
            m.add(
                telebot.types.InlineKeyboardButton("📖 О проекте", callback_data="edittext_about"),
                telebot.types.InlineKeyboardButton("📜 Правила", callback_data="edittext_rules"),
                telebot.types.InlineKeyboardButton("❓ FAQ", callback_data="edittext_faq"),
                telebot.types.InlineKeyboardButton("📞 Контакты", callback_data="edittext_contact"),
                telebot.types.InlineKeyboardButton("⬅️ Назад", callback_data="admin_panel"),
            )
            bot.edit_message_text("📝 <b>ТЕКСТЫ</b>", call.message.chat.id, call.message.message_id,
                                  parse_mode='HTML', reply_markup=m)
        elif call.data.startswith("edittext_"):
            key = call.data.replace("edittext_", "")
            current = get_text(key, "(пусто)")
            bot.edit_message_text(
                f"📝 <b>{key}</b>\n\n{current[:300]}...\n\n📩 Введите новый текст:\nKEY:{key}",
                call.message.chat.id, call.message.message_id, parse_mode='HTML')
        elif call.data == "admin_portfolio":
            rows = get_portfolio(10)
            text = "📸 <b>ПОРТФОЛИО</b>\n\n"
            for r in rows:
                text += f"#{r[0]} — {r[1]}\n{r[2]}\n\n"
            m = telebot.types.InlineKeyboardMarkup(row_width=1)
            m.add(telebot.types.InlineKeyboardButton("➕ Добавить", callback_data="add_portfolio"))
            m.add(telebot.types.InlineKeyboardButton("⬅️ Назад", callback_data="admin_panel"))
            bot.edit_message_text(text or "📸 Пусто.", call.message.chat.id, call.message.message_id,
                                  parse_mode='HTML', reply_markup=m)
        elif call.data == "add_portfolio":
            bot.send_message(call.message.chat.id, "📸 Формат:\n\n<code>Название | https://ссылка</code>", parse_mode='HTML')
            set_setting(f"waiting_portfolio_{call.from_user.id}", "yes")
        elif call.data == "admin_messages":
            conn = get_db(); c = conn.cursor()
            c.execute("SELECT user_id, username, text, created_at FROM messages ORDER BY id DESC LIMIT 10")
            rows = c.fetchall(); conn.close()
            text = "💬 <b>СООБЩЕНИЯ</b>\n\n"
            for r in rows:
                text += f"@{r[1] or r[0]}\n{r[2]}\n\n"
            m = telebot.types.InlineKeyboardMarkup(row_width=1)
            m.add(telebot.types.InlineKeyboardButton("⬅️ Назад", callback_data="admin_panel"))
            bot.edit_message_text(text or "💬 Пусто.", call.message.chat.id, call.message.message_id,
                                  parse_mode='HTML', reply_markup=m)
        elif call.data == "admin_stats":
            count = get_users_count()
            orders = get_orders(1000)
            done = sum(1 for o in orders if o[5] == "done")
            income = sum(o[4] for o in orders if o[5] == "done")
            text = (
                f"📊 <b>СТАТИСТИКА</b>\n\n"
                f"👥 Пользователей: <b>{count}</b>\n"
                f"📋 Заказов: <b>{len(orders)}</b>\n"
                f"✅ Выполнено: <b>{done}</b>\n"
                f"💰 Доход: <b>{income}₽</b>"
            )
            bot.edit_message_text(text, call.message.chat.id, call.message.message_id,
                                  parse_mode='HTML', reply_markup=admin_menu())
        elif call.data == "admin_orders":
            orders = get_orders(10)
            text = "📋 <b>ЗАКАЗЫ</b>\n\n" if orders else "📋 Заказов нет."
            for o in orders:
                oid, uid, uname, service, price, status, date = o
                em = "⏳" if status == "pending" else ("✅" if status == "confirmed" else "🎉")
                text += f"{em} №{oid} | {service} | {price}₽\n\n"
            bot.edit_message_text(text, call.message.chat.id, call.message.message_id,
                                  parse_mode='HTML', reply_markup=admin_menu())
    except Exception as e:
        logger.error(f"Ошибка callback: {e}")


# === ОБЩИЙ ОБРАБОТЧИК ===
@bot.message_handler(func=lambda message: True)
def echo_handler(message):
    if message.reply_to_message:
        return
    if message.text and not message.text.startswith('/'):
        bot.reply_to(message, "🤔 /help")


# === ВЕБХУК ===
@app.route('/' + BOT_TOKEN, methods=['POST'])
def get_message():
    try:
        json_string = request.get_data().decode('utf-8')
        update = telebot.types.Update.de_json(json_string)
        bot.process_new_updates([update])
        return "OK", 200
    except Exception as e:
        logger.error(f"Ошибка: {e}")
        return "Error", 500


@app.route("/")
def webhook():
    try:
        bot.remove_webhook()
        result = bot.set_webhook(
            url=WEBHOOK_URL + "/" + BOT_TOKEN,
            allowed_updates=["message", "callback_query", "edited_message", "channel_post"])
        return "OK", 200 if result else 500
    except Exception as e:
        return f"Ошибка: {e}", 500


@app.route("/health")
def health():
    return "Bot is alive!", 200


# === ЗАПУСК ===
if __name__ == "__main__":
    import os
    init_db()
    start_scheduler()
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, threaded=True)
