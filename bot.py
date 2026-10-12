import logging
import sqlite3
import telebot
from flask import Flask, request

# === НАСТРОЙКИ ===
BOT_TOKEN = "8337839229:AAH7EuRNbQK2xn74o1WiDa-TxZHdDA795tg"
WEBHOOK_URL = "https://piar-bot-5zlx.onrender.com"
ADMIN_ID = 8718572838

# === ЛОГИ (только ошибки) ===
logging.basicConfig(level=logging.WARNING)
logger = logging.getLogger(__name__)

# === БОТ (threaded=True для скорости) ===
bot = telebot.TeleBot(BOT_TOKEN, threaded=True)

# === FLASK (без логирования запросов) ===
app = Flask(__name__)
app.logger.disabled = True
logging.getLogger('werkzeug').disabled = True

# === БАЗА ДАННЫХ ===
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
    conn.commit()
    conn.close()


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


# === ТЕКСТЫ ===
def article_about():
    return (
        "📖 <b>О ПРОЕКТЕ</b>\n"
        "ПИАР ЧАТ | SAMP | CRMP | MTA\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "Мы — сообщество, где игроки находят единомышленников "
        "и заказывают качественный пиар своих проектов.\n\n"
        "🔥 <b>НАШИ ПРЕИМУЩЕСТВА:</b>\n\n"
        "✅ Опытная команда\n"
        "✅ Честные правила\n"
        "✅ Быстрая поддержка\n"
        "✅ Гибкие цены\n\n"
        "📩 Админ: @MaleficentR7\n"
        "📢 Чат: @BeanRussiaOnline"
    )


def article_rules():
    return (
        "📜 <b>ПРАВИЛА</b>\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "<b>1️⃣ УВАЖЕНИЕ</b> — не оскорбляй других.\n\n"
        "<b>2️⃣ БЕЗ СПАМА</b> — пиар по правилам.\n\n"
        "<b>3️⃣ БЕЗ 18+</b> — контент для взрослых запрещён.\n\n"
        "<b>4️⃣ БЕЗ СТОРОННИХ ССЫЛОК</b>\n\n"
        "<b>5️⃣ ПОДЧИНЯЙСЯ АДМИНАМ</b>\n\n"
        "📩 Вопросы — @MaleficentR7"
    )


def article_price():
    return (
        "💰 <b>ПРАЙС</b>\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "📢 Пост в чате — <b>20₽</b>\n"
        "📺 Пост в канале — <b>100₽</b>\n"
        "📌 Закреп — <b>150₽</b>\n"
        "🤖 Авторассылка — <b>200₽</b>\n"
        "🔥 3 поста — <b>400₽</b>\n"
        "👑 Полный пакет — <b>500₽</b>\n"
        "💎 5 постов — <b>600₽</b>\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "📩 Заказать: @MaleficentR7"
    )


def article_order():
    return (
        "📩 <b>ЗАКАЗ ПИАРА</b>\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "Выбери услугу ниже 👇\n\n"
        "После выбора бот пришлёт контакт админа."
    )


def article_faq():
    return (
        "❓ <b>FAQ</b>\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "<b>Как заказать?</b> — /order\n\n"
        "<b>Сколько ждать?</b> — До 24 часов.\n\n"
        "<b>Как оплатить?</b> — Переводом на ЮMoney. Реквизиты у @MaleficentR7.\n\n"
        "<b>Какие проекты запрещены?</b> — 18+, скам, читы.\n\n"
        "📩 Не нашёл ответ? Пиши @MaleficentR7"
    )


def article_contact():
    return (
        "📞 <b>КОНТАКТЫ</b>\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "🛡 <b>Администратор:</b>\n"
        "@MaleficentR7\n\n"
        "📢 <b>Telegram-канал:</b>\n"
        "@BeanRussiaOnline\n\n"
        "💬 <b>Чат ВК:</b>\n"
        "vk.me/join/kuBhzS34RI7dc8140qevGBk11iBjwb8mcGk=\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "📩 Пиши — ответим в течение 1-2 часов!"
    )


# === УСЛУГИ ===
SERVICES = {
    "post_chat": {"name": "📢 Пост в чате", "price": 20},
    "post_channel": {"name": "📺 Пост в канале", "price": 100},
    "pin": {"name": "📌 Закреп на 24 часа", "price": 150},
    "autopost": {"name": "🤖 Авторассылка", "price": 200},
    "posts3": {"name": "🔥 3 поста подряд", "price": 400},
    "package": {"name": "👑 Полный пакет", "price": 500},
    "posts5": {"name": "💎 5 постов подряд", "price": 600},
}


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
    markup = telebot.types.InlineKeyboardMarkup(row_width=1)
    for key, service in SERVICES.items():
        markup.add(
            telebot.types.InlineKeyboardButton(
                f"{service['name']} — {service['price']}₽",
                callback_data=f"buy_{key}"
            )
        )
    markup.add(telebot.types.InlineKeyboardButton("⬅️ Назад", callback_data="back"))
    return markup


def main_menu(user_id):
    markup = telebot.types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        telebot.types.InlineKeyboardButton("📖 О проекте", callback_data="about"),
        telebot.types.InlineKeyboardButton("💰 Прайс на пиар", callback_data="price"),
        telebot.types.InlineKeyboardButton("📩 Заказать пиар", callback_data="order"),
        telebot.types.InlineKeyboardButton("📜 Правила", callback_data="rules"),
        telebot.types.InlineKeyboardButton("❓ FAQ", callback_data="faq"),
        telebot.types.InlineKeyboardButton("📞 Контакты", callback_data="contact"),
    )
    if user_id == ADMIN_ID:
        markup.add(telebot.types.InlineKeyboardButton("⚙️ Админ-панель", callback_data="admin_panel"))
    return markup


def admin_menu():
    markup = telebot.types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        telebot.types.InlineKeyboardButton("📊 Статистика", callback_data="admin_stats"),
        telebot.types.InlineKeyboardButton("👥 Пользователи", callback_data="admin_users"),
        telebot.types.InlineKeyboardButton("📋 Заказы", callback_data="admin_orders"),
        telebot.types.InlineKeyboardButton("📢 Рассылка", callback_data="admin_broadcast"),
        telebot.types.InlineKeyboardButton("🛠 Команды", callback_data="admin_commands"),
        telebot.types.InlineKeyboardButton("⬅️ Назад", callback_data="back"),
    )
    return markup


# === КОМАНДЫ ===
@bot.message_handler(commands=['start'])
def start_command(message):
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
        "🆘 <b>КОМАНДЫ</b>\n\n"
        "/start — меню\n"
        "/about — о проекте\n"
        "/rules — правила\n"
        "/price — прайс\n"
        "/order — заказать\n"
        "/contact — контакты\n"
        "/faq — FAQ\n"
        "/help — справка",
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


# === АДМИН ===
@bot.message_handler(commands=['stats'])
def stats_command(message):
    if message.from_user.id != ADMIN_ID:
        return
    count = get_users_count()
    bot.reply_to(message, f"📊 Пользователей: <b>{count}</b>", parse_mode='HTML')


@bot.message_handler(commands=['users'])
def users_command(message):
    if message.from_user.id != ADMIN_ID:
        return
    users = get_all_users()
    text = f"👥 Пользователи ({len(users)}):\n\n"
    for uid in users[:50]:
        text += f"• <code>{uid}</code>\n"
    bot.send_message(message.chat.id, text, parse_mode='HTML')


@bot.message_handler(commands=['myorders'])
def myorders_command(message):
    if message.from_user.id != ADMIN_ID:
        return
    orders = get_orders(20)
    if not orders:
        bot.reply_to(message, "📋 Заказов пока нет.")
        return
    text = "📋 <b>ПОСЛЕДНИЕ ЗАКАЗЫ</b>\n\n"
    for o in orders:
        oid, uid, uname, service, price, status, date = o
        status_emoji = "⏳" if status == "pending" else ("✅" if status == "confirmed" else "🎉")
        text += f"{status_emoji} <b>№{oid}</b> | {service} | {price}₽\n"
        text += f"    👤 @{uname or uid}\n\n"
    bot.send_message(message.chat.id, text, parse_mode='HTML')


@bot.message_handler(commands=['confirm'])
def confirm_command(message):
    if message.from_user.id != ADMIN_ID:
        return
    try:
        order_id = int(message.text.split()[1])
    except (IndexError, ValueError):
        bot.reply_to(message, "📝 /confirm [id]")
        return
    order = get_order(order_id)
    if not order:
        bot.reply_to(message, "❌ Заказ не найден.")
        return
    update_order_status(order_id, "confirmed")
    bot.reply_to(message, f"✅ Заказ №{order_id} подтверждён.")
    try:
        bot.send_message(order[1], f"✅ <b>Заказ №{order_id} подтверждён!</b>\n\nМы запустим пиар в ближайшее время.", parse_mode='HTML')
    except Exception:
        pass


@bot.message_handler(commands=['done'])
def done_command(message):
    if message.from_user.id != ADMIN_ID:
        return
    try:
        order_id = int(message.text.split()[1])
    except (IndexError, ValueError):
        bot.reply_to(message, "📝 /done [id]")
        return
    order = get_order(order_id)
    if not order:
        bot.reply_to(message, "❌ Заказ не найден.")
        return
    update_order_status(order_id, "done")
    bot.reply_to(message, f"🎉 Заказ №{order_id} выполнен.")
    try:
        bot.send_message(order[1], f"🎉 <b>Заказ №{order_id} выполнен!</b>\n\nСпасибо! 🤝", parse_mode='HTML')
    except Exception:
        pass


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


@bot.message_handler(commands=['say'])
def say_command(message):
    if message.from_user.id != ADMIN_ID:
        return
    text = message.text.replace('/say ', '', 1)
    if text:
        bot.send_message(message.chat.id, text, parse_mode='HTML')


# === КНОПКИ ===
@bot.callback_query_handler(func=lambda call: True)
def callback_handler(call):
    try:
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
            service = SERVICES.get(key)
            if not service:
                bot.answer_callback_query(call.id, "Услуга не найдена")
                return
            order_id = create_order(
                call.from_user.id,
                call.from_user.username or call.from_user.first_name,
                service["name"],
                service["price"]
            )
            text = (
                f"📩 <b>ЗАЯВКА №{order_id}</b>\n\n"
                f"━━━━━━━━━━━━━━━━━━━━\n\n"
                f"🛠 Услуга: {service['name']}\n"
                f"💰 Сумма: <b>{service['price']}₽</b>\n"
                f"⏳ Статус: <b>Ожидает подтверждения</b>\n\n"
                f"━━━━━━━━━━━━━━━━━━━━\n\n"
                f"📋 <b>ЧТО ДАЛЬШЕ:</b>\n\n"
                f"1️⃣ Напиши @MaleficentR7\n"
                f"2️⃣ Укажи номер: <b>№{order_id}</b>\n"
                f"3️⃣ Согласуй детали и оплату\n"
                f"4️⃣ Мы запустим пиар\n\n"
                f"⚠️ <i>Без подтверждения админа заявка не запускается.</i>"
            )
            markup = telebot.types.InlineKeyboardMarkup(row_width=1)
            markup.add(
                telebot.types.InlineKeyboardButton("📩 Написать админу", url="https://t.me/MaleficentR7"),
                telebot.types.InlineKeyboardButton("⬅️ Назад", callback_data="order"),
            )
            bot.edit_message_text(text, call.message.chat.id, call.message.message_id,
                                  parse_mode='HTML', reply_markup=markup)
            try:
                bot.send_message(
                    ADMIN_ID,
                    f"🆕 <b>НОВАЯ ЗАЯВКА №{order_id}</b>\n\n"
                    f"👤 @{call.from_user.username or 'без ника'}\n"
                    f"🆔 <code>{call.from_user.id}</code>\n"
                    f"🛠 {service['name']}\n"
                    f"💰 {service['price']}₽\n\n"
                    f"/confirm {order_id}",
                    parse_mode='HTML'
                )
            except Exception:
                pass
        elif call.data == "admin_panel":
            if call.from_user.id != ADMIN_ID:
                bot.answer_callback_query(call.id, "❌ Доступ запрещён.")
                return
            bot.edit_message_text("⚙️ <b>АДМИН-ПАНЕЛЬ</b>", call.message.chat.id, call.message.message_id,
                                  parse_mode='HTML', reply_markup=admin_menu())
        elif call.data == "admin_stats":
            if call.from_user.id != ADMIN_ID:
                return
            count = get_users_count()
            bot.edit_message_text(f"📊 Пользователей: <b>{count}</b>",
                                  call.message.chat.id, call.message.message_id,
                                  parse_mode='HTML', reply_markup=admin_menu())
        elif call.data == "admin_users":
            if call.from_user.id != ADMIN_ID:
                return
            users = get_all_users()
            text = f"👥 Пользователи ({len(users)}):\n\n"
            for uid in users[:20]:
                text += f"• <code>{uid}</code>\n"
            bot.edit_message_text(text, call.message.chat.id, call.message.message_id,
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
        elif call.data == "admin_commands":
            if call.from_user.id != ADMIN_ID:
                return
            bot.edit_message_text(
                "🛠 <b>КОМАНДЫ</b>\n\n"
                "/stats — статистика\n"
                "/users — пользователи\n"
                "/myorders — заказы\n"
                "/confirm [id] — подтвердить\n"
                "/done [id] — выполнено\n"
                "/broadcast [текст] — рассылка\n"
                "/say [текст] — сообщение",
                call.message.chat.id, call.message.message_id,
                parse_mode='HTML', reply_markup=admin_menu()
            )
        bot.answer_callback_query(call.id)
    except Exception as e:
        logger.error(f"Ошибка callback: {e}")
        bot.answer_callback_query(call.id, "Ошибка")


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
        return "Ошибка установки вебхука", 500
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
