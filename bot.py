import asyncio
import logging
import sqlite3
import os
import random
from datetime import datetime
from aiogram import Bot, Dispatcher, types
from aiogram.types import ReplyKeyboardMarkup, KeyboardButton
from aiogram.utils import executor

API_TOKEN = '7940443179:AAFRX9c0svolP3MAtvjG7Do4Jk9KGZpwvdo'
DATABASE = 'tasks.db'
MEME_DIR = "memes"

logging.basicConfig(level=logging.INFO)
bot = Bot(token=API_TOKEN)
dp = Dispatcher(bot)

# --- Клавиатура ---
main_keyboard = ReplyKeyboardMarkup(
    keyboard=[
        [KeyboardButton(text="🚀 Начать"), KeyboardButton(text="➕ Добавить задачу")],
        [KeyboardButton(text="📋 Мои задачи"), KeyboardButton(text="❌ Удалить задачу")],
        [KeyboardButton(text="🧠 Цитата дня")],
    ],
    resize_keyboard=True
)

# --- Инициализация базы ---
def init_db():
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    cursor.execute('''CREATE TABLE IF NOT EXISTS tasks (
                        user_id INTEGER,
                        text TEXT,
                        remind_at TEXT
                    )''')
    conn.commit()
    conn.close()

# --- Старт ---
@dp.message_handler(commands=['start'])
async def start_handler(message: types.Message):
    await message.answer("Привет! Я твой бот-помощник. Выбирай действие ниже:", reply_markup=main_keyboard)

@dp.message_handler(lambda msg: msg.text == "🚀 Начать")
async def restart_command(message: types.Message):
    await start_handler(message)

# --- Переменные состояния ---
user_state = {}

# --- Добавление задачи ---
@dp.message_handler(lambda msg: msg.text == "➕ Добавить задачу")
async def add_task(message: types.Message):
    user_state[message.from_user.id] = {'stage': 'awaiting_text'}
    await message.answer("Введи текст задачи:")

@dp.message_handler(lambda msg: user_state.get(msg.from_user.id, {}).get('stage') == 'awaiting_text')
async def get_task_text(message: types.Message):
    user_state[message.from_user.id]['text'] = message.text
    user_state[message.from_user.id]['stage'] = 'awaiting_date'
    await message.answer("Введи дату в формате ДД.ММ.ГГГГ:")

@dp.message_handler(lambda msg: user_state.get(msg.from_user.id, {}).get('stage') == 'awaiting_date')
async def get_task_date(message: types.Message):
    try:
        date = datetime.strptime(message.text.strip(), '%d.%m.%Y').date()
        user_state[message.from_user.id]['date'] = date
        user_state[message.from_user.id]['stage'] = 'awaiting_time'
        await message.answer("Теперь введи время в формате ЧЧ:ММ:")
    except ValueError:
        await message.answer("Неверный формат даты. Попробуй снова в формате ДД.ММ.ГГГГ")

@dp.message_handler(lambda msg: user_state.get(msg.from_user.id, {}).get('stage') == 'awaiting_time')
async def get_task_time(message: types.Message):
    try:
        time = datetime.strptime(message.text.strip(), '%H:%M').time()
        data = user_state.pop(message.from_user.id)
        remind_at = datetime.combine(data['date'], time).replace(second=0, microsecond=0)

        conn = sqlite3.connect(DATABASE)
        cursor = conn.cursor()
        cursor.execute("INSERT INTO tasks (user_id, text, remind_at) VALUES (?, ?, ?)",
                       (message.from_user.id, data['text'], remind_at.isoformat()))
        conn.commit()
        conn.close()

        await message.answer("Задача добавлена!", reply_markup=main_keyboard)
    except ValueError:
        await message.answer("Неверный формат времени. Попробуй снова в формате ЧЧ:ММ")

# --- Просмотр задач ---
@dp.message_handler(lambda msg: msg.text == "📋 Мои задачи")
async def list_tasks(message: types.Message):
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    cursor.execute("SELECT rowid, text, remind_at FROM tasks WHERE user_id=?", (message.from_user.id,))
    tasks = cursor.fetchall()
    conn.close()

    if not tasks:
        await message.answer("У тебя нет задач.")
    else:
        response = "Твои задачи:\n"
        for rowid, text, remind_at in tasks:
            remind_time = datetime.fromisoformat(remind_at).strftime('%d.%m.%Y %H:%M')
            response += f"[{rowid}] {text} - {remind_time}\n"
        await message.answer(response)

# --- Удаление задачи ---
@dp.message_handler(lambda msg: msg.text == "❌ Удалить задачу")
async def delete_task(message: types.Message):
    conn = sqlite3.connect(DATABASE)
    cursor = conn.cursor()
    cursor.execute("SELECT rowid, text FROM tasks WHERE user_id=?", (message.from_user.id,))
    tasks = cursor.fetchall()

    if not tasks:
        await message.answer("У тебя нет задач для удаления.")
        return

    response = "Введи номер задачи для удаления:\n"
    for rowid, text in tasks:
        response += f"[{rowid}] {text}\n"
    await message.answer(response)

    user_state[message.from_user.id] = {'stage': 'awaiting_delete'}

@dp.message_handler(lambda msg: user_state.get(msg.from_user.id, {}).get('stage') == 'awaiting_delete')
async def confirm_delete(message: types.Message):
    try:
        task_id = int(message.text.strip())
        conn = sqlite3.connect(DATABASE)
        cursor = conn.cursor()
        cursor.execute("DELETE FROM tasks WHERE rowid=? AND user_id=?", (task_id, message.from_user.id))
        conn.commit()
        conn.close()
        user_state.pop(message.from_user.id)
        await message.answer("Задача удалена.", reply_markup=main_keyboard)
    except:
        await message.answer("Ошибка. Убедись, что номер задачи правильный.")

# --- Цитата дня с мемом из папки ---
@dp.message_handler(lambda msg: msg.text == "🧠 Цитата дня")
async def send_quote(message: types.Message):
    quotes = [
    "«Никогда не поздно стать тем, кем ты мог бы быть.» — Джордж Элиот",
    "«Жизнь — это 10% того, что с тобой происходит, и 90% того, как ты на это реагируешь.»",
    "«Будь собой. Прочие роли уже заняты.» — Оскар Уайльд",
    "«Единственный способ делать великие дела — любить то, что ты делаешь.» — Стив Джобс",
    "«Ты становишься тем, о чём ты думаешь большую часть времени.» — Эрл Найтингейл",
    "«Сначала они тебя не замечают, потом смеются над тобой, потом борются с тобой, а потом ты побеждаешь.» — Махатма Ганди",
    "«Настойчивость — это не длинный пробег, это много коротких забегов один за другим.» — Уолтер Эллиот",
    "«Ты сильнее, чем думаешь, и способен на большее, чем представляешь.»",
    "«Каждая ошибка — это шанс начать заново, но уже более мудро.» — Генри Форд",
    "«Успех — это сумма небольших усилий, повторяемых изо дня в день.» — Роберт Колльер",
    "«Страх — это ложь, которую мы говорим себе.» — Джонатан Хайнц",
    "«Даже самый долгий путь начинается с первого шага.» — Лао-цзы",
    "«Великие дела никогда не совершаются в зоне комфорта.»",
    "«Никогда не сдавайся, потому что именно тогда, когда ты готов сдаться, обычно наступает прорыв.»",
    "«Тот, кто хочет — ищет возможности. Кто не хочет — ищет причины.»",
    "«Ты не обязан быть великим, чтобы начать. Но ты должен начать, чтобы стать великим.»",
    "«Ошибки — это доказательство того, что ты пытаешься.»",
    "«Сила не в победе, а в отказе сдаться.»",
    "«Ты сам пишешь свою историю. Сделай её вдохновляющей.»",
    "«Если не сейчас, то когда?»"
]
    quote = random.choice(quotes)
    await message.answer(f"💬 {quote}")

    if os.path.isdir(MEME_DIR):
        memes = [f for f in os.listdir(MEME_DIR) if f.endswith(('.jpg', '.png', '.jpeg'))]
        if memes:
            meme_file = random.choice(memes)
            with open(os.path.join(MEME_DIR, meme_file), 'rb') as photo:
                await bot.send_photo(message.chat.id, photo)

# --- Проверка напоминаний ---
async def check_reminders():
    while True:
        now = datetime.now().replace(second=0, microsecond=0)
        conn = sqlite3.connect(DATABASE)
        cursor = conn.cursor()
        cursor.execute("SELECT rowid, user_id, text FROM tasks WHERE remind_at=?", (now.isoformat(),))
        tasks = cursor.fetchall()
        for rowid, user_id, text in tasks:
            try:
                await bot.send_message(user_id, f"🔔 Напоминание: {text}")
                cursor.execute("DELETE FROM tasks WHERE rowid=?", (rowid,))
            except:
                pass
        conn.commit()
        conn.close()
        await asyncio.sleep(30)

# --- Запуск ---
if __name__ == '__main__':
    init_db()
    loop = asyncio.get_event_loop()
    loop.create_task(check_reminders())
    executor.start_polling(dp, skip_updates=True)
