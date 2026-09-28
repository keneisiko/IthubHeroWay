"""Ожидание портала Hik перед кликами по меню.

Разведка сообщала «пункт Access Control не найден», хотя в портале он есть:
клик уходил, пока страница ещё оставалась на маршруте логина. Проверяем, что
переход по меню начинается только после отрисовки портала.
"""

from __future__ import annotations

from unittest import mock

from django.test import TestCase

from apps.integrations.services import hik_browser_export


class FakePage:
    """Страница, которая доезжает до портала не сразу."""

    def __init__(self, urls: list[str]):
        self._urls = urls
        self.waits = 0

    @property
    def url(self) -> str:
        return self._urls[min(self.waits, len(self._urls) - 1)]

    def wait_for_timeout(self, _ms: int) -> None:
        self.waits += 1

    def get_by_text(self, *_args, **_kwargs):
        locator = mock.Mock()
        locator.first = locator
        locator.count.return_value = 0
        return locator


class WaitForPortalTests(TestCase):
    def test_waits_until_portal_route_appears(self):
        login = "https://www.hik-connectru.com/views/login/index.html#/login"
        portal = "https://www.hik-connectru.com/views/login/index.html#/portal"
        page = FakePage([login, login, portal])

        self.assertTrue(hik_browser_export.wait_for_portal(page, timeout_s=10))
        self.assertGreater(page.waits, 0)

    def test_menu_text_counts_as_ready(self):
        page = FakePage(["https://www.hik-connectru.com/views/login/index.html#/login"])
        locator = mock.Mock()
        locator.first = locator
        locator.count.return_value = 1
        locator.is_visible.return_value = True
        page.get_by_text = lambda *a, **k: locator

        self.assertTrue(hik_browser_export.wait_for_portal(page, timeout_s=5))

    def test_gives_up_and_reports_failure(self):
        """Молчаливое зависание хуже честного отказа: дальше пишется в лог."""
        page = FakePage(["https://www.hik-connectru.com/views/login/index.html#/login"])

        self.assertFalse(hik_browser_export.wait_for_portal(page, timeout_s=2))
