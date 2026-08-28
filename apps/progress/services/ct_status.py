"""Единое определение «контрольная точка закрыта».

Раньше определений было два: рейтинг искал подстроки в статусе, а верификатор
квеста сверял точное равенство по своему списку. Один и тот же статус мог
считаться закрытым для рейтинга и открытым для квеста — студент видел
«+20 за КТ» и невыполненный квест «закрой КТ» одновременно.
"""

from __future__ import annotations

# Подстроки, а не точные значения: LXP отдаёт статусы в разном регистре
# и с разными префиксами (`TOPIC_PASSED`, `passed`, `Зачтено`).
CLOSED_STATUS_MARKERS = (
    "PASSED",
    "DONE",
    "SUCCESS",
    "ACCEPTED",
    "CLOSED",
    "COMPLETE",
    "APPROVED",
    "ЗАЧТ",
    "СДАН",
    "ЗАКРЫТ",
)


def is_topic_closed(status) -> bool:
    """Закрыта ли тема по её статусу из снимка LXP."""
    text = ("" if status is None else str(status)).strip().upper()
    if not text:
        return False
    return any(marker in text for marker in CLOSED_STATUS_MARKERS)


def topic_key(discipline_id, topic_payload: dict, index: int) -> str:
    """Устойчивый ключ темы для сравнения снимков между собой.

    Идентификатор темы есть в `topic.id`. Если LXP его не отдал, ключом
    становится название, а в крайнем случае — порядковый номер: без него все
    безымянные темы одной дисциплины схлопнулись бы в один ключ, и закрытие
    девяти тем из десяти выглядело бы как одно событие.
    """
    topic_obj = topic_payload.get("topic") if isinstance(topic_payload, dict) else None
    raw_id = None
    if isinstance(topic_obj, dict):
        raw_id = topic_obj.get("id") or topic_obj.get("name")
    if not raw_id:
        raw_id = topic_payload.get("id") or topic_payload.get("name")
    return f"{discipline_id}:{raw_id or index}"


def iter_user_topics(control_points_for_user: dict):
    """Пройти темы студента: (ключ, закрыта ли)."""
    if not isinstance(control_points_for_user, dict):
        return
    for discipline_id, discipline in control_points_for_user.items():
        if not isinstance(discipline, dict):
            continue
        topics = discipline.get("topics") or []
        if isinstance(topics, dict):
            topics = list(topics.values())
        if not isinstance(topics, list):
            continue
        for index, topic in enumerate(topics):
            if not isinstance(topic, dict):
                continue
            status = topic.get("status") or topic.get("state")
            yield topic_key(discipline_id, topic, index), is_topic_closed(status)
