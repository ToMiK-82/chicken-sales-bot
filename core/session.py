"""
Простое хранилище сессий для бота.
Сохраняет состояние пользователя между запросами.

📌 В продакшене замени на Redis или другую in-memory БД.
"""
from typing import Dict, Any
from dataclasses import dataclass
from datetime import datetime

# Глобальное хранилище сессий (RAM)
_sessions: Dict[str, "UserSession"] = {}


@dataclass
class UserSession:
    """
    Сессия пользователя.
    """
    user_id: str
    chat_id: str
    state: str  # состояние: 'idle', 'selecting_breed', 'enter_phone' и т.д.
    data: Dict[str, Any]  # временные данные (выбор породы, кол-во и т.п.)
    updated_at: datetime  # время последнего обновления

    def __init__(self, user_id: str, chat_id: str = ""):
        self.user_id = user_id
        self.chat_id = chat_id
        self.state = "idle"  # начальное состояние
        self.data = {}
        self.updated_at = datetime.now()

    def touch(self):
        """Обновить метку времени."""
        self.updated_at = datetime.now()


def get_session(user_id: str) -> UserSession:
    """
    Получить сессию пользователя.
    Создаёт новую, если не существует.
    """
    user_id_str = str(user_id)
    if user_id_str not in _sessions:
        _sessions[user_id_str] = UserSession(user_id_str)
    session = _sessions[user_id_str]
    session.touch()
    return session


def clear_session(user_id: str) -> None:
    """
    Очистить сессию пользователя.
    """
    user_id_str = str(user_id)
    if user_id_str in _sessions:
        del _sessions[user_id_str]


def cleanup_expired_sessions(max_age_seconds: int = 3600):
    """
    Удалить старые сессии (опционально, можно запускать по расписанию).
    Например, каждые 10 минут.
    """
    now = datetime.now()
    expired = [
        uid for uid, session in _sessions.items()
        if (now - session.updated_at).total_seconds() > max_age_seconds
    ]
    for uid in expired:
        del _sessions[uid]
    return len(expired)


# === Пример использования ===
# session = get_session("1631997197")
# session.state = "selecting_breed"
# session.data["selected_breed"] = "Бройлер"
