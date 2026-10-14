"""Статусы раздела 8 и принятие Положения из раздела 2."""

from __future__ import annotations

from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from rest_framework.test import APITestCase

from apps.accounts.models import PolicyAcceptance, Role
from apps.progress.services.rating_zones import (
    rating_progress,
    rating_status_label,
    rating_zone,
)

User = get_user_model()


class RatingStatusTests(TestCase):
    """Границы из раздела 8: нижняя включительно."""

    def test_boundaries(self):
        cases = {
            0: "Новобранец",
            99.99: "Новобранец",
            100: "Стажёр",
            249.99: "Стажёр",
            250: "Специалист",
            499.99: "Специалист",
            500: "Профи",
            700: "Мастер",
            899.99: "Мастер",
            900: "Легенда",
        }
        for rating, expected in cases.items():
            with self.subTest(rating=rating):
                self.assertEqual(rating_status_label(Decimal(str(rating))), expected)

    def test_rating_above_thousand_stays_legend(self):
        """Пункт 1.3: рейтинг может превышать 1000."""
        self.assertEqual(rating_status_label(Decimal("1500")), "Легенда")
        self.assertEqual(rating_zone(Decimal("1500")), "legend")

    def test_progress_to_next_status(self):
        progress = rating_progress(Decimal("150"))

        self.assertEqual(progress["zone_label"], "Стажёр")
        self.assertEqual(progress["next_zone_label"], "Специалист")
        self.assertEqual(progress["points_to_next"], 100.0)

    def test_legend_has_no_next_status(self):
        progress = rating_progress(Decimal("950"))

        self.assertIsNone(progress["next_zone"])
        self.assertEqual(progress["progress_percent"], 100.0)

    def test_new_student_starts_as_recruit(self):
        """Пункт 2.2: рейтинг на начало сезона равен нулю."""
        user = User.objects.create_user(username="fresh", password="x", callsign="fresh")

        self.assertEqual(user.rating_current, Decimal("0"))
        self.assertEqual(rating_status_label(user.rating_current), "Новобранец")


class PolicyAcceptanceApiTests(APITestCase):
    """Пункт 2.1: ознакомление и принятие Положения."""

    def setUp(self):
        self.user = User.objects.create_user(
            username="student",
            email="s@nalchik.ithub.ru",
            password="x",
            callsign="stud",
            role=Role.AGENT,
        )
        self.client.force_authenticate(self.user)
        self.url = reverse("policy-state")

    def test_state_reports_not_accepted_first(self):
        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertFalse(response.data["accepted"])
        self.assertEqual(response.data["version"], "2.0")
        self.assertEqual(response.data["season_start"], "2026-10-19")

    def test_accepting_records_version(self):
        response = self.client.post(self.url, {}, format="json")

        self.assertEqual(response.status_code, 201)
        self.assertTrue(PolicyAcceptance.objects.filter(user=self.user, version="2.0").exists())

    def test_repeated_acceptance_does_not_duplicate(self):
        self.client.post(self.url, {}, format="json")
        again = self.client.post(self.url, {}, format="json")

        self.assertEqual(again.status_code, 200)
        self.assertEqual(PolicyAcceptance.objects.filter(user=self.user).count(), 1)

    def test_old_version_cannot_be_accepted(self):
        response = self.client.post(self.url, {"version": "1.0"}, format="json")

        self.assertEqual(response.status_code, 400)
        self.assertFalse(PolicyAcceptance.objects.filter(user=self.user).exists())

    def test_profile_exposes_acceptance_and_status(self):
        self.client.post(self.url, {}, format="json")

        profile = self.client.get(reverse("profile-me"))

        self.assertTrue(profile.data["policy_accepted"])
        self.assertEqual(profile.data["rating_status"], "Новобранец")
