import logging
import sqlite3
import telebot
from flask import Flask, request

# === НАСТРОЙКИ ===
BOT_TOKEN = "8337839229:AAH7EuRNbQK2xn74o1WiDa-TxZHdDA795tg"
WEBHOOK_URL = "https://piar-bot-5zlx.onrender.com"
ADMIN_ID = 8718572838

# === ЛОГИ ===
logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)

# === БОТ ===
bot = telebot.TeleBot(BOT_TOKEN, threaded=True)

# === FLASK ===
app = Flask(__name__)
app.logger.disabled = True
logging.getLogger('werkzeug').disabled = True

# === БАЗА ===
DB_PATH = "/tmp/users.db"


def get_db():
    return sqlite3.connect(DB_PATH, timeout=5)


def init_db():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            first_name TEXT,
            joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS orders (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            user_id INTEGER,
            username TEXT,
            service TEXT,
            price INTEGER,
            status TEXT DEFAULT 'pending',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS settings (
            key TEXT PRIMARY KEY,
            value TEXT
        )
    """)
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS services (
            key TEXT PRIMARY KEY,
            name TEXT,
            price INTEGER,
            enabled INTEGER DEFAULT 1
        )
    """)
    # Инициализация услуг
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
        cursor.execute("INSERT OR IGNORE INTO services (key, name, price, enabled) VALUES (?, ?, ?, ?)",
                       (key, name, price, enabled))
    conn.commit()
    conn.close()


# === НАСТРОЙКИ ===
def set_setting(key, value):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("INSERT OR REPLACE INTO settings (key, value) VALUES (?, ?)", (key, str(value)))
    conn.commit()
    conn.close()


def get_setting(key, default=None):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT value FROM settings WHERE key = ?", (key,))
    row = cursor.fetchone()
    conn.close()
    return row[0] if row else default


# === УСЛУГИ ===
def get_services():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT key, name, price, enabled FROM services")
    rows = cursor.fetchall()
    conn.close()
    return {row[0]: {"name": row[1], "price": row[2], "enabled": row[3]} for row in rows}


def update_service_price(key, price):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("UPDATE services SET price = ? WHERE key = ?", (price, key))
    conn.commit()
    conn.close()


def toggle_service(key):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("UPDATE services SET enabled = 1 - enabled WHERE key = ?", (key,))
    conn.commit()
    conn.close()


# === ПОЛЬЗОВАТЕЛИ ===
def add_user(user):
    try:
        conn = get_db()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT OR IGNORE INTO users (user_id, username, first_name) VALUES (?, ?, ?)",
            (user.id, user.username or "", user.first_name or "")
        )
        conn.commit()
        conn.close()
    except Exception as e:
        logger.error(f"Ошибка: {e}")


def get_all_users():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM users")
    users = [row[0] for row in cursor.fetchall()]
    conn.close()
    return users


def get_users_count():
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM users")
    count = cursor.fetchone()[0]
    conn.close()
    return count


# === ЗАКАЗЫ ===
def create_order(user_id, username, service, price):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO orders (user_id, username, service, price) VALUES (?, ?, ?, ?)",
        (user_id, username, service, price)
    )
    order_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return order_id


def get_orders(limit=20):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute(
        "SELECT id, user_id, username, service, price, status, created_at FROM orders ORDER BY id DESC LIMIT ?",
        (limit,)
    )
    orders = cursor.fetchall()
    conn.close()
    return orders


def update_order_status(order_id, status):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("UPDATE orders SET status = ? WHERE id = ?", (status, order_id))
    conn.commit()
    conn.close()


def get_order(order_id):
    conn = get_db()
    cursor = conn.cursor()
    cursor.execute("SELECT id, user_id, username, service, price, status FROM orders WHERE id = ?", (order_id,))
    order = cursor.fetchone()
    conn.close()
    return order


# === СТАТУС БОТА ===
def set_bot_status(status):
    set_setting("bot_status", status)


def get_bot_status():
    return get_setting("bot_status", "open")


# === ТЕКСТЫ ===
def get_text(key, default=""):
    return get_setting(f"text_{key}", default)


def set_text(key, value):
    set_setting(f"text_{key}", value)


# === СТАТЬИ ===
def article_about():
    return get_text("about",
        "📖 <b>О ПРОЕКТЕ</b>\n"
        "ПИАР ЧАТ | SAMP | CRMP | MTA\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "Мы — сообщество, где игроки заказывают качественный пиар своих проектов.\n\n"
        "📩 Админ: @MaleficentR7"
    )


def article_rules():
    return get_text("rules",
        "📜 <b>ПРАВИЛА</b>\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "1️⃣ Уважение\n2️⃣ Без спама\n3️⃣ Без 18+\n4️⃣ Подчиняйся админам\n\n"
        "📩 @MaleficentR7"
    )


def article_faq():
    return get_text("faq",
        "❓ <b>FAQ</b>\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "Как заказать? — /order\n"
        "Сколько ждать? — До 24 часов\n"
        "Как оплатить? — @MaleficentR7\n\n"
        "📩 Не нашёл ответ? Пиши @MaleficentR7"
    )


def article_contact():
    return get_text("contact",
        "📞 <b>КОНТАКТЫ</b>\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "🛡 Админ: @MaleficentR7\n"
        "📢 Канал: @BeanRussiaOnline\n\n"
        "📩 Пиши — ответим в течение 1-2 часов!"
    )


def article_price():
    services = get_services()
    text = "💰 <b>ПРАЙС</b>\n\n━━━━━━━━━━━━━━━━━━━━\n\n"
    for key, s in services.items():
        if s["enabled"]:
            text += f"{s['name']} — <b>{s['price']}₽</b>\n"
    text += "\n📩 Заказать: /order"
    return text


def article_order():
    return (
        "📩 <b>ЗАКАЗ ПИАРА</b>\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "Выбери услугу ниже 👇"
    )


# === КЛАВИАТУРЫ ===
def menu_after_article():
    markup = telebot.types.InlineKeyboardMarkup(row_width=2)
    markup.add(
        telebot.types.InlineKeyboardButton("📖 О проекте", callback_data="about"),
        telebot.types.InlineKeyboardButton("📜 Правила", callback_data="rules"),
    )
    markup.add(
        telebot.types.InlineKeyboardButton("💰 Прайс", callback_data="price"),
        telebot.types.InlineKeyboardButton("❓ FAQ", callback_data="faq"),
    )
    markup.add(
        telebot.types.InlineKeyboardButton("📩 Заказать", callback_data="order"),
        telebot.types.InlineKeyboardButton("📞 Контакты", callback_data="contact"),
    )
    markup.add(telebot.types.InlineKeyboardButton("🏠 Главная", callback_data="back"))
    return markup


def services_menu():
    services = get_services()
    markup = telebot.types.InlineKeyboardMarkup(row_width=1)
    for key, s in services.items():
        if s["enabled"]:
            markup.add(telebot.types.InlineKeyboardButton(
                f"{s['name']} — {s['price']}₽",
                callback_data=f"buy_{key}"
            ))
    markup.add(telebot.types.InlineKeyboardButton("⬅️ Назад", callback_data="back"))
    return markup


def main_menu(user_id):
    markup = telebot.types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        telebot.types.InlineKeyboardButton("📖 О проекте", callback_data="about"),
        telebot.types.InlineKeyboardButton("💰 Прайс", callback_data="price"),
        telebot.types.InlineKeyboardButton("📩 Заказать пиар", callback_data="order"),
        telebot.types.InlineKeyboardButton("📜 Правила", callback_data="rules"),
        telebot.types.InlineKeyboardButton("❓ FAQ", callback_data="faq"),
        telebot.types.InlineKeyboardButton("📞 Контакты", callback_data="contact"),
    )
    if user_id == ADMIN_ID:
        markup.add(telebot.types.InlineKeyboardButton("⚙️ Админ-панель", callback_data="admin_panel"))
    return markup


def admin_menu():
    status = get_bot_status()
    status_text = "🔓 Открыт" if status == "open" else "🔒 Закрыт"
    markup = telebot.types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        telebot.types.InlineKeyboardButton(f"📊 Статус: {status_text}", callback_data="admin_status"),
        telebot.types.InlineKeyboardButton("💰 Управление ценами", callback_data="admin_prices"),
        telebot.types.InlineKeyboardButton("🛠 Управление услугами", callback_data="admin_services"),
        telebot.types.InlineKeyboardButton("📝 Редактор текстов", callback_data="admin_texts"),
        telebot.types.InlineKeyboardButton("📈 Статистика", callback_data="admin_stats"),
        telebot.types.InlineKeyboardButton("📋 Заказы", callback_data="admin_orders"),
        telebot.types.InlineKeyboardButton("📢 Рассылка", callback_data="admin_broadcast"),
        telebot.types.InlineKeyboardButton("⬅️ Назад", callback_data="back"),
    )
    return markup


# === КОМАНДЫ ===
@bot.message_handler(commands=['start'])
def start_command(message):
    if get_bot_status() == "closed" and message.from_user.id != ADMIN_ID:
        bot.send_message(message.chat.id,
            "🔒 <b>Бот временно закрыт</b>\n\n"
            "Мы проводим техническое обслуживание.\n\n"
            "📢 Следите за новостями: @BeanRussiaOnline\n"
            "📩 Срочно: @MaleficentR7",
            parse_mode='HTML')
        return
    add_user(message.from_user)
    text = (
        "👋 <b>Добро пожаловать в ПИАР ЧАТ | SAMP | CRMP | MTA!</b>\n\n"
        "📌 Здесь ты можешь заказать пиар своего проекта.\n\n"
        "👇 <b>Выбери действие:</b>"
    )
    bot.send_message(message.chat.id, text, parse_mode='HTML', reply_markup=main_menu(message.from_user.id))


@bot.message_handler(commands=['help'])
def help_command(message):
    bot.send_message(message.chat.id,
        "🆘 /start — меню\n/about — о проекте\n/rules — правила\n/price — прайс\n/order — заказать\n/contact — контакты\n/faq — FAQ",
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
    bot.send_message(message.chat.id, article_order(), parse_mode='HTML', reply_markup=services_menu())


@bot.message_handler(commands=['faq'])
def faq_command(message):
    bot.send_message(message.chat.id, article_faq(), parse_mode='HTML', reply_markup=menu_after_article())


@bot.message_handler(commands=['contact'])
def contact_command(message):
    bot.send_message(message.chat.id, article_contact(), parse_mode='HTML', reply_markup=menu_after_article())


# === АДМИН-КОМАНДЫ ===
@bot.message_handler(commands=['stats'])
def stats_command(message):
    if message.from_user.id != ADMIN_ID:
        return
    count = get_users_count()
    bot.reply_to(message, f"📊 Пользователей: <b>{count}</b>", parse_mode='HTML')


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


# === РЕДАКТОР ЦЕН ===
@bot.message_handler(func=lambda m: m.from_user.id == ADMIN_ID and m.reply_to_message and
                                   m.reply_to_message.text and "Введите новую цену" in m.reply_to_message.text)
def handle_price_input(message):
    try:
        price = int(message.text.strip())
        # Извлекаем ключ услуги из текста
        lines = message.reply_to_message.text.split("\n")
        for line in lines:
            if line.startswith("KEY:"):
                key = line.replace("KEY:", "").strip()
                update_service_price(key, price)
                bot.reply_to(message, f"✅ Цена обновлена: {price}₽")
                return
    except ValueError:
        bot.reply_to(message, "❌ Введите число.")


# === РЕДАКТОР ТЕКСТОВ ===
@bot.message_handler(func=lambda m: m.from_user.id == ADMIN_ID and m.reply_to_message and
                                   m.reply_to_message.text and "Введите новый текст" in m.reply_to_message.text)
def handle_text_input(message):
    lines = message.reply_to_message.text.split("\n")
    for line in lines:
        if line.startswith("KEY:"):
            key = line.replace("KEY:", "").strip()
            set_text(key, message.text)
            bot.reply_to(message, f"✅ Текст «{key}» обновлён.")
            return


# === CALLBACK ===
@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    try:
        bot.answer_callback_query(call.id)

        if get_bot_status() == "closed" and call.from_user.id != ADMIN_ID:
            bot.answer_callback_query(call.id, "🔒 Бот на техническом обслуживании", show_alert=True)
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
            text = "👋 <b>ПИАР ЧАТ | SAMP | CRMP | MTA</b>\n\n👇 Выбери действие:"
            bot.edit_message_text(text, call.message.chat.id, call.message.message_id,
                                  parse_mode='HTML', reply_markup=main_menu(call.from_user.id))
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
                f"━━━━━━━━━━━━━━━━━━━━\n\n"
                f"🛠 Услуга: {service['name']}\n"
                f"💰 Сумма: <b>{service['price']}₽</b>\n\n"
                f"📋 Напиши @MaleficentR7 с номером <b>№{order_id}</b>"
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
                    f"🆕 <b>НОВАЯ ЗАЯВКА №{order_id}</b>\n\n"
                    f"👤 @{call.from_user.username or 'без ника'}\n"
                    f"🛠 {service['name']}\n"
                    f"💰 {service['price']}₽\n\n"
                    f"/confirm {order_id}",
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
            text = f"🔓 Бот <b>открыт</b>\n\nЧтобы закрыть: /close" if status == "open" else f"🔒 Бот <b>закрыт</b>\n\nЧтобы открыть: /open"
            bot.edit_message_text(text, call.message.chat.id, call.message.message_id,
                                  parse_mode='HTML', reply_markup=admin_menu())
        elif call.data == "admin_prices":
            if call.from_user.id != ADMIN_ID:
                return
            services = get_services()
            markup = telebot.types.InlineKeyboardMarkup(row_width=1)
            for key, s in services.items():
                markup.add(telebot.types.InlineKeyboardButton(
                    f"{s['name']} — {s['price']}₽",
                    callback_data=f"editprice_{key}"
                ))
            markup.add(telebot.types.InlineKeyboardButton("⬅️ Назад", callback_data="admin_panel"))
            bot.edit_message_text("💰 <b>УПРАВЛЕНИЕ ЦЕНАМИ</b>\n\nВыбери услугу:", 
                                  call.message.chat.id, call.message.message_id,
                                  parse_mode='HTML', reply_markup=markup)
        elif call.data.startswith("editprice_"):
            if call.from_user.id != ADMIN_ID:
                return
            key = call.data.replace("editprice_", "")
            services = get_services()
            s = services.get(key)
            if not s:
                return
            bot.edit_message_text(
                f"💰 <b>Изменение цены</b>\n\n"
                f"Услуга: {s['name']}\n"
                f"Текущая цена: <b>{s['price']}₽</b>\n\n"
                f"📝 Ответьте на это сообщение числом — новая цена.\n"
                f"KEY:{key}",
                call.message.chat.id, call.message.message_id,
                parse_mode='HTML'
            )
        elif call.data == "admin_services":
            if call.from_user.id != ADMIN_ID:
                return
            services = get_services()
            markup = telebot.types.InlineKeyboardMarkup(row_width=1)
            for key, s in services.items():
                status = "✅" if s["enabled"] else "❌"
                markup.add(telebot.types.InlineKeyboardButton(
                    f"{status} {s['name']}",
                    callback_data=f"toggle_{key}"
                ))
            markup.add(telebot.types.InlineKeyboardButton("⬅️ Назад", callback_data="admin_panel"))
            bot.edit_message_text("🛠 <b>УПРАВЛЕНИЕ УСЛУГАМИ</b>\n\nНажми — вкл/выкл:",
                                  call.message.chat.id, call.message.message_id,
                                  parse_mode='HTML', reply_markup=markup)
        elif call.data.startswith("toggle_"):
            if call.from_user.id != ADMIN_ID:
                return
            key = call.data.replace("toggle_", "")
            toggle_service(key)
            # Перерисовать меню
            services = get_services()
            markup = telebot.types.InlineKeyboardMarkup(row_width=1)
            for k, s in services.items():
                status = "✅" if s["enabled"] else "❌"
                markup.add(telebot.types.InlineKeyboardButton(
                    f"{status} {s['name']}",
                    callback_data=f"toggle_{k}"
                ))
            markup.add(telebot.types.InlineKeyboardButton("⬅️ Назад", callback_data="admin_panel"))
            bot.edit_message_text("🛠 <b>УПРАВЛЕНИЕ УСЛУГАМИ</b>",
                                  call.message.chat.id, call.message.message_id,
                                  parse_mode='HTML', reply_markup=markup)
        elif call.data == "admin_texts":
            if call.from_user.id != ADMIN_ID:
                return
            markup = telebot.types.InlineKeyboardMarkup(row_width=1)
            markup.add(
                telebot.types.InlineKeyboardButton("📖 О проекте", callback_data="edittext_about"),
                telebot.types.InlineKeyboardButton("📜 Правила", callback_data="edittext_rules"),
                telebot.types.InlineKeyboardButton("❓ FAQ", callback_data="edittext_faq"),
                telebot.types.InlineKeyboardButton("📞 Контакты", callback_data="edittext_contact"),
                telebot.types.InlineKeyboardButton("⬅️ Назад", callback_data="admin_panel"),
            )
            bot.edit_message_text("📝 <b>РЕДАКТОР ТЕКСТОВ</b>\n\nЧто редактируем?",
                                  call.message.chat.id, call.message.message_id,
                                  parse_mode='HTML', reply_markup=markup)
        elif call.data.startswith("edittext_"):
            if call.from_user.id != ADMIN_ID:
                return
            key = call.data.replace("edittext_", "")
            current = get_text(key, "(пусто)")
            bot.edit_message_text(
                f"📝 <b>Редактирование «{key}»</b>\n\n"
                f"Текущий текст:\n\n{current[:500]}\n\n"
                f"📩 Ответьте на это сообщение новым текстом.\n"
                f"KEY:{key}",
                call.message.chat.id, call.message.message_id,
                parse_mode='HTML'
            )
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
                text = "📋 Заказов пока нет."
            else:
                text = "📋 <b>ПОСЛЕДНИЕ ЗАКАЗЫ</b>\n\n"
                for o in orders:
                    oid, uid, uname, service, price, status, date = o
                    status_emoji = "⏳" if status == "pending" else ("✅" if status == "confirmed" else "🎉")
                    text += f"{status_emoji} <b>№{oid}</b> | {service} | {price}₽\n\n"
            bot.edit_message_text(text, call.message.chat.id, call.message.message_id,
                                  parse_mode='HTML', reply_markup=admin_menu())
        elif call.data == "admin_broadcast":
            if call.from_user.id != ADMIN_ID:
                return
            bot.edit_message_text("📢 /broadcast [текст]", call.message.chat.id, call.message.message_id,
                                  parse_mode='HTML', reply_markup=admin_menu())
    except Exception as e:
        logger.error(f"Ошибка: {e}")


# === ПРИЁМ СООБЩЕНИЙ ===
@bot.message_handler(func=lambda message: True)
def echo_handler(message):
    if message.text and not message.text.startswith('/'):
        bot.reply_to(message, "🤔 Не понимаю команду.\nНапишите /help")


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
            allowed_updates=["message", "callback_query", "edited_message", "channel_post"]
        )
        if result:
            return "Webhook установлен!", 200
        return "Ошибка", 500
    except Exception as e:
        return f"Ошибка: {e}", 500


@app.route("/health")
def health():
    return "Bot is alive!", 200


# === ЗАПУСК ===
if __name__ == "__main__":
    import os
    init_db()
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, threaded=True)
