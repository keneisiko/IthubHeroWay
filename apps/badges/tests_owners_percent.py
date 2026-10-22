from django.test import TestCase
from rest_framework.test import APIClient

from apps.accounts.models import Role, User
from apps.badges.models import Badge, UserBadge


class OwnersPercentTests(TestCase):
    def test_share_of_activated_students(self):
        badge = Badge.objects.create(code="b1", title="B", rarity="common", category="path")
        students = [
            User.objects.create_user(username=f"s{i}", callsign=f"s{i}", password=None, role=Role.AGENT)
            for i in range(4)
        ]
        # неактивированный импорт и сотрудник не входят ни в долю, ни в базу
        idle = User.objects.create_user(
            username="idle", callsign="idle", password=None, role=Role.AGENT, is_active=False
        )
        staff = User.objects.create_user(username="c", callsign="c", password=None, role=Role.CURATOR)
        for user in (students[0], idle, staff):
            UserBadge.objects.create(user=user, badge=badge)

        client = APIClient()
        client.force_authenticate(students[1])
        row = next(b for b in client.get("/api/v1/badges/").json() if b["code"] == "b1")

        self.assertEqual(row["owners_percent"], 25.0)
