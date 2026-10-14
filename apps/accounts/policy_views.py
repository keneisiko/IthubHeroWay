"""Ознакомление с Положением и его принятие (п. 2.1).

Пункт 2.1 Положения: «Студент активирует профиль входом с учебным логином
и паролем после ознакомления и принятия настоящего Положения». До этого
в платформе такого шага не было вовсе — студент сразу попадал на дашборд.

Начислений это не касается: по п. 2.2 они идут с общей даты запуска всем,
и непринятое Положение их не отменяет. Принятие — отдельный факт, который
колледж должен уметь показать.
"""

from __future__ import annotations

from django.conf import settings
from rest_framework import serializers, status, views
from rest_framework.response import Response

from apps.accounts.models import PolicyAcceptance
from apps.accounts.permissions import IsKnownRole


def current_version() -> str:
    return str(getattr(settings, "POLOZHENIE_VERSION", "")).strip()


def has_accepted_current(user) -> bool:
    version = current_version()
    if not version:
        return True
    return PolicyAcceptance.objects.filter(user=user, version=version).exists()


class PolicyAcceptanceSerializer(serializers.Serializer):
    version = serializers.CharField(required=False, allow_blank=True)

    def validate_version(self, value: str) -> str:
        expected = current_version()
        value = (value or "").strip()
        if value and value != expected:
            # Принять можно только действующую редакцию: иначе согласие
            # с прошлой версией выглядело бы как согласие с новой.
            raise serializers.ValidationError(
                f"Действующая редакция Положения — {expected}."
            )
        return expected


class PolicyStateView(views.APIView):
    """Что показать студенту и принял ли он действующую редакцию."""

    permission_classes = [IsKnownRole]

    def get(self, request, *args, **kwargs):
        accepted = (
            PolicyAcceptance.objects.filter(user=request.user, version=current_version())
            .order_by("-accepted_at")
            .first()
        )
        return Response(
            {
                "version": current_version(),
                "document_date": getattr(settings, "POLOZHENIE_DATE", ""),
                "accepted": accepted is not None,
                "accepted_at": accepted.accepted_at if accepted else None,
                "season_start": getattr(settings, "POLOZHENIE_PERIOD", {}).get(
                    "SEASON_START_DATE", ""
                ),
            }
        )

    def post(self, request, *args, **kwargs):
        serializer = PolicyAcceptanceSerializer(data=request.data)
        serializer.is_valid(raise_exception=True)
        # Поле необязательное: фронт может прислать пустой запрос, и тогда
        # принимается действующая редакция.
        version = serializer.validated_data.get("version") or current_version()

        # Повторное принятие не создаёт вторую запись и не считается ошибкой:
        # студент мог обновить страницу.
        acceptance, created = PolicyAcceptance.objects.get_or_create(
            user=request.user, version=version
        )
        return Response(
            {
                "version": version,
                "accepted": True,
                "accepted_at": acceptance.accepted_at,
                "created": created,
            },
            status=status.HTTP_201_CREATED if created else status.HTTP_200_OK,
        )
