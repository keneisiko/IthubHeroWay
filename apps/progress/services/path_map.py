"""Карта пути студента.

Интерфейс профиля рисует семь вех — от входа до выпуска, — но поле
`path_reached` бэкенд не отдавал, и фронт подставлял `['entry']`. У всех
студентов, независимо от достижений, была пройдена ровно одна точка.

Каждая веха выводится из уже существующих данных, кроме двух последних:
стажировка и выпуск фиксируются значком, который выдаёт куратор. Автоматики
для них нет — в LXP и Hik таких событий не существует, а привязывать «выпуск»
к номеру курса значило бы объявить выпускниками всех четверокурсников
первого сентября.
"""

from __future__ import annotations

from apps.badges.models import UserBadge
from apps.progress.models import RatingLog
from apps.quests.models import QuestRewardTransaction, QuestType, SelfReportProofStatus, UserQuestProgress

# Коды вех совпадают с теми, что рисует фронт (Profile.tsx).
PATH_ENTRY = "entry"
PATH_FIRST_WIN = "first_win"
PATH_FIRST_FAIL = "first_fail"
PATH_FIRST_MISSION = "first_mission"
PATH_PRODUCT = "product"
PATH_INTERNSHIP = "internship"
PATH_GRADUATION = "graduation"

PATH_ORDER = (
    PATH_ENTRY,
    PATH_FIRST_WIN,
    PATH_FIRST_FAIL,
    PATH_FIRST_MISSION,
    PATH_PRODUCT,
    PATH_INTERNSHIP,
    PATH_GRADUATION,
)

# Значки, которыми куратор отмечает вехи, не выводимые из данных.
INTERNSHIP_BADGE_CODE = "path-internship"
GRADUATION_BADGE_CODE = "path-graduation"


def path_reached(user) -> list[str]:
    """Коды пройденных вех карты пути в порядке следования."""
    reached: list[str] = []

    # Вход: аккаунт подтверждён в Telegram. Без привязки студент вообще
    # не может войти на платформу, так что до этой точки он не дошёл.
    telegram_link = getattr(user, "telegram_link", None)
    if telegram_link and telegram_link.is_active:
        reached.append(PATH_ENTRY)

    if QuestRewardTransaction.objects.filter(user=user).exists():
        reached.append(PATH_FIRST_WIN)

    # Первый провал: любое списание рейтинга — штраф за опоздание,
    # просроченная контрольная точка, дисциплинарное взыскание.
    if RatingLog.objects.filter(user=user, delta__lt=0).exists():
        reached.append(PATH_FIRST_FAIL)

    if UserQuestProgress.objects.filter(
        user=user, is_completed=True, quest__quest_type=QuestType.WEEKLY
    ).exists():
        reached.append(PATH_FIRST_MISSION)

    # Продукт: защищённый самоотчёт — единственное место, где студент сдаёт
    # собственную работу и её принимает человек.
    if user.self_report_proofs.filter(status=SelfReportProofStatus.APPROVED).exists():
        reached.append(PATH_PRODUCT)

    badge_codes = set(
        UserBadge.objects.filter(
            user=user, badge__code__in=[INTERNSHIP_BADGE_CODE, GRADUATION_BADGE_CODE]
        ).values_list("badge__code", flat=True)
    )
    if INTERNSHIP_BADGE_CODE in badge_codes:
        reached.append(PATH_INTERNSHIP)
    if GRADUATION_BADGE_CODE in badge_codes:
        reached.append(PATH_GRADUATION)

    return [code for code in PATH_ORDER if code in reached]
