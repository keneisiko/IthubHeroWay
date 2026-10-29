"""Страница «Правила»: за что даются баллы и монеты.

Цифры берутся из тех же настроек и констант, по которым идут начисления,
а не вписываются в интерфейс руками: поменялся тариф — страница показывает
новый, и студент не видит одно, а получает другое.
"""

from __future__ import annotations

from decimal import Decimal

from django.conf import settings
from django.db.models import Max, Min
from rest_framework import views
from rest_framework.response import Response

from apps.accounts.permissions import IsKnownRole
from apps.badges.models import Badge
from apps.operations.services.platform_settings import platform_setting
from apps.progress.services import king_of_hill as king
from apps.quests.models import QuestTemplate, QuestType
from apps.social.services.rewards import MENTOR_CAP_PER_MENTEE, MENTOR_SHARE


def _num(value) -> float:
    return float(Decimal(str(value)))


def _matrix(tariffs: dict, rows: tuple, row_titles: dict, cols: tuple, col_titles: dict) -> dict:
    """Таблица тарифов «роль × уровень» в виде, удобном фронту."""
    return {
        "columns": [col_titles.get(c, c) for c in cols],
        "rows": [
            {
                "title": row_titles.get(r, r),
                "cells": [
                    {"rating": _num(tariffs[(r, c)][0]), "coins": _num(tariffs[(r, c)][1])}
                    for c in cols
                ],
            }
            for r in rows
        ],
    }


def _quest_ranges() -> list[dict]:
    titles = {
        QuestType.DAILY: "Ежедневные",
        QuestType.WEEKLY: "Еженедельные",
        QuestType.SELF_REPORT: "Самоотчёты (проверяет куратор)",
    }
    rows = []
    for quest_type, title in titles.items():
        agg = QuestTemplate.objects.filter(is_active=True, quest_type=quest_type).aggregate(
            low=Min("reward_coins"), high=Max("reward_coins")
        )
        if agg["low"] is not None:
            rows.append({"title": title, "coins_min": agg["low"], "coins_max": agg["high"]})
    return rows


def rules_payload() -> dict:
    academic = settings.POLOZHENIE_ACADEMIC
    penalties = settings.POLOZHENIE_PENALTIES
    badge_coins = Badge.objects.filter(is_active=True, reward_coins__gt=0).aggregate(
        low=Min("reward_coins"), high=Max("reward_coins")
    )
    return {
        "polozhenie": {"version": settings.POLOZHENIE_VERSION, "date": settings.POLOZHENIE_DATE},
        "academic": {
            "ct_weekly_max": _num(academic["CT_WEEKLY_MAX"]),
            "attendance_weekly_max": _num(academic["ATTENDANCE_WEEKLY_MAX"]),
        },
        "roles": [
            {"title": r["title"], "rating": _num(r["rating"]), "coins": _num(r["coins"])}
            for r in sorted(settings.POLOZHENIE_ROLES.values(), key=lambda r: r["rating"])
        ],
        "events": _matrix(
            settings.POLOZHENIE_EVENT_TARIFFS,
            settings.POLOZHENIE_EVENT_ROLES,
            settings.POLOZHENIE_EVENT_ROLE_TITLES,
            settings.POLOZHENIE_EVENT_LEVELS,
            settings.POLOZHENIE_EVENT_LEVEL_TITLES,
        ),
        "olympiads": _matrix(
            settings.POLOZHENIE_OLYMPIAD_TARIFFS,
            settings.POLOZHENIE_OLYMPIAD_RESULTS,
            settings.POLOZHENIE_OLYMPIAD_RESULT_TITLES,
            settings.POLOZHENIE_OLYMPIAD_LEVELS,
            settings.POLOZHENIE_OLYMPIAD_LEVEL_TITLES,
        ),
        "projects": [
            {"title": p["title"], "rating": _num(p["rating"]), "coins": _num(p["coins"])}
            for p in settings.POLOZHENIE_PROJECT_TARIFFS.values()
        ],
        "mentorship": {
            "share_percent": int(MENTOR_SHARE * 100),
            "cap_per_mentee": _num(MENTOR_CAP_PER_MENTEE),
        },
        "penalties": {
            "per_missed_lesson": _num(penalties["ABSENCE_PER_LESSON"]),
            "daily_max": _num(penalties["ABSENCE_DAILY_MAX"]),
        },
        "coins_only": {
            "quests": _quest_ranges(),
            "max_daily_quest_coins": int(platform_setting("max_daily_coins")),
            "badges": {"coins_min": badge_coins["low"] or 0, "coins_max": badge_coins["high"] or 0},
            "respect_coins": int(getattr(settings, "QUESTS_REWARDS", {}).get("RESPECT_REWARD", 0)),
            "duel_bet": int(platform_setting("duel_bet")),
            "king": {
                "top": list(king.TOP_REWARDS),
                "course_leader": king.COURSE_LEADER_REWARD,
                "streak_days": king.STREAK_DAYS,
                "streak_reward": king.STREAK_REWARD,
                "dethrone": king.DETHRONE_REWARD,
                "squad_leader": king.SQUAD_LEADER_REWARD,
            },
        },
    }


class RulesView(views.APIView):
    permission_classes = [IsKnownRole]

    def get(self, request, *args, **kwargs):
        return Response(rules_payload())
