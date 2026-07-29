"""
curriculum.py — темы, которые агент изучает в фоне по кругу.
Индекс текущей позиции хранится в settings (curriculum_index),
чтобы после перезапуска контейнера продолжать, а не начинать заново.
"""

TOPICS: list[tuple[str, str]] = [
    # (категория, тема)
    ("web", "Основы REST API и HTTP-методов"),
    ("web", "Аутентификация: JWT vs сессии vs OAuth2"),
    ("web", "React: хуки useState/useEffect на практике"),
    ("web", "WebSocket и real-time коммуникация"),
    ("web", "Основы Docker для веб-разработчика"),
    ("web", "SQL: индексы и оптимизация запросов"),
    ("web", "CI/CD пайплайны для веб-проектов"),
    ("game", "Игровые циклы (game loop) и фиксированный таймстеп"),
    ("game", "Object Pooling и оптимизация памяти в играх"),
    ("game", "Основы 2D-физики: коллизии, rigidbody"),
    ("game", "Процедурная генерация уровней: алгоритмы"),
    ("game", "State Machine для AI врагов"),
    ("game", "Экономика и баланс F2P-игр"),
    ("game", "ECS-архитектура (Entity Component System)"),
    ("mobile", "Flutter: основы виджетов и state management"),
    ("mobile", "React Native vs нативная разработка"),
    ("mobile", "Оптимизация производительности мобильных приложений"),
    ("mobile", "Push-уведомления: архитектура на бэкенде"),
    ("mobile", "Публикация в Google Play и App Store: чек-лист"),
    ("mobile", "Оффлайн-режим и синхронизация данных"),
]


def get_topic(index: int) -> tuple[str, str]:
    return TOPICS[index % len(TOPICS)]


def total_topics() -> int:
    return len(TOPICS)
