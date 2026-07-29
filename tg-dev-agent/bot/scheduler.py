"""
scheduler.py — фоновая задача "самообучения". Раз в STUDY_INTERVAL_HOURS
берёт следующую тему по кругу из curriculum.py, просит Claude написать
учебную заметку, кладёт её в БД как pending-модуль и, если известен
чат владельца, присылает уведомление с кнопкой открыть /modules.
"""

import asyncio
import os
import logging

from apscheduler.schedulers.asyncio import AsyncIOScheduler

from bot import db, curriculum, claude_client

logger = logging.getLogger(__name__)

STUDY_INTERVAL_HOURS = float(os.environ.get("STUDY_INTERVAL_HOURS", "6"))


async def study_job(bot):
    index_raw = await asyncio.to_thread(db.get_setting, "curriculum_index")
    index = int(index_raw) if index_raw else 0
    category, topic = curriculum.get_topic(index)

    logger.info("Study job: %s / %s", category, topic)
    try:
        content = await claude_client.generate_study_note(category, topic)
    except Exception:
        logger.exception("Study job failed to generate note")
        return

    module_id = await asyncio.to_thread(db.add_module, category, topic, content)
    await asyncio.to_thread(db.set_setting, "curriculum_index", str(index + 1))

    owner_chat_id = await asyncio.to_thread(db.get_setting, "owner_chat_id")
    if owner_chat_id:
        try:
            await bot.send_message(
                int(owner_chat_id),
                f"📚 Изучил новую тему: <b>{topic}</b>\n"
                f"Посмотреть и подтвердить — /modules",
                parse_mode="HTML"
            )
        except Exception:
            logger.exception("Failed to notify owner about new module %s", module_id)


def start_scheduler(bot) -> AsyncIOScheduler:
    scheduler = AsyncIOScheduler()
    scheduler.add_job(
        study_job,
        "interval",
        hours=STUDY_INTERVAL_HOURS,
        args=[bot],
        next_run_time=None,  # первый запуск — через полный интервал; см. main.py для запуска раньше при желании
    )
    scheduler.start()
    return scheduler
