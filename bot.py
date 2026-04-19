import asyncio
import os
import logging
from datetime import datetime, timedelta
from aiogram import Bot, Dispatcher, types
from aiogram.contrib.middlewares.logging import LoggingMiddleware
from aiogram.utils import executor
from flask import Flask

# --- Настройки ---
BOT_TOKEN = os.environ.get("BOT_TOKEN")
if not BOT_TOKEN:
    raise ValueError("Не установлена переменная окружения BOT_TOKEN")

logging.basicConfig(level=logging.INFO)

# --- Инициализация бота ---
bot = Bot(token=BOT_TOKEN)
dp = Dispatcher(bot)
dp.middleware.setup(LoggingMiddleware())

# --- Структуры данных ---
pairs = {}
queue = []
user_info = {}
last_activity = {}
user_states = {}  # Для хранения временных данных (имя, возраст)

# --- Проверка бездействия ---
async def check_inactivity():
    while True:
        await asyncio.sleep(60)
        now = datetime.now()
        to_remove = []
        for user_id, last_active in list(last_activity.items()):
            if now - last_active > timedelta(minutes=10):
                if user_id in pairs:
                    partner = pairs[user_id]
                    try:
                        await bot.send_message(partner, "⏰ Собеседник неактивен более 10 минут. Чат закрыт.")
                        await bot.send_message(user_id, "⏰ Чат закрыт из-за бездействия.")
                    except:
                        pass
                    if partner in pairs:
                        del pairs[partner]
                    if user_id in pairs:
                        del pairs[user_id]
                    to_remove.extend([user_id, partner])
                elif user_id in queue:
                    if user_id in queue:
                        queue.remove(user_id)
                    to_remove.append(user_id)
        for uid in to_remove:
            if uid in last_activity:
                del last_activity[uid]

# --- Команда /start ---
@dp.message_handler(commands=['start'])
async def cmd_start(message: types.Message):
    user_id = message.from_user.id
    
    if user_id not in user_info:
        user_states[user_id] = {'step': 'name'}
        await message.answer(
            "🔒 *Анонимный чат*\n\nДля начала общения представьтесь (можно вымышленное имя):\n\nВведите ваше имя:",
            parse_mode="Markdown"
        )
        return
    
    if user_id in pairs:
        await message.answer("Вы уже в чате. /next — новый собеседник, /stop — выйти")
        return
    
    if user_id in queue:
        await message.answer("Вы уже в очереди. Ждите... /stop чтобы выйти")
        return
    
    if queue:
        partner_id = queue.pop(0)
        pairs[user_id] = partner_id
        pairs[partner_id] = user_id
        last_activity[user_id] = datetime.now()
        last_activity[partner_id] = datetime.now()
        user_info_str = f"{user_info[user_id]['name']}, {user_info[user_id]['age']} лет"
        partner_info_str = f"{user_info[partner_id]['name']}, {user_info[partner_id]['age']} лет"
        try:
            await bot.send_message(partner_id, f"✅ *Собеседник найден!*\n\n📝 Собеседник: {user_info_str}\n\n🤫 Общение полностью анонимное.\n⏰ Чат закроется через 10 минут бездействия.\n\n/next — новый собеседник\n/stop — выйти", parse_mode="Markdown")
        except:
            pass
        await message.answer(f"✅ *Собеседник найден!*\n\n📝 Собеседник: {partner_info_str}\n\n🤫 Общение полностью анонимное.\n⏰ Чат закроется через 10 минут бездействия.\n\n/next — новый собеседник\n/stop — выйти", parse_mode="Markdown")
    else:
        queue.append(user_id)
        last_activity[user_id] = datetime.now()
        await message.answer(f"⏳ *Ищем собеседника...*\n\n📝 Вы: {user_info[user_id]['name']}, {user_info[user_id]['age']} лет\n\nКак только найдём — сообщим.\n/stop — выйти", parse_mode="Markdown")

# --- Обработка имени и возраста ---
@dp.message_handler(lambda message: message.from_user.id in user_states)
async def process_registration(message: types.Message):
    user_id = message.from_user.id
    state = user_states.get(user_id, {})
    
    if state.get('step') == 'name':
        name = message.text.strip()
        if len(name) < 2 or len(name) > 30:
            await message.answer("Имя должно быть от 2 до 30 символов. Попробуйте ещё раз:")
            return
        user_states[user_id] = {'step': 'age', 'name': name}
        await message.answer("📅 Теперь укажите ваш возраст (число от 1 до 120):")
    
    elif state.get('step') == 'age':
        try:
            age = int(message.text.strip())
            if age < 1 or age > 120:
                raise ValueError
        except:
            await message.answer("Пожалуйста, введите корректное число (от 1 до 120):")
            return
        user_info[user_id] = {"name": state['name'], "age": age}
        del user_states[user_id]
        await message.answer(f"✅ *Регистрация завершена!*\n\n📝 Вы: {state['name']}, {age} лет\n\nТеперь напишите /start для поиска собеседника", parse_mode="Markdown")

# --- Команда /next ---
@dp.message_handler(commands=['next'])
async def cmd_next(message: types.Message):
    user_id = message.from_user.id
    if user_id not in user_info:
        await message.answer("Сначала напишите /start и представьтесь")
        return
    if user_id in pairs:
        partner = pairs[user_id]
        if user_id in pairs:
            del pairs[user_id]
        if partner in pairs:
            del pairs[partner]
        try:
            await bot.send_message(partner, "🚫 Собеседник покинул чат. /start для нового поиска")
        except:
            pass
        if partner in last_activity:
            del last_activity[partner]
    if user_id in queue:
        queue.remove(user_id)
    if user_id in last_activity:
        del last_activity[user_id]
    await cmd_start(message)

# --- Команда /stop ---
@dp.message_handler(commands=['stop'])
async def cmd_stop(message: types.Message):
    user_id = message.from_user.id
    if user_id in pairs:
        partner = pairs[user_id]
        if user_id in pairs:
            del pairs[user_id]
        if partner in pairs:
            del pairs[partner]
        try:
            await bot.send_message(partner, "🚫 Собеседник завершил чат. /start для нового")
        except:
            pass
        if partner in last_activity:
            del last_activity[partner]
    if user_id in queue:
        queue.remove(user_id)
    if user_id in last_activity:
        del last_activity[user_id]
    await message.answer("Вы вышли из чата. /start чтобы найти собеседника")

# --- Пересылка сообщений ---
@dp.message_handler()
async def forward_message(message: types.Message):
    user_id = message.from_user.id
    last_activity[user_id] = datetime.now()
    
    if user_id not in user_info:
        await message.answer("Сначала напишите /start и представьтесь")
        return
    if user_id in pairs:
        partner_id = pairs[user_id]
        try:
            if message.text:
                await bot.send_message(partner_id, message.text)
            elif message.photo:
                await bot.send_photo(partner_id, message.photo[-1].file_id, caption=message.caption)
            elif message.video:
                await bot.send_video(partner_id, message.video.file_id, caption=message.caption)
            elif message.voice:
                await bot.send_voice(partner_id, message.voice.file_id)
            elif message.sticker:
                await bot.send_sticker(partner_id, message.sticker.file_id)
            else:
                await message.copy_to(partner_id)
        except Exception:
            await message.answer("❌ Не удалось отправить сообщение. Собеседник недоступен.")
            if user_id in pairs:
                partner = pairs[user_id]
                if partner in pairs:
                    del pairs[partner]
                del pairs[user_id]
    else:
        await message.answer("Вы не в чате. Напишите /start для поиска собеседника")

# --- Flask для Render ---
flask_app = Flask(__name__)

@flask_app.route('/')
def health_check():
    return "Анонимный чат-бот работает!", 200

@flask_app.route('/health')
def health():
    return "OK", 200

def run_flask():
    port = int(os.environ.get("PORT", 5000))
    flask_app.run(host="0.0.0.0", port=port)

# --- Запуск ---
if __name__ == "__main__":
    import threading
    web_thread = threading.Thread(target=run_flask)
    web_thread.start()
    
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    loop.create_task(check_inactivity())
    executor.start_polling(dp, skip_updates=True)
