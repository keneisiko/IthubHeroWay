"""
Коэффициенты рейтинга 1000 v2.0 (Путь героя).
Используются квестами, интеграцией LXP и ручными начислениями.
"""

# --- Гигиена (~КП): успеваемость, посещаемость, дисциплина ---
RATING_KP = {
    "CT_ON_TIME": 20,
    "CT_LATE_WITHIN_7D": 10,
    "CT_LATE_MORE_7D": 5,
    "CT_NOT_SUBMITTED": -20,
    "CT_RETAKE_SUCCESS": 5,
    "CT_ALL_CLOSED_BONUS": 30,
    "CT_DEBT_WEEKLY_PENALTY": -10,
    "ATTENDANCE_FULL_WEEK": 15,
    "ATTENDANCE_STREAK_7D": 5,
    "ABSENCE_UNEXCUSED": -10,
    "ABSENCE_EXCUSED": 0,
    "LATE_LIGHT": -3,
    "LATE_MODERATE": -5,
    "LATE_SEVERE": -8,
    "LATE_STREAK_BREAK_BONUS": 10,
    "LATE_STREAK_7D": 5,
    "LATE_STREAK_14D": 10,
    "LATE_STREAK_21D": 15,
    "DISCIPLINE_MINOR": -15,
    "DISCIPLINE_MAJOR": -40,
    "ZONE_RED_TO_ORANGE": 30,
    "ZONE_ORANGE_TO_YELLOW": 20,
}

# --- Движ: мероприятия, проекты (не из ежедневного снимка LXP) ---
RATING_DRIVE = {
    "EVENT_PARTICIPATION": 20,
    "CLUB_ACTIVITY_MONTHLY": 30,
    "VOLUNTEER_ONE_TIME": 25,
    "VOLUNTEER_SYSTEMATIC": 40,
    "EVENT_ORGANIZER": 45,
    "MENTORING": 15,
    "DEMO_DAY_SPEAKER": 40,
    "OLYMPIAD_PARTICIPATION": 50,
    "OLYMPIAD_WIN": 90,
    "PROJECT_FIRST_VICTORY": 100,
    "PROJECT_INCUBATOR": 120,
    "CLUB_LEADERSHIP": 35,
    "MEDIA_HELP": 5,
}

QUESTS_REWARDS = {
    "DAILY_QUEST_REWARD": 3,
    "WEEKLY_QUEST_REWARD": 10,
    "SEASONAL_QUEST_REWARD": 50,
    "PERSONAL_QUEST_REWARD": 8,
    "TEAM_QUEST_REWARD": 80,
    "STREAK_3D_COINS": 5,
    "STREAK_7D_COINS": 15,
    "STREAK_21D_COINS": 30,
    "RESPECT_REWARD": 3,
    "MENTEE_WEEKLY_COINS": 2,
}

# --- Годовая модель рейтинга ---
# Рейтинг копится за учебный год: старт 300 в сентябре, рост — только за события
# (закрытая КТ, выполненный квест, мероприятие), а не за ежедневную переоценку
# одного и того же состояния. Годовой бюджет делится на ожидаемое число тем
# курса, поэтому курс с 60 темами в году и курс с 30 темами получают за год
# сопоставимый максимум.
RATING_YEAR = {
    "ACADEMIC_YEAR_START_MONTH": 9,
    "ACADEMIC_YEAR_START_DAY": 1,
    # Сколько рейтинга можно набрать за год закрытием контрольных точек.
    "CT_YEAR_BUDGET": 400,
    # Границы стоимости одной темы после нормировки — защита от вырожденных
    # когорт (одна тема на курс дала бы +400 за штуку).
    "CT_POINTS_MIN": 4,
    "CT_POINTS_MAX": 40,
    # Пока о курсе нет данных (первый снимок), считаем по этому числу тем.
    "CT_EXPECTED_TOPICS_FALLBACK": 40,
    # Сколько дней тема может оставаться открытой, прежде чем считается
    # просроченной. У LXP нет поля дедлайна, поэтому «просрочка» выводится
    # из наблюдений: тема висит открытой дольше этого срока.
    "TOPIC_STALE_DAYS": 30,
    # Штраф за просроченную тему начисляется один раз на тему, а не ежедневно.
    "STALE_PENALTY_PER_TOPIC": -20,
    # Сколько просроченных тем блокируют рост рейтинга выше жёлтой зоны.
    "STALE_BLOCK_THRESHOLD": 2,
    # Бонус «все КТ закрыты» — не чаще раза в этот период.
    "ALL_CLOSED_BONUS_COOLDOWN_DAYS": 30,
}

RATING_LIMITS = {
    "MAX_DAILY_COINS": 20,
    "MAX_DAILY_SELF_REPORTS": 3,
    "CT_UNCLOSED_BLOCK_THRESHOLD": 2,
    "MAX_RATING_WHEN_BLOCKED": 399,
    "DEFAULT_RATING_START": 300,
    "DUEL_MAX_RATING_DIFF": 150,
    "DUEL_ACTIVE_LIMIT": 1,
    "DUEL_BET": 5,
    "RESPECT_WEEKLY_LIMIT": 1,
    "RESPECT_SAME_USER_COOLDOWN": 14,
    # Лимиты на одну итерацию пересчёта из снимка LXP (защита от выбросов)
    "LXP_SNAPSHOT_CT_POSITIVE_CAP": 40,
    "LXP_SNAPSHOT_CT_NEGATIVE_CAP": 60,
    "LXP_SNAPSHOT_ABSENCE_CAP": 10,
}
