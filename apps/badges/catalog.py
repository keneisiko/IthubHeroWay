"""Каталог нашивок.

Лежал внутри `seed_demo_data` и в продакшен не попадал. Вынесен сюда для
прод-команды `sync_catalogs`.

Награда — только в монетах. Положение перечисляет источники рейтинга
исчерпывающе (разделы 3-7), и нашивок среди них нет: нашивка, добавляющая
рейтинг, начисляла бы его без основания.

Условие — имя метрики и порог, список метрик в `apps/badges/metrics.py`.
Несколько условий в одной нашивке действуют вместе.

Награда растёт с редкостью, но остаётся в масштабе недельного дохода
(30 монет за учёбу плюс около 15 за квесты): легендарная нашивка — это
примерно две недели заработка, а не месяц.
"""

from __future__ import annotations

from apps.badges.models import BadgeCategory, BadgeRarity

BADGES: tuple[dict, ...] = (
    # --- Прогресс: первые шаги на платформе -------------------------------
    {
        "code": "telegram-linked",
        "title": "На связи",
        "description": "Привяжи аккаунт к Telegram-боту @ItHubHeroWaybot (команда /activate) — тогда платформа сможет писать тебе о квестах и наградах.",
        "category": BadgeCategory.PROGRESS,
        "rarity": BadgeRarity.COMMON,
        "condition": {"telegram_linked": True},
        "reward_coins": 5,
    },
    {
        "code": "first-quest",
        "title": "Первый шаг",
        "description": "Выполни свой первый квест.",
        "category": BadgeCategory.PROGRESS,
        "rarity": BadgeRarity.COMMON,
        "condition": {"completed_quests_at_least": 1},
        "reward_coins": 10,
    },
    {
        "code": "quest-master",
        "title": "Мастер квестов",
        "description": "Выполни три квеста.",
        "category": BadgeCategory.PROGRESS,
        "rarity": BadgeRarity.RARE,
        "condition": {"completed_quests_at_least": 3},
        "reward_coins": 20,
    },
    {
        "code": "quest-veteran",
        "title": "Ветеран квестов",
        "description": "Выполни десять квестов.",
        "category": BadgeCategory.PROGRESS,
        "rarity": BadgeRarity.EPIC,
        "condition": {"completed_quests_at_least": 10},
        "reward_coins": 40,
    },
    {
        "code": "weekly-hunter",
        "title": "Охотник за неделями",
        "description": "Закрой пять недельных квестов — они дороже ежедневных и требуют ровного темпа.",
        "category": BadgeCategory.PROGRESS,
        "rarity": BadgeRarity.RARE,
        "condition": {"completed_weekly_quests_at_least": 5},
        "reward_coins": 25,
    },
    {
        "code": "collector",
        "title": "Коллекционер",
        "description": "Собери десять нашивок.",
        "category": BadgeCategory.PROGRESS,
        "rarity": BadgeRarity.EPIC,
        "condition": {"badges_at_least": 10},
        "reward_coins": 40,
    },
    # --- Учёба -------------------------------------------------------------
    {
        "code": "first-ct",
        "title": "Первая контрольная",
        "description": "Закрой первую контрольную точку после подключения к платформе.",
        "category": BadgeCategory.ACADEMIC,
        "rarity": BadgeRarity.COMMON,
        "condition": {"ct_closed_at_least": 1},
        "reward_coins": 10,
    },
    {
        "code": "ct-ten",
        "title": "Десяток закрыт",
        "description": "Закрой десять контрольных точек.",
        "category": BadgeCategory.ACADEMIC,
        "rarity": BadgeRarity.RARE,
        "condition": {"ct_closed_at_least": 10},
        "reward_coins": 25,
    },
    {
        "code": "ct-collector",
        "title": "Собиратель КТ",
        "description": "Закрой двадцать контрольных точек за сезон.",
        "category": BadgeCategory.ACADEMIC,
        "rarity": BadgeRarity.EPIC,
        "condition": {"ct_closed_at_least": 20},
        "reward_coins": 45,
    },
    {
        "code": "rating-trainee",
        "title": "Стажёр",
        "description": "Подними рейтинг до 100 — первый статус за учёбу и посещаемость.",
        "category": BadgeCategory.ACADEMIC,
        "rarity": BadgeRarity.COMMON,
        "condition": {"rating_at_least": 100},
        "reward_coins": 10,
    },
    {
        "code": "rating-specialist",
        "title": "Специалист",
        "description": "Подними рейтинг до 250.",
        "category": BadgeCategory.ACADEMIC,
        "rarity": BadgeRarity.RARE,
        "condition": {"rating_at_least": 250},
        "reward_coins": 25,
    },
    {
        "code": "rating-pro",
        "title": "Профи",
        "description": "Подними рейтинг до 500.",
        "category": BadgeCategory.ACADEMIC,
        "rarity": BadgeRarity.EPIC,
        "condition": {"rating_at_least": 500},
        "reward_coins": 45,
    },
    {
        "code": "rating-legend",
        "title": "Легенда",
        "description": "Подними рейтинг до 900 — высший статус сезона.",
        "category": BadgeCategory.ACADEMIC,
        "rarity": BadgeRarity.LEGENDARY,
        "condition": {"rating_at_least": 900},
        "reward_coins": 70,
    },
    # --- Дисциплина --------------------------------------------------------
    {
        "code": "discipline-week",
        "title": "Неделя в строю",
        "description": "Семь дней подряд без опозданий.",
        "category": BadgeCategory.PROGRESS,
        "rarity": BadgeRarity.COMMON,
        "condition": {"late_streak_at_least": 7},
        "reward_coins": 10,
    },
    {
        "code": "discipline-iron",
        "title": "Железная дисциплина",
        "description": "Двадцать один день подряд без опозданий.",
        "category": BadgeCategory.PROGRESS,
        "rarity": BadgeRarity.EPIC,
        "condition": {"late_streak_at_least": 21},
        "reward_coins": 45,
    },
    {
        "code": "attendance-month",
        "title": "Месяц без пропусков",
        "description": "Двадцать учебных дней подряд без пропусков.",
        "category": BadgeCategory.ACADEMIC,
        "rarity": BadgeRarity.EPIC,
        "condition": {"attendance_streak_at_least": 20},
        "reward_coins": 45,
    },
    # --- Социальное --------------------------------------------------------
    {
        "code": "generous",
        "title": "Щедрый",
        "description": "Отдай десять респектов однокурсникам.",
        "category": BadgeCategory.SOCIAL,
        "rarity": BadgeRarity.COMMON,
        "condition": {"respects_given_at_least": 10},
        "reward_coins": 10,
    },
    {
        "code": "respected",
        "title": "Уважаемый",
        "description": "Получи десять респектов от однокурсников.",
        "category": BadgeCategory.SOCIAL,
        "rarity": BadgeRarity.RARE,
        "condition": {"respects_received_at_least": 10},
        "reward_coins": 25,
    },
    {
        "code": "duelist",
        "title": "Дуэлянт",
        "description": "Выиграй три дуэли.",
        "category": BadgeCategory.SOCIAL,
        "rarity": BadgeRarity.RARE,
        "condition": {"duels_won_at_least": 3},
        "reward_coins": 25,
    },
    {
        "code": "shopper",
        "title": "Транжира",
        "description": "Потрать в магазине двести монет.",
        "category": BadgeCategory.SOCIAL,
        "rarity": BadgeRarity.COMMON,
        "condition": {"coins_spent_at_least": 200},
        "reward_coins": 10,
    },
    {
        "code": "pillar-peak",
        "title": "На пике",
        "description": "Доведи любую из опор до 18 из 20.",
        "category": BadgeCategory.SPECIAL,
        "rarity": BadgeRarity.EPIC,
        "condition": {"max_pillar_at_least": 18},
        "reward_coins": 45,
    },
    # --- Вехи карты пути: их отмечает куратор ------------------------------
    # Событий «вышел на стажировку» и «выпустился» нет ни в LXP, ни в Hik,
    # а привязывать выпуск к номеру курса значило бы объявить выпускниками
    # всех четверокурсников первого сентября.
    {
        "code": "path-internship",
        "title": "Стажировка",
        "description": "Веха карты пути: студент вышел на стажировку. Отмечает куратор.",
        "category": BadgeCategory.SPECIAL,
        "rarity": BadgeRarity.EPIC,
        "condition": {"manual": True},
        "reward_coins": 0,
    },
    {
        "code": "path-graduation",
        "title": "Выпуск",
        "description": "Веха карты пути: студент завершил обучение. Отмечает куратор.",
        "category": BadgeCategory.SPECIAL,
        "rarity": BadgeRarity.LEGENDARY,
        "condition": {"manual": True},
        "reward_coins": 0,
    },
    {
        "code": "king-of-hill",
        "title": "Царь горы",
        "description": "7 дней подряд на первом месте общего рейтинга. Выдаётся автоматически.",
        "category": BadgeCategory.SPECIAL,
        "rarity": BadgeRarity.RARE,
        "condition": {"manual": True},
        "reward_coins": 0,
    },
    {
        "code": "olympiad-winner",
        "title": "Победитель олимпиады",
        "description": "Победа в олимпиаде любого уровня. Отмечает ответственный за мероприятия.",
        "category": BadgeCategory.SPECIAL,
        "rarity": BadgeRarity.LEGENDARY,
        "condition": {"manual": True},
        "reward_coins": 0,
    },
)
