"""Тарифы и правила «Положения о системе рейтинга и поощрения студентов».

Редакция Положения от 12 октября 2026 года. Здесь лежат только те величины,
которые названы в самом документе, с указанием пункта. Всё остальное —
квесты, нашивки, дуэли — живёт в `rating_coefficients.py` и Положением
не регулируется.

Правило при расхождении: числа в этом файле главнее любых других констант
проекта. Если тариф из Положения продублирован где-то ещё — дубликат
убирается, а не правится.
"""

from __future__ import annotations

from decimal import Decimal

# Версия документа. Пишется в согласие студента (п. 2.1) и в журнал начислений,
# чтобы при смене редакции было видно, по каким правилам начислено.
POLOZHENIE_VERSION = "2.0"
POLOZHENIE_DATE = "2026-10-12"

# --- Раздел 2: участие и расчётный период -----------------------------------

POLOZHENIE_PERIOD = {
    # п. 2.2: первая общая дата начала начислений. За недели до неё
    # начисления не производятся ни при каких условиях.
    "SEASON_START_DATE": "2026-10-19",
    # п. 2.3: в последующие годы сезон стартует 1 сентября.
    "SEASON_START_MONTH": 9,
    "SEASON_START_DAY": 1,
    # п. 2.3: расчётный ориентир полного года. Используется только для
    # прогнозов и отчётов: тарифы от длины сезона не зависят.
    "FULL_SEASON_WEEKS": 42,
    # п. 2.4: рейтинг и монеты учитываются до двух знаков после запятой.
    "DECIMAL_PLACES": 2,
}

# --- Раздел 3: учебные начисления -------------------------------------------
# п. 3.4: Б = 17 × К / 100 + 13 × П / 100, где К — средний процент актуальных
# КТ семестра, П — процент посещаемости недели. Монеты равны рейтингу.

POLOZHENIE_ACADEMIC = {
    "CT_WEEKLY_MAX": Decimal("17"),
    "ATTENDANCE_WEEKLY_MAX": Decimal("13"),
}

# п. 3.1: будущие КТ исключаются по признаку актуальности в LXP. Поля
# «актуальна» в выгрузке нет, поэтому актуальность выводится из статуса темы:
# всё, что не помечено как ещё не открытая, считается актуальным, а несданная
# актуальная КТ идёт в расчёт как 0%.
#
# Набор маркеров подтверждается по живым данным: команда
# `probe_topic_statuses` печатает, какие статусы реально приходят из LXP.
POLOZHENIE_FUTURE_TOPIC_MARKERS = (
    "NOT_STARTED",
    "NOT_AVAILABLE",
    "UNAVAILABLE",
    "LOCKED",
    "FUTURE",
    "PLANNED",
    "НЕ НАЧ",
    "НЕДОСТУП",
    "ЗАПЛАНИР",
)

# --- Раздел 4: регулярные роли студентов ------------------------------------
# Ставка за полную неделю действующего подтверждённого статуса.
# Совмещаемые роли оплачиваются отдельно и суммируются (п. 4.2).

POLOZHENIE_ROLES = {
    "curator": {"title": "Куратор", "rating": Decimal("5"), "coins": Decimal("20")},
    "teacher": {"title": "Преподаватель", "rating": Decimal("7"), "coins": Decimal("25")},
    "tech": {
        "title": "Технический специалист",
        "rating": Decimal("9"),
        "coins": Decimal("30"),
    },
    "group_lead": {
        "title": "Тимлид учебной группы",
        "rating": Decimal("2"),
        "coins": Decimal("8"),
    },
    "council_lead": {
        "title": "Тимлид студенческого совета",
        "rating": Decimal("3"),
        "coins": Decimal("12"),
    },
    "club_lead": {"title": "Руководитель клуба", "rating": Decimal("4"), "coins": Decimal("16")},
    "volunteer_lead": {
        "title": "Руководитель волонтёрского корпуса",
        "rating": Decimal("5"),
        "coins": Decimal("20"),
    },
}

# --- Раздел 5: мероприятия ---------------------------------------------------
# Уровень определяется уровнем мероприятия, а не местом проведения (п. 5.1).
# Применяется одна наиболее высокая из подтверждённых ролей (п. 5.2).

POLOZHENIE_EVENT_LEVELS = ("college", "city", "region", "federal")
POLOZHENIE_EVENT_LEVEL_TITLES = {
    "college": "Колледж",
    "city": "Город",
    "region": "Регион",
    "federal": "Федерация",
}

# Роли перечислены по возрастанию старшинства: спикер старше волонтёра,
# волонтёр старше слушателя. Порядок используется правилом «одна высшая роль».
POLOZHENIE_EVENT_ROLES = ("listener", "volunteer", "speaker")
POLOZHENIE_EVENT_ROLE_TITLES = {
    "listener": "Слушатель",
    "volunteer": "Волонтёр или помощь в организации",
    "speaker": "Спикер",
}

# (рейтинг, монеты) за одно мероприятие.
POLOZHENIE_EVENT_TARIFFS = {
    ("listener", "college"): (Decimal("1"), Decimal("3")),
    ("listener", "city"): (Decimal("2"), Decimal("5")),
    ("listener", "region"): (Decimal("3"), Decimal("8")),
    ("listener", "federal"): (Decimal("5"), Decimal("12")),
    ("speaker", "college"): (Decimal("5"), Decimal("15")),
    ("speaker", "city"): (Decimal("8"), Decimal("25")),
    ("speaker", "region"): (Decimal("12"), Decimal("40")),
    ("speaker", "federal"): (Decimal("20"), Decimal("60")),
    ("volunteer", "college"): (Decimal("4"), Decimal("12")),
    ("volunteer", "city"): (Decimal("7"), Decimal("20")),
    ("volunteer", "region"): (Decimal("10"), Decimal("30")),
    ("volunteer", "federal"): (Decimal("15"), Decimal("45")),
}

# --- Раздел 6: олимпиады -----------------------------------------------------
# Уровень определяется уровнем организатора и официальным положением (п. 6.1).

POLOZHENIE_OLYMPIAD_LEVELS = ("college", "municipal", "region", "federal")
POLOZHENIE_OLYMPIAD_LEVEL_TITLES = {
    "college": "Колледж",
    "municipal": "Муниципальный",
    "region": "Региональный",
    "federal": "Федеральный",
}

# Результаты по возрастанию: победа старше участия (п. 6.3).
POLOZHENIE_OLYMPIAD_RESULTS = ("participation", "win")
POLOZHENIE_OLYMPIAD_RESULT_TITLES = {
    "participation": "Участие",
    "win": "Победа",
}

POLOZHENIE_OLYMPIAD_TARIFFS = {
    ("participation", "college"): (Decimal("1"), Decimal("3")),
    ("participation", "municipal"): (Decimal("2"), Decimal("5")),
    ("participation", "region"): (Decimal("3"), Decimal("8")),
    ("participation", "federal"): (Decimal("5"), Decimal("12")),
    ("win", "college"): (Decimal("5"), Decimal("15")),
    ("win", "municipal"): (Decimal("10"), Decimal("30")),
    ("win", "region"): (Decimal("15"), Decimal("50")),
    ("win", "federal"): (Decimal("25"), Decimal("80")),
}

# --- Раздел 7: проекты бизнес-инкубатора ------------------------------------

POLOZHENIE_PROJECT_RESULTS = ("task", "stage", "project")
POLOZHENIE_PROJECT_TARIFFS = {
    "task": {
        "title": "Небольшая самостоятельная задача",
        "rating": Decimal("5"),
        "coins": Decimal("20"),
    },
    "stage": {
        "title": "Завершённый этап проекта",
        "rating": Decimal("10"),
        "coins": Decimal("40"),
    },
    "project": {
        "title": "Завершённый проект",
        "rating": Decimal("25"),
        "coins": Decimal("100"),
    },
}

# --- Раздел 8: статусы -------------------------------------------------------
# Нижняя граница включительно. Статус определяется текущим рейтингом (п. 8.1).

POLOZHENIE_STATUSES = (
    (Decimal("0"), "recruit", "Новобранец"),
    (Decimal("100"), "trainee", "Стажёр"),
    (Decimal("250"), "specialist", "Специалист"),
    (Decimal("500"), "pro", "Профи"),
    (Decimal("700"), "master", "Мастер"),
    (Decimal("900"), "legend", "Легенда"),
)

# --- Раздел 9: списания рейтинга --------------------------------------------
# п. 9.1: 1 балл за пару, максимум 4 за учебный день. Дополнительного штрафа
# за сам день нет. п. 9.4: штрафы затрагивают только рейтинг.

POLOZHENIE_PENALTIES = {
    "ABSENCE_PER_LESSON": Decimal("1"),
    "ABSENCE_DAILY_MAX": Decimal("4"),
}

# --- Раздел 10: обращения ----------------------------------------------------

POLOZHENIE_APPEALS = {
    "RESOLUTION_WORKING_DAYS": 5,
}
