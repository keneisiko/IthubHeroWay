"""Страница «Правила» показывает те же тарифы, по которым идут начисления."""

from __future__ import annotations

from django.conf import settings
from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.test import APITestCase

from apps.accounts.models import Role


class RulesApiTests(APITestCase):
    def setUp(self):
        user = get_user_model().objects.create_user(
            username="st", password="x", callsign="st", role=Role.AGENT
        )
        self.client.force_authenticate(user)

    def test_tariffs_come_from_polozhenie_settings(self):
        body = self.client.get(reverse("rules")).json()
        self.assertEqual(body["academic"]["ct_weekly_max"], float(settings.POLOZHENIE_ACADEMIC["CT_WEEKLY_MAX"]))
        self.assertEqual(len(body["roles"]), len(settings.POLOZHENIE_ROLES))
        self.assertEqual(len(body["events"]["columns"]), len(settings.POLOZHENIE_EVENT_LEVELS))
        self.assertEqual(body["penalties"]["daily_max"], 4)
        self.assertEqual(body["mentorship"]["share_percent"], 10)
        self.assertEqual(body["coins_only"]["king"]["top"], [4, 2, 1])

    def test_requires_login(self):
        self.client.force_authenticate(None)
        self.assertEqual(self.client.get(reverse("rules")).status_code, 401)
