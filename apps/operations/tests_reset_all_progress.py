"""Полное обнуление данных студентов перед запуском."""

from __future__ import annotations

from datetime import date
from decimal import Decimal
from io import StringIO
from unittest.mock import patch

from django.core.cache import cache
from django.core.management import CommandError, call_command
from django.test import TestCase
from django.utils import timezone

from apps.accounts.models import PolicyAcceptance, Role, Squad, Track, User
from apps.badges.models import Badge, UserBadge
from apps.integrations.models import ExternalEvent, TelegramAccountLink
from apps.progress.models import (
    Characteristic,
    CharacteristicHistory,
    LessonAttendance,
    LXPTopicState,
    PolozhenieAward,
    RatingLog,
    StudentRoleAssignment,
    UserStrike,
)
from apps.quests.models import (
    Quest,
    QuestRewardTransaction,
    QuestTemplate,
    SelfReportProof,
    SquadLeaderboardSnapshot,
    UserQuestProgress,
    WeeklyFocus,
)
from apps.shop.models import Purchase, ShopItem
from apps.social.models import Duel, Mentorship, Respect

PER_USER_MODELS = (
    UserBadge, QuestRewardTransaction, SelfReportProof, UserQuestProgress, WeeklyFocus,
    RatingLog, PolozhenieAward, UserStrike, LXPTopicState, Characteristic, Purchase,
    TelegramAccountLink, PolicyAcceptance,
    StudentRoleAssignment,
)

ACCRUALS_PATCH = "apps.operations.management.commands.reset_all_progress._accruals_enabled"


def run(**kwargs) -> str:
    if kwargs.get("apply"):
        kwargs.setdefault("confirm", "RESET")
        kwargs.setdefault("expect_students", 2)
    out = StringIO()
    call_command("reset_all_progress", stdout=out, **kwargs)
    return out.getvalue()


class ResetAllProgressTests(TestCase):
    def setUp(self):
        # В тестовых настройках начисления включены по умолчанию (миграция 0002).
        patcher = patch(ACCRUALS_PATCH, return_value=False)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.squad = Squad.objects.create(code="s1", name="S1", course=1)
        self.track = Track.objects.create(code="t1", name="T1")
        self.badge = Badge.objects.create(code="b1", title="B1")
        self.dev_badge = Badge.objects.create(code="developer", title="Разработчик", avatar_frame="developer")
        self.quest = Quest.objects.create(code="q1", title="Q1", quest_type="weekly")
        self.template = QuestTemplate.objects.create(code="qt1", title="QT1", quest_type="weekly")
        self.item = ShopItem.objects.create(code="i1", title="I1", price_coins=10)

        self.s1 = self._user("stud1", Role.AGENT, 1)
        self.s2 = self._user("stud2", Role.AGENT, 2)
        self.staff = self._user("curator", Role.CURATOR, 3)
        # Решение сотрудника о закрытом входе сохраняется.
        User.objects.filter(pk=self.s2.pk).update(login_blocked=True)

        Respect.objects.create(from_user=self.s1, to_user=self.staff)
        Respect.objects.create(from_user=self.staff, to_user=self.s1)
        Respect.objects.create(from_user=self.s1, to_user=self.s2)
        Duel.objects.create(challenger=self.s1, opponent=self.s2)
        Duel.objects.create(challenger=self.s1, opponent=self.staff)
        Mentorship.objects.create(mentor=self.s2, mentee=self.s1)
        Mentorship.objects.create(mentor=self.staff, mentee=self.s1)
        SquadLeaderboardSnapshot.objects.create(squad=self.squad, avg_rating=5)
        ExternalEvent.objects.create(source="hik", external_event_id="e1", user=self.s1)
        LessonAttendance.objects.create(
            user=self.s1, lxp_class_id="c1", lesson_date=date(2026, 9, 1), status="present"
        )

    def _user(self, name, role, tg_id):
        user = User.objects.create_user(
            username=name, email=f"{name}@t.ru", password="x", callsign=f"cs_{name}", role=role,
            squad=self.squad, track=self.track, lxp_user_id=f"lxp_{name}",
            rating_current=Decimal("120.5"), coins_balance=Decimal("33"), level=4,
            unclosed_ct_count=3, status="active", is_active=True, last_login=timezone.now(),
        )
        UserBadge.objects.create(user=user, badge=self.badge)
        UserBadge.objects.create(user=user, badge=self.dev_badge)
        prog = UserQuestProgress.objects.create(user=user, quest=self.quest, is_completed=True)
        QuestRewardTransaction.objects.create(user=user, quest=self.quest, progress=prog, coins_delta=5)
        SelfReportProof.objects.create(user=user, quest=self.quest, quest_progress=prog, comment="c")
        WeeklyFocus.objects.create(user=user, quest=self.quest, period_key="2026-W40")
        RatingLog.objects.create(user=user, value_before=0, value_after=5, delta=5)
        PolozhenieAward.objects.create(user=user, kind="event", activity_key="k", happened_on=date(2026, 9, 1))
        UserStrike.objects.create(user=user, attendance_strike=4)
        LXPTopicState.objects.create(user=user, topics={"d:1": {"closed": True}}, baseline_done=True)
        char = Characteristic.objects.create(user=user, pillar="focus", current=7)
        CharacteristicHistory.objects.create(characteristic=char, value=7)
        Purchase.objects.create(user=user, item=self.item, coins_spent=10)
        TelegramAccountLink.objects.create(user=user, telegram_user_id=tg_id, telegram_chat_id=tg_id)
        PolicyAcceptance.objects.create(user=user, version="1")
        StudentRoleAssignment.objects.create(user=user, kind="tech", started_on=date(2026, 9, 1))
        return user

    def test_dry_run_changes_nothing(self):
        out = run()

        self.s1.refresh_from_db()
        self.assertEqual(self.s1.rating_current, Decimal("120.5"))
        self.assertTrue(self.s1.is_active)
        self.assertEqual(RatingLog.objects.count(), 3)
        self.assertEqual(UserBadge.objects.count(), 6)
        self.assertEqual(Respect.objects.count(), 3)
        self.assertIn("Пробный прогон", out)

    def test_apply_requires_confirm(self):
        with self.assertRaises(CommandError):
            call_command("reset_all_progress", apply=True, expect_students=2, stdout=StringIO())
        with self.assertRaises(CommandError):
            run(apply=True, confirm="yes")

        self.s1.refresh_from_db()
        self.assertEqual(self.s1.rating_current, Decimal("120.5"))

    def test_apply_zeroes_students(self):
        out = run(apply=True, confirm="RESET")

        for user in (self.s1, self.s2):
            user.refresh_from_db()
            self.assertEqual(user.rating_current, 0)
            self.assertEqual(user.coins_balance, 0)
            self.assertEqual(user.level, 1)
            self.assertEqual(user.unclosed_ct_count, 0)
            self.assertFalse(user.is_active)
            self.assertEqual(user.status, "imported_lxp")
            self.assertIsNone(user.last_login)
            # База пользователей остаётся.
            self.assertEqual(user.squad, self.squad)
            self.assertEqual(user.track, self.track)
            self.assertTrue(user.lxp_user_id.startswith("lxp_"))
            self.assertTrue(user.callsign.startswith("cs_"))
        self.assertFalse(self.s1.login_blocked)
        self.assertTrue(self.s2.login_blocked)
        for model in PER_USER_MODELS:
            self.assertEqual(model.objects.filter(user__role=Role.AGENT).count(), 0, model.__name__)
        self.assertEqual(CharacteristicHistory.objects.count(), 1)  # только сотрудника
        # Пары студент–студент удалены, связи с сотрудником сохранены.
        self.assertEqual(Respect.objects.count(), 2)
        self.assertFalse(Respect.objects.filter(from_user=self.s1, to_user=self.s2).exists())
        self.assertEqual(Duel.objects.count(), 1)
        self.assertEqual(Duel.objects.get().opponent, self.staff)
        self.assertEqual(Mentorship.objects.count(), 1)
        self.assertEqual(Mentorship.objects.get().mentor, self.staff)
        self.assertEqual(SquadLeaderboardSnapshot.objects.count(), 0)
        self.assertIn("активированных: 0", out)

    def test_staff_untouched(self):
        run(apply=True, confirm="RESET")

        self.staff.refresh_from_db()
        self.assertEqual(self.staff.rating_current, Decimal("120.5"))
        self.assertEqual(self.staff.coins_balance, 33)
        self.assertEqual(self.staff.level, 4)
        self.assertTrue(self.staff.is_active)
        self.assertEqual(self.staff.status, "active")
        self.assertIsNotNone(self.staff.last_login)
        for model in PER_USER_MODELS:
            expected = 2 if model is UserBadge else 1
            self.assertEqual(model.objects.filter(user=self.staff).count(), expected, model.__name__)

    def test_catalogs_and_raw_data_kept(self):
        run(apply=True, confirm="RESET")

        for obj in (self.badge, self.dev_badge, self.quest, self.template, self.item):
            self.assertTrue(type(obj).objects.filter(pk=obj.pk).exists(), type(obj).__name__)
        self.assertTrue(Squad.objects.filter(pk=self.squad.pk).exists())
        self.assertTrue(Track.objects.filter(pk=self.track.pk).exists())
        self.assertEqual(ExternalEvent.objects.count(), 1)
        self.assertEqual(LessonAttendance.objects.count(), 1)

    def test_keep_badge(self):
        run(apply=True, confirm="RESET", keep_badge=["developer"])

        kept = UserBadge.objects.filter(user__role=Role.AGENT)
        self.assertEqual(kept.count(), 2)
        self.assertEqual({b.badge.code for b in kept}, {"developer"})
        self.assertEqual(UserBadge.objects.filter(user=self.staff).count(), 2)

    def test_roles_deleted_by_default_and_kept_with_flag(self):
        run(apply=True, keep_roles=True)
        self.assertEqual(StudentRoleAssignment.objects.filter(user__role=Role.AGENT).count(), 2)

        run(apply=True)
        self.assertEqual(StudentRoleAssignment.objects.filter(user__role=Role.AGENT).count(), 0)
        self.assertEqual(StudentRoleAssignment.objects.filter(user=self.staff).count(), 1)

    def test_refused_while_accruals_enabled(self):
        with patch(ACCRUALS_PATCH, return_value=True):
            with self.assertRaisesMessage(CommandError, "остановите начисления"):
                run(apply=True)
        self.s1.refresh_from_db()
        self.assertEqual(self.s1.rating_current, Decimal("120.5"))

    def test_expect_students_is_required_and_checked(self):
        with self.assertRaises(CommandError):
            call_command("reset_all_progress", apply=True, confirm="RESET", stdout=StringIO())
        with self.assertRaisesMessage(CommandError, "ожидалось 574"):
            run(apply=True, expect_students=574)
        self.s1.refresh_from_db()
        self.assertEqual(self.s1.rating_current, Decimal("120.5"))

    def test_apply_reminds_about_dump(self):
        self.assertIn("pg_dump", run(apply=True))

    def test_cache_is_not_flushed(self):
        with patch.object(cache, "delete_pattern", create=True) as deleter, patch.object(cache, "clear") as clear:
            run(apply=True)

        clear.assert_not_called()
        patterns = {call.args[0] for call in deleter.call_args_list}
        self.assertIn("profile:*", patterns)
        self.assertIn("leaderboard:*", patterns)
