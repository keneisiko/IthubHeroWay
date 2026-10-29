"""Шефство как дуэль: предложение → согласие подшефного → действующее.

Раньше шефство оформлялось одной кнопкой без согласия второй стороны, а за
каждого нового подшефного сразу начислялись 15 баллов. Взять подшефного,
завершить и взять следующего можно было без ограничений — на запуске один
студент так набрал 495 баллов за вечер.

Теперь:
- предложение ждёт согласия подшефного;
- баллы наставник получает только за успехи подшефного (rewards.pay_mentors_weekly);
- открытое предложение у наставника одно, нового подшефного — не чаще
  раза в MENTORSHIP_COOLDOWN_DAYS дней (считается от последнего согласия);
- взаимное шефство (A шефствует над B, B над A) запрещено;
- пара наставник–подшефный бывает один раз: повторно её не оформить.
"""

from __future__ import annotations

from datetime import timedelta

from django.conf import settings
from django.db import transaction
from django.utils import timezone

from apps.accounts.models import User
from apps.social.models import Mentorship, MentorshipStatus

MENTORSHIP_COOLDOWN_DAYS = 7
OPEN_STATUSES = (MentorshipStatus.PENDING, MentorshipStatus.ACTIVE)


class MentorshipNotAllowed(ValueError):
    pass


def _limit() -> int:
    return int(getattr(settings, "RATING_LIMITS", {}).get("MENTORSHIP_ACTIVE_LIMIT", 5))


def next_request_at(mentor: User):
    """Когда наставник сможет предложить шефство снова; None — уже может."""
    last = (
        Mentorship.objects.filter(mentor=mentor, accepted_at__isnull=False)
        .order_by("-accepted_at")
        .values_list("accepted_at", flat=True)
        .first()
    )
    if last is None:
        return None
    ready = last + timedelta(days=MENTORSHIP_COOLDOWN_DAYS)
    return ready if ready > timezone.now() else None


@transaction.atomic
def request_mentorship(mentor: User, mentee: User) -> Mentorship:
    if mentee.pk == mentor.pk:
        raise MentorshipNotAllowed("Нельзя стать наставником самому себе.")
    # Блокировка наставника: параллельные запросы не обойдут лимиты.
    User.objects.select_for_update().filter(pk=mentor.pk).first()

    previous = Mentorship.objects.select_for_update().filter(mentor=mentor, mentee=mentee).first()
    if previous is not None and (previous.accepted_at or previous.status == MentorshipStatus.PENDING):
        raise MentorshipNotAllowed("Шефство над этим студентом уже было — повторно его не оформить.")
    if Mentorship.objects.filter(mentor=mentee, mentee=mentor, status__in=OPEN_STATUSES).exists():
        raise MentorshipNotAllowed("Этот студент сам ваш наставник — взаимное шефство не оформляется.")
    if Mentorship.objects.filter(mentor=mentor, status=MentorshipStatus.PENDING).exists():
        raise MentorshipNotAllowed("Дождитесь ответа на прошлое предложение или отмените его.")
    ready = next_request_at(mentor)
    if ready is not None:
        raise MentorshipNotAllowed(
            f"Нового подшефного можно взять не раньше {timezone.localtime(ready):%d.%m %H:%M}."
        )
    limit = _limit()
    if limit > 0 and Mentorship.objects.filter(mentor=mentor, status=MentorshipStatus.ACTIVE).count() >= limit:
        raise MentorshipNotAllowed(f"У вас уже {limit} подшефных — это предел.")

    if previous is not None:
        # Отклонённое или отозванное предложение можно повторить: баллов оно
        # не давало. Запись одна на пару (unique_together), поэтому переоткрываем её.
        previous.status = MentorshipStatus.PENDING
        previous.ended_at = None
        previous.started_at = timezone.now()
        previous.save(update_fields=["status", "ended_at", "started_at"])
        return previous
    return Mentorship.objects.create(mentor=mentor, mentee=mentee, status=MentorshipStatus.PENDING)


def _locked(mentorship_id: int, **lookup) -> Mentorship:
    row = Mentorship.objects.select_for_update().filter(pk=mentorship_id, **lookup).first()
    if row is None:
        raise MentorshipNotAllowed("Шефство не найдено.")
    return row


@transaction.atomic
def accept_mentorship(mentee: User, mentorship_id: int) -> Mentorship:
    row = _locked(mentorship_id, mentee=mentee)
    if row.status != MentorshipStatus.PENDING:
        raise MentorshipNotAllowed("На это предложение уже ответили.")
    User.objects.select_for_update().filter(pk=row.mentor_id).first()
    limit = _limit()
    if limit > 0 and Mentorship.objects.filter(mentor_id=row.mentor_id, status=MentorshipStatus.ACTIVE).count() >= limit:
        raise MentorshipNotAllowed("У наставника уже полный набор подшефных.")
    row.status = MentorshipStatus.ACTIVE
    row.accepted_at = timezone.now()
    row.save(update_fields=["status", "accepted_at"])
    return row


@transaction.atomic
def decline_mentorship(mentee: User, mentorship_id: int) -> Mentorship:
    row = _locked(mentorship_id, mentee=mentee)
    if row.status != MentorshipStatus.PENDING:
        raise MentorshipNotAllowed("На это предложение уже ответили.")
    row.status = MentorshipStatus.DECLINED
    row.ended_at = timezone.now()
    row.save(update_fields=["status", "ended_at"])
    return row


@transaction.atomic
def end_mentorship(user: User, mentorship_id: int) -> Mentorship:
    """Завершить действующее шефство или отозвать своё предложение.

    Завершить может любая сторона: подшефному не нужно ждать, пока
    наставник сам его отпустит.
    """
    row = Mentorship.objects.select_for_update().filter(pk=mentorship_id).first()
    if row is None or user.pk not in (row.mentor_id, row.mentee_id):
        raise MentorshipNotAllowed("Шефство не найдено.")
    if row.status not in OPEN_STATUSES:
        raise MentorshipNotAllowed("Шефство уже завершено.")
    if row.status == MentorshipStatus.PENDING and user.pk != row.mentor_id:
        raise MentorshipNotAllowed("Предложение можно только принять или отклонить.")
    row.status = (
        MentorshipStatus.DECLINED if row.status == MentorshipStatus.PENDING else MentorshipStatus.ENDED
    )
    row.ended_at = timezone.now()
    row.save(update_fields=["status", "ended_at"])
    return row
