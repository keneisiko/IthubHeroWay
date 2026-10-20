"""Ночная синхронизация расписания и отметок посещения.

Обе команды были разовыми: «Неделя без пропусков» закрылась один раз и дальше
считалась по данным двухнедельной давности, а расписание устаревало при первом
же изменении в LXP — и тогда проход вовремя засчитывался как опоздание.
"""

from __future__ import annotations

from unittest import mock

from django.core.management.base import CommandError
from django.test import TestCase

from apps.accounts.models import Squad
from apps.integrations.services.lxp_groups import LXPNoClassesError
from apps.integrations.tasks import sync_lxp_class_attendance, sync_lxp_schedules


class SyncTasksTests(TestCase):
    def setUp(self):
        self.linked = Squad.objects.create(
            code="itr2-24", name="3ИТР2.9.24", course=3, lxp_group_id="g-itr2"
        )
        # Отряд без привязки к группе LXP — синхронизировать нечего.
        Squad.objects.create(code="manual", name="Ручной отряд", course=1)

    def test_attendance_runs_only_for_linked_squads(self):
        with mock.patch("django.core.management.call_command") as call:
            result = sync_lxp_class_attendance(weeks=1)

        call.assert_called_once_with(
            "pull_lxp_class_attendance", group_id="g-itr2", squad_code="itr2-24", weeks=1
        )
        self.assertIn("отрядов 1", result)

    def test_schedule_runs_only_for_linked_squads(self):
        with mock.patch("django.core.management.call_command") as call:
            sync_lxp_schedules(weeks=2)

        call.assert_called_once_with(
            "import_lxp_schedule", group_id="g-itr2", squad_code="itr2-24", weeks=2
        )

    def test_failure_of_one_squad_does_not_stop_the_rest(self):
        Squad.objects.create(code="second", name="Второй", course=2, lxp_group_id="g-2")

        with mock.patch("django.core.management.call_command", side_effect=[RuntimeError("LXP"), None]):
            with mock.patch("apps.integrations.tasks.send_alert_to_admin") as alert:
                result = sync_lxp_schedules()

        self.assertIn("с ошибкой 1", result)
        alert.assert_called_once()

    def test_without_linked_squads_nothing_happens(self):
        Squad.objects.all().update(lxp_group_id="")

        with mock.patch("django.core.management.call_command") as call:
            result = sync_lxp_class_attendance()

        call.assert_not_called()
        self.assertIn("нет отрядов", result)


class NoClassesAndAlertTextTests(TestCase):
    """Отряд без занятий в LXP (практика, диплом) — не сбой и не тревога."""

    def setUp(self):
        Squad.objects.create(code="graduates", name="4ИТР2", course=4, lxp_group_id="g-grad")
        Squad.objects.create(code="second", name="2ИТР1", course=2, lxp_group_id="g-second")

    @staticmethod
    def _graduates_have_no_classes(*args, **kwargs):
        if kwargs.get("squad_code") == "graduates":
            raise LXPNoClassesError("нет занятий")

    def test_squad_without_classes_does_not_raise_alert(self):
        """Выпускники на практике, остальные учатся — тревоги нет."""
        with mock.patch(
            "django.core.management.call_command", side_effect=self._graduates_have_no_classes
        ):
            with mock.patch("apps.integrations.tasks.send_alert_to_admin") as alert:
                schedule = sync_lxp_schedules()
                attendance = sync_lxp_class_attendance()

        alert.assert_not_called()
        self.assertIn("без занятий в LXP 1", schedule)
        self.assertIn("без занятий в LXP 1", attendance)

    def test_no_classes_anywhere_is_an_alert(self):
        """Пустота по всем группам сразу — сбой выгрузки, а не каникулы.

        Без этой проверки поломка ответа LXP прошла бы молча: «нет занятий»
        перестало быть тревогой.
        """
        with mock.patch(
            "django.core.management.call_command", side_effect=LXPNoClassesError("нет занятий")
        ):
            with mock.patch("apps.integrations.tasks.send_alert_to_admin") as alert:
                sync_lxp_class_attendance()

        alert.assert_called_once()
        self.assertIn("ни по одному из 2", alert.call_args.kwargs["message"])

    def test_alert_names_squad_and_reason(self):
        with mock.patch("django.core.management.call_command", side_effect=CommandError("LXP: таймаут")):
            with mock.patch("apps.integrations.tasks.send_alert_to_admin") as alert:
                sync_lxp_schedules()

        message = alert.call_args.kwargs["message"]
        self.assertIn("graduates", message)
        self.assertIn("LXP: таймаут", message)
