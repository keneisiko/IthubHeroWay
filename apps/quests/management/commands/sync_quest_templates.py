"""Sync Quest records from QuestTemplate definitions."""

from __future__ import annotations

from django.conf import settings
from django.core.management.base import BaseCommand

from apps.quests.models import Quest, QuestTemplate, QuestType, QuestVerifierKind

DEFAULT_TEMPLATES = [
    {
        "code": "daily-hik-on-time",
        "title": "Утренний чек-ин",
        "description": "Пройди через турникет до 10:00 без опоздания (HikCentral + расписание отряда).",
        "quest_type": QuestType.DAILY,
        "verifier": QuestVerifierKind.HIK_ON_TIME,
        "verifier_params": {"deadline_hour": 10, "deadline_minute": 0},
        "reward_coins": 5,
        "reward_rating_delta": 2,
    },
    {
        "code": "daily-hik-no-late",
        "title": "День без опозданий",
        "description": "Ни одного опоздания за день по данным HikCentral.",
        "quest_type": QuestType.DAILY,
        "verifier": QuestVerifierKind.HIK_NO_LATE,
        "verifier_params": {"days": 1},
        "reward_coins": 5,
        "reward_rating_delta": 3,
    },
    {
        "code": "daily-lxp-attendance",
        "title": "Посещение занятий",
        "description": "Подтверждённая посещаемость в LXP за учебный день.",
        "quest_type": QuestType.DAILY,
        "verifier": QuestVerifierKind.LXP_ATTENDANCE,
        "verifier_params": {"use_previous_day": True},
        "reward_coins": 8,
        "reward_rating_delta": 3,
    },
    {
        "code": "weekly-yougile-tasks",
        "title": "Спринт YouGile",
        "description": "Закрой минимум 3 задачи в YouGile за неделю (webhook).",
        "quest_type": QuestType.WEEKLY,
        "verifier": QuestVerifierKind.YOUGILE_TASKS,
        "verifier_params": {"days": 7, "min_count": 3},
        "reward_coins": 25,
        "reward_rating_delta": 10,
    },
    {
        "code": "weekly-lxp-ct",
        "title": "Закрыть контрольную точку",
        "description": "Сдай минимум одну КТ в LXP за неделю.",
        "quest_type": QuestType.WEEKLY,
        "verifier": QuestVerifierKind.LXP_CT_CLOSED,
        "verifier_params": {"min_closed": 1},
        "reward_coins": 15,
        "reward_rating_delta": 8,
    },
    {
        "code": "weekly-no-late",
        "title": "Неделя без опозданий",
        "description": "5 учебных дней подряд без опозданий (HikCentral).",
        "quest_type": QuestType.WEEKLY,
        "verifier": QuestVerifierKind.HIK_NO_LATE,
        "verifier_params": {"days": 5},
        "reward_coins": 20,
        "reward_rating_delta": 12,
    },
    {
        "code": "weekly-late-streak",
        "title": "Серия дисциплины",
        "description": "Поддерживай серию минимум 7 дней без опозданий.",
        "quest_type": QuestType.WEEKLY,
        "verifier": QuestVerifierKind.LATE_STREAK,
        "verifier_params": {"min_days": 7},
        "reward_coins": 10,
        "reward_rating_delta": 5,
    },
    {
        "code": "self-report-lab",
        "title": "Лабораторная работа",
        "description": "Сдай отчёт о выполненной лабораторной (проверка куратором).",
        "quest_type": QuestType.SELF_REPORT,
        "verifier": QuestVerifierKind.MANUAL,
        "verifier_params": {},
        "reward_coins": 20,
        "reward_rating_delta": 8,
    },
    {
        "code": "self-report-project",
        "title": "Мини-проект",
        "description": "Опиши прогресс по мини-проекту (проверка куратором).",
        "quest_type": QuestType.SELF_REPORT,
        "verifier": QuestVerifierKind.MANUAL,
        "verifier_params": {},
        "reward_coins": 30,
        "reward_rating_delta": 12,
    },
]


class Command(BaseCommand):
    help = "Create/update QuestTemplate and Quest records from built-in templates."

    def handle(self, *args, **options):
        rewards = getattr(settings, "QUESTS_REWARDS", {})
        created_tpl = 0
        synced_quests = 0

        for row in DEFAULT_TEMPLATES:
            coins = row.get("reward_coins")
            if row["quest_type"] == QuestType.DAILY and not coins:
                coins = rewards.get("DAILY_QUEST_REWARD", 3)
            if row["quest_type"] == QuestType.WEEKLY and not coins:
                coins = rewards.get("WEEKLY_QUEST_REWARD", 10)

            tpl, tpl_created = QuestTemplate.objects.update_or_create(
                code=row["code"],
                defaults={
                    "title": row["title"],
                    "description": row["description"],
                    "quest_type": row["quest_type"],
                    "verifier": row["verifier"],
                    "verifier_params": row.get("verifier_params") or {},
                    "reward_coins": coins,
                    "reward_rating_delta": row.get("reward_rating_delta", 0),
                    "is_active": True,
                },
            )
            if tpl_created:
                created_tpl += 1

            conditions = tpl.build_conditions()
            quest, _ = Quest.objects.update_or_create(
                code=tpl.code,
                defaults={
                    "title": tpl.title,
                    "description": tpl.description,
                    "quest_type": tpl.quest_type,
                    "reward_coins": tpl.reward_coins,
                    "reward_rating_delta": tpl.reward_rating_delta,
                    "conditions": conditions,
                    "is_active": tpl.is_active,
                },
            )
            synced_quests += 1
            self.stdout.write(f"  {quest.code} [{quest.quest_type}] verifier={conditions.get('verifier')}")

        self.stdout.write(
            self.style.SUCCESS(
                f"Templates: {len(DEFAULT_TEMPLATES)} ({created_tpl} new), quests synced: {synced_quests}"
            )
        )
