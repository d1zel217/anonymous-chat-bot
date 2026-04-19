import os
import logging
from datetime import datetime, timedelta
from telegram import Update, ParseMode
from telegram.ext import Updater, CommandHandler, MessageHandler, Filters, CallbackContext

# --- Настройки ---
BOT_TOKEN = os.environ.get("BOT_TOKEN")
if not BOT_TOKEN:
    raise ValueError("Не установлена переменная окружения BOT_TOKEN")

logging.basicConfig(level=logging.INFO)

# --- Структуры данных ---
pairs = {}
queue = []
user_info = {}
last_activity = {}
user_states = {}

# --- Проверка бездействия (в отдельном потоке) ---
def check_inactivity(context: CallbackContext):
    now = datetime.now()
    to_remove = []
    for user_id, last_active in list(last_activity.items()):
        if now - last_active > timedelta(minutes=10):
            if user_id in pairs:
                partner = pairs[user_id]
                try:
                    context.bot.send_message(partner, "⏰ Собеседник неактивен более 10 минут. Чат закрыт.")
                    context.bot.send_message(user_id, "⏰ Чат закрыт из-за бездействия.")
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
def start(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    
    if user_id not in user_info:
        user_states[user_id] = {'step': 'name'}
        update.message.reply_text(
            "🔒 *Анонимный чат*\n\nДля начала общения представьтесь (можно вымышленное имя):\n\nВведите ваше имя:",
            parse_mode=ParseMode.MARKDOWN
        )
        return
    
    if user_id in pairs:
        update.message.reply_text("Вы уже в чате. /next — новый собеседник, /stop — выйти")
        return
    
    if user_id in queue:
        update.message.reply_text("Вы уже в очереди. Ждите... /stop чтобы выйти")
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
            context.bot.send_message(partner_id, f"✅ *Собеседник найден!*\n\n📝 Собеседник: {user_info_str}\n\n🤫 Общение полностью анонимное.\n⏰ Чат закроется через 10 минут бездействия.\n\n/next — новый собеседник\n/stop — выйти", parse_mode=ParseMode.MARKDOWN)
        except:
            pass
        update.message.reply_text(f"✅ *Собеседник найден!*\n\n📝 Собеседник: {partner_info_str}\n\n🤫 Общение полностью анонимное.\n⏰ Чат закроется через 10 минут бездействия.\n\n/next — новый собеседник\n/stop — выйти", parse_mode=ParseMode.MARKDOWN)
    else:
        queue.append(user_id)
        last_activity[user_id] = datetime.now()
        update.message.reply_text(f"⏳ *Ищем собеседника...*\n\n📝 Вы: {user_info[user_id]['name']}, {user_info[user_id]['age']} лет\n\nКак только найдём — сообщим.\n/stop — выйти", parse_mode=ParseMode.MARKDOWN)

# --- Обработка текста (регистрация) ---
def handle_text(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    last_activity[user_id] = datetime.now()
    
    # Регистрация нового пользователя
    if user_id in user_states:
        state = user_states[user_id]
        
        if state.get('step') == 'name':
            name = update.message.text.strip()
            if len(name) < 2 or len(name) > 30:
                update.message.reply_text("Имя должно быть от 2 до 30 символов. Попробуйте ещё раз:")
                return
            user_states[user_id] = {'step': 'age', 'name': name}
            update.message.reply_text("📅 Теперь укажите ваш возраст (число от 1 до 120):")
        
        elif state.get('step') == 'age':
            try:
                age = int(update.message.text.strip())
                if age < 1 or age > 120:
                    raise ValueError
            except:
                update.message.reply_text("Пожалуйста, введите корректное число (от 1 до 120):")
                return
            user_info[user_id] = {"name": state['name'], "age": age}
            del user_states[user_id]
            update.message.reply_text(f"✅ *Регистрация завершена!*\n\n📝 Вы: {state['name']}, {age} лет\n\nТеперь напишите /start для поиска собеседника", parse_mode=ParseMode.MARKDOWN)
        return
    
    # Если пользователь не зарегистрирован
    if user_id not in user_info:
        update.message.reply_text("Сначала напишите /start и представьтесь")
        return
    
    # Пересылка сообщений
    if user_id in pairs:
        partner_id = pairs[user_id]
        try:
            if update.message.text:
                context.bot.send_message(partner_id, update.message.text)
            elif update.message.photo:
                context.bot.send_photo(partner_id, update.message.photo[-1].file_id, caption=update.message.caption)
            elif update.message.video:
                context.bot.send_video(partner_id, update.message.video.file_id, caption=update.message.caption)
            elif update.message.voice:
                context.bot.send_voice(partner_id, update.message.voice.file_id)
            elif update.message.sticker:
                context.bot.send_sticker(partner_id, update.message.sticker.file_id)
        except Exception:
            update.message.reply_text("❌ Не удалось отправить сообщение. Собеседник недоступен.")
            if user_id in pairs:
                partner = pairs[user_id]
                if partner in pairs:
                    del pairs[partner]
                del pairs[user_id]
    else:
        update.message.reply_text("Вы не в чате. Напишите /start для поиска собеседника")

# --- Команда /next ---
def next_chat(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    if user_id not in user_info:
        update.message.reply_text("Сначала напишите /start и представьтесь")
        return
    if user_id in pairs:
        partner = pairs[user_id]
        if user_id in pairs:
            del pairs[user_id]
        if partner in pairs:
            del pairs[partner]
        try:
            context.bot.send_message(partner, "🚫 Собеседник покинул чат. /start для нового поиска")
        except:
            pass
        if partner in last_activity:
            del last_activity[partner]
    if user_id in queue:
        queue.remove(user_id)
    if user_id in last_activity:
        del last_activity[user_id]
    start(update, context)

# --- Команда /stop ---
def stop_chat(update: Update, context: CallbackContext):
    user_id = update.effective_user.id
    if user_id in pairs:
        partner = pairs[user_id]
        if user_id in pairs:
            del pairs[user_id]
        if partner in pairs:
            del pairs[partner]
        try:
            context.bot.send_message(partner, "🚫 Собеседник завершил чат. /start для нового")
        except:
            pass
        if partner in last_activity:
            del last_activity[partner]
    if user_id in queue:
        queue.remove(user_id)
    if user_id in last_activity:
        del last_activity[user_id]
    update.message.reply_text("Вы вышли из чата. /start чтобы найти собеседника")

# --- Запуск бота ---
def main():
    updater = Updater(BOT_TOKEN, use_context=True)
    dp = updater.dispatcher
    
    # Команды
    dp.add_handler(CommandHandler("start", start))
    dp.add_handler(CommandHandler("next", next_chat))
    dp.add_handler(CommandHandler("stop", stop_chat))
    
    # Обработка сообщений
    dp.add_handler(MessageHandler(Filters.text & ~Filters.command, handle_text))
    dp.add_handler(MessageHandler(Filters.photo, handle_text))
    dp.add_handler(MessageHandler(Filters.video, handle_text))
    dp.add_handler(MessageHandler(Filters.voice, handle_text))
    dp.add_handler(MessageHandler(Filters.sticker, handle_text))
    
    # Проверка бездействия каждую минуту
    job_queue = updater.job_queue
    job_queue.run_repeating(check_inactivity, interval=60, first=10)
    
    # Запуск
    updater.start_polling()
    updater.idle()

if __name__ == "__main__":
    main()
