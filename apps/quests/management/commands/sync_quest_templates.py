"""Sync Quest records from QuestTemplate definitions."""

from __future__ import annotations

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import transaction

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


def _reward_coins(row: dict, rewards: dict) -> int:
    """Награда шаблона: значение из DEFAULT_TEMPLATES, иначе значение из settings."""
    # Раньше подстановка из QUESTS_REWARDS проверяла `not coins` уже после того,
    # как все шаблоны проставили ненулевой reward_coins, поэтому ветка была
    # недостижима. Условие переписано на отсутствие ключа: шаблон может награду
    # не задавать, и тогда действует общая настройка для своего типа квеста.
    coins = row.get("reward_coins")
    if coins is not None:
        return int(coins)
    if row["quest_type"] == QuestType.DAILY:
        return int(rewards.get("DAILY_QUEST_REWARD", 3))
    if row["quest_type"] == QuestType.WEEKLY:
        return int(rewards.get("WEEKLY_QUEST_REWARD", 10))
    return 0


class Command(BaseCommand):
    help = (
        "Создаёт QuestTemplate и Quest по встроенным шаблонам. "
        "Существующие записи по умолчанию не трогает (см. --update-existing)."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--update-existing",
            action="store_true",
            help="Перезаписать поля уже существующих шаблонов и квестов значениями из кода.",
        )

    def handle(self, *args, **options):
        rewards = getattr(settings, "QUESTS_REWARDS", {})
        update_existing = bool(options.get("update_existing"))
        created_tpl = 0
        created_quests = 0
        updated = 0
        skipped = 0

        # Транзакция: раньше падение на середине списка оставляло часть шаблонов
        # синхронизированной, а часть — нет, и повторный прогон было не с чего начинать.
        with transaction.atomic():
            for row in DEFAULT_TEMPLATES:
                defaults = {
                    "title": row["title"],
                    "description": row["description"],
                    "quest_type": row["quest_type"],
                    "verifier": row["verifier"],
                    "verifier_params": row.get("verifier_params") or {},
                    "reward_coins": _reward_coins(row, rewards),
                    "reward_rating_delta": row.get("reward_rating_delta", 0),
                    "is_active": True,
                }
                # get_or_create вместо update_or_create: команда вызывается по расписанию
                # и из seed_demo_data, и каждый её прогон затирал правки, сделанные
                # вручную в админке (название, описание, награда, активность).
                tpl, tpl_created = QuestTemplate.objects.get_or_create(code=row["code"], defaults=defaults)
                if tpl_created:
                    created_tpl += 1
                elif update_existing:
                    for field, value in defaults.items():
                        setattr(tpl, field, value)
                    tpl.save(update_fields=list(defaults))

                conditions = tpl.build_conditions()
                quest_defaults = {
                    "title": tpl.title,
                    "description": tpl.description,
                    "quest_type": tpl.quest_type,
                    "reward_coins": tpl.reward_coins,
                    "reward_rating_delta": tpl.reward_rating_delta,
                    "conditions": conditions,
                    "is_active": tpl.is_active,
                }
                quest, quest_created = Quest.objects.get_or_create(code=tpl.code, defaults=quest_defaults)
                if quest_created:
                    created_quests += 1
                elif update_existing:
                    for field, value in quest_defaults.items():
                        setattr(quest, field, value)
                    quest.save(update_fields=list(quest_defaults))
                    updated += 1
                else:
                    skipped += 1

                self.stdout.write(f"  {quest.code} [{quest.quest_type}] verifier={conditions.get('verifier')}")

        self.stdout.write(
            self.style.SUCCESS(
                f"Шаблонов: {len(DEFAULT_TEMPLATES)} (новых {created_tpl}), "
                f"квестов создано: {created_quests}, обновлено: {updated}, без изменений: {skipped}"
            )
        )
