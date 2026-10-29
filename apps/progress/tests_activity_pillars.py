from datetime import date, timedelta
from unittest.mock import patch

from django.test import TestCase
from django.utils import timezone

from apps.accounts.models import Role, User
from apps.integrations.models import ExternalEvent
from apps.progress.models import Characteristic
from apps.progress.services.activity_pillars import (
    PILLAR_FOCUS,
    PILLAR_INITIATIVE,
    PILLAR_TEAMWORK,
    activity_pillars,
    window_start,
)
from apps.progress.services.characteristics import update_all_characteristics
from apps.progress.services.lxp_characteristics import save_pillar
from apps.quests.models import Quest, QuestType, UserQuestProgress
from apps.social.models import Mentorship, Respect

TODAY = date(2026, 11, 20)
SEASON = date(2026, 10, 1)


def student(username: str, **extra) -> User:
    return User.objects.create_user(
        username=username, callsign=username, password=None, role=Role.AGENT, **extra
    )


@patch("apps.progress.services.activity_pillars.season_start_date", return_value=SEASON)
class ActivityPillarsTests(TestCase):
    def setUp(self):
        self.user = student("walker")
        self.other = student("friend")
        self.seq = 0

    def hik(self, day: date, event_type: str = "access"):
        self.seq += 1
        ExternalEvent.objects.create(
            source="hik", external_event_id=f"e{self.seq}", user=self.user,
            event_date=day, event_type=event_type,
        )

    def test_three_pillars_differ_and_stay_in_scale(self, _season):
        for i in range(10):
            self.hik(timezone.localdate() - timedelta(days=i), "late" if i < 2 else "access")
        quest = Quest.objects.create(code="q", title="q", quest_type=QuestType.DAILY)
        UserQuestProgress.objects.create(
            user=self.user, quest=quest, is_completed=True, completed_at=timezone.now()
        )
        for _ in range(30):
            Respect.objects.create(from_user=self.other, to_user=self.user)

        values = activity_pillars(self.user.pk, timezone.localdate())

        self.assertEqual(values[PILLAR_FOCUS], 16.0)  # 8 из 10 дней без опоздания
        self.assertEqual(values[PILLAR_INITIATIVE], 1.0)  # 1 квест из 20 для полной шкалы
        self.assertEqual(values[PILLAR_TEAMWORK], 20.0)  # респектов с избытком — потолок 20

    def test_focus_without_hik_data_is_unknown_not_zero(self, _season):
        self.assertIsNone(activity_pillars(self.user.pk, TODAY)[PILLAR_FOCUS])

    def test_mentorship_counts_for_both_sides(self, _season):
        Mentorship.objects.create(
            mentor=self.other, mentee=self.user, status="active", accepted_at=timezone.now()
        )
        self.assertEqual(activity_pillars(self.user.pk, TODAY)[PILLAR_TEAMWORK], 6.0)
        self.assertEqual(activity_pillars(self.other.pk, TODAY)[PILLAR_TEAMWORK], 6.0)

    def test_window_does_not_reach_before_season(self, _season):
        self.assertEqual(window_start(SEASON + timedelta(days=3)), SEASON)
        self.assertEqual(window_start(TODAY), TODAY - timedelta(days=27))


class SavePillarPeakTests(TestCase):
    def test_peak_restarts_in_new_season(self):
        user = student("old")
        char = Characteristic.objects.create(user=user, pillar="power", current=19, peak=19)
        Characteristic.objects.filter(pk=char.pk).update(
            last_updated=timezone.make_aware(timezone.datetime(2026, 5, 1))
        )
        with patch(
            "apps.progress.services.lxp_characteristics.season_start_date", return_value=SEASON
        ):
            save_pillar(user, "power", 12.0, "test")
        char.refresh_from_db()
        self.assertEqual(char.peak, 12.0)


class UpdateAllTests(TestCase):
    def test_staff_get_no_characteristics(self):
        student("s1")
        User.objects.create_user(username="cur", callsign="cur", password=None, role=Role.CURATOR)
        update_all_characteristics()
        self.assertFalse(Characteristic.objects.exclude(user__role=Role.AGENT).exists())
        self.assertFalse(Characteristic.objects.filter(pillar__in=["leadership", "growth"]).exists())
