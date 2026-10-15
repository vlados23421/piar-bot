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

logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)

bot = telebot.TeleBot(BOT_TOKEN, threaded=True)
app = Flask(__name__)
app.logger.disabled = True
logging.getLogger('werkzeug').disabled = True


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


DB_PATH = "/tmp/users.db"


def get_db():
    return sqlite3.connect(DB_PATH, timeout=5)


def init_db():
    conn = get_db()
    c = conn.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY, username TEXT, first_name TEXT,
        joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, last_bonus TIMESTAMP, 
        ref_by INTEGER, ref_code TEXT)""")
    c.execute("""CREATE TABLE IF NOT EXISTS orders (
        id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, username TEXT,
        service TEXT, price INTEGER, status TEXT DEFAULT 'pending',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP, 
        reminder_sent INTEGER DEFAULT 0, review_sent INTEGER DEFAULT 0)""")
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
    c.execute("""SELECT user_id, username, first_name, joined_at, last_bonus, ref_by, ref_code 
                 FROM users WHERE user_id = ?""", (user_id,))
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
    c.execute("""SELECT id, user_id, username, service, price, status, created_at 
                 FROM orders ORDER BY id DESC LIMIT ?""", (limit,))
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


def post_to_channel(text, photo=None):
    try:
        if photo:
            bot.send_photo(CHANNEL_ID, photo, caption=text, parse_mode='HTML')
        else:
            bot.send_message(CHANNEL_ID, text, parse_mode='HTML')
        return True
    except Exception as e:
        logger.error(f"Ошибка публикации: {e}")
        return False


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
    """Напоминания клиентам + запрос отзывов."""
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

            c.execute("""SELECT id, user_id, service FROM orders 
                         WHERE status = 'done' AND review_sent = 0 
                         AND datetime(created_at) < datetime('now', '-1 day')""")
            rows = c.fetchall()
            for oid, uid, service in rows:
                try:
                    bot.send_message(uid,
                        f"⭐ <b>Как вам пиар?</b>\n\n"
                        f"Заказ №{oid} ({service}) выполнен.\n\n"
                        f"Оставьте отзыв: /review",
                        parse_mode='HTML')
                    c.execute("UPDATE orders SET review_sent = 1 WHERE id = ?", (oid,))
                except Exception:
                    pass

            conn.commit(); conn.close()
            time.sleep(1800)
        except Exception as e:
            logger.error(f"Напоминания: {e}")
            time.sleep(1800)


def auto_poster():
    time.sleep(21600)
    while True:
        try:
            if get_setting("autopost_enabled", "1") == "1":
                posts = [
                    "🔥 <b>ПИАР ЧАТ | SAMP • CRMP • MTA</b>\n\nЗакажи пиар своего проекта!\n\n📩 @MaleficentR7",
                    "💰 <b>АКЦИЯ</b>\n\nСкидка 10% на первый заказ!\n\n🎁 Промокод: START\n\n📩 @MaleficentR7",
                    "📢 <b>ПИАР ЧАТ</b>\n\nБыстро, качественно, недорого.\n\n📩 @MaleficentR7",
                ]
                post_to_channel(random.choice(posts))
            time.sleep(86400)
        except Exception as e:
            logger.error(f"Автопостер: {e}")
            time.sleep(86400)


def daily_report():
    """Ежедневный отчёт админу в 10:00 МСК."""
    while True:
        try:
            now = datetime.now()
            target = now.replace(hour=7, minute=0, second=0, microsecond=0)
            if now > target:
                target += timedelta(days=1)
            time.sleep((target - now).total_seconds())

            conn = get_db(); c = conn.cursor()
            c.execute("SELECT COUNT(*) FROM users")
            users_total = c.fetchone()[0]
            c.execute("SELECT COUNT(*) FROM users WHERE datetime(joined_at) > datetime('now', '-1 day')")
            users_new = c.fetchone()[0]
            c.execute("SELECT COUNT(*) FROM orders")
            orders_total = c.fetchone()[0]
            c.execute("SELECT COUNT(*) FROM orders WHERE datetime(created_at) > datetime('now', '-1 day')")
            orders_today = c.fetchone()[0]
            c.execute("SELECT COUNT(*) FROM orders WHERE status = 'pending'")
            orders_pending = c.fetchone()[0]
            c.execute("""SELECT COALESCE(SUM(price), 0) FROM orders 
                         WHERE status = 'done' AND datetime(created_at) > datetime('now', '-1 day')""")
            income_today = c.fetchone()[0]
            conn.close()

            bot.send_message(ADMIN_ID,
                f"📊 <b>ОТЧЁТ ЗА ДЕНЬ</b>\n\n━━━━━━━━━━━━━━━━━━━━\n\n"
                f"👥 Всего: <b>{users_total}</b>\n"
                f"🆕 Новых: <b>{users_new}</b>\n\n"
                f"📋 Заказов: <b>{orders_total}</b>\n"
                f"🆕 Сегодня: <b>{orders_today}</b>\n"
                f"⏳ В ожидании: <b>{orders_pending}</b>\n\n"
                f"💰 Доход: <b>{income_today}₽</b>",
                parse_mode='HTML')
        except Exception as e:
            logger.error(f"Отчёт: {e}")
            time.sleep(3600)


def start_scheduler():
    threading.Thread(target=scheduler, daemon=True).start()
    threading.Thread(target=reminder_scheduler, daemon=True).start()
    threading.Thread(target=auto_poster, daemon=True).start()
    threading.Thread(target=daily_report, daemon=True).start()
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
        "📜 <b>ПРАВИЛА</b>\n\n━━━━━━━━━━━━━━━━━━━━\n\n"
        "1️⃣ Уважение\n2️⃣ Без спама\n3️⃣ Без 18+\n4️⃣ Без сторонних ссылок\n5️⃣ Подчиняйся админам\n\n"
        "📩 @MaleficentR7"
    )


def article_faq():
    return get_text("faq",
        "❓ <b>FAQ</b>\n\n━━━━━━━━━━━━━━━━━━━━\n\n"
        "<b>Как заказать?</b>\n1. Напиши @MaleficentR7\n2. Выбери услугу\n3. Оплати\n4. Получи результат\n\n"
        "<b>Сколько ждать?</b>\nОт 1 до 24 часов.\n\n"
        "<b>Как оплатить?</b>\nЮMoney, карта, СБП.\n\n"
        "<b>Есть возврат?</b>\nДа, если услуга не выполнена.\n\n"
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
    text = "💰 <b>ПРАЙС</b>\n\n━━━━━━━━━━━━━━━━━━━━\n\n"
    for key, s in services.items():
        if s["enabled"]:
            text += f"{s['name']} — <b>{s['price']}₽</b>\n"
    text += "\n━━━━━━━━━━━━━━━━━━━━\n\n🎁 Есть промокод?\n\n📩 Заказать: /order"
    return text


def article_order():
    return "📩 <b>ЗАКАЗ ПИАРА</b>\n\n━━━━━━━━━━━━━━━━━━━━\n\nВыбери услугу ниже 👇"


# === КОМПАКТНЫЕ КЛАВИАТУРЫ ===

def main_menu(user_id):
    """Главное меню — компактно, по 2 кнопки в ряд."""
    m = telebot.types.InlineKeyboardMarkup(row_width=2)
    m.add(
        telebot.types.InlineKeyboardButton("📖 О проекте", callback_data="about"),
        telebot.types.InlineKeyboardButton("💰 Прайс", callback_data="price"),
    )
    m.add(
        telebot.types.InlineKeyboardButton("📩 Заказать", callback_data="order"),
        telebot.types.InlineKeyboardButton("👤 Кабинет", callback_data="my"),
    )
    m.add(
        telebot.types.InlineKeyboardButton("⭐ Отзывы", callback_data="reviews"),
        telebot.types.InlineKeyboardButton("📸 Портфолио", callback_data="portfolio"),
    )
    m.add(
        telebot.types.InlineKeyboardButton("🎁 Бонус", callback_data="daily_bonus"),
        telebot.types.InlineKeyboardButton("📅 Записаться", callback_data="book"),
    )
    m.add(
        telebot.types.InlineKeyboardButton("📢 Канал", url=CHANNEL_LINK),
        telebot.types.InlineKeyboardButton("📞 Контакты", callback_data="contact"),
    )
    m.add(telebot.types.InlineKeyboardButton("❓ FAQ", callback_data="faq"))
    if user_id == ADMIN_ID:
        m.add(telebot.types.InlineKeyboardButton("⚙️ Админ-панель", callback_data="admin_panel"))
    return m


def menu_after_article():
    """Меню под статьёй — компактно."""
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
    """Услуги — компактно, по 1 кнопке для длинных названий."""
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


def admin_menu():
    """Админ-панель — компактно, по 2 кнопки в ряд."""
    status = get_bot_status()
    status_text = "🔓 Открыт" if status == "open" else "🔒 Закрыт"
    schedule_enabled = get_setting("schedule_enabled", "0") == "1"
    schedule_text = "🟢 Вкл" if schedule_enabled else "🔴 Выкл"
    autopost_enabled = get_setting("autopost_enabled", "1") == "1"
    autopost_text = "🟢 Вкл" if autopost_enabled else "🔴 Выкл"

    m = telebot.types.InlineKeyboardMarkup(row_width=2)
    m.add(
        telebot.types.InlineKeyboardButton(f"📊 {status_text}", callback_data="admin_status"),
        telebot.types.InlineKeyboardButton(f"⏰ {schedule_text}", callback_data="admin_schedule"),
    )
    m.add(
        telebot.types.InlineKeyboardButton(f"📢 Автопост: {autopost_text}", callback_data="admin_autopost"),
    )
    m.add(
        telebot.types.InlineKeyboardButton("💰 Цены", callback_data="admin_prices"),
        telebot.types.InlineKeyboardButton("🛠 Услуги", callback_data="admin_services"),
    )
    m.add(
        telebot.types.InlineKeyboardButton("🎁 Промокоды", callback_data="admin_promos"),
        telebot.types.InlineKeyboardButton("🚫 Наказания", callback_data="admin_punishments"),
    )
    m.add(
        telebot.types.InlineKeyboardButton("📝 Тексты", callback_data="admin_texts"),
        telebot.types.InlineKeyboardButton("📸 Портфолио", callback_data="admin_portfolio"),
    )
    m.add(
        telebot.types.InlineKeyboardButton("💬 Сообщения", callback_data="admin_messages"),
        telebot.types.InlineKeyboardButton("📊 Статистика", callback_data="admin_stats"),
    )
    m.add(
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
        "/my — кабинет\n/reviews — отзывы\n/portfolio — портфолио\n"
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

    m = telebot.types.InlineKeyboardMarkup(row_width=2)
    m.add(
        telebot.types.InlineKeyboardButton("📩 Заказать", callback_data="order"),
        telebot.types.InlineKeyboardButton("🏆 Топ", callback_data="top"),
    )
    m.add(telebot.types.InlineKeyboardButton("⬅️ Назад", callback_data="back"))
    bot.send_message(chat_id, text, parse_mode='HTML', reply_markup=m)


@bot.message_handler(commands=['reviews'])
def reviews_command(message):
    show_reviews(message.chat.id)


def show_reviews(chat_id, edit=False, message_id=None):
    rows = get_reviews(10)
    text = "⭐ <b>ОТЗЫВЫ</b>\n\n━━━━━━━━━━━━━━━━━━━━\n\n"
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
        "📜 <b>ПРАВИЛА</b>\n\n━━━━━━━━━━━━━━━━━━━━\n\n"
        "1️⃣ Уважение\n2️⃣ Без спама\n3️⃣ Без 18+\n4️⃣ Без сторонних ссылок\n5️⃣ Подчиняйся админам\n\n"
        "📩 @MaleficentR7"
    )


def article_faq():
    return get_text("faq",
        "❓ <b>FAQ</b>\n\n━━━━━━━━━━━━━━━━━━━━\n\n"
        "<b>Как заказать?</b>\n1. Напиши @MaleficentR7\n2. Выбери услугу\n3. Оплати\n4. Получи результат\n\n"
        "<b>Сколько ждать?</b>\nОт 1 до 24 часов.\n\n"
        "<b>Как оплатить?</b>\nЮMoney, карта, СБП.\n\n"
        "<b>Есть возврат?</b>\nДа, если услуга не выполнена.\n\n"
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
    text = "💰 <b>ПРАЙС</b>\n\n━━━━━━━━━━━━━━━━━━━━\n\n"
    for key, s in services.items():
        if s["enabled"]:
            text += f"{s['name']} — <b>{s['price']}₽</b>\n"
    text += "\n━━━━━━━━━━━━━━━━━━━━\n\n🎁 Есть промокод?\n\n📩 Заказать: /order"
    return text


def article_order():
    return "📩 <b>ЗАКАЗ ПИАРА</b>\n\n━━━━━━━━━━━━━━━━━━━━\n\nВыбери услугу ниже 👇"


# === КОМПАКТНЫЕ КЛАВИАТУРЫ ===

def main_menu(user_id):
    """Главное меню — компактно, по 2 кнопки в ряд."""
    m = telebot.types.InlineKeyboardMarkup(row_width=2)
    m.add(
        telebot.types.InlineKeyboardButton("📖 О проекте", callback_data="about"),
        telebot.types.InlineKeyboardButton("💰 Прайс", callback_data="price"),
    )
    m.add(
        telebot.types.InlineKeyboardButton("📩 Заказать", callback_data="order"),
        telebot.types.InlineKeyboardButton("👤 Кабинет", callback_data="my"),
    )
    m.add(
        telebot.types.InlineKeyboardButton("⭐ Отзывы", callback_data="reviews"),
        telebot.types.InlineKeyboardButton("📸 Портфолио", callback_data="portfolio"),
    )
    m.add(
        telebot.types.InlineKeyboardButton("🎁 Бонус", callback_data="daily_bonus"),
        telebot.types.InlineKeyboardButton("📅 Записаться", callback_data="book"),
    )
    m.add(
        telebot.types.InlineKeyboardButton("📢 Канал", url=CHANNEL_LINK),
        telebot.types.InlineKeyboardButton("📞 Контакты", callback_data="contact"),
    )
    m.add(telebot.types.InlineKeyboardButton("❓ FAQ", callback_data="faq"))
    if user_id == ADMIN_ID:
        m.add(telebot.types.InlineKeyboardButton("⚙️ Админ-панель", callback_data="admin_panel"))
    return m


def menu_after_article():
    """Меню под статьёй — компактно."""
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
    """Услуги — компактно, по 1 кнопке для длинных названий."""
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


def admin_menu():
    """Админ-панель — компактно, по 2 кнопки в ряд."""
    status = get_bot_status()
    status_text = "🔓 Открыт" if status == "open" else "🔒 Закрыт"
    schedule_enabled = get_setting("schedule_enabled", "0") == "1"
    schedule_text = "🟢 Вкл" if schedule_enabled else "🔴 Выкл"
    autopost_enabled = get_setting("autopost_enabled", "1") == "1"
    autopost_text = "🟢 Вкл" if autopost_enabled else "🔴 Выкл"

    m = telebot.types.InlineKeyboardMarkup(row_width=2)
    m.add(
        telebot.types.InlineKeyboardButton(f"📊 {status_text}", callback_data="admin_status"),
        telebot.types.InlineKeyboardButton(f"⏰ {schedule_text}", callback_data="admin_schedule"),
    )
    m.add(
        telebot.types.InlineKeyboardButton(f"📢 Автопост: {autopost_text}", callback_data="admin_autopost"),
    )
    m.add(
        telebot.types.InlineKeyboardButton("💰 Цены", callback_data="admin_prices"),
        telebot.types.InlineKeyboardButton("🛠 Услуги", callback_data="admin_services"),
    )
    m.add(
        telebot.types.InlineKeyboardButton("🎁 Промокоды", callback_data="admin_promos"),
        telebot.types.InlineKeyboardButton("🚫 Наказания", callback_data="admin_punishments"),
    )
    m.add(
        telebot.types.InlineKeyboardButton("📝 Тексты", callback_data="admin_texts"),
        telebot.types.InlineKeyboardButton("📸 Портфолио", callback_data="admin_portfolio"),
    )
    m.add(
        telebot.types.InlineKeyboardButton("💬 Сообщения", callback_data="admin_messages"),
        telebot.types.InlineKeyboardButton("📊 Статистика", callback_data="admin_stats"),
    )
    m.add(
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
        "/my — кабинет\n/reviews — отзывы\n/portfolio — портфолио\n"
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

    m = telebot.types.InlineKeyboardMarkup(row_width=2)
    m.add(
        telebot.types.InlineKeyboardButton("📩 Заказать", callback_data="order"),
        telebot.types.InlineKeyboardButton("🏆 Топ", callback_data="top"),
    )
    m.add(telebot.types.InlineKeyboardButton("⬅️ Назад", callback_data="back"))
    bot.send_message(chat_id, text, parse_mode='HTML', reply_markup=m)


@bot.message_handler(commands=['reviews'])
def reviews_command(message):
    show_reviews(message.chat.id)


def show_reviews(chat_id, edit=False, message_id=None):
    rows = get_reviews(10)
    text = "⭐ <b>ОТЗЫВЫ</b>\n\n━━━━━━━━━━━━━━━━━━━━\n\n"
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
