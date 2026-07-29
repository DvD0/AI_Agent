"""
claude_client.py — обёртка над Anthropic API.
Используется и для обычного чата с владельцем, и для фоновой генерации
"учебных заметок" по темам из curriculum.py.
"""

import os
from anthropic import AsyncAnthropic

MODEL = os.environ.get("CLAUDE_MODEL", "claude-sonnet-4-6")

client = AsyncAnthropic(api_key=os.environ["ANTHROPIC_API_KEY"])

SYSTEM_PROMPT = """Ты — личный ИИ-агент разработчика, специализируешься на \
веб-разработке, играх и мобильной разработке. Отвечаешь по делу, кратко, \
на русском языке, используешь примеры кода при необходимости. Ты не \
выдумываешь факты о собственных возможностях — если не уверен, так и говоришь."""


async def chat_reply(user_message: str, memory_context: str, recent_history: str) -> str:
    system = SYSTEM_PROMPT
    if memory_context:
        system += "\n\nТемы, которые ты уже изучил и подтвердил (используй это как свои знания):\n" + memory_context

    messages = []
    if recent_history:
        messages.append({"role": "user", "content": f"[Контекст предыдущего разговора]\n{recent_history}"})
        messages.append({"role": "assistant", "content": "Понял контекст, продолжаем."})
    messages.append({"role": "user", "content": user_message})

    resp = await client.messages.create(
        model=MODEL,
        max_tokens=1200,
        system=system,
        messages=messages,
    )
    return "".join(block.text for block in resp.content if block.type == "text")


async def generate_study_note(category: str, topic: str) -> str:
    prompt = (
        f"Напиши краткую учебную заметку (200-350 слов) по теме "
        f"\"{topic}\" (категория: {category}) для разработчика веб/игр/"
        f"мобильных приложений. Структура: суть темы, когда применяется, "
        f"1 короткий пример кода или конкретный практический совет. "
        f"Пиши на русском, по делу, без вступлений и воды."
    )
    resp = await client.messages.create(
        model=MODEL,
        max_tokens=800,
        system="Ты пишешь сжатые технические учебные заметки для собственной памяти.",
        messages=[{"role": "user", "content": prompt}],
    )
    return "".join(block.text for block in resp.content if block.type == "text")
