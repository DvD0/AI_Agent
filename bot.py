import os
import json
import logging
from datetime import datetime
from pathlib import Path

import requests
from dotenv import load_dotenv
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CommandHandler, CallbackQueryHandler, ContextTypes
)

from topics import TOPICS

load_dotenv()

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(message)s")
logger = logging.getLogger("dev-agent-bot")

BOT_TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
OLLAMA_HOST = os.environ.get("OLLAMA_HOST", "http://ollama:11434")
OLLAMA_MODEL = os.environ.get("OLLAMA_MODEL", "qwen2.5:1.5b-instruct")
STUDY_INTERVAL_HOURS = float(os.environ.get("STUDY_INTERVAL_HOURS", "6"))

DATA_DIR = Path(__file__).parent / "data"
DATA_DIR.mkdir(exist_ok=True)
KB_FILE = DATA_DIR / "knowledge_base.json"
PROGRESS_FILE = DATA_DIR / "progress.json"
STATE_FILE = DATA_DIR / "state.json"


def ask_local_model(prompt: str) -> str:
    """Запрос к локальной модели через Ollama. Ничего не уходит в интернет."""
    resp = requests.post(
        f"{OLLAMA_HOST}/api/generate",
        json={"model": OLLAMA_MODEL, "prompt": prompt, "stream": False},
        timeout=180,
    )
    resp.raise_for_status()
    return resp.json().get("response", "").strip()


def load_json(path, default):
    if path.exists():
        return json.loads(path.read_text())
    return default


def save_json(path, data):
    path.write_text(json.dumps(data, ensure_ascii=False, indent=2))


def get_progress():
    return load_json(PROGRESS_FILE, {"learned": [], "pending": None})


def get_kb():
    return load_json(KB_FILE, [])


def get_state():
    return load_json(STATE_FILE, {"chat_id": None})


def pick_next_topic():
    progress = get_progress()
    learned = set(progress["learned"])
    for t in TOPICS:
        if t not in learned:
            return t
    return None


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    state = get_state()
    state["chat_id"] = update.effective_chat.id
    save_json(STATE_FILE, state)
    kb = [
        [InlineKeyboardButton("📚 Мои модули", callback_data="show_modules")],
        [InlineKeyboardButton("🎓 Изучить сейчас", callback_data="learn_now")],
    ]
    await update.message.reply_text(
        "Привет! Я твой личный AI-агент разработчика web/game/mobile.\n\n"
        "В свободное время я буду изучать темы из своего списка и "
        "присылать тебе краткий конспект. Ты подтверждаешь — я добавляю "
        "тему в постоянную память (модуль), нет — пропускаю.\n\n"
        f"Изучаю новую тему примерно раз в {STUDY_INTERVAL_HOURS:.0f} ч, "
        "либо запусти вручную кнопкой ниже.",
        reply_markup=InlineKeyboardMarkup(kb),
    )


async def cmd_modules(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await show_modules(update.effective_chat.id, context)


async def show_modules(chat_id, context: ContextTypes.DEFAULT_TYPE):
    kb_data = get_kb()
    if not kb_data:
        text = "Пока ничего не изучено и подтверждено. Нажми «Изучить сейчас»."
    else:
        lines = [f"• {m['title']}" for m in kb_data]
        text = f"📚 Изученные модули ({len(kb_data)}):\n\n" + "\n".join(lines)
    await context.bot.send_message(chat_id, text)


async def study_topic(topic: str, context: ContextTypes.DEFAULT_TYPE):
    state = get_state()
    chat_id = state.get("chat_id")
    if not chat_id:
        logger.warning("Нет chat_id — сначала напиши боту /start")
        return

    await context.bot.send_message(chat_id, f"🎓 Изучаю тему: «{topic}»...")

    prompt = (
        f"Кратко и по делу объясни тему для разработчика web/mobile/game "
        f"приложений: '{topic}'. Дай ключевые концепции и 3-5 практических "
        f"пунктов, без воды, на русском языке."
    )
    try:
        content = ask_local_model(prompt)
    except requests.exceptions.RequestException as e:
        await context.bot.send_message(
            chat_id,
            f"⚠️ Не удалось достучаться до локальной модели (Ollama): {e}\n"
            f"Проверь, что контейнер ollama запущен и модель {OLLAMA_MODEL} скачана."
        )
        return

    if not content:
        await context.bot.send_message(chat_id, "⚠️ Модель вернула пустой ответ, попробуй ещё раз.")
        return

    progress = get_progress()
    progress["pending"] = {"topic": topic, "content": content}
    save_json(PROGRESS_FILE, progress)

    kb = [[
        InlineKeyboardButton("✅ Добавить в память", callback_data="confirm_learn"),
        InlineKeyboardButton("❌ Пропустить", callback_data="skip_learn"),
    ]]
    await context.bot.send_message(
        chat_id,
        f"🎓 Изучил тему: *{topic}*\n\n{content}\n\nДобавить это в память?",
        parse_mode="Markdown",
        reply_markup=InlineKeyboardMarkup(kb),
    )


async def scheduled_study(context: ContextTypes.DEFAULT_TYPE):
    topic = pick_next_topic()
    if topic:
        await study_topic(topic, context)
    else:
        logger.info("Все темы из списка уже изучены — нечего изучать по расписанию.")


async def cb_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    chat_id = query.message.chat_id

    if data == "show_modules":
        await show_modules(chat_id, context)

    elif data == "learn_now":
        topic = pick_next_topic()
        if topic:
            await study_topic(topic, context)
        else:
            await context.bot.send_message(chat_id, "Все темы из списка уже изучены!")

    elif data == "confirm_learn":
        progress = get_progress()
        pending = progress.get("pending")
        if pending:
            kb_data = get_kb()
            kb_data.append({
                "title": pending["topic"],
                "content": pending["content"],
                "added_at": datetime.utcnow().isoformat(),
            })
            save_json(KB_FILE, kb_data)
            progress["learned"].append(pending["topic"])
            progress["pending"] = None
            save_json(PROGRESS_FILE, progress)
            await context.bot.send_message(chat_id, f"✅ Добавлено в память: {pending['topic']}")
        else:
            await context.bot.send_message(chat_id, "Нечего подтверждать.")

    elif data == "skip_learn":
        progress = get_progress()
        pending = progress.get("pending")
        if pending:
            progress["learned"].append(pending["topic"])
            progress["pending"] = None
            save_json(PROGRESS_FILE, progress)
        await context.bot.send_message(chat_id, "Пропущено, к этой теме больше не вернусь.")


def main():
    app = Application.builder().token(BOT_TOKEN).build()
    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("modules", cmd_modules))
    app.add_handler(CallbackQueryHandler(cb_handler))
    app.job_queue.run_repeating(
        scheduled_study, interval=STUDY_INTERVAL_HOURS * 3600, first=60
    )
    logger.info("Бот запущен, жду сообщений...")
    app.run_polling()


if __name__ == "__main__":
    main()
