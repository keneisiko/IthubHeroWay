from __future__ import annotations

from datetime import date

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings

from apps.integrations.models import LXPSnapshot, TelegramAccountLink
from apps.progress.models import RatingLog
from apps.progress.services.lxp_rating_from_snapshot import apply_rating_from_lxp_snapshot


User = get_user_model()


@override_settings(
    RATING_KP={
        "CT_ON_TIME": 20,
        "CT_NOT_SUBMITTED": -20,
        "ABSENCE_UNEXCUSED": -10,
    },
    RATING_LIMITS={
        "CT_UNCLOSED_BLOCK_THRESHOLD": 2,
        "MAX_RATING_WHEN_BLOCKED": 399,
        "LXP_SNAPSHOT_CT_POSITIVE_CAP": 40,
        "LXP_SNAPSHOT_CT_NEGATIVE_CAP": 60,
        "LXP_SNAPSHOT_ABSENCE_CAP": 10,
    },
)
class LxpRatingFromSnapshotTests(TestCase):
    def setUp(self):
        self.u = User.objects.create_user(
            username="stu1",
            email="stu1@test.ru",
            password="x",
            callsign="call_stu1",
            rating_current=400,
            unclosed_ct_count=0,
            lxp_user_id="lxp-uid-1",
        )
        TelegramAccountLink.objects.create(
            user=self.u,
            telegram_user_id=999001,
            telegram_chat_id=999001,
            is_active=True,
        )

    def test_topics_update_unclosed_and_rating_delta(self):
        snap_data = {
            "meta": {"partial": False},
            "control_points": {
                "ok": True,
                "data": {
                    "lxp-uid-1": {
                        "disc-a": {
                            "topics": [
                                {"status": "PASSED"},
                                {"status": "OPEN"},
                            ]
                        },
                    },
                },
            },
            "attendance": {"ok": True, "data": {"lxp-uid-1": {"has_attendance": True}}},
        }
        LXPSnapshot.objects.create(date=date(2026, 5, 10), data=snap_data)

        result = apply_rating_from_lxp_snapshot(date(2026, 5, 10))
        self.assertEqual(result.users_updated, 1)

        self.u.refresh_from_db()
        self.assertEqual(self.u.unclosed_ct_count, 1)
        self.assertTrue(RatingLog.objects.filter(user=self.u).exists())

    def test_absence_penalty_when_flag_false(self):
        snap_data = {
            "meta": {"partial": False},
            "control_points": {"ok": True, "data": {}},
            "attendance": {"ok": True, "data": {"lxp-uid-1": {"has_attendance": False}}},
        }
        LXPSnapshot.objects.create(date=date(2026, 5, 11), data=snap_data)

        apply_rating_from_lxp_snapshot(date(2026, 5, 11))
        self.u.refresh_from_db()
        self.assertEqual(self.u.rating_current, 390)
