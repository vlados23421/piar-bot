import os
import asyncio
import logging
from aiohttp import web
from aiogram import Bot, Dispatcher, Router, types, F
from aiogram.filters import Command
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode

BOT_TOKEN = os.getenv("BOT_TOKEN", "ВАШ_ТОКЕН")
ADMIN_ID = int(os.getenv("ADMIN_ID", "0"))
PORT = int(os.getenv("PORT", "8080"))

logging.basicConfig(level=logging.INFO)

bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()
router = Router()
dp.include_router(router)


# === ГЛАВНОЕ МЕНЮ ===
@router.message(Command("start"))
async def start_command(message: types.Message):
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📜 Правила чата", callback_data="rules")],
        [InlineKeyboardButton(text="💰 Прайс на пиар", callback_data="price")],
        [InlineKeyboardButton(text="📩 Заказать пиар", callback_data="order")],
        [InlineKeyboardButton(text="❓ FAQ", callback_data="faq")],
        [InlineKeyboardButton(text="📢 Наш чат", url="https://t.me/BeanRussiaOnline")],
        [InlineKeyboardButton(text="🛡 Связь с админом", url="https://t.me/MaleficentR7")],
    ])
    await message.answer(
        "👋 <b>Добро пожаловать в ПИАР ЧАТ | SAMP | CRMP | MTA!</b>\n\n"
        "📌 Здесь ты можешь:\n"
        "• Заказать пиар своего проекта\n"
        "• Узнать правила чата\n"
        "• Посмотреть прайс\n"
        "• Задать вопрос администрации\n\n"
        "👇 Выбери действие:",
        reply_markup=keyboard
    )


# === ПРАВИЛА ===
@router.callback_query(F.data == "rules")
async def rules_callback(callback: types.CallbackQuery):
    text = (
        "📜 <b>ПРАВИЛА ПИАР ЧАТА</b>\n\n"
        "1️⃣ <b>Уважение</b> — не оскорбляй других участников.\n\n"
        "2️⃣ <b>Без спама</b> — пиар только по правилам, не флуди.\n\n"
        "3️⃣ <b>Без рекламы 18+</b> — контент только для взрослой аудитории запрещён.\n\n"
        "4️⃣ <b>Без сторонних ссылок</b> — только согласованная реклама.\n\n"
        "5️⃣ <b>Подчиняйся админам</b> — их решения окончательны.\n\n"
        "⚠️ За нарушение — мут или бан без предупреждения."
    )
    await callback.message.edit_text(text, reply_markup=back_keyboard())
    await callback.answer()


# === ПРАЙС ===
@router.callback_query(F.data == "price")
async def price_callback(callback: types.CallbackQuery):
    text = (
        "💰 <b>ПРАЙС НА ПИАР</b>\n\n"
        "📢 <b>Пост в чате</b> — 50₽\n"
        "📢 <b>Пост в канале</b> — 100₽\n"
        "📢 <b>Авторассылка по 5 чатам</b> — 200₽\n"
        "📢 <b>Закреп на 24 часа</b> — 150₽\n"
        "📢 <b>Полный пакет (пост + рассылка + закреп)</b> — 500₽\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "💎 <b>Скидки:</b>\n"
        "• При заказе от 3 постов — 10%\n"
        "• Постоянным клиентам — 20%\n\n"
        "📩 Для заказа: /order"
    )
    await callback.message.edit_text(text, reply_markup=back_keyboard())
    await callback.answer()


# === ЗАЯВКА ===
@router.callback_query(F.data == "order")
async def order_callback(callback: types.CallbackQuery):
    text = (
        "📩 <b>ЗАКАЗ ПИАРА</b>\n\n"
        "Чтобы заказать пиар, напишите админу:\n"
        "👉 @MaleficentR7\n\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "📋 <b>Что указать:</b>\n"
        "1. Название вашего проекта\n"
        "2. Ссылка на проект (чат/канал)\n"
        "3. Тип пиара (пост, рассылка, закреп)\n"
        "4. Бюджет\n"
        "5. Желаемая дата размещения\n\n"
        "⏳ Ответ в течение 24 часов."
    )
    await callback.message.edit_text(text, reply_markup=back_keyboard())
    await callback.answer()


# === FAQ ===
@router.callback_query(F.data == "faq")
async def faq_callback(callback: types.CallbackQuery):
    text = (
        "❓ <b>ЧАСТЫЕ ВОПРОСЫ</b>\n\n"
        "<b>— Как заказать пиар?</b>\n"
        "Напишите @MaleficentR7 с описанием проекта.\n\n"
        "<b>— Сколько ждать ответа?</b>\n"
        "До 24 часов.\n\n"
        "<b>— Можно ли пиарить бесплатно?</b>\n"
        "Да, если проект соответствует правилам чата.\n\n"
        "<b>— Какие проекты запрещены?</b>\n"
        "18+, скам, читы, нарушающие правила Telegram.\n\n"
        "<b>— Как стать админом чата?</b>\n"
        "Подать заявку в @MaleficentR7."
    )
    await callback.message.edit_text(text, reply_markup=back_keyboard())
    await callback.answer()


# === КНОПКА «НАЗАД» ===
def back_keyboard():
    return InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="⬅️ Назад", callback_data="back")]
    ])


@router.callback_query(F.data == "back")
async def back_callback(callback: types.CallbackQuery):
    keyboard = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="📜 Правила чата", callback_data="rules")],
        [InlineKeyboardButton(text="💰 Прайс на пиар", callback_data="price")],
        [InlineKeyboardButton(text="📩 Заказать пиар", callback_data="order")],
        [InlineKeyboardButton(text="❓ FAQ", callback_data="faq")],
        [InlineKeyboardButton(text="📢 Наш чат", url="https://t.me/BeanRussiaOnline")],
        [InlineKeyboardButton(text="🛡 Связь с админом", url="https://t.me/MaleficentR7")],
    ])
    await callback.message.edit_text(
        "👋 <b>ПИАР ЧАТ | SAMP | CRMP | MTA</b>\n\n"
        "👇 Выбери действие:",
        reply_markup=keyboard
    )
    await callback.answer()


# === КОМАНДЫ ===
@router.message(Command("price"))
async def price_command(message: types.Message):
    await price_callback(message)


@router.message(Command("rules"))
async def rules_command(message: types.Message):
    await rules_callback(message)


@router.message(Command("order"))
async def order_command(message: types.Message):
    await order_callback(message)


@router.message(Command("help"))
async def help_command(message: types.Message):
    await message.answer(
        "🆘 <b>ПОМОЩЬ</b>\n\n"
        "/start — Главное меню\n"
        "/rules — Правила чата\n"
        "/price — Прайс на пиар\n"
        "/order — Заказать пиар\n"
        "/help — Справка\n\n"
        "📩 Поддержка: @MaleficentR7"
    )


@router.message()
async def echo_handler(message: types.Message):
    await message.answer(
        "🤔 Не понимаю команду.\n"
        "Напишите /help для списка команд."
    )


# === ВЕБ-СЕРВЕР ДЛЯ RENDER ===
async def health_check(request):
    return web.Response(text="ПИАР ЧАТ БОТ работает!")


async def start_web_server():
    app = web.Application()
    app.router.add_get("/", health_check)
    app.router.add_get("/health", health_check)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", PORT)
    await site.start()
    logging.info(f"Web server started on port {PORT}")


async def main():
    await start_web_server()
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
