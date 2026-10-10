import logging
import sqlite3
import telebot
from flask import Flask, request

# === НАСТРОЙКИ ===
BOT_TOKEN = "8337839229:AAH7EuRNbQK2xn74o1WiDa-TxZHdDA795tg"
WEBHOOK_URL = "https://piar-bot-5zlx.onrender.com"
ADMIN_ID = 8718572838

# === ЛОГИ ===
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# === БОТ И FLASK ===
bot = telebot.TeleBot(BOT_TOKEN, threaded=False)
app = Flask(__name__)

# === БАЗА ДАННЫХ ===
DB_PATH = "/tmp/users.db"


def init_db():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS users (
            user_id INTEGER PRIMARY KEY,
            username TEXT,
            first_name TEXT,
            joined_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)
    conn.commit()
    conn.close()


def add_user(user):
    try:
        conn = sqlite3.connect(DB_PATH)
        cursor = conn.cursor()
        cursor.execute(
            "INSERT OR IGNORE INTO users (user_id, username, first_name) VALUES (?, ?, ?)",
            (user.id, user.username or "", user.first_name or "")
        )
        conn.commit()
        conn.close()
    except Exception as e:
        logger.error(f"Ошибка добавления пользователя: {e}")


def get_all_users():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM users")
    users = [row[0] for row in cursor.fetchall()]
    conn.close()
    return users


def get_users_count():
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    cursor.execute("SELECT COUNT(*) FROM users")
    count = cursor.fetchone()[0]
    conn.close()
    return count


# === СТАТЬИ (HTML) ===
def article_about():
    return (
        "📖 <b>О ПРОЕКТЕ</b>\n"
        "ПИАР ЧАТ | SAMP | CRMP | MTA\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "Мы — сообщество, где игроки находят единомышленников "
        "и заказывают качественный пиар своих проектов.\n\n"
        "<b>🔥 НАШИ ПРЕИМУЩЕСТВА:</b>\n\n"
        "✅ <b>Опытная команда</b>\n"
        "Модераторы с опытом в CRMP и SAMP\n\n"
        "✅ <b>Честные правила</b>\n"
        "Все участники равны, без привилегий\n\n"
        "✅ <b>Быстрая поддержка</b>\n"
        "Отвечаем в течение 24 часов\n\n"
        "✅ <b>Гибкие цены</b>\n"
        "От 50₽ за пост, есть скидки\n\n"
        "✅ <b>Растущее сообщество</b>\n"
        "Новые участники каждый день\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "<b>📌 ЧТО МЫ ПРЕДЛАГАЕМ:</b>\n\n"
        "🔹 Посты в чате — 50₽\n"
        "🔹 Посты в канале — 100₽\n"
        "🔹 Авторассылка — 200₽\n"
        "🔹 Полный пакет — 500₽\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "<b>📩 СВЯЗАТЬСЯ С НАМИ:</b>\n\n"
        "🛡 Админ: @MaleficentR7\n"
        "📢 Наш чат: @BeanRussiaOnline\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "🤝 <i>Присоединяйся — здесь начинается твой пиар!</i>"
    )


def article_rules():
    return (
        "📜 <b>ПРАВИЛА ПИАР ЧАТА</b>\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "<b>1️⃣ УВАЖЕНИЕ</b>\n"
        "Не оскорбляй других участников, не разжигай конфликты.\n\n"
        "<b>2️⃣ БЕЗ СПАМА</b>\n"
        "Пиар только по правилам. Флуд и повторяющиеся сообщения запрещены.\n\n"
        "<b>3️⃣ БЕЗ 18+</b>\n"
        "Контент для взрослых, шок-контент и NSFW запрещены.\n\n"
        "<b>4️⃣ БЕЗ СТОРОННИХ ССЫЛОК</b>\n"
        "Только согласованная реклама. Ссылки — только через админа.\n\n"
        "<b>5️⃣ ПОДЧИНЯЙСЯ АДМИНАМ</b>\n"
        "Решения администрации окончательны и обжалованию не подлежат.\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "<b>⚠️ ЗА НАРУШЕНИЕ:</b>\n\n"
        "🔸 Предупреждение — за мелкие нарушения\n"
        "🔸 Мут (1–24 часа) — за спам и флуд\n"
        "🔸 Бан (7–30 дней) — за рекламу и оскорбления\n"
        "🔸 Перманентный бан — за мошенничество и слив\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "📩 Вопросы — @MaleficentR7"
    )


def article_price():
    return (
        "💰 <b>ПРАЙС НА ПИАР</b>\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "<b>📢 РАЗОВЫЕ УСЛУГИ:</b>\n\n"
        "🔹 Пост в чате — <b>50₽</b>\n"
        "🔹 Пост в канале — <b>100₽</b>\n"
        "🔹 Закреп на 24 часа — <b>150₽</b>\n"
        "🔹 Авторассылка по 5 чатам — <b>200₽</b>\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "<b>📦 ПАКЕТЫ (ВЫГОДНЕЕ):</b>\n\n"
        "🔹 Полный пакет — <b>500₽</b>\n"
        "<i>пост + рассылка + закреп</i>\n\n"
        "🔹 3 поста подряд — <b>400₽</b>\n"
        "<i>вместо 450₽ — экономия 50₽</i>\n\n"
        "🔹 5 постов подряд — <b>600₽</b>\n"
        "<i>вместо 750₽ — экономия 150₽</i>\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "<b>💎 СКИДКИ:</b>\n\n"
        "🔸 От 3 заказов — <b>10%</b>\n"
        "🔸 Постоянным клиентам — <b>20%</b>\n"
        "🔸 Партнёрам сообщества — <b>25%</b>\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "<b>📩 ЗАКАЗАТЬ:</b>\n"
        "👉 @MaleficentR7"
    )


def article_order():
    return (
        "📩 <b>ЗАКАЗ ПИАРА</b>\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "Чтобы заказать пиар, напишите админу:\n\n"
        "👉 <b>@MaleficentR7</b>\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "<b>📋 ЧТО УКАЗАТЬ В ЗАЯВКЕ:</b>\n\n"
        "1️⃣ Название проекта\n"
        "2️⃣ Ссылка на проект\n"
        "3️⃣ Тип пиара\n"
        "4️⃣ Бюджет\n"
        "5️⃣ Дата размещения\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "⏳ <i>Ответ в течение 24 часов.</i>"
    )


def article_faq():
    return (
        "❓ <b>ЧАСТЫЕ ВОПРОСЫ</b>\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "<b>Как заказать пиар?</b>\n"
        "Напишите @MaleficentR7 с описанием проекта.\n\n"
        "<b>Сколько ждать ответа?</b>\n"
        "До 24 часов.\n\n"
        "<b>Можно ли пиарить бесплатно?</b>\n"
        "Да, если проект подходит под правила.\n\n"
        "<b>Какие проекты запрещены?</b>\n"
        "18+, скам, читы, нарушающие правила Telegram.\n\n"
        "<b>Как стать админом?</b>\n"
        "Подать заявку в @MaleficentR7.\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "📩 <i>Не нашёл ответ? Напиши нам!</i>"
    )


# === КЛАВИАТУРЫ ===
def menu_after_article():
    """Маленькое меню под статьёй."""
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
        telebot.types.InlineKeyboardButton("🏠 Главная", callback_data="back"),
    )
    return markup


def main_menu(user_id):
    markup = telebot.types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        telebot.types.InlineKeyboardButton("📖 О проекте", callback_data="about"),
        telebot.types.InlineKeyboardButton("📜 Правила чата", callback_data="rules"),
        telebot.types.InlineKeyboardButton("💰 Прайс на пиар", callback_data="price"),
        telebot.types.InlineKeyboardButton("📩 Заказать пиар", callback_data="order"),
        telebot.types.InlineKeyboardButton("❓ FAQ", callback_data="faq"),
        telebot.types.InlineKeyboardButton("📢 Наш чат", url="https://t.me/BeanRussiaOnline"),
        telebot.types.InlineKeyboardButton("🛡 Связь с админом", url="https://t.me/MaleficentR7"),
    )
    if user_id == ADMIN_ID:
        markup.add(telebot.types.InlineKeyboardButton("⚙️ Админ-панель", callback_data="admin_panel"))
    return markup


def admin_menu():
    markup = telebot.types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        telebot.types.InlineKeyboardButton("📊 Статистика", callback_data="admin_stats"),
        telebot.types.InlineKeyboardButton("👥 Пользователи", callback_data="admin_users"),
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
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "📌 Здесь ты можешь:\n\n"
        "• Заказать пиар своего проекта\n"
        "• Узнать правила чата\n"
        "• Посмотреть прайс\n"
        "• Задать вопрос администрации\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "👇 <b>Выбери действие:</b>"
    )
    bot.send_message(message.chat.id, text, parse_mode='HTML', reply_markup=main_menu(message.from_user.id))


@bot.message_handler(commands=['help'])
def help_command(message):
    text = (
        "🆘 <b>ПОМОЩЬ</b>\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "/start — Главное меню\n"
        "/about — О проекте\n"
        "/rules — Правила чата\n"
        "/price — Прайс на пиар\n"
        "/order — Заказать пиар\n"
        "/faq — Частые вопросы\n"
        "/help — Справка\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "📩 Поддержка: @MaleficentR7"
    )
    bot.send_message(message.chat.id, text, parse_mode='HTML')


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
    bot.send_message(message.chat.id, article_order(), parse_mode='HTML', reply_markup=menu_after_article())


@bot.message_handler(commands=['faq'])
def faq_command(message):
    bot.send_message(message.chat.id, article_faq(), parse_mode='HTML', reply_markup=menu_after_article())


# === АДМИН-КОМАНДЫ ===
@bot.message_handler(commands=['stats'])
def stats_command(message):
    if message.from_user.id != ADMIN_ID:
        bot.reply_to(message, "❌ У вас нет доступа.")
        return
    count = get_users_count()
    bot.reply_to(
        message,
        f"📊 <b>СТАТИСТИКА</b>\n\n"
        f"👥 Пользователей: <b>{count}</b>\n"
        f"🟢 Бот работает стабильно.",
        parse_mode='HTML'
    )


@bot.message_handler(commands=['users'])
def users_command(message):
    if message.from_user.id != ADMIN_ID:
        return
    users = get_all_users()
    text = f"👥 <b>ПОЛЬЗОВАТЕЛИ ({len(users)})</b>\n\n"
    for uid in users[:50]:
        text += f"• <code>{uid}</code>\n"
    if len(users) > 50:
        text += f"\n...и ещё {len(users) - 50}"
    bot.send_message(message.chat.id, text, parse_mode='HTML')


@bot.message_handler(commands=['broadcast'])
def broadcast_command(message):
    if message.from_user.id != ADMIN_ID:
        return
    text = message.text.replace('/broadcast ', '', 1)
    if not text or text == '/broadcast':
        bot.reply_to(message, "📝 Используйте: /broadcast [текст]")
        return
    users = get_all_users()
    success = 0
    failed = 0
    for uid in users:
        try:
            bot.send_message(uid, text, parse_mode='HTML')
            success += 1
        except Exception:
            failed += 1
    bot.reply_to(message, f"📢 Рассылка завершена.\n✅ Успешно: {success}\n❌ Ошибок: {failed}")


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
        logger.info(f"Callback: {call.data} от {call.from_user.id}")

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
                                  parse_mode='HTML', reply_markup=menu_after_article())
        elif call.data == "faq":
            bot.edit_message_text(article_faq(), call.message.chat.id, call.message.message_id,
                                  parse_mode='HTML', reply_markup=menu_after_article())
        elif call.data == "back":
            text = (
                "👋 <b>ПИАР ЧАТ | SAMP | CRMP | MTA</b>\n\n"
                "👇 <b>Выбери действие:</b>"
            )
            bot.edit_message_text(text, call.message.chat.id, call.message.message_id,
                                  parse_mode='HTML', reply_markup=main_menu(call.from_user.id))
        elif call.data == "admin_panel":
            if call.from_user.id != ADMIN_ID:
                bot.answer_callback_query(call.id, "❌ Доступ запрещён.")
                return
            bot.edit_message_text(
                "⚙️ <b>АДМИН-ПАНЕЛЬ</b>\n\nВыбери действие:",
                call.message.chat.id, call.message.message_id,
                parse_mode='HTML', reply_markup=admin_menu()
            )
        elif call.data == "admin_stats":
            if call.from_user.id != ADMIN_ID:
                return
            count = get_users_count()
            bot.edit_message_text(
                f"📊 <b>СТАТИСТИКА</b>\n\n👥 Пользователей: <b>{count}</b>",
                call.message.chat.id, call.message.message_id,
                parse_mode='HTML', reply_markup=admin_menu()
            )
        elif call.data == "admin_users":
            if call.from_user.id != ADMIN_ID:
                return
            users = get_all_users()
            text = f"👥 <b>ПОЛЬЗОВАТЕЛИ ({len(users)})</b>\n\n"
            for uid in users[:20]:
                text += f"• <code>{uid}</code>\n"
            bot.edit_message_text(text, call.message.chat.id, call.message.message_id,
                                  parse_mode='HTML', reply_markup=admin_menu())
        elif call.data == "admin_broadcast":
            if call.from_user.id != ADMIN_ID:
                return
            bot.edit_message_text(
                "📢 <b>РАССЫЛКА</b>\n\nИспользуйте команду:\n<code>/broadcast [текст]</code>",
                call.message.chat.id, call.message.message_id,
                parse_mode='HTML', reply_markup=admin_menu()
            )
        elif call.data == "admin_commands":
            if call.from_user.id != ADMIN_ID:
                return
            bot.edit_message_text(
                "🛠 <b>АДМИН-КОМАНДЫ</b>\n\n"
                "/stats — статистика\n"
                "/users — список пользователей\n"
                "/broadcast [текст] — рассылка\n"
                "/say [текст] — сообщение от бота",
                call.message.chat.id, call.message.message_id,
                parse_mode='HTML', reply_markup=admin_menu()
            )

        bot.answer_callback_query(call.id)
    except Exception as e:
        logger.error(f"Ошибка callback: {e}")
        bot.answer_callback_query(call.id, "Ошибка. Попробуйте позже.")


# === ПРИЁМ СООБЩЕНИЙ ===
@bot.message_handler(func=lambda message: True)
def echo_handler(message):
    if message.text and not message.text.startswith('/'):
        bot.reply_to(
            message,
            "🤔 Не понимаю команду.\n"
            "Напишите /help для списка команд."
        )


# === ВЕБХУК ===
@app.route('/' + BOT_TOKEN, methods=['POST'])
def get_message():
    try:
        json_string = request.get_data().decode('utf-8')
        update = telebot.types.Update.de_json(json_string)
        bot.process_new_updates([update])
        return "OK", 200
    except Exception as e:
        logger.error(f"Ошибка обработки: {e}")
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
            return f"Webhook установлен на {WEBHOOK_URL}/{BOT_TOKEN}", 200
        return "Ошибка установки вебхука", 500
    except Exception as e:
        logger.error(f"Ошибка установки вебхука: {e}")
        return f"Ошибка: {e}", 500


@app.route("/health")
def health():
    return "Bot is alive!", 200


# === ЗАПУСК ===
if __name__ == "__main__":
    import os
    init_db()
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
