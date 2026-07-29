"""
main.py — точка входа Telegram-бота.

Команды:
  /start    — приветствие, запоминает chat_id владельца для уведомлений
  /modules  — список ещё не подтверждённых изученных тем с кнопками
  /memory   — список уже подтверждённых (сохранённых в память) тем
Обычные текстовые сообщения — чат с агентом (учитывает подтверждённую память).

Бот отвечает ТОЛЬКО пользователю с ALLOWED_USER_ID (см. .env) — это личный
агент, не публичный бот.
"""

import asyncio
import logging
import os

from aiogram import Bot, Dispatcher, F
from aiogram.filters import Command
from aiogram.types import (
    Message, CallbackQuery,
    InlineKeyboardMarkup, InlineKeyboardButton,
)

from bot import db, claude_client
from bot.scheduler import start_scheduler

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
ALLOWED_USER_ID = os.environ.get("ALLOWED_USER_ID")  # строка или None

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()


def _is_allowed(message_or_call) -> bool:
    if not ALLOWED_USER_ID:
        return True  # не задано — считаем, что владелец ещё настраивает бота
    return str(message_or_call.from_user.id) == str(ALLOWED_USER_ID)


def _modules_keyboard(module_id: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[
        InlineKeyboardButton(text="✅ Добавить в память", callback_data=f"confirm:{module_id}"),
        InlineKeyboardButton(text="❌ Пропустить", callback_data=f"skip:{module_id}"),
    ]])


@dp.message(Command("start"))
async def cmd_start(message: Message):
    if not _is_allowed(message):
        await message.answer("Этот бот приватный.")
        return

    await asyncio.to_thread(db.set_setting, "owner_chat_id", str(message.chat.id))

    pending = await asyncio.to_thread(db.get_pending_modules)
    text = (
        "Привет! Я твой личный агент-разработчик (веб / игры / mobile).\n\n"
        "В свободное время я изучаю новые темы и присылаю их сюда на "
        "подтверждение — ничего не попадёт в мою память без твоего ОК.\n\n"
        "Команды:\n"
        "/modules — новые изученные темы, ждут подтверждения\n"
        "/memory — что уже подтверждено и что я 'умею'\n\n"
        "Просто пиши мне вопросы по разработке — отвечу с учётом того, "
        "что уже подтверждено в памяти."
    )
    if pending:
        text += f"\n\n📚 Сейчас есть {len(pending)} новых тем — глянь /modules"
    await message.answer(text)


@dp.message(Command("modules"))
async def cmd_modules(message: Message):
    if not _is_allowed(message):
        return
    pending = await asyncio.to_thread(db.get_pending_modules)
    if not pending:
        await message.answer("Пока нет новых непросмотренных тем. Загляну позже — я всё ещё изучаю фоном.")
        return
    for row in pending:
        preview = row["content"][:600] + ("…" if len(row["content"]) > 600 else "")
        text = f"<b>[{row['category']}] {row['topic']}</b>\n\n{preview}"
        await message.answer(text, reply_markup=_modules_keyboard(row["id"]), parse_mode="HTML")


@dp.message(Command("memory"))
async def cmd_memory(message: Message):
    if not _is_allowed(message):
        return
    confirmed = await asyncio.to_thread(db.get_confirmed_modules)
    if not confirmed:
        await message.answer("Память пока пустая — ни одна тема ещё не подтверждена через /modules.")
        return
    lines = [f"• [{r['category']}] {r['topic']}" for r in confirmed]
    await message.answer("Подтверждённые темы в памяти:\n\n" + "\n".join(lines))


@dp.callback_query(F.data.startswith("confirm:"))
async def cb_confirm(call: CallbackQuery):
    if not _is_allowed(call):
        await call.answer()
        return
    module_id = int(call.data.split(":")[1])
    await asyncio.to_thread(db.set_module_status, module_id, "confirmed")
    await call.answer("Добавлено в память ✅")
    await call.message.edit_reply_markup(reply_markup=None)


@dp.callback_query(F.data.startswith("skip:"))
async def cb_skip(call: CallbackQuery):
    if not _is_allowed(call):
        await call.answer()
        return
    module_id = int(call.data.split(":")[1])
    await asyncio.to_thread(db.set_module_status, module_id, "skipped")
    await call.answer("Пропущено")
    await call.message.edit_reply_markup(reply_markup=None)


@dp.message(F.text)
async def handle_chat(message: Message):
    if not _is_allowed(message):
        await message.answer("Этот бот приватный.")
        return

    await bot.send_chat_action(message.chat.id, "typing")

    confirmed = await asyncio.to_thread(db.get_confirmed_modules)
    memory_context = "\n".join(f"- [{r['category']}] {r['topic']}" for r in confirmed) if confirmed else ""

    recent = await asyncio.to_thread(db.get_recent_chat, 12)
    history_text = "\n".join(f"{r['role']}: {r['content']}" for r in recent)

    await asyncio.to_thread(db.add_chat_message, "user", message.text)
    try:
        reply = await claude_client.chat_reply(message.text, memory_context, history_text)
    except Exception:
        logger.exception("chat_reply failed")
        await message.answer("Что-то пошло не так при обращении к модели. Попробуй ещё раз.")
        return

    await asyncio.to_thread(db.add_chat_message, "assistant", reply)
    await message.answer(reply)


async def main():
    await asyncio.to_thread(db.init_db)
    start_scheduler(bot)
    logger.info("Bot started")
    await dp.start_polling(bot)


if __name__ == "__main__":
    asyncio.run(main())
