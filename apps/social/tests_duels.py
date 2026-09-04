"""Дуэли: полный цикл от вызова до подведения итога.

Механики не было: вызов создавался, принятие меняло статус — и всё.
Победителя никто не определял, ставка `DUEL_BET` не использовалась нигде,
а принятая дуэль навсегда оставалась активной и блокировала обоим
участникам любые новые вызовы.
"""

from __future__ import annotations

from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import override_settings
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APITestCase

from apps.accounts.models import Role
from apps.social.models import Duel, DuelStatus
from apps.social.services.duels import (
    DuelNotAllowed,
    accept_duel,
    cancel_duel,
    duel_wins,
    reject_duel,
    resolve_due_duels,
)

User = get_user_model()

LIMITS = {
    "DUEL_BET": 5,
    "DUEL_DURATION_DAYS": 7,
    "DUEL_INVITE_TTL_DAYS": 3,
    "DUEL_MAX_RATING_DIFF": 150,
    "MAX_DAILY_COINS": 20,
}


def make_agent(username: str, rating: int = 300, coins: int = 100) -> User:
    return User.objects.create_user(
        username=username,
        email=f"{username}@test.ru",
        password="x",
        callsign=f"call_{username}",
        role=Role.AGENT,
        rating_current=rating,
        coins_balance=coins,
    )


@override_settings(RATING_LIMITS=LIMITS)
class DuelFlowTests(APITestCase):
    def setUp(self):
        self.challenger = make_agent("duelist_a", rating=500)
        self.opponent = make_agent("duelist_b", rating=520)
        self.client.force_authenticate(self.challenger)

    def _create(self) -> Duel:
        return Duel.objects.create(
            challenger=self.challenger, opponent=self.opponent, status=DuelStatus.PENDING
        )

    def test_accept_records_start_ratings_and_deadline(self):
        duel = self._create()

        accepted = accept_duel(self.opponent, duel.pk)

        self.assertEqual(accepted.status, DuelStatus.ACCEPTED)
        self.assertEqual(accepted.challenger_rating_start, 500)
        self.assertEqual(accepted.opponent_rating_start, 520)
        self.assertIsNotNone(accepted.resolve_after)
        self.assertEqual(accepted.bet_coins, 5)

    def test_only_opponent_can_accept(self):
        duel = self._create()

        with self.assertRaises(DuelNotAllowed):
            accept_duel(self.challenger, duel.pk)

    def test_answered_invite_cannot_be_answered_again(self):
        duel = self._create()
        reject_duel(self.opponent, duel.pk)

        with self.assertRaises(DuelNotAllowed):
            accept_duel(self.opponent, duel.pk)

    def test_challenger_can_cancel_pending_invite(self):
        duel = self._create()

        cancelled = cancel_duel(self.challenger, duel.pk)

        self.assertEqual(cancelled.status, DuelStatus.REJECTED)
        self.assertIsNotNone(cancelled.resolved_at)

    def test_winner_is_the_one_who_gained_more_rating(self):
        duel = self._create()
        accept_duel(self.opponent, duel.pk)

        self.opponent.rating_current += 40
        self.opponent.save(update_fields=["rating_current"])
        self.challenger.rating_current += 10
        self.challenger.save(update_fields=["rating_current"])
        Duel.objects.filter(pk=duel.pk).update(resolve_after=timezone.now() - timedelta(minutes=1))

        result = resolve_due_duels()

        duel.refresh_from_db()
        self.assertEqual(result["resolved"], 1)
        self.assertEqual(duel.winner, self.opponent)
        self.assertEqual(duel.status, DuelStatus.FINISHED)

    def test_bet_is_transferred_not_burned(self):
        """Ставка — перевод между студентами: сколько списали, столько и дали."""
        duel = self._create()
        accept_duel(self.opponent, duel.pk)
        self.opponent.rating_current += 30
        self.opponent.save(update_fields=["rating_current"])
        Duel.objects.filter(pk=duel.pk).update(resolve_after=timezone.now() - timedelta(minutes=1))

        resolve_due_duels()

        self.challenger.refresh_from_db()
        self.opponent.refresh_from_db()
        self.assertEqual(self.challenger.coins_balance, 95)
        self.assertEqual(self.opponent.coins_balance, 105)

    def test_draw_changes_nothing(self):
        duel = self._create()
        accept_duel(self.opponent, duel.pk)
        Duel.objects.filter(pk=duel.pk).update(resolve_after=timezone.now() - timedelta(minutes=1))

        resolve_due_duels()

        duel.refresh_from_db()
        self.challenger.refresh_from_db()
        self.opponent.refresh_from_db()
        self.assertIsNone(duel.winner)
        self.assertEqual(duel.status, DuelStatus.FINISHED)
        self.assertEqual(self.challenger.coins_balance, 100)
        self.assertEqual(self.opponent.coins_balance, 100)

    def test_loser_without_coins_does_not_go_negative(self):
        self.challenger.coins_balance = 2
        self.challenger.save(update_fields=["coins_balance"])
        duel = self._create()
        accept_duel(self.opponent, duel.pk)
        self.opponent.rating_current += 30
        self.opponent.save(update_fields=["rating_current"])
        Duel.objects.filter(pk=duel.pk).update(resolve_after=timezone.now() - timedelta(minutes=1))

        resolve_due_duels()

        self.challenger.refresh_from_db()
        self.opponent.refresh_from_db()
        self.assertEqual(self.challenger.coins_balance, 0)
        self.assertEqual(self.opponent.coins_balance, 102)

    def test_finished_duel_unblocks_new_challenges(self):
        """Раньше принятая дуэль оставалась активной вечно."""
        duel = self._create()
        accept_duel(self.opponent, duel.pk)
        Duel.objects.filter(pk=duel.pk).update(resolve_after=timezone.now() - timedelta(minutes=1))
        resolve_due_duels()

        response = self.client.post(
            reverse("social-duels-create"), {"opponent_username": self.opponent.username}, format="json"
        )

        self.assertEqual(response.status_code, 201)

    def test_stale_invite_expires(self):
        duel = self._create()
        Duel.objects.filter(pk=duel.pk).update(created_at=timezone.now() - timedelta(days=5))

        result = resolve_due_duels()

        duel.refresh_from_db()
        self.assertEqual(result["expired_invites"], 1)
        self.assertEqual(duel.status, DuelStatus.REJECTED)

    def test_wins_are_counted(self):
        duel = self._create()
        accept_duel(self.opponent, duel.pk)
        self.challenger.rating_current += 50
        self.challenger.save(update_fields=["rating_current"])
        Duel.objects.filter(pk=duel.pk).update(resolve_after=timezone.now() - timedelta(minutes=1))
        resolve_due_duels()

        self.assertEqual(duel_wins(self.challenger), 1)
        self.assertEqual(duel_wins(self.opponent), 0)


@override_settings(RATING_LIMITS=LIMITS)
class DuelApiTests(APITestCase):
    def setUp(self):
        self.user = make_agent("api_duelist", rating=400)
        self.rival = make_agent("api_rival", rating=420)
        self.client.force_authenticate(self.user)

    def test_my_duels_list_shows_invites(self):
        Duel.objects.create(challenger=self.rival, opponent=self.user, status=DuelStatus.PENDING)

        response = self.client.get(reverse("social-duels-my"))

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(len(body["results"]), 1)
        self.assertEqual(body["bet_coins"], 5)
        self.assertEqual(body["duration_days"], 7)

    def test_accept_via_api(self):
        duel = Duel.objects.create(
            challenger=self.rival, opponent=self.user, status=DuelStatus.PENDING
        )

        response = self.client.post(reverse("social-duels-accept", args=[duel.pk]))

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["status"], DuelStatus.ACCEPTED)

    def test_cancel_someone_elses_invite_is_rejected(self):
        duel = Duel.objects.create(
            challenger=self.rival, opponent=self.user, status=DuelStatus.PENDING
        )

        response = self.client.post(reverse("social-duels-cancel", args=[duel.pk]))

        self.assertEqual(response.status_code, 400)


@override_settings(RATING_LIMITS=LIMITS)
class DuelListLimitsTests(APITestCase):
    """Интерфейс подсвечивает доступных соперников до нажатия.

    Раньше порог разницы рейтинга знал только бэкенд: студент выбирал
    соперника, жал «вызвать» и получал отказ.
    """

    def setUp(self):
        self.user = make_agent("limits_user", rating=500)
        self.client.force_authenticate(self.user)

    def test_list_exposes_limit_and_my_rating(self):
        response = self.client.get(reverse("social-duels-my"))

        body = response.json()
        self.assertEqual(body["max_rating_diff"], 150)
        self.assertEqual(body["my_rating"], 500)
