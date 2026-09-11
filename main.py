
import asyncio
import logging
import os
from datetime import datetime
from aiogram import Bot, Dispatcher, types
from aiogram.filters import CommandStart, Command
from aiogram.types import Message
import aiosqlite

# === КОНФИГУРАЦИЯ ===
TELEGRAM_BOT_TOKEN = "8674246097:AAHtXZW5BRIIYE7qOg4EiiSJ_hpCBmFE2zo"

DB_PATH = "tasks.db"

# === ИНИЦИАЛИЗАЦИЯ ===
logging.basicConfig(level=logging.INFO)
bot = Bot(token=TELEGRAM_BOT_TOKEN)
dp = Dispatcher()

# === БАЗА ДАННЫХ ===
async def init_db():
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute("""
            CREATE TABLE IF NOT EXISTS tasks (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                user_id INTEGER NOT NULL,
                text TEXT NOT NULL,
                remind_at TEXT NOT NULL,
                done INTEGER DEFAULT 0,
                created_at TEXT NOT NULL
            )
        """)
        await db.commit()

async def add_task(user_id: int, text: str, remind_at: datetime):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            """
            INSERT INTO tasks (user_id, text, remind_at, done, created_at)
            VALUES (?, ?, ?, 0, ?)
            """,
            (user_id, text, remind_at.isoformat(), datetime.now().isoformat())
        )
        await db.commit()

async def get_active_tasks(user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            """
            SELECT id, text, remind_at, done, created_at
            FROM tasks
            WHERE user_id = ? AND done = 0
            ORDER BY remind_at ASC
            """,
            (user_id,)
        )
        return await cur.fetchall()

async def mark_task_done(task_id: int, user_id: int):
    async with aiosqlite.connect(DB_PATH) as db:
        await db.execute(
            "UPDATE tasks SET done = 1 WHERE id = ? AND user_id = ?",
            (task_id, user_id)
        )
        await db.commit()

async def get_due_tasks(now: datetime):
    # Задачи, у которых remind_at <= now и done = 0
    async with aiosqlite.connect(DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cur = await db.execute(
            """
            SELECT id, user_id, text, remind_at
            FROM tasks
            WHERE done = 0 AND remind_at <= ?
            """,
            (now.isoformat(),)
        )
        return await cur.fetchall()

# === ОБРАБОТЧИКИ КОМАНД ===
@dp.message(CommandStart())
async def cmd_start(message: Message):
    await message.answer(
        "Привет! Я бот‑напоминалка.\n\n"
        "Команды:\n"
        "/add — добавить задачу (формат: /add Купить продукты 2026-09-10 18:30)\n"
        "/list — показать все активные задачи\n"
        "/done <id> — отметить задачу выполненной"
    )

@dp.message(Command("add"))
async def cmd_add(message: Message):
    # Ожидаем: /add Текст задачи YYYY-MM-DD HH:MM
    args = message.text.split(maxsplit=2)
    if len(args) < 3:
        await message.answer(
            "Неверный формат.\nПример:\n/add Купить продукты 2026-09-10 18:30"
        )
        return

    task_text = args[1]
    dt_str = args[2]

    try:
        remind_at = datetime.strptime(dt_str, "%Y-%m-%d %H:%M")
    except ValueError:
        await message.answer(
            "Неверный формат даты/времени. Используйте: YYYY-MM-DD HH:MM"
        )
        return

    if remind_at <= datetime.now():
        await message.answer("Время напоминания должно быть в будущем.")
        return

    await add_task(message.from_user.id, task_text, remind_at)
    await message.answer(
        f"✅ Задача добавлена:\n«{task_text}»\nНапомнить: {remind_at.strftime('%d.%m.%Y %H:%M')}"
    )

@dp.message(Command("list"))
async def cmd_list(message: Message):
    tasks = await get_active_tasks(message.from_user.id)
    if not tasks:
        await message.answer("Нет активных задач.")
        return

    lines = []
    for t in tasks:
        dt = datetime.fromisoformat(t["remind_at"])
        lines.append(
            f"{t['id']}. {t['text']} — {dt.strftime('%d.%m.%Y %H:%M')}"
        )

    text = "Ваши задачи:\n" + "\n".join(lines)
    await message.answer(text)

@dp.message(Command("done"))
async def cmd_done(message: Message):
    args = message.text.split()
    if len(args) < 2 or not args[1].isdigit():
        await message.answer("Используйте: /done <id задачи>")
        return

    task_id = int(args[1])
    await mark_task_done(task_id, message.from_user.id)
    await message.answer(f"✅ Задача #{task_id} отмечена выполненной.")

# === ФОНОВАЯ ПРОВЕРКА НАПОМИНАНИЙ ===
async def reminders_loop():
    while True:
        try:
            now = datetime.now()
            due = await get_due_tasks(now)
            for task in due:
                try:
                    await bot.send_message(
                        task["user_id"],
                        f"⏰ Напоминание:\n{task['text']}\n(запланировано на {datetime.fromisoformat(task['remind_at']).strftime('%d.%m.%Y %H:%M')})"
                    )
                    await mark_task_done(task["id"], task["user_id"])
                except Exception:
                    logging.exception("Ошибка отправки напоминания")
        except Exception:
            logging.exception("Ошибка в цикле напоминаний")

        await asyncio.sleep(60)  # проверка раз в минуту

# === ЗАПУСК ===
async def main():
    await init_db()
    asyncio.create_task(reminders_loop())
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
