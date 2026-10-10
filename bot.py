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
DB_PATH = "/tmp/users.db"  # /tmp — потому что на Render постоянная папка не сохраняется


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


# === КЛАВИАТУРЫ ===
def main_menu(user_id):
    markup = telebot.types.InlineKeyboardMarkup(row_width=1)
    markup.add(
        telebot.types.InlineKeyboardButton("📜 Правила чата", callback_data="rules"),
        telebot.types.InlineKeyboardButton("💰 Прайс на пиар", callback_data="price"),
        telebot.types.InlineKeyboardButton("📩 Заказать пиар", callback_data="order"),
        telebot.types.InlineKeyboardButton("❓ FAQ", callback_data="faq"),
        telebot.types.InlineKeyboardButton("📢 Наш чат", url="https://t.me/BeanRussiaOnline"),
        telebot.types.InlineKeyboardButton("🛡 Связь с админом", url="https://t.me/MaleficentR7"),
    )
    # Добавляем кнопку админ-панели ТОЛЬКО для админа
    if user_id == ADMIN_ID:
        markup.add(telebot.types.InlineKeyboardButton("⚙️ Админ-панель", callback_data="admin_panel"))
    return markup


def back_menu():
    markup = telebot.types.InlineKeyboardMarkup()
    markup.add(telebot.types.InlineKeyboardButton("⬅️ Назад", callback_data="back"))
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
        "📌 Здесь ты можешь:\n"
        "• Заказать пиар своего проекта\n"
        "• Узнать правила чата\n"
        "• Посмотреть прайс\n"
        "• Задать вопрос администрации\n\n"
        "👇 <b>Выбери действие:</b>"
    )
    bot.send_message(message.chat.id, text, parse_mode='HTML', reply_markup=main_menu(message.from_user.id))


@bot.message_handler(commands=['help'])
def help_command(message):
    text = (
        "🆘 <b>ПОМОЩЬ</b>\n\n"
        "/start — Главное меню\n"
        "/rules — Правила чата\n"
        "/price — Прайс на пиар\n"
        "/order — Заказать пиар\n"
        "/faq — Частые вопросы\n"
        "/help — Справка\n\n"
        "📩 Поддержка: @MaleficentR7"
    )
    bot.send_message(message.chat.id, text, parse_mode='HTML')


@bot.message_handler(commands=['rules'])
def rules_command(message):
    send_rules(message.chat.id)


@bot.message_handler(commands=['price'])
def price_command(message):
    send_price(message.chat.id)


@bot.message_handler(commands=['order'])
def order_command(message):
    send_order(message.chat.id)


@bot.message_handler(commands=['faq'])
def faq_command(message):
    send_faq(message.chat.id)


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
        f"👥 Всего пользователей: <b>{count}</b>\n"
        f"🟢 Бот работает стабильно.",
        parse_mode='HTML'
    )


@bot.message_handler(commands=['users'])
def users_command(message):
    if message.from_user.id != ADMIN_ID:
        return
    users = get_all_users()
    text = f"👥 <b>ПОЛЬЗОВАТЕЛИ ({len(users)})</b>\n\n"
    for uid in users[:50]:  # максимум 50
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

        # Обычные кнопки
        if call.data == "rules":
            send_rules(call.message.chat.id, edit=True, message_id=call.message.message_id)
        elif call.data == "price":
            send_price(call.message.chat.id, edit=True, message_id=call.message.message_id)
        elif call.data == "order":
            send_order(call.message.chat.id, edit=True, message_id=call.message.message_id)
        elif call.data == "faq":
            send_faq(call.message.chat.id, edit=True, message_id=call.message.message_id)
        elif call.data == "back":
            text = "👋 <b>ПИАР ЧАТ | SAMP | CRMP | MTA</b>\n\n👇 <b>Выбери действие:</b>"
            bot.edit_message_text(
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                text=text,
                parse_mode='HTML',
                reply_markup=main_menu(call.from_user.id)
            )

        # Админ-кнопки (только для админа)
        elif call.data == "admin_panel":
            if call.from_user.id != ADMIN_ID:
                bot.answer_callback_query(call.id, "❌ Доступ запрещён.")
                return
            bot.edit_message_text(
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                text="⚙️ <b>АДМИН-ПАНЕЛЬ</b>\n\nВыбери действие:",
                parse_mode='HTML',
                reply_markup=admin_menu()
            )
        elif call.data == "admin_stats":
            if call.from_user.id != ADMIN_ID:
                return
            count = get_users_count()
            bot.edit_message_text(
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                text=f"📊 <b>СТАТИСТИКА</b>\n\n👥 Пользователей: <b>{count}</b>",
                parse_mode='HTML',
                reply_markup=admin_menu()
            )
        elif call.data == "admin_users":
            if call.from_user.id != ADMIN_ID:
                return
            users = get_all_users()
            text = f"👥 <b>ПОЛЬЗОВАТЕЛИ ({len(users)})</b>\n\n"
            for uid in users[:20]:
                text += f"• <code>{uid}</code>\n"
            bot.edit_message_text(
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                text=text,
                parse_mode='HTML',
                reply_markup=admin_menu()
            )
        elif call.data == "admin_broadcast":
            if call.from_user.id != ADMIN_ID:
                return
            bot.edit_message_text(
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                text="📢 <b>РАССЫЛКА</b>\n\nИспользуйте команду:\n<code>/broadcast [текст]</code>",
                parse_mode='HTML',
                reply_markup=admin_menu()
            )
        elif call.data == "admin_commands":
            if call.from_user.id != ADMIN_ID:
                return
            bot.edit_message_text(
                chat_id=call.message.chat.id,
                message_id=call.message.message_id,
                text=(
                    "🛠 <b>АДМИН-КОМАНДЫ</b>\n\n"
                    "/stats — статистика\n"
                    "/users — список пользователей\n"
                    "/broadcast [текст] — рассылка\n"
                    "/say [текст] — сообщение от бота"
                ),
                parse_mode='HTML',
                reply_markup=admin_menu()
            )

        bot.answer_callback_query(call.id)
    except Exception as e:
        logger.error(f"Ошибка callback: {e}")
        bot.answer_callback_query(call.id, "Ошибка. Попробуйте позже.")


# === ФУНКЦИИ ОТПРАВКИ ===
def send_rules(chat_id, edit=False, message_id=None):
    text = (
        "📜 <b>ПРАВИЛА ПИАР ЧАТА</b>\n\n"
        "1️⃣ <b>Уважение</b> — не оскорбляй других участников.\n\n"
        "2️⃣ <b>Без спама</b> — пиар только по правилам.\n\n"
        "3️⃣ <b>Без 18+</b> — контент для взрослых запрещён.\n\n"
        "4️⃣ <b>Без сторонних ссылок</b> — только согласованная реклама.\n\n"
        "5️⃣ <b>Подчиняйся админам</b> — их решения окончательны.\n\n"
        "⚠️ За нарушение — мут или бан без предупреждения."
    )
    if edit:
        bot.edit_message_text(chat_id, message_id, text, parse_mode='HTML', reply_markup=back_menu())
    else:
        bot.send_message(chat_id, text, parse_mode='HTML', reply_markup=back_menu())


def send_price(chat_id, edit=False, message_id=None):
    text = (
        "💰 <b>ПРАЙС НА ПИАР</b>\n\n"
        "📢 <b>Пост в чате</b> — 50₽\n"
        "📢 <b>Пост в канале</b> — 100₽\n"
        "📢 <b>Авторассылка по 5 чатам</b> — 200₽\n"
        "📢 <b>Закреп на 24 часа</b> — 150₽\n"
        "📢 <b>Полный пакет</b> — 500₽\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "💎 <b>Скидки:</b>\n"
        "• От 3 постов — 10%\n"
        "• Постоянным клиентам — 20%\n\n"
        "📩 Для заказа: /order"
    )
    if edit:
        bot.edit_message_text(chat_id, message_id, text, parse_mode='HTML', reply_markup=back_menu())
    else:
        bot.send_message(chat_id, text, parse_mode='HTML', reply_markup=back_menu())


def send_order(chat_id, edit=False, message_id=None):
    text = (
        "📩 <b>ЗАКАЗ ПИАРА</b>\n\n"
        "Чтобы заказать пиар, напишите админу:\n"
        "👉 @MaleficentR7\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "📋 <b>Что указать:</b>\n"
        "1. Название проекта\n"
        "2. Ссылка на проект\n"
        "3. Тип пиара\n"
        "4. Бюджет\n"
        "5. Дата размещения\n\n"
        "⏳ Ответ в течение 24 часов."
    )
    if edit:
        bot.edit_message_text(chat_id, message_id, text, parse_mode='HTML', reply_markup=back_menu())
    else:
        bot.send_message(chat_id, text, parse_mode='HTML', reply_markup=back_menu())


def send_faq(chat_id, edit=False, message_id=None):
    text = (
        "❓ <b>ЧАСТЫЕ ВОПРОСЫ</b>\n\n"
        "<b>— Как заказать пиар?</b>\n"
        "Напишите @MaleficentR7.\n\n"
        "<b>— Сколько ждать ответа?</b>\n"
        "До 24 часов.\n\n"
        "<b>— Можно ли бесплатно?</b>\n"
        "Да, если проект подходит под правила.\n\n"
        "<b>— Какие проекты запрещены?</b>\n"
        "18+, скам, читы.\n\n"
        "<b>— Как стать админом?</b>\n"
        "Подать заявку в @MaleficentR7."
    )
    if edit:
        bot.edit_message_text(chat_id, message_id, text, parse_mode='HTML', reply_markup=back_menu())
    else:
        bot.send_message(chat_id, text, parse_mode='HTML', reply_markup=back_menu())


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
