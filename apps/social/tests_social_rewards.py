"""Награды за респект и наставничество.

Коэффициенты `RESPECT_REWARD`, `MENTEE_WEEKLY_COINS` и `MENTORING` лежали
в настройках, но не начислялись нигде: респект уходил «в пустоту»,
а наставник за подшефных не получал ничего.
"""

from __future__ import annotations

from datetime import timedelta

from django.contrib.auth import get_user_model
from django.test import override_settings
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APITestCase

from apps.accounts.models import Role
from apps.progress.models import RatingLog
from apps.social.models import Mentorship, Respect
from apps.social.services.rewards import (
    grant_respect_reward,
    pay_mentors_weekly,
    respects_received_count,
)

User = get_user_model()

REWARDS = {"RESPECT_REWARD": 3, "MENTEE_WEEKLY_COINS": 2}
LIMITS = {"MAX_DAILY_COINS": 100, "RESPECT_WEEKLY_LIMIT": 1, "RESPECT_SAME_USER_COOLDOWN": 14}


def make_agent(username: str) -> User:
    return User.objects.create_user(
        username=username,
        email=f"{username}@test.ru",
        password="x",
        callsign=f"call_{username}",
        role=Role.AGENT,
        rating_current=300,
        coins_balance=0,
    )


@override_settings(QUESTS_REWARDS=REWARDS, RATING_LIMITS=LIMITS)
class RespectRewardTests(APITestCase):
    def setUp(self):
        self.sender = make_agent("respect_sender")
        self.receiver = make_agent("respect_receiver")
        self.client.force_authenticate(self.sender)

    def test_recipient_gets_coins(self):
        """Награду получает тот, кого отметили, а не отправитель."""
        response = self.client.post(
            reverse("social-respects-create"),
            {"to_username": self.receiver.username},
            format="json",
        )

        self.assertEqual(response.status_code, 201)
        self.receiver.refresh_from_db()
        self.sender.refresh_from_db()
        self.assertEqual(self.receiver.coins_balance, 3)
        self.assertEqual(self.sender.coins_balance, 0)
        self.assertEqual(response.json()["coins_granted_to_recipient"], 3)

    def test_service_is_reusable_outside_the_view(self):
        respect = Respect.objects.create(from_user=self.sender, to_user=self.receiver)

        granted = grant_respect_reward(respect)

        self.receiver.refresh_from_db()
        self.assertEqual(granted, 3)
        self.assertEqual(self.receiver.coins_balance, 3)

    def test_received_counter_covers_the_last_month(self):
        Respect.objects.create(from_user=self.sender, to_user=self.receiver)
        old = Respect.objects.create(from_user=self.sender, to_user=self.receiver)
        Respect.objects.filter(pk=old.pk).update(created_at=timezone.now() - timedelta(days=60))

        self.assertEqual(respects_received_count(self.receiver), 1)


@override_settings(
    QUESTS_REWARDS=REWARDS, RATING_LIMITS=LIMITS
)
class MentorshipRewardTests(APITestCase):
    def setUp(self):
        self.mentor = make_agent("mentor_user")
        self.mentee = make_agent("mentee_user")
        self.client.force_authenticate(self.mentor)

    def active(self, mentee, days_ago: int = 30) -> Mentorship:
        return Mentorship.objects.create(
            mentor=self.mentor,
            mentee=mentee,
            status="active",
            accepted_at=timezone.now() - timedelta(days=days_ago),
        )

    def mentee_earned(self, mentee, amount: int, source: str = "academic", days_ago: int = 7) -> None:
        log = RatingLog.objects.create(
            user=mentee, value_before=0, value_after=amount, delta=amount, source=source
        )
        RatingLog.objects.filter(pk=log.pk).update(created_at=timezone.now() - timedelta(days=days_ago))

    def test_accepting_a_mentee_gives_no_points_by_itself(self):
        before = self.mentor.rating_current
        offer = self.client.post(
            reverse("social-mentorships-create"), {"mentee_username": self.mentee.username}, format="json"
        ).data["id"]
        self.client.force_authenticate(self.mentee)
        self.client.post(reverse("social-mentorships-accept", args=[offer]))
        self.mentor.refresh_from_db()
        self.assertEqual(self.mentor.rating_current, before)

    def test_mentor_gets_share_of_mentee_success(self):
        self.active(self.mentee)
        self.mentee_earned(self.mentee, 30)
        before = self.mentor.rating_current

        result = pay_mentors_weekly()

        self.mentor.refresh_from_db()
        self.assertEqual(result["mentors_paid"], 1)
        self.assertEqual(self.mentor.rating_current - before, 3, "10% от 30")

    def test_share_is_capped_per_mentee(self):
        self.active(self.mentee)
        self.mentee_earned(self.mentee, 500)
        before = self.mentor.rating_current
        pay_mentors_weekly()
        self.mentor.refresh_from_db()
        self.assertEqual(self.mentor.rating_current - before, 5)

    def test_idle_mentee_brings_nothing(self):
        self.active(self.mentee)
        self.assertEqual(pay_mentors_weekly()["mentors_paid"], 0)

    def test_social_points_of_mentee_do_not_count(self):
        self.active(self.mentee)
        self.mentee_earned(self.mentee, 50, source="social")
        self.assertEqual(pay_mentors_weekly()["mentors_paid"], 0)

    def test_fresh_mentorship_is_not_paid(self):
        self.active(self.mentee, days_ago=2)
        self.mentee_earned(self.mentee, 30)
        self.assertEqual(pay_mentors_weekly()["mentors_paid"], 0)

    def test_payout_is_not_doubled_on_rerun(self):
        self.active(self.mentee)
        self.mentee_earned(self.mentee, 30)
        pay_mentors_weekly()
        self.assertEqual(pay_mentors_weekly()["mentors_paid"], 0)

    def test_mentor_can_end_mentorship(self):
        mentorship = Mentorship.objects.create(mentor=self.mentor, mentee=self.mentee)

        response = self.client.post(reverse("social-mentorships-end", args=[mentorship.pk]))

        mentorship.refresh_from_db()
        self.assertEqual(response.status_code, 200)
        self.assertIsNotNone(mentorship.ended_at)

    def test_my_mentorships_list(self):
        Mentorship.objects.create(mentor=self.mentor, mentee=self.mentee)

        response = self.client.get(reverse("social-mentorships-my"))

        body = response.json()
        self.assertEqual(len(body["mentees"]), 1)
        self.assertEqual(body["mentor_share_percent"], 10)

