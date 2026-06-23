"""Helpers for quest conditions / auto-verification flags."""

from __future__ import annotations

from apps.quests.models import Quest, QuestTemplate, QuestType, QuestVerifierKind


def quest_conditions(quest: Quest) -> dict:
    return quest.conditions if isinstance(quest.conditions, dict) else {}


def is_auto_verified(quest: Quest) -> bool:
    cond = quest_conditions(quest)
    if cond.get("auto_verify"):
        return True
    verifier = cond.get("verifier")
    return bool(verifier and verifier != QuestVerifierKind.MANUAL)


def is_manual_complete_allowed(quest: Quest) -> bool:
    """POST /complete/ — только для legacy-ручных квестов без автопроверки."""
    if is_auto_verified(quest):
        return False
    if quest.quest_type in {QuestType.SELF_REPORT, QuestType.MIXED}:
        return False
    cond = quest_conditions(quest)
    return cond.get("manual_complete_allowed", True) is not False


def resolve_verifier_config(quest: Quest) -> tuple[str | None, dict]:
    cond = quest_conditions(quest)
    verifier = cond.get("verifier")
    params = dict(cond.get("params") or {})
    template_code = cond.get("template_code")
    if template_code and not verifier:
        tpl = QuestTemplate.objects.filter(code=template_code, is_active=True).first()
        if tpl:
            verifier = tpl.verifier
            merged = dict(tpl.verifier_params or {})
            merged.update(params)
            params = merged
    return verifier, params
