from io import StringIO

from django.core.management import call_command
from django.test import TestCase

from apps.accounts.models import Role, Squad, Track, User
from apps.accounts.tracks import assign_track_if_empty, track_for_group


class TrackForGroupTests(TestCase):
    def test_three_tracks_by_group_code(self):
        cases = {
            "3Д1.9.24": "Дизайн",
            "1М1.9.26": "Маркетинг",
            "4ИТР2.9.23 (Бэкэнд)": "Программирование",
            "2ИТП1.9.25": "Программирование",
            "1ИТ1.11.26": "Программирование",
            "1ИИ2.9.26": "Программирование",
            "2ИБ1.9.25": "Программирование",
        }
        for group, title in cases.items():
            with self.subTest(group=group):
                self.assertEqual(track_for_group(group).name, title)
        self.assertEqual(Track.objects.count(), 3)

    def test_unknown_code_is_not_guessed(self):
        self.assertIsNone(track_for_group("Преподаватели 23-24"))
        self.assertIsNone(track_for_group("3ХЗ1.9.24"))


class AssignTrackTests(TestCase):
    def setUp(self):
        self.squad = Squad.objects.create(code="3d1", name="3Д1.9.24", course=3)

    def make_student(self, username, **extra):
        return User.objects.create_user(
            username=username, password="x", role=Role.AGENT, squad=self.squad, **extra
        )

    def test_manual_track_is_kept(self):
        manual = Track.objects.create(code="custom", name="Своё")
        user = self.make_student("a", track=manual)
        self.assertFalse(assign_track_if_empty(user, self.squad.name))
        user.refresh_from_db()
        self.assertEqual(user.track, manual)

    def test_command_fills_students_without_track(self):
        user = self.make_student("b")
        call_command("assign_tracks", stdout=StringIO())
        user.refresh_from_db()
        self.assertEqual(user.track.name, "Дизайн")
