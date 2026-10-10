import os
import telebot
from flask import Flask, request

# Инициализация
BOT_TOKEN = os.getenv("BOT_TOKEN", "ВАШ_ТОКЕН")
bot = telebot.TeleBot(BOT_TOKEN, threaded=False) # threaded=False важно для Render [citation:2]
app = Flask(__name__)

# === ОБРАБОТЧИКИ КОМАНД ===
@bot.message_handler(commands=['start'])
def start_message(message):
    markup = telebot.types.InlineKeyboardMarkup()
    markup.row(telebot.types.InlineKeyboardButton("📜 Правила чата", callback_data="rules"))
    markup.row(telebot.types.InlineKeyboardButton("💰 Прайс на пиар", callback_data="price"))
    markup.row(telebot.types.InlineKeyboardButton("📩 Заказать пиар", callback_data="order"))
    
    bot.send_message(message.chat.id, 
        "👋 <b>Добро пожаловать в ПИАР ЧАТ | SAMP | CRMP | MTA!</b>\n\n"
        "📌 Здесь ты можешь заказать пиар своего проекта или задать вопрос.",
        parse_mode='HTML', reply_markup=markup)

@bot.callback_query_handler(func=lambda call: True)
def callback_query(call):
    if call.data == "rules":
        bot.send_message(call.message.chat.id, "📜 <b>ПРАВИЛА ПИАР ЧАТА</b>\n\n1. Уважение\n2. Без спама\n3. Без 18+", parse_mode='HTML')
    elif call.data == "price":
        bot.send_message(call.message.chat.id, "💰 <b>ПРАЙС НА ПИАР</b>\n\n📢 Пост — 50₽\n📢 Канал — 100₽", parse_mode='HTML')
    elif call.data == "order":
        bot.send_message(call.message.chat.id, "📩 <b>ЗАЯВКА</b>\n\nНапишите @MaleficentR7", parse_mode='HTML')
    bot.answer_callback_query(call.id)

@bot.message_handler(commands=['help'])
def help_message(message):
    bot.reply_to(message, "🆘 /start, /help")

@bot.message_handler(func=lambda message: True)
def echo_all(message):
    bot.reply_to(message, "🤔 Не понимаю команду. Напишите /help")

# === ВЕБХУК ДЛЯ RENDER ===
@app.route('/' + BOT_TOKEN, methods=['POST'])
def getMessage():
    json_string = request.get_data().decode('utf-8')
    update = telebot.types.Update.de_json(json_string)
    bot.process_new_updates([update])
    return "!", 200

@app.route("/")
def webhook():
    bot.remove_webhook()
    # URL вашего приложения на Render (он виден в дашборде)
    # Например: https://piar-chat-bot.onrender.com
    WEBHOOK_URL = os.getenv('WEBHOOK_URL') 
    bot.set_webhook(url=WEBHOOK_URL + BOT_TOKEN)
    return "Webhook set!", 200

if __name__ == "__main__":
    port = int(os.environ.get('PORT', 5000))
    app.run(host='0.0.0.0', port=port)
