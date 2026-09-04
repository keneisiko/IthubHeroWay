"""Очередь подтверждений: кто что проверяет.

Правило видимости было записано дважды — в админке `SelfReportProofAdmin`
и в дашбордах куратора и тьютора. Расхождение здесь означает, что счётчик
показывает одно число, а список открывается с другим.
"""

from __future__ import annotations

from apps.accounts.models import Role
from apps.quests.models import SelfReportProof, SelfReportProofStatus


def reviewable_proofs(user):
    """Заявки, которые этот сотрудник имеет право проверять."""
    queryset = SelfReportProof.objects.select_related("user", "user__squad", "quest")

    if user.is_superuser or user.role == Role.ADMIN:
        return queryset
    if user.role == Role.CURATOR:
        # Куратор отвечает за свой отряд; без отряда проверять нечего.
        if not user.squad_id:
            return queryset.none()
        return queryset.filter(user__squad_id=user.squad_id)
    if user.role == Role.TUTOR:
        return queryset.filter(user__squad__course__gte=2, user__squad__course__lte=4)
    # Штаб к проверке подтверждений не допущен.
    return queryset.none()


def pending_proofs(user):
    return reviewable_proofs(user).filter(status=SelfReportProofStatus.PENDING).order_by("-created_at")


def pending_proofs_count(user) -> int:
    return pending_proofs(user).count()
