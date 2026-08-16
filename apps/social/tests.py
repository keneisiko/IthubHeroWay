from datetime import timedelta

from django.conf import settings
from django.contrib.auth import get_user_model
from django.db import IntegrityError
from django.urls import reverse
from django.utils import timezone
from rest_framework import status
from rest_framework.test import APITestCase

from apps.social.models import Mentorship, Respect


class SocialLimitsTests(APITestCase):
    def setUp(self):
        self.user = get_user_model().objects.create_user(username="u1", password="x", callsign="u1")
        self.opponent = get_user_model().objects.create_user(
            username="u2", password="x", callsign="u2", rating_current=600
        )
        self.other = get_user_model().objects.create_user(username="u3", password="x", callsign="u3")
        self.client.force_authenticate(self.user)

    def test_duel_rating_diff_limit(self):
        url = reverse("social-duels-create")
        response = self.client.post(url, {"opponent_username": self.opponent.username}, format="json")
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)

    def test_accepted_duel_blocks_second_one(self):
        """Инвариант «одна активная дуэль» не работал никогда: принятие
        дуэли сразу проставляло resolved_at, и она переставала считаться
        активной в тот же момент."""
        peer = get_user_model().objects.create_user(
            username="u4", password="x", callsign="u4", rating_current=300
        )
        third = get_user_model().objects.create_user(
            username="u5", password="x", callsign="u5", rating_current=300
        )

        created = self.client.post(
            reverse("social-duels-create"), {"opponent_username": peer.username}, format="json"
        )
        self.assertEqual(created.status_code, status.HTTP_201_CREATED)
        duel_id = created.data["id"]

        self.client.force_authenticate(peer)
        accepted = self.client.post(reverse("social-duels-accept", args=[duel_id]))
        self.assertEqual(accepted.status_code, status.HTTP_200_OK)

        self.client.force_authenticate(self.user)
        second = self.client.post(
            reverse("social-duels-create"), {"opponent_username": third.username}, format="json"
        )
        self.assertEqual(second.status_code, status.HTTP_400_BAD_REQUEST)

    def test_duel_cannot_be_accepted_twice(self):
        peer = get_user_model().objects.create_user(
            username="u6", password="x", callsign="u6", rating_current=300
        )
        created = self.client.post(
            reverse("social-duels-create"), {"opponent_username": peer.username}, format="json"
        )
        duel_id = created.data["id"]

        self.client.force_authenticate(peer)
        self.assertEqual(
            self.client.post(reverse("social-duels-accept", args=[duel_id])).status_code, 200
        )
        self.assertEqual(
            self.client.post(reverse("social-duels-accept", args=[duel_id])).status_code, 400
        )

    def test_rejected_duel_cannot_be_accepted(self):
        peer = get_user_model().objects.create_user(
            username="u7", password="x", callsign="u7", rating_current=300
        )
        created = self.client.post(
            reverse("social-duels-create"), {"opponent_username": peer.username}, format="json"
        )
        duel_id = created.data["id"]

        self.client.force_authenticate(peer)
        self.client.post(reverse("social-duels-reject", args=[duel_id]))
        self.assertEqual(
            self.client.post(reverse("social-duels-accept", args=[duel_id])).status_code, 400
        )

    def test_respect_weekly_limit(self):
        url = reverse("social-respects-create")
        first = self.client.post(url, {"to_username": self.opponent.username}, format="json")
        self.assertEqual(first.status_code, status.HTTP_201_CREATED)
        second = self.client.post(url, {"to_username": self.other.username}, format="json")
        self.assertEqual(second.status_code, status.HTTP_429_TOO_MANY_REQUESTS)
        self.assertEqual(Respect.objects.filter(from_user=self.user).count(), 1)

    def test_respect_same_user_cooldown(self):
        url = reverse("social-respects-create")
        self.client.post(url, {"to_username": self.opponent.username}, format="json")
        Respect.objects.filter(from_user=self.user).update(
            created_at=timezone.now() - timedelta(days=8)
        )
        again = self.client.post(url, {"to_username": self.opponent.username}, format="json")
        self.assertEqual(again.status_code, status.HTTP_429_TOO_MANY_REQUESTS)
        self.assertEqual(Respect.objects.filter(from_user=self.user).count(), 1)

    def test_respect_returns_usernames_not_pks(self):
        response = self.client.post(
            reverse("social-respects-create"),
            {"to_username": self.opponent.username},
            format="json",
        )
        self.assertEqual(response.data["from_user"]["username"], self.user.username)
        self.assertEqual(response.data["to_user"]["callsign"], self.opponent.callsign)


class MentorshipTests(APITestCase):
    def setUp(self):
        self.mentor = get_user_model().objects.create_user(
            username="m1", password="x", callsign="m1"
        )
        self.mentee = get_user_model().objects.create_user(
            username="m2", password="x", callsign="m2"
        )
        self.client.force_authenticate(self.mentor)

    def test_self_mentorship_is_rejected(self):
        response = self.client.post(
            reverse("social-mentorships-create"),
            {"mentee_username": self.mentor.username},
            format="json",
        )
        self.assertEqual(response.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertFalse(Mentorship.objects.exists())

    def test_repeated_mentorship_returns_200_and_does_not_duplicate(self):
        url = reverse("social-mentorships-create")
        first = self.client.post(url, {"mentee_username": self.mentee.username}, format="json")
        self.assertEqual(first.status_code, status.HTTP_201_CREATED)
        second = self.client.post(url, {"mentee_username": self.mentee.username}, format="json")
        self.assertEqual(second.status_code, status.HTTP_200_OK)
        self.assertEqual(second.data["id"], first.data["id"])
        self.assertEqual(Mentorship.objects.filter(mentor=self.mentor).count(), 1)

    def test_mentee_limit(self):
        url = reverse("social-mentorships-create")
        limit = int(settings.RATING_LIMITS.get("MENTORSHIP_ACTIVE_LIMIT", 5))
        for i in range(limit):
            mentee = get_user_model().objects.create_user(
                username=f"mm{i}", password="x", callsign=f"mm{i}"
            )
            self.assertEqual(
                self.client.post(url, {"mentee_username": mentee.username}, format="json").status_code,
                status.HTTP_201_CREATED,
            )
        extra = self.client.post(url, {"mentee_username": self.mentee.username}, format="json")
        self.assertEqual(extra.status_code, status.HTTP_400_BAD_REQUEST)
        self.assertEqual(Mentorship.objects.filter(mentor=self.mentor).count(), limit)

    def test_self_mentorship_blocked_by_db_constraint(self):
        """Вьюха — не единственная точка входа: записи заводят и из админки."""
        with self.assertRaises(IntegrityError):
            Mentorship.objects.create(mentor=self.mentor, mentee=self.mentor)

