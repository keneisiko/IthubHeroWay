"""Каталог нашивок.

Как и каталог магазина, лежал внутри `seed_demo_data` и в продакшен не
попадал. Вынесен сюда для прод-команды `sync_catalogs`.

Награда — только в монетах. Положение перечисляет источники рейтинга
исчерпывающе (разделы 3-7), и нашивок среди них нет: нашивка, добавляющая
рейтинг, начисляла бы его без основания.

Движок выдачи понимает два ключа условия: «выполнено не меньше N квестов»
и «выдаётся вручную». Нашивки на серии, рейтинг, оценки и социальные
действия потребуют расширения движка — см. отчёт
`docs/Нашивки_магазин_достижения.docx`.
"""

from __future__ import annotations

from apps.badges.models import BadgeCategory, BadgeRarity

BADGES: tuple[dict, ...] = (
    {
        "code": "first-quest",
        "title": "Первый шаг",
        "description": "Выполни первый квест",
        "category": BadgeCategory.PROGRESS,
        "rarity": BadgeRarity.COMMON,
        "condition": {"completed_quests_at_least": 1},
        "reward_coins": 10,
    },
    {
        "code": "quest-master",
        "title": "Мастер квестов",
        "description": "Выполни 3 квеста",
        "category": BadgeCategory.PROGRESS,
        "rarity": BadgeRarity.RARE,
        "condition": {"completed_quests_at_least": 3},
        "reward_coins": 25,
    },
    {
        "code": "quest-veteran",
        "title": "Ветеран квестов",
        "description": "Выполни 10 квестов",
        "category": BadgeCategory.PROGRESS,
        "rarity": BadgeRarity.EPIC,
        "condition": {"completed_quests_at_least": 10},
        "reward_coins": 50,
    },
    # Две последние вехи карты пути отмечает куратор: событий «вышел на
    # стажировку» и «выпустился» нет ни в LXP, ни в Hik.
    {
        "code": "path-internship",
        "title": "Стажировка",
        "description": "Веха карты пути: студент вышел на стажировку. Выдаётся куратором.",
        "category": BadgeCategory.SPECIAL,
        "rarity": BadgeRarity.EPIC,
        "condition": {"manual": True},
        "reward_coins": 0,
    },
    {
        "code": "path-graduation",
        "title": "Выпуск",
        "description": "Веха карты пути: студент завершил обучение. Выдаётся куратором.",
        "category": BadgeCategory.SPECIAL,
        "rarity": BadgeRarity.LEGENDARY,
        "condition": {"manual": True},
        "reward_coins": 0,
    },
)
