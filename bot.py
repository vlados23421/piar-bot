import logging
import sqlite3
import telebot
import threading
import time
from datetime import datetime, timedelta
from flask import Flask, request

# === НАСТРОЙКИ ===
BOT_TOKEN = "8337839229:AAH7EuRNbQK2xn74o1WiDa-TxZHdDA795tg"
WEBHOOK_URL = "https://piar-bot-5zlx.onrender.com"
ADMIN_ID = 8718572838

# === ЛОГИ ===
logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)

bot = telebot.TeleBot(BOT_TOKEN, threaded=True)
app = Flask(__name__)
app.logger.disabled = True
logging.getLogger('werkzeug').disabled = True

# === БАЗА ===
DB_PATH = "/tmp/users.db"


def get_db():
    return sqlite3.connect(DB_PATH, timeout=5)


def init_db():
    conn = get_db()
    c = conn.cursor()
    c.execute("""CREATE TABLE IF NOT EXISTS users (
        user_id INTEGER PRIMARY KEY, username TEXT, first_name TEXT,
        joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""")
    c.execute("""CREATE TABLE IF NOT EXISTS orders (
        id INTEGER PRIMARY KEY AUTOINCREMENT, user_id INTEGER, username TEXT,
        service TEXT, price INTEGER, status TEXT DEFAULT 'pending',
        created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP)""")
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
        ("schedule_enabled", "0"),
        ("schedule_open", "09:00"),
        ("schedule_close", "23:00"),
        ("schedule_days", "1,2,3,4,5,6,7"),
        ("bot_status", "open"),
    ]
    for key, value in default_settings:
        c.execute("INSERT OR IGNORE INTO settings VALUES (?, ?)", (key, value))
    conn.commit()
    conn.close()


# === НАСТРОЙКИ ===
def set_setting(key, value):
    conn = get_db(); c = conn.cursor()
    c.execute("INSERT OR REPLACE INTO settings VALUES (?, ?)", (key, str(value)))
    conn.commit(); conn.close()


def get_setting(key, default=None):
    conn = get_db(); c = conn.cursor()
    c.execute("SELECT value FROM settings WHERE key = ?", (key,))
    row = c.fetchone(); conn.close()
    return row[0] if row else default


# === УСЛУГИ ===
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


# === ПОЛЬЗОВАТЕЛИ ===
def add_user(user):
    try:
        conn = get_db(); c = conn.cursor()
        c.execute("INSERT OR IGNORE INTO users VALUES (?, ?, ?, CURRENT_TIMESTAMP)",
                  (user.id, user.username or "", user.first_name or ""))
        conn.commit(); conn.close()
    except Exception as e:
        logger.error(f"Ошибка: {e}")


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


# === ЗАКАЗЫ ===
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


def update_order_status(oid, status):
    conn = get_db(); c = conn.cursor()
    c.execute("UPDATE orders SET status = ? WHERE id = ?", (status, oid))
    conn.commit(); conn.close()


def get_order(oid):
    conn = get_db(); c = conn.cursor()
    c.execute("SELECT id, user_id, username, service, price, status FROM orders WHERE id = ?", (oid,))
    r = c.fetchone(); conn.close()
    return r


# === ПРОМОКОДЫ ===
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


# === НАКАЗАНИЯ ===
def add_punishment(user_id, username, ptype, reason, until=None):
    """Добавить наказание. ptype: mute, ban, permban."""
    conn = get_db(); c = conn.cursor()
    c.execute("INSERT INTO punishments (user_id, username, type, reason, until) VALUES (?, ?, ?, ?, ?)",
              (user_id, username, ptype, reason, until))
    conn.commit(); conn.close()


def get_active_punishment(user_id):
    """Проверить активное наказание пользователя."""
    conn = get_db(); c = conn.cursor()
    c.execute("""SELECT id, type, reason, until FROM punishments 
                 WHERE user_id = ? AND active = 1 ORDER BY id DESC LIMIT 1""", (user_id,))
    r = c.fetchone(); conn.close()

    if not r:
        return None

    pid, ptype, reason, until_str = r

    # Проверка срока
    if until_str:
        try:
            until = datetime.strptime(until_str, "%Y-%m-%d %H:%M:%S")
            if datetime.now() > until:
                # Срок истёк — снимаем
                conn = get_db(); c = conn.cursor()
                c.execute("UPDATE punishments SET active = 0 WHERE id = ?", (pid,))
                conn.commit(); conn.close()
                return None
        except Exception:
            pass

    return {"id": pid, "type": ptype, "reason": reason, "until": until_str}


def remove_punishment(user_id, ptype=None):
    """Снять наказание. Если ptype=None — снять все."""
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
    except Exception as e:
        logger.error(f"Ошибка графика: {e}")
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
                    logger.warning(f"⏰ Бот автоматически {current_status}")
            time.sleep(60)
        except Exception as e:
            logger.error(f"Ошибка планировщика: {e}")
            time.sleep(60)


def start_scheduler():
    thread = threading.Thread(target=scheduler, daemon=True)
    thread.start()


# === ТЕКСТЫ ===
def get_text(key, default=""): return get_setting(f"text_{key}", default)
def set_text(key, value): set_setting(f"text_{key}", value)


def article_about():
    return get_text("about",
        "📖 <b>О ПРОЕКТЕ ПИАР ЧАТ</b>\n\n━━━━━━━━━━━━━━━━━━━━\n\n"
        "ПИАР ЧАТ — сервис продвижения проектов на SAMP, CRMP и MTA.\n\n"
        "📩 @MaleficentR7"
    )


def article_rules():
    return get_text("rules",
        "📜 <b>ПРАВИЛА ПИАР ЧАТА</b>\n\n━━━━━━━━━━━━━━━━━━━━\n\n"
        "Полные правила: /rules\n\n"
        "📩 Вопросы — @MaleficentR7"
    )


def article_faq():
    return get_text("faq",
        "❓ <b>FAQ</b>\n\n━━━━━━━━━━━━━━━━━━━━\n\n"
        "Как заказать? — /order\n"
        "Сколько ждать? — До 24 часов\n"
        "Как оплатить? — @MaleficentR7\n\n"
        "📩 @MaleficentR7"
    )


def article_contact():
    return get_text("contact",
        "📞 <b>КОНТАКТЫ</b>\n\n━━━━━━━━━━━━━━━━━━━━\n\n"
        "🛡 @MaleficentR7\n"
        "📢 @BeanRussiaOnline"
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
    return (
        "📩 <b>ЗАКАЗ ПИАРА</b>\n\n━━━━━━━━━━━━━━━━━━━━\n\n"
        "Выбери услугу ниже 👇"
    )


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
        telebot.types.InlineKeyboardButton("🎁 Промокод", callback_data="enter_promo"),
        telebot.types.InlineKeyboardButton("📜 Правила", callback_data="rules"),
        telebot.types.InlineKeyboardButton("❓ FAQ", callback_data="faq"),
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
    m = telebot.types.InlineKeyboardMarkup(row_width=1)
    m.add(
        telebot.types.InlineKeyboardButton(f"📊 Статус: {status_text}", callback_data="admin_status"),
        telebot.types.InlineKeyboardButton(f"⏰ График: {schedule_text}", callback_data="admin_schedule"),
        telebot.types.InlineKeyboardButton("💰 Управление ценами", callback_data="admin_prices"),
        telebot.types.InlineKeyboardButton("🛠 Управление услугами", callback_data="admin_services"),
        telebot.types.InlineKeyboardButton("🎁 Промокоды", callback_data="admin_promos"),
        telebot.types.InlineKeyboardButton("🚫 Наказания", callback_data="admin_punishments"),
        telebot.types.InlineKeyboardButton("📝 Редактор текстов", callback_data="admin_texts"),
        telebot.types.InlineKeyboardButton("📈 Статистика", callback_data="admin_stats"),
        telebot.types.InlineKeyboardButton("📋 Заказы", callback_data="admin_orders"),
        telebot.types.InlineKeyboardButton("📢 Рассылка", callback_data="admin_broadcast"),
        telebot.types.InlineKeyboardButton("⬅️ Назад", callback_data="back"),
    )
    return m


# === КОМАНДЫ ===
@bot.message_handler(commands=['start'])
def start_command(message):
    # Проверка бана
    if message.from_user.id != ADMIN_ID:
        p = get_active_punishment(message.from_user.id)
        if p and p["type"] in ("ban", "permban"):
            until = p["until"] or "навсегда"
            bot.send_message(message.chat.id,
                f"🚫 <b>Вы забанены в боте</b>\n\n"
                f"📝 Причина: {p['reason']}\n"
                f"⏰ До: {until}\n\n"
                f"📩 Апелляция: @MaleficentR7",
                parse_mode='HTML')
            return

    if get_bot_status() == "closed" and message.from_user.id != ADMIN_ID:
        if get_setting("schedule_enabled", "0") == "1":
            open_t = get_setting("schedule_open", "09:00")
            close_t = get_setting("schedule_close", "23:00")
            bot.send_message(message.chat.id,
                f"🔒 <b>Бот сейчас закрыт</b>\n\n"
                f"⏰ Мы работаем с <b>{open_t}</b> до <b>{close_t}</b>.\n\n"
                f"📢 @BeanRussiaOnline\n📩 @MaleficentR7",
                parse_mode='HTML')
        else:
            bot.send_message(message.chat.id,
                "🔒 <b>Бот временно закрыт</b>\n\n📩 @MaleficentR7",
                parse_mode='HTML')
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


# === НАКАЗАНИЯ (АДМИН) ===
@bot.message_handler(commands=['mute'])
def mute_command(message):
    if message.from_user.id != ADMIN_ID:
        return
    try:
        parts = message.text.split(maxsplit=3)
        user_id = int(parts[1])
        duration = parts[2]  # Например: 1h, 30m, 2d
        reason = parts[3] if len(parts) > 3 else "Без причины"

        # Парсим время
        until = parse_duration(duration)

        add_punishment(user_id, "", "mute", reason, until)
        bot.reply_to(message, f"🔇 Пользователь <code>{user_id}</code> замучен до {until}\nПричина: {reason}",
                     parse_mode='HTML')

        # Уведомление
        try:
            bot.send_message(user_id,
                f"🔇 <b>Вы замучены</b>\n\n"
                f"📝 Причина: {reason}\n"
                f"⏰ До: {until}",
                parse_mode='HTML')
        except Exception:
            pass
    except (IndexError, ValueError):
        bot.reply_to(message,
            "📝 Формат: /mute [ID] [время] [причина]\n\n"
            "Пример: /mute 123456789 1h Спам\n\n"
            "Время: 30m = 30 минут, 1h = 1 час, 2d = 2 дня",
            parse_mode='HTML')


@bot.message_handler(commands=['ban'])
def ban_command(message):
    if message.from_user.id != ADMIN_ID:
        return
    try:
        parts = message.text.split(maxsplit=3)
        user_id = int(parts[1])
        duration = parts[2]
        reason = parts[3] if len(parts) > 3 else "Без причины"

        until = parse_duration(duration)
        add_punishment(user_id, "", "ban", reason, until)
        bot.reply_to(message, f"🚫 Пользователь <code>{user_id}</code> забанен до {until}\nПричина: {reason}",
                     parse_mode='HTML')

        try:
            bot.send_message(user_id,
                f"🚫 <b>Вы забанены</b>\n\n"
                f"📝 Причина: {reason}\n"
                f"⏰ До: {until}",
                parse_mode='HTML')
        except Exception:
            pass
    except (IndexError, ValueError):
        bot.reply_to(message,
            "📝 Формат: /ban [ID] [время] [причина]\n\n"
            "Пример: /ban 123456789 7d Реклама",
            parse_mode='HTML')


@bot.message_handler(commands=['permban'])
def permban_command(message):
    if message.from_user.id != ADMIN_ID:
        return
    try:
        parts = message.text.split(maxsplit=2)
        user_id = int(parts[1])
        reason = parts[2] if len(parts) > 2 else "Без причины"

        add_punishment(user_id, "", "permban", reason, None)
        bot.reply_to(message, f"⛔ Пользователь <code>{user_id}</code> перманентно забанен\nПричина: {reason}",
                     parse_mode='HTML')

        try:
            bot.send_message(user_id,
                f"⛔ <b>Вы перманентно забанены</b>\n\n"
                f"📝 Причина: {reason}\n"
                f"⏰ Срок: навсегда",
                parse_mode='HTML')
        except Exception:
            pass
    except (IndexError, ValueError):
        bot.reply_to(message, "📝 Формат: /permban [ID] [причина]", parse_mode='HTML')


@bot.message_handler(commands=['unmute'])
def unmute_command(message):
    if message.from_user.id != ADMIN_ID:
        return
    try:
        user_id = int(message.text.split()[1])
        remove_punishment(user_id, "mute")
        bot.reply_to(message, f"🔊 Мут снят с <code>{user_id}</code>", parse_mode='HTML')
        try:
            bot.send_message(user_id, "🔊 <b>Мут снят!</b>", parse_mode='HTML')
        except Exception:
            pass
    except (IndexError, ValueError):
        bot.reply_to(message, "📝 /unmute [ID]")


@bot.message_handler(commands=['unban'])
def unban_command(message):
    if message.from_user.id != ADMIN_ID:
        return
    try:
        user_id = int(message.text.split()[1])
        remove_punishment(user_id)
        bot.reply_to(message, f"✅ Пользователь <code>{user_id}</code> разбанен", parse_mode='HTML')
        try:
            bot.send_message(user_id, "✅ <b>Вы разбанены!</b>", parse_mode='HTML')
        except Exception:
            pass
    except (IndexError, ValueError):
        bot.reply_to(message, "📝 /unban [ID]")


@bot.message_handler(commands=['check'])
def check_command(message):
    if message.from_user.id != ADMIN_ID:
        return
    try:
        user_id = int(message.text.split()[1])
        p = get_active_punishment(user_id)
        if not p:
            bot.reply_to(message, f"✅ <code>{user_id}</code> — чист.", parse_mode='HTML')
        else:
            until = p["until"] or "навсегда"
            bot.reply_to(message,
                f"⚠️ <b>Наказание</b>\n\n"
                f"👤 ID: <code>{user_id}</code>\n"
                f"📛 Тип: {p['type']}\n"
                f"📝 Причина: {p['reason']}\n"
                f"⏰ До: {until}",
                parse_mode='HTML')
    except (IndexError, ValueError):
        bot.reply_to(message, "📝 /check [ID]")


@bot.message_handler(commands=['punishments'])
def punishments_command(message):
    if message.from_user.id != ADMIN_ID:
        return
    rows = get_all_punishments(20)
    if not rows:
        bot.reply_to(message, "📋 Наказаний пока нет.")
        return
    text = "📋 <b>ПОСЛЕДНИЕ НАКАЗАНИЯ</b>\n\n"
    for r in rows:
        pid, uid, uname, ptype, reason, until, created, active = r
        st = "🟢" if active else "⚪"
        emoji = {"mute": "🔇", "ban": "🚫", "permban": "⛔"}.get(ptype, "⚠️")
        text += f"{st}{emoji} <code>{uid}</code>\n"
        text += f"   {reason}\n"
        text += f"   ⏰ {until or 'навсегда'}\n\n"
    bot.send_message(message.chat.id, text, parse_mode='HTML')


def parse_duration(duration):
    """Парсит '1h', '30m', '7d' → возвращает строку даты окончания."""
    try:
        unit = duration[-1].lower()
        value = int(duration[:-1])
        if unit == 'm':
            delta = timedelta(minutes=value)
        elif unit == 'h':
            delta = timedelta(hours=value)
        elif unit == 'd':
            delta = timedelta(days=value)
        else:
            delta = timedelta(hours=1)
        until = datetime.now() + delta
        return until.strftime("%Y-%m-%d %H:%M:%S")
    except Exception:
        until = datetime.now() + timedelta(hours=1)
        return until.strftime("%Y-%m-%d %H:%M:%S")


# === ОСТАЛЬНЫЕ КОМАНДЫ ===
@bot.message_handler(commands=['close'])
def close_command(message):
    if message.from_user.id != ADMIN_ID:
        return
    set_bot_status("closed")
    bot.reply_to(message, "🔒 <b>Бот закрыт.</b>", parse_mode='HTML')


@bot.message_handler(commands=['open'])
def open_command(message):
    if message.from_user.id != ADMIN_ID:
        return
    set_bot_status("open")
    bot.reply_to(message, "🔓 <b>Бот открыт.</b>", parse_mode='HTML')


@bot.message_handler(commands=['stats'])
def stats_command(message):
    if message.from_user.id != ADMIN_ID:
        return
    count = get_users_count()
    bot.reply_to(message, f"📊 Пользователей: <b>{count}</b>", parse_mode='HTML')


@bot.message_handler(commands=['broadcast'])
def broadcast_command(message):
    if message.from_user.id != ADMIN_ID:
        return
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


@bot.message_handler(commands=['confirm'])
def confirm_command(message):
    if message.from_user.id != ADMIN_ID:
        return
    try:
        oid = int(message.text.split()[1])
    except (IndexError, ValueError):
        bot.reply_to(message, "📝 /confirm [id]")
        return
    order = get_order(oid)
    if not order:
        bot.reply_to(message, "❌ Заказ не найден.")
        return
    update_order_status(oid, "confirmed")
    bot.reply_to(message, f"✅ Заказ №{oid} подтверждён.")
    try:
        bot.send_message(order[1], f"✅ <b>Заказ №{oid} подтверждён!</b>", parse_mode='HTML')
    except Exception:
        pass


@bot.message_handler(commands=['done'])
def done_command(message):
    if message.from_user.id != ADMIN_ID:
        return
    try:
        oid = int(message.text.split()[1])
    except (IndexError, ValueError):
        bot.reply_to(message, "📝 /done [id]")
        return
    order = get_order(oid)
    if not order:
        bot.reply_to(message, "❌ Заказ не найден.")
        return
    update_order_status(oid, "done")
    bot.reply_to(message, f"🎉 Заказ №{oid} выполнен.")
    try:
        bot.send_message(order[1], f"🎉 <b>Заказ №{oid} выполнен!</b>", parse_mode='HTML')
    except Exception:
        pass


# === ОБРАБОТЧИКИ РЕДАКТИРОВАНИЯ ===
@bot.message_handler(func=lambda m: m.from_user.id == ADMIN_ID and m.reply_to_message and
                                   m.reply_to_message.text and "Введите новую цену" in m.reply_to_message.text)
def handle_price_input(message):
    try:
        price = int(message.text.strip())
        for line in message.reply_to_message.text.split("\n"):
            if line.startswith("KEY:"):
                key = line.replace("KEY:", "").strip()
                update_service_price(key, price)
                bot.reply_to(message, f"✅ Цена обновлена: <b>{price}₽</b>", parse_mode='HTML')
                return
    except ValueError:
        bot.reply_to(message, "❌ Введите число.")


@bot.message_handler(func=lambda m: m.from_user.id == ADMIN_ID and m.reply_to_message and
                                   m.reply_to_message.text and "Введите новый текст" in m.reply_to_message.text)
def handle_text_input(message):
    for line in message.reply_to_message.text.split("\n"):
        if line.startswith("KEY:"):
            key = line.replace("KEY:", "").strip()
            set_text(key, message.text)
            bot.reply_to(message, f"✅ Текст «{key}» обновлён.")
            return


@bot.message_handler(func=lambda m: m.from_user.id == ADMIN_ID and m.reply_to_message and
                                   m.reply_to_message.text and "Введите новый промокод" in m.reply_to_message.text)
def handle_promo_input(message):
    try:
        parts = message.text.split()
        if len(parts) != 3:
            bot.reply_to(message, "❌ Формат: КОД СКИДКА ЛИМИТ")
            return
        code, discount, max_uses = parts[0], int(parts[1]), int(parts[2])
        if create_promo(code, discount, max_uses):
            bot.reply_to(message, f"✅ Промокод <b>{code.upper()}</b> создан!", parse_mode='HTML')
        else:
            bot.reply_to(message, "❌ Такой промокод уже существует.")
    except ValueError:
        bot.reply_to(message, "❌ Неверный формат.")


@bot.message_handler(func=lambda m: m.from_user.id == ADMIN_ID and m.reply_to_message and
                                   m.reply_to_message.text and "Введите график" in m.reply_to_message.text)
def handle_schedule_input(message):
    try:
        parts = message.text.strip().split()
        if len(parts) < 2:
            bot.reply_to(message, "❌ Формат: ОТКРЫТИЕ ЗАКРЫТИЕ [ДНИ]")
            return
        open_time = parts[0]
        close_time = parts[1]
        days = parts[2] if len(parts) > 2 else "1,2,3,4,5,6,7"
        set_setting("schedule_open", open_time)
        set_setting("schedule_close", close_time)
        set_setting("schedule_days", days)
        set_setting("schedule_enabled", "1")
        bot.reply_to(message, f"✅ График: {open_time} – {close_time}\n📅 Дни: {days}", parse_mode='HTML')
    except Exception as e:
        bot.reply_to(message, f"❌ Ошибка: {e}")


# === CALLBACK ===
@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    try:
        bot.answer_callback_query(call.id)

        # Проверка бана
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
        elif call.data == "enter_promo":
            bot.send_message(call.message.chat.id, "🎁 Введи промокод:", parse_mode='HTML')
        elif call.data.startswith("buy_"):
            key = call.data.replace("buy_", "")
            services = get_services()
            service = services.get(key)
            if not service:
                return
            order_id = create_order(call.from_user.id,
                                    call.from_user.username or call.from_user.first_name,
                                    service["name"], service["price"])
            text = (
                f"📩 <b>ЗАЯВКА №{order_id}</b>\n\n"
                f"🛠 {service['name']}\n"
                f"💰 <b>{service['price']}₽</b>\n\n"
                f"📋 Напиши @MaleficentR7 с номером №{order_id}"
            )
            markup = telebot.types.InlineKeyboardMarkup(row_width=1)
            markup.add(
                telebot.types.InlineKeyboardButton("📩 Написать админу", url="https://t.me/MaleficentR7"),
                telebot.types.InlineKeyboardButton("⬅️ Назад", callback_data="order"),
            )
            bot.edit_message_text(text, call.message.chat.id, call.message.message_id,
                                  parse_mode='HTML', reply_markup=markup)
            try:
                bot.send_message(ADMIN_ID,
                    f"🆕 <b>ЗАЯВКА №{order_id}</b>\n"
                    f"👤 @{call.from_user.username or 'без ника'}\n"
                    f"🛠 {service['name']}\n💰 {service['price']}₽\n\n/confirm {order_id}",
                    parse_mode='HTML')
            except Exception:
                pass

        # === АДМИН-ПАНЕЛЬ ===
        elif call.data == "admin_panel":
            if call.from_user.id != ADMIN_ID:
                return
            bot.edit_message_text("⚙️ <b>АДМИН-ПАНЕЛЬ</b>", call.message.chat.id, call.message.message_id,
                                  parse_mode='HTML', reply_markup=admin_menu())
        elif call.data == "admin_status":
            if call.from_user.id != ADMIN_ID:
                return
            status = get_bot_status()
            text = f"🔓 Бот <b>открыт</b>" if status == "open" else f"🔒 Бот <b>закрыт</b>"
            bot.edit_message_text(text, call.message.chat.id, call.message.message_id,
                                  parse_mode='HTML', reply_markup=admin_menu())
        elif call.data == "admin_schedule":
            if call.from_user.id != ADMIN_ID:
                return
            enabled = get_setting("schedule_enabled", "0") == "1"
            open_t = get_setting("schedule_open", "09:00")
            close_t = get_setting("schedule_close", "23:00")
            days = get_setting("schedule_days", "1,2,3,4,5,6,7")
            status = "🟢 Включён" if enabled else "🔴 Выключен"
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
            if call.from_user.id != ADMIN_ID:
                return
            bot.edit_message_text(
                "⏰ Введите график — ответьте на это сообщение.\n\n"
                "Формат: <code>ОТКРЫТИЕ ЗАКРЫТИЕ ДНИ</code>\n"
                "Пример: <code>09:00 23:00 1,2,3,4,5</code>\n\n"
                "📝 Введите график.",
                call.message.chat.id, call.message.message_id, parse_mode='HTML')
        elif call.data == "disable_schedule":
            if call.from_user.id != ADMIN_ID:
                return
            set_setting("schedule_enabled", "0")
            bot.edit_message_text("🔴 График выключен.", call.message.chat.id, call.message.message_id,
                                  parse_mode='HTML', reply_markup=admin_menu())
        elif call.data == "admin_punishments":
            if call.from_user.id != ADMIN_ID:
                return
            rows = get_all_punishments(10)
            if not rows:
                text = "🚫 Наказаний пока нет."
            else:
                text = "🚫 <b>ПОСЛЕДНИЕ НАКАЗАНИЯ</b>\n\n"
                for r in rows:
                    pid, uid, uname, ptype, reason, until, created, active = r
                    st = "🟢" if active else "⚪"
                    emoji = {"mute": "🔇", "ban": "🚫", "permban": "⛔"}.get(ptype, "⚠️")
                    text += f"{st}{emoji} <code>{uid}</code>\n   {reason}\n   {until or 'навсегда'}\n\n"
            m = telebot.types.InlineKeyboardMarkup(row_width=1)
            m.add(
                telebot.types.InlineKeyboardButton("📝 Как наказывать", callback_data="punish_help"),
                telebot.types.InlineKeyboardButton("⬅️ Назад", callback_data="admin_panel"),
            )
            bot.edit_message_text(text, call.message.chat.id, call.message.message_id,
                                  parse_mode='HTML', reply_markup=m)
        elif call.data == "punish_help":
            if call.from_user.id != ADMIN_ID:
                return
            text = (
                "🚫 <b>КОМАНДЫ НАКАЗАНИЙ</b>\n\n"
                "/mute [ID] [время] [причина]\n"
                "<i>Пример: /mute 123456789 1h Спам</i>\n\n"
                "/ban [ID] [время] [причина]\n"
                "<i>Пример: /ban 123456789 7d Реклама</i>\n\n"
                "/permban [ID] [причина]\n"
                "<i>Пример: /permban 123456789 Скам</i>\n\n"
                "/unmute [ID] — снять мут\n"
                "/unban [ID] — снять бан\n"
                "/check [ID] — проверить\n"
                "/punishments — список\n\n"
                "⏰ Время: <b>30m</b> = 30 мин, <b>1h</b> = 1 час, <b>7d</b> = 7 дней"
            )
            m = telebot.types.InlineKeyboardMarkup(row_width=1)
            m.add(telebot.types.InlineKeyboardButton("⬅️ Назад", callback_data="admin_punishments"))
            bot.edit_message_text(text, call.message.chat.id, call.message.message_id,
                                  parse_mode='HTML', reply_markup=m)
        elif call.data == "admin_prices":
            if call.from_user.id != ADMIN_ID:
                return
            services = get_services()
            m = telebot.types.InlineKeyboardMarkup(row_width=1)
            for key, s in services.items():
                m.add(telebot.types.InlineKeyboardButton(f"{s['name']} — {s['price']}₽", callback_data=f"editprice_{key}"))
            m.add(telebot.types.InlineKeyboardButton("⬅️ Назад", callback_data="admin_panel"))
            bot.edit_message_text("💰 <b>ЦЕНЫ</b>", call.message.chat.id, call.message.message_id,
                                  parse_mode='HTML', reply_markup=m)
        elif call.data.startswith("editprice_"):
            if call.from_user.id != ADMIN_ID:
                return
            key = call.data.replace("editprice_", "")
            services = get_services()
            s = services.get(key)
            if not s:
                return
            bot.edit_message_text(
                f"💰 <b>{s['name']}</b>\nТекущая цена: <b>{s['price']}₽</b>\n\n"
                f"📝 Введите новую цену — ответьте на это сообщение.\nKEY:{key}",
                call.message.chat.id, call.message.message_id, parse_mode='HTML')
        elif call.data == "admin_services":
            if call.from_user.id != ADMIN_ID:
                return
            services = get_services()
            m = telebot.types.InlineKeyboardMarkup(row_width=1)
            for key, s in services.items():
                st = "✅" if s["enabled"] else "❌"
                m.add(telebot.types.InlineKeyboardButton(f"{st} {s['name']}", callback_data=f"toggle_{key}"))
            m.add(telebot.types.InlineKeyboardButton("⬅️ Назад", callback_data="admin_panel"))
            bot.edit_message_text("🛠 <b>УСЛУГИ</b>", call.message.chat.id, call.message.message_id,
                                  parse_mode='HTML', reply_markup=m)
        elif call.data.startswith("toggle_"):
            if call.from_user.id != ADMIN_ID:
                return
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
            if call.from_user.id != ADMIN_ID:
                return
            promos = get_promos()
            text = "🎁 <b>ПРОМОКОДЫ</b>\n\n"
            if promos:
                for p in promos:
                    code, disc, mx, uses, active = p
                    st = "✅" if active else "❌"
                    text += f"{st} <b>{code}</b> — {disc}% ({uses}/{mx})\n"
            else:
                text += "Пока нет промокодов.\n"
            m = telebot.types.InlineKeyboardMarkup(row_width=1)
            m.add(telebot.types.InlineKeyboardButton("➕ Создать", callback_data="create_promo"))
            m.add(telebot.types.InlineKeyboardButton("⬅️ Назад", callback_data="admin_panel"))
            bot.edit_message_text(text, call.message.chat.id, call.message.message_id,
                                  parse_mode='HTML', reply_markup=m)
        elif call.data == "create_promo":
            if call.from_user.id != ADMIN_ID:
                return
            bot.edit_message_text(
                "🎁 Введите промокод — ответьте на это сообщение.\n\n"
                "Формат: <code>КОД СКИДКА ЛИМИТ</code>\n"
                "Пример: <code>START 10 100</code>",
                call.message.chat.id, call.message.message_id, parse_mode='HTML')
        elif call.data == "admin_texts":
            if call.from_user.id != ADMIN_ID:
                return
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
            if call.from_user.id != ADMIN_ID:
                return
            key = call.data.replace("edittext_", "")
            current = get_text(key, "(пусто)")
            bot.edit_message_text(
                f"📝 <b>{key}</b>\n\n{current[:300]}...\n\n"
                f"📩 Введите новый текст — ответьте на это сообщение.\nKEY:{key}",
                call.message.chat.id, call.message.message_id, parse_mode='HTML')
        elif call.data == "admin_stats":
            if call.from_user.id != ADMIN_ID:
                return
            count = get_users_count()
            bot.edit_message_text(f"📊 Пользователей: <b>{count}</b>",
                                  call.message.chat.id, call.message.message_id,
                                  parse_mode='HTML', reply_markup=admin_menu())
        elif call.data == "admin_orders":
            if call.from_user.id != ADMIN_ID:
                return
            orders = get_orders(10)
            if not orders:
                text = "📋 Заказов нет."
            else:
                text = "📋 <b>ЗАКАЗЫ</b>\n\n"
                for o in orders:
                    oid, uid, uname, service, price, status, date = o
                    em = "⏳" if status == "pending" else ("✅" if status == "confirmed" else "🎉")
                    text += f"{em} <b>№{oid}</b> | {service} | {price}₽\n\n"
            bot.edit_message_text(text, call.message.chat.id, call.message.message_id,
                                  parse_mode='HTML', reply_markup=admin_menu())
        elif call.data == "admin_broadcast":
            if call.from_user.id != ADMIN_ID:
                return
            bot.edit_message_text("📢 /broadcast [текст]", call.message.chat.id, call.message.message_id,
                                  parse_mode='HTML', reply_markup=admin_menu())
    except Exception as e:
        logger.error(f"Ошибка: {e}")


@bot.message_handler(func=lambda message: True)
def echo_handler(message):
    if message.reply_to_message:
        return
    if message.text and not message.text.startswith('/'):
        bot.reply_to(message, "🤔 Не понимаю. /help")


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


if __name__ == "__main__":
    import os
    init_db()
    start_scheduler()
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, threaded=True)
