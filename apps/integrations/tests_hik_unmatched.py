"""События Hik без студента: помечаются, но не теряются.

Проходы сотрудников, гостей и студентов без пропуска не сопоставляются ни с
кем. Раньше их оставляли необработанными, и каждый прогон перечитывал их
заново. Хуже того, обработчик берёт первые 5000 необработанных по времени —
к 20.10.2026 таких «ничьих» было 4931, и на свежие проходы оставалось 69
мест за прогон. Ещё немного, и новые проходы перестали бы обрабатываться
совсем, без единой ошибки в логах.

Пометить навсегда тоже нельзя: студенту могут выдать пропуск или связать
его в Hik позже, и тогда его прошлые проходы должны засчитаться.
"""

from __future__ import annotations

from datetime import datetime, time

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from apps.accounts.models import Role, Squad
from apps.integrations.models import ExternalEvent, HikEvent
from apps.integrations.services.hik_attendance_processor import process_unprocessed_hik_events
from apps.schedule.models import Schedule

User = get_user_model()
TUESDAY = datetime(2026, 10, 6)


def moment(hour: int, minute: int):
    return timezone.make_aware(TUESDAY.replace(hour=hour, minute=minute))


class UnmatchedHikEventsTests(TestCase):
    def setUp(self):
        self.squad = Squad.objects.create(code="itr2-24", name="3ИТР2.9.24", course=3)
        Schedule.objects.create(
            squad=self.squad, day_of_week=1, start_time=time(9, 0), end_time=time(16, 0), is_active=True
        )
        self.student = User.objects.create_user(
            username="agent",
            email="agent@test.ru",
            password="x",
            callsign="Агент",
            squad=self.squad,
            role=Role.AGENT,
            hik_card_code="111",
        )

    def stranger_pass(self, n: int, *, code: str = "999", email: str = "guest@mail.ru"):
        return HikEvent.objects.create(
            event_id=f"stranger-{n}",
            event_time=moment(8, 0),
            student_code=code,
            raw_data={"direction": 1, "personEmail": email},
        )

    def student_pass(self, n: int):
        return HikEvent.objects.create(
            event_id=f"student-{n}",
            event_time=moment(8, 50),
            student_code="111",
            raw_data={"direction": 1},
        )

    def test_unmatched_event_is_marked(self):
        event = self.stranger_pass(1)

        process_unprocessed_hik_events()

        event.refresh_from_db()
        self.assertTrue(event.unmatched)
        self.assertFalse(event.processed, "событие не засчитано — оно не обработано")

    def test_marked_event_is_not_read_again(self):
        self.stranger_pass(1)
        process_unprocessed_hik_events()

        seen, _, skipped = process_unprocessed_hik_events()

        self.assertEqual(seen, 0)
        self.assertEqual(skipped, 0)

    def test_strangers_do_not_starve_new_passes(self):
        """Главное: «ничьи» события не должны занимать очередь.

        Тот же сценарий, что на проде, в уменьшенном масштабе: лимит прогона
        меньше, чем число ничьих событий, а проход студента — позже них.
        """
        for n in range(5):
            self.stranger_pass(n)
        self.student_pass(1)

        # Первый прогон: лимит 3 целиком уходит на ничьи события.
        process_unprocessed_hik_events(limit=3)
        process_unprocessed_hik_events(limit=3)
        # Ко второму прогону ничьи помечены, и проход студента доходит.

        self.assertTrue(
            ExternalEvent.objects.filter(user=self.student).exists(),
            "проход студента так и не обработан — очередь занята ничьими событиями",
        )

    def test_event_comes_back_when_student_gets_a_pass(self):
        """Выдали пропуск позже — прошлые проходы засчитываются."""
        event = self.stranger_pass(1, code="222")
        process_unprocessed_hik_events()
        event.refresh_from_db()
        self.assertTrue(event.unmatched)

        self.student.hik_card_code = "222"
        self.student.save(update_fields=["hik_card_code"])
        process_unprocessed_hik_events()

        event.refresh_from_db()
        self.assertFalse(event.unmatched)
        self.assertTrue(event.processed)
        self.assertTrue(ExternalEvent.objects.filter(user=self.student, external_event_id="stranger-1").exists())

    def test_event_comes_back_by_email_case_insensitively(self):
        """Портал отдаёт почту как есть, в базе она может быть в другом регистре."""
        event = self.stranger_pass(1, code="", email="New.Student@Test.ru")
        process_unprocessed_hik_events()

        User.objects.create_user(
            username="newcomer",
            email="new.student@test.ru",
            password="x",
            callsign="Новичок",
            squad=self.squad,
            role=Role.AGENT,
        )
        process_unprocessed_hik_events()

        event.refresh_from_db()
        self.assertTrue(event.processed)
