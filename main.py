import asyncio
import json
import logging
import os
from datetime import datetime
from pathlib import Path

from aiogram import Bot, Dispatcher
from aiogram.filters import Command, CommandStart
from aiogram.types import Message


# =========================
# НАСТРОЙКИ
# =========================
BOT_TOKEN = "8674246097:AAHtXZW5BRIIYE7qOg4EiiSJ_hpCBmFE2zo"

if not BOT_TOKEN:
    raise RuntimeError(
        "Не задан токен. Добавьте переменную окружения BOT_TOKEN."
    )

TASKS_FILE = Path("tasks.json")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(message)s"
)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()


# =========================
# РАБОТА С ФАЙЛОМ ЗАДАЧ
# =========================

def load_tasks() -> list:
    if not TASKS_FILE.exists():
        return []

    try:
        with TASKS_FILE.open("r", encoding="utf-8") as file:
            data = json.load(file)

        if isinstance(data, list):
            return data

        return []

    except (json.JSONDecodeError, OSError):
        logging.exception("Не удалось прочитать tasks.json")
        return []


def save_tasks(tasks: list) -> None:
    temporary_file = TASKS_FILE.with_suffix(".tmp")

    with temporary_file.open("w", encoding="utf-8") as file:
        json.dump(tasks, file, ensure_ascii=False, indent=2)

    temporary_file.replace(TASKS_FILE)


def get_next_task_id(tasks: list) -> int:
    if not tasks:
        return 1

    return max(int(task["id"]) for task in tasks) + 1


def add_task(
    user_id: int,
    text: str,
    remind_at: datetime
) -> int:
    tasks = load_tasks()

    task_id = get_next_task_id(tasks)

    tasks.append(
        {
            "id": task_id,
            "user_id": user_id,
            "text": text,
            "remind_at": remind_at.isoformat(),
            "done": False,
            "notified": False,
            "created_at": datetime.now().isoformat()
        }
    )

    save_tasks(tasks)

    return task_id


def get_user_active_tasks(user_id: int) -> list:
    tasks = load_tasks()

    user_tasks = [
        task
        for task in tasks
        if int(task["user_id"]) == user_id
        and not task.get("done", False)
    ]

    user_tasks.sort(key=lambda task: task["remind_at"])

    return user_tasks


def complete_task(user_id: int, task_id: int) -> bool:
    tasks = load_tasks()
    changed = False

    for task in tasks:
        if (
            int(task["id"]) == task_id
            and int(task["user_id"]) == user_id
            and not task.get("done", False)
        ):
            task["done"] = True
            changed = True
            break

    if changed:
        save_tasks(tasks)

    return changed


def delete_task(user_id: int, task_id: int) -> bool:
    tasks = load_tasks()

    new_tasks = [
        task
        for task in tasks
        if not (
            int(task["id"]) == task_id
            and int(task["user_id"]) == user_id
        )
    ]

    changed = len(new_tasks) != len(tasks)

    if changed:
        save_tasks(new_tasks)

    return changed


def get_due_tasks() -> list:
    tasks = load_tasks()
    now = datetime.now()
    due_tasks = []

    for task in tasks:
        if task.get("done", False):
            continue

        if task.get("notified", False):
            continue

        try:
            remind_at = datetime.fromisoformat(
                task["remind_at"]
            )
        except ValueError:
            logging.error(
                "Неверная дата у задачи #%s",
                task.get("id")
            )
            continue

        if remind_at <= now:
            due_tasks.append(task)

    return due_tasks
