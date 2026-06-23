from __future__ import annotations

from datetime import date

from celery import shared_task
from django.core.management import call_command
from django.utils import timezone

from apps.quests.models import QuestType
from apps.quests.services.quest_verification import verify_all_auto_quests


@shared_task
def send_daily_quest() -> str:
    """Ensure quest templates are synced (07:30). Notifications — отдельно."""
    call_command("sync_quest_templates")
    return "sync_quest_templates:ok"


@shared_task
def verify_auto_quests(target_date_iso: str | None = None) -> dict:
    """Проверка daily + weekly квестов с auto_verify."""
    target = date.fromisoformat(target_date_iso) if target_date_iso else timezone.localdate()
    daily = verify_all_auto_quests(target, quest_types=[QuestType.DAILY])
    weekly = verify_all_auto_quests(target, quest_types=[QuestType.WEEKLY])
    return {"daily": daily, "weekly": weekly}
