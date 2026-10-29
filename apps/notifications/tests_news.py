"""Новости: блок на главной и разовая рассылка в бот."""

from __future__ import annotations

from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.urls import reverse
from rest_framework.test import APITestCase

from apps.accounts.models import Role
from apps.notifications.models import News
from apps.notifications.services.news import publish, telegram_text

User = get_user_model()
SEND = "apps.notifications.services.news.notify_users"


class NewsTests(APITestCase):
    def setUp(self):
        self.user = User.objects.create_user(username="st", password="x", callsign="st", role=Role.AGENT)
        self.client.force_authenticate(self.user)
        self.news = News.objects.create(title="Правила", body="Новая страница", link="/rules")

    def test_draft_is_hidden_published_is_listed(self):
        self.assertEqual(self.client.get(reverse("news-list")).json(), [])
        with patch(SEND, return_value=0):
            publish(self.news, send_to_telegram=False)
        rows = self.client.get(reverse("news-list")).json()
        self.assertEqual([r["title"] for r in rows], ["Правила"])

    @patch(SEND, return_value=5)
    def test_telegram_is_sent_only_once(self, send):
        self.assertEqual(publish(self.news, send_to_telegram=True), 5)
        self.assertEqual(publish(self.news, send_to_telegram=True), 0)
        send.assert_called_once()

    def test_telegram_text_has_full_link(self):
        self.assertIn("https://hero.ithub-nalchik.ru/rules", telegram_text(self.news))
