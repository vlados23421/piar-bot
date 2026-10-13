import logging
import sqlite3
import telebot
from flask import Flask, request
from datetime import datetime, timedelta

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


def toggle_promo(code):
    conn = get_db(); c = conn.cursor()
    c.execute("UPDATE promos SET active = 1 - active WHERE code = ?", (code.upper(),))
    conn.commit(); conn.close()


def delete_promo(code):
    conn = get_db(); c = conn.cursor()
    c.execute("DELETE FROM promos WHERE code = ?", (code.upper(),))
    conn.commit(); conn.close()


# === СТАТУС БОТА ===
def set_bot_status(s): set_setting("bot_status", s)
def get_bot_status(): return get_setting("bot_status", "open")


# === ТЕКСТЫ ===
def get_text(key, default=""): return get_setting(f"text_{key}", default)
def set_text(key, value): set_setting(f"text_{key}", value)


def article_about():
    return get_text("about",
        "📖 <b>О ПРОЕКТЕ ПИАР ЧАТ</b>\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "ПИАР ЧАТ — это сервис продвижения игровых проектов на платформах <b>SAMP</b>, <b>CRMP</b> и <b>MTA</b>.\n\n"
        "Мы размещаем рекламу твоего проекта в сети активных пиар-чатов, где сидят реальные игроки.\n\n"
        "🔥 <b>НАШИ ПРЕИМУЩЕСТВА:</b>\n\n"
        "✅ Опытная команда\n"
        "✅ Честные правила\n"
        "✅ Быстрая поддержка\n"
        "✅ Гибкие цены от 20₽\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "📩 Админ: @MaleficentR7\n"
        "📢 Канал: @BeanRussiaOnline"
    )


def article_rules():
    return get_text("rules",
        "📜 <b>ПРАВИЛА ПИАР ЧАТА</b>\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "<b>1️⃣ УВАЖЕНИЕ</b>\n"
        "Не оскорбляй других участников, не разжигай конфликты.\n\n"
        "<b>2️⃣ БЕЗ СПАМА</b>\n"
        "Пиар только по правилам. Флуд запрещён.\n\n"
        "<b>3️⃣ БЕЗ 18+</b>\n"
        "Контент для взрослых запрещён.\n\n"
        "<b>4️⃣ БЕЗ СТОРОННИХ ССЫЛОК</b>\n"
        "Только согласованная реклама.\n\n"
        "<b>5️⃣ ПОДЧИНЯЙСЯ АДМИНАМ</b>\n"
        "Решения администрации окончательны.\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "⚠️ <b>За нарушение:</b> мут или бан без предупреждения.\n\n"
        "📩 Вопросы — @MaleficentR7"
    )


def article_faq():
    return get_text("faq",
        "❓ <b>ЧАСТЫЕ ВОПРОСЫ</b>\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "<b>— Как заказать?</b>\n"
        "Напиши @MaleficentR7.\n\n"
        "<b>— Сколько ждать?</b>\n"
        "До 24 часов.\n\n"
        "<b>— Как оплатить?</b>\n"
        "Переводом на ЮMoney.\n\n"
        "<b>— Можно ли бесплатно?</b>\n"
        "Да, если проект подходит под правила.\n\n"
        "<b>— Какие проекты запрещены?</b>\n"
        "18+, скам, читы.\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "📩 Не нашёл ответ? Пиши @MaleficentR7"
    )


def article_contact():
    return get_text("contact",
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


def article_price():
    services = get_services()
    text = "💰 <b>ПРАЙС НА ПИАР</b>\n\n━━━━━━━━━━━━━━━━━━━━\n\n"
    for key, s in services.items():
        if s["enabled"]:
            text += f"{s['name']} — <b>{s['price']}₽</b>\n"
    text += "\n━━━━━━━━━━━━━━━━━━━━\n\n"
    text += "💎 <b>Скидки:</b>\n"
    text += "🔸 От 3 заказов — 10%\n"
    text += "🔸 Постоянным клиентам — 20%\n\n"
    text += "🎁 Есть промокод? Введи его при заказе!\n\n"
    text += "📩 Заказать: /order"
    return text


def article_order():
    return (
        "📩 <b>ЗАКАЗ ПИАРА</b>\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "Выбери услугу ниже 👇\n\n"
        "🎁 <b>Есть промокод?</b>\n"
        "Напиши его после выбора услуги."
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
    m = telebot.types.InlineKeyboardMarkup(row_width=1)
    m.add(
        telebot.types.InlineKeyboardButton(f"📊 Статус: {status_text}", callback_data="admin_status"),
        telebot.types.InlineKeyboardButton("💰 Управление ценами", callback_data="admin_prices"),
        telebot.types.InlineKeyboardButton("🛠 Управление услугами", callback_data="admin_services"),
        telebot.types.InlineKeyboardButton("🎁 Промокоды", callback_data="admin_promos"),
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
    if get_bot_status() == "closed" and message.from_user.id != ADMIN_ID:
        bot.send_message(message.chat.id,
            "🔒 <b>Бот временно закрыт</b>\n\n"
            "Мы проводим техническое обслуживание.\n\n"
            "📢 Новости: @BeanRussiaOnline\n"
            "📩 Срочно: @MaleficentR7",
            parse_mode='HTML')
        return
    add_user(message.from_user)
    text = (
        "👋 <b>Добро пожаловать в ПИАР ЧАТ | SAMP | CRMP | MTA!</b>\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "📌 Здесь ты можешь:\n\n"
        "• Заказать пиар своего проекта\n"
        "• Узнать правила и прайс\n"
        "• Ввести промокод на скидку\n\n"
        "👇 <b>Выбери действие:</b>"
    )
    bot.send_message(message.chat.id, text, parse_mode='HTML', reply_markup=main_menu(message.from_user.id))


@bot.message_handler(commands=['help'])
def help_command(message):
    bot.send_message(message.chat.id,
        "🆘 <b>КОМАНДЫ</b>\n\n"
        "🏠 /start — меню\n"
        "📖 /about — о проекте\n"
        "💰 /price — прайс\n"
        "📩 /order — заказать\n"
        "📜 /rules — правила\n"
        "❓ /faq — FAQ\n"
        "📞 /contact — контакты\n"
        "🆘 /help — справка",
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
        bot.send_message(order[1], f"✅ <b>Заказ №{oid} подтверждён!</b>\n\nЗапускаем пиар в ближайшее время.", parse_mode='HTML')
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
        bot.send_message(order[1], f"🎉 <b>Заказ №{oid} выполнен!</b>\n\nСпасибо! 🤝", parse_mode='HTML')
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
            bot.reply_to(message, f"✅ Промокод <b>{code.upper()}</b> создан!\n\n"
                                  f"💰 Скидка: {discount}%\n"
                                  f"📊 Лимит: {max_uses}", parse_mode='HTML')
        else:
            bot.reply_to(message, "❌ Такой промокод уже существует.")
    except ValueError:
        bot.reply_to(message, "❌ Неверный формат.")


@bot.message_handler(func=lambda m: m.from_user.id != ADMIN_ID and m.reply_to_message is None and
                                   get_setting(f"waiting_promo_{m.from_user.id}") == "yes")
def handle_promo_apply(message):
    code = message.text.strip().upper()
    discount = check_promo(code)
    if discount:
        set_setting(f"promo_{message.from_user.id}", code)
        bot.reply_to(message, f"✅ Промокод <b>{code}</b> применён!\n\n💰 Скидка: <b>{discount}%</b>", parse_mode='HTML')
    else:
        bot.reply_to(message, f"❌ Промокод <b>{code}</b> не найден или неактивен.", parse_mode='HTML')
    set_setting(f"waiting_promo_{message.from_user.id}", "no")


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
        elif call.data == "enter_promo":
            set_setting(f"waiting_promo_{call.from_user.id}", "yes")
            bot.send_message(call.message.chat.id,
                "🎁 <b>ВВЕДИ ПРОМОКОД</b>\n\n"
                "Отправь его следующим сообщением.",
                parse_mode='HTML')
        elif call.data.startswith("buy_"):
            key = call.data.replace("buy_", "")
            services = get_services()
            service = services.get(key)
            if not service:
                return

            # Проверка промокода
            promo_code = get_setting(f"promo_{call.from_user.id}")
            price = service["price"]
            promo_text = ""

            if promo_code:
                discount = check_promo(promo_code)
                if discount:
                    new_price = int(price * (100 - discount) / 100)
                    promo_text = f"\n🎁 Промокод: <b>{promo_code}</b> (-{discount}%)\n💰 Было: <s>{price}₽</s>\n💵 Стало: <b>{new_price}₽</b>"
                    price = new_price
                    use_promo(promo_code)
                    set_setting(f"promo_{call.from_user.id}", "")

            order_id = create_order(call.from_user.id,
                                    call.from_user.username or call.from_user.first_name,
                                    service["name"], price)
            text = (
                f"📩 <b>ЗАЯВКА №{order_id}</b>\n\n"
                f"━━━━━━━━━━━━━━━━━━━━\n\n"
                f"🛠 Услуга: {service['name']}\n"
                f"💰 Сумма: <b>{price}₽</b>{promo_text}\n"
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
                bot.send_message(ADMIN_ID,
                    f"🆕 <b>НОВАЯ ЗАЯВКА №{order_id}</b>\n\n"
                    f"👤 @{call.from_user.username or 'без ника'}\n"
                    f"🆔 <code>{call.from_user.id}</code>\n"
                    f"🛠 {service['name']}\n"
                    f"💰 {price}₽{promo_text}\n\n"
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
            m = telebot.types.InlineKeyboardMarkup(row_width=1)
            for key, s in services.items():
                m.add(telebot.types.InlineKeyboardButton(f"{s['name']} — {s['price']}₽", callback_data=f"editprice_{key}"))
            m.add(telebot.types.InlineKeyboardButton("⬅️ Назад", callback_data="admin_panel"))
            bot.edit_message_text("💰 <b>УПРАВЛЕНИЕ ЦЕНАМИ</b>\n\nВыбери услугу:",
                                  call.message.chat.id, call.message.message_id,
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
                f"💰 <b>Изменение цены</b>\n\n"
                f"Услуга: {s['name']}\n"
                f"Текущая цена: <b>{s['price']}₽</b>\n\n"
                f"📝 Введите новую цену — ответьте на это сообщение числом.\n"
                f"KEY:{key}",
                call.message.chat.id, call.message.message_id, parse_mode='HTML')
        elif call.data == "admin_services":
            if call.from_user.id != ADMIN_ID:
                return
            services = get_services()
            m = telebot.types.InlineKeyboardMarkup(row_width=1)
            for key, s in services.items():
                status = "✅" if s["enabled"] else "❌"
                m.add(telebot.types.InlineKeyboardButton(f"{status} {s['name']}", callback_data=f"toggle_{key}"))
            m.add(telebot.types.InlineKeyboardButton("⬅️ Назад", callback_data="admin_panel"))
            bot.edit_message_text("🛠 <b>УПРАВЛЕНИЕ УСЛУГАМИ</b>\n\nНажми — вкл/выкл:",
                                  call.message.chat.id, call.message.message_id,
                                  parse_mode='HTML', reply_markup=m)
        elif call.data.startswith("toggle_"):
            if call.from_user.id != ADMIN_ID:
                return
            key = call.data.replace("toggle_", "")
            toggle_service(key)
            services = get_services()
            m = telebot.types.InlineKeyboardMarkup(row_width=1)
            for k, s in services.items():
                status = "✅" if s["enabled"] else "❌"
                m.add(telebot.types.InlineKeyboardButton(f"{status} {s['name']}", callback_data=f"toggle_{k}"))
            m.add(telebot.types.InlineKeyboardButton("⬅️ Назад", callback_data="admin_panel"))
            bot.edit_message_text("🛠 <b>УПРАВЛЕНИЕ УСЛУГАМИ</b>",
                                  call.message.chat.id, call.message.message_id,
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
            m.add(telebot.types.InlineKeyboardButton("➕ Создать промокод", callback_data="create_promo"))
            if promos:
                m.add(telebot.types.InlineKeyboardButton("🗑 Удалить все", callback_data="delete_all_promos"))
            m.add(telebot.types.InlineKeyboardButton("⬅️ Назад", callback_data="admin_panel"))
            bot.edit_message_text(text, call.message.chat.id, call.message.message_id,
                                  parse_mode='HTML', reply_markup=m)
        elif call.data == "create_promo":
            if call.from_user.id != ADMIN_ID:
                return
            bot.edit_message_text(
                "🎁 <b>СОЗДАНИЕ ПРОМОКОДА</b>\n\n"
                "Отправьте сообщение в формате:\n\n"
                "<code>КОД СКИДКА ЛИМИТ</code>\n\n"
                "Пример:\n"
                "<code>START 10 100</code>\n\n"
                "Это создаст промокод START со скидкой 10% на 100 использований.\n\n"
                "📝 Введите новый промокод — ответьте на это сообщение.",
                call.message.chat.id, call.message.message_id, parse_mode='HTML')
        elif call.data == "delete_all_promos":
            if call.from_user.id != ADMIN_ID:
                return
            for p in get_promos():
                delete_promo(p[0])
            bot.edit_message_text("🗑 Все промокоды удалены.",
                                  call.message.chat.id, call.message.message_id,
                                  parse_mode='HTML', reply_markup=admin_menu())
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
            bot.edit_message_text("📝 <b>РЕДАКТОР ТЕКСТОВ</b>\n\nЧто редактируем?",
                                  call.message.chat.id, call.message.message_id,
                                  parse_mode='HTML', reply_markup=m)
        elif call.data.startswith("edittext_"):
            if call.from_user.id != ADMIN_ID:
                return
            key = call.data.replace("edittext_", "")
            current = get_text(key, "(пусто)")
            bot.edit_message_text(
                f"📝 <b>Редактирование «{key}»</b>\n\n"
                f"Текущий текст:\n\n{current[:400]}...\n\n"
                f"📩 Введите новый текст — ответьте на это сообщение.\n"
                f"KEY:{key}",
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
                text = "📋 Заказов пока нет."
            else:
                text = "📋 <b>ПОСЛЕДНИЕ ЗАКАЗЫ</b>\n\n"
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
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port, threaded=True)
