"""Сравнение правил определения актуальных КТ.

Проверяется на той же форме данных, что пришла с прода: у студента почти
две сотни тем, из них несколько сданных, несколько на проверке, остальные
в NOT_PASSED_YET. Именно на таких данных действующее правило даёт 100%
при двух сданных темах.
"""

from __future__ import annotations

from io import StringIO

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.test import TestCase

from apps.accounts.models import Role
from apps.integrations.models import LXPSnapshot

User = get_user_model()


def snapshot(topics_by_discipline: dict[str, list[str]], lessons: dict[str, int]) -> LXPSnapshot:
    """Снимок в том же виде, в каком его собирает клиент LXP."""
    return LXPSnapshot.objects.create(
        date="2026-10-12",
        data={
            "meta": {"partial": False},
            "control_points": {
                "ok": True,
                "data": {
                    "lxp-1": {
                        discipline: {
                            "topics": [
                                {"status": status, "topic": {"id": f"{discipline}-{i}"}}
                                for i, status in enumerate(statuses)
                            ]
                        }
                        for discipline, statuses in topics_by_discipline.items()
                    }
                },
            },
            "attendance": {
                "ok": True,
                "data": {
                    "lxp-1": {
                        "by_discipline": {
                            discipline: {"visited": total, "total": total, "percent": 100}
                            for discipline, total in lessons.items()
                        }
                    }
                },
            },
        },
    )


class CompareCtRulesTests(TestCase):
    def setUp(self):
        self.user = User.objects.create_user(
            username="student",
            email="s@nalchik.ithub.ru",
            password="x",
            callsign="stud",
            role=Role.AGENT,
            first_name="Иван",
            last_name="Иванов",
            lxp_user_id="lxp-1",
        )

    def run_command(self) -> str:
        out = StringIO()
        call_command("compare_ct_rules", stdout=out)
        return out.getvalue()

    def test_decided_rule_gives_full_marks_on_two_passed_topics(self):
        """Воспроизведение прода: две сданные темы дают 100%."""
        snapshot(
            {"d1": ["PASSED", "PASSED"] + ["NOT_PASSED_YET"] * 190, "d2": ["IN_REVIEW"] * 3},
            {"d1": 12, "d2": 8},
        )

        output = self.run_command()

        self.assertIn("1. решённые (сейчас)", output)
        self.assertIn("да, негодно", output, "правило должно быть помечено как вырожденное")

    def test_taught_disciplines_rule_lowers_the_percent(self):
        """Темы преподаваемой дисциплины попадают в знаменатель целиком."""
        snapshot(
            {"d1": ["PASSED", "PASSED"] + ["NOT_PASSED_YET"] * 18},
            {"d1": 10},
        )

        output = self.run_command()

        # 2 сданные из 20 тем преподаваемой дисциплины — 10%.
        self.assertIn("10.00", output)

    def test_discipline_without_lessons_is_excluded(self):
        """Дисциплина без проведённых занятий в расчёт не входит."""
        snapshot(
            {"d1": ["PASSED"], "d2": ["NOT_PASSED_YET"] * 50},
            {"d1": 6, "d2": 0},
        )

        output = self.run_command()

        self.assertIn("100.00", output)

    def test_student_without_snapshot_row_is_skipped(self):
        snapshot({"d1": ["PASSED"]}, {"d1": 4})
        User.objects.create_user(
            username="ghost",
            email="g@nalchik.ithub.ru",
            password="x",
            callsign="ghost",
            role=Role.AGENT,
            lxp_user_id="lxp-404",
        )

        output = self.run_command()

        self.assertNotIn("ghost", output)

    def test_runs_without_snapshot_attendance(self):
        """Без блока посещаемости правило по дисциплинам просто пустое."""
        LXPSnapshot.objects.create(
            date="2026-10-12",
            data={
                "control_points": {
                    "ok": True,
                    "data": {"lxp-1": {"d1": {"topics": [{"status": "PASSED"}]}}},
                }
            },
        )

        output = self.run_command()

        self.assertIn("Иванов", output)
