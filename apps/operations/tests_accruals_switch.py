"""Выключатель начислений: «заморозка до запуска».

До запуска ничего не начисляется, а в день включения сезон стартует с этого
дня: данные за прошлые дни не оплачиваются. Главное, что здесь проверяется:
при выключенных начислениях каждый путь ничего не меняет И не оставляет
маркеров идемпотентности — иначе после включения неделю или квест уже
нельзя было бы оплатить.
"""

from __future__ import annotations

from datetime import date, timedelta
from decimal import Decimal
from unittest import mock

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APITestCase

from apps.accounts.models import Role
from apps.badges.models import Badge, UserBadge
from apps.badges.services import award_badge_manually, award_badges_for_user
from apps.badges.tasks import check_badges_weekly
from apps.operations.models import PlatformSettings
from apps.operations.services.platform_settings import (
    AccrualsDisabled,
    accruals_active_on,
    accruals_enabled,
    accruals_start_date,
    invalidate,
    switch_accruals,
)
from apps.progress.models import LessonAttendance, LessonAttendanceStatus, RatingChangeSource, RatingLog
from apps.progress.services.polozhenie_academic import run_weekly_accrual
from apps.progress.services.polozhenie_ledger import grant
from apps.progress.services.polozhenie_period import is_payable_week, season_start_date
from apps.progress.services.rewards import apply_rating_delta_with_cap, grant_coins_with_daily_cap
from apps.progress.tasks import accrue_polozhenie_week, apply_strike_bonuses_daily
from apps.quests.models import Quest, QuestRewardTransaction, QuestTemplate, QuestType, UserQuestProgress
from apps.quests.services.quest_completion import complete_quest_idempotent
from apps.quests.tasks import create_period_quests, verify_auto_quests
from apps.social.models import Duel, DuelStatus, Mentorship
from apps.social.tasks import pay_mentorship_weekly, resolve_duels

User = get_user_model()


def freeze_accruals() -> None:
    """Состояние платформы до запуска: выключено, даты старта нет."""
    PlatformSettings.objects.filter(pk=PlatformSettings.SINGLETON_PK).update(
        accruals_enabled=False, accruals_started_on=None
    )
    invalidate()


def make_agent(username: str, **extra) -> User:
    return User.objects.create_user(
        username=username, password="x", callsign=f"call_{username}", role=Role.AGENT, **extra
    )


class AccrualsCase(TestCase):
    def setUp(self):
        # Откат транзакции возвращает строку, но не кеш настроек.
        invalidate()
        self.addCleanup(invalidate)


class SwitchServiceTests(AccrualsCase):
    def test_switch_on_sets_today_as_start(self):
        freeze_accruals()

        switch_accruals(True)

        self.assertTrue(accruals_enabled())
        self.assertEqual(accruals_start_date(), timezone.localdate())

    def test_switch_off_keeps_the_date(self):
        freeze_accruals()
        switch_accruals(True)

        switch_accruals(False)

        self.assertFalse(accruals_enabled())
        self.assertEqual(accruals_start_date(), timezone.localdate())

    def test_switching_on_again_moves_start_to_the_new_day(self):
        PlatformSettings.objects.filter(pk=1).update(
            accruals_enabled=False, accruals_started_on=date(2026, 1, 5)
        )
        invalidate()

        switch_accruals(True)

        self.assertEqual(accruals_start_date(), timezone.localdate())

    def test_switch_on_twice_does_not_move_the_date(self):
        PlatformSettings.objects.filter(pk=1).update(
            accruals_enabled=True, accruals_started_on=date(2026, 1, 5)
        )
        invalidate()

        switch_accruals(True)

        self.assertEqual(accruals_start_date(), date(2026, 1, 5))

    def test_active_on_respects_start_date(self):
        freeze_accruals()
        switch_accruals(True)
        today = timezone.localdate()

        self.assertTrue(accruals_active_on(today))
        self.assertFalse(accruals_active_on(today - timedelta(days=1)))

    def test_active_on_is_false_when_disabled(self):
        freeze_accruals()
        self.assertFalse(accruals_active_on(timezone.localdate()))

    def test_season_start_prefers_activation_date(self):
        freeze_accruals()
        switch_accruals(True)

        self.assertEqual(season_start_date(), timezone.localdate())

    @override_settings(POLOZHENIE_PERIOD={"SEASON_START_DATE": "2026-10-19", "DECIMAL_PLACES": 2})
    def test_season_start_falls_back_to_settings_without_activation(self):
        PlatformSettings.objects.filter(pk=1).update(accruals_started_on=None)
        invalidate()

        self.assertEqual(season_start_date(), date(2026, 10, 19))

    def test_weeks_are_not_payable_while_disabled(self):
        freeze_accruals()
        self.assertFalse(is_payable_week(timezone.localdate()))


class CoreIsClosedTests(AccrualsCase):
    def setUp(self):
        super().setUp()
        self.agent = make_agent("core", rating_current=100, coins_balance=0)
        freeze_accruals()

    def assert_untouched(self):
        self.agent.refresh_from_db()
        self.assertEqual(self.agent.rating_current, 100)
        self.assertEqual(self.agent.coins_balance, 0)
        self.assertEqual(RatingLog.objects.filter(user=self.agent).count(), 0)

    def test_ledger_grant_does_nothing(self):
        result = grant(
            self.agent, rating=5, coins=5, source=RatingChangeSource.ACADEMIC, source_id="w:1", reason="x"
        )

        self.assertFalse(result.applied)
        self.assertEqual(result.reason, "accruals_disabled")
        self.assert_untouched()

    def test_ledger_leaves_no_marker_so_it_can_be_paid_after_launch(self):
        grant(self.agent, rating=5, coins=5, source=RatingChangeSource.ACADEMIC, source_id="w:1", reason="x")

        switch_accruals(True)
        result = grant(
            self.agent, rating=5, coins=5, source=RatingChangeSource.ACADEMIC, source_id="w:1", reason="x"
        )

        self.assertTrue(result.applied)

    def test_rating_delta_with_cap_does_nothing(self):
        applied = apply_rating_delta_with_cap(self.agent, 10, RatingChangeSource.QUEST, "x", "q1")

        self.assertEqual(applied, 0)
        self.assert_untouched()

    def test_daily_cap_coins_does_nothing(self):
        self.assertEqual(grant_coins_with_daily_cap(self.agent, 5), 0)
        self.assert_untouched()

    def test_quest_completion_is_refused_without_trace(self):
        quest = Quest.objects.create(code="q-off", title="Q", quest_type=QuestType.LONG, reward_coins=5)

        with self.assertRaises(AccrualsDisabled):
            complete_quest_idempotent(self.agent, quest, reason="x")

        self.assertFalse(QuestRewardTransaction.objects.exists())
        self.assertFalse(UserQuestProgress.objects.filter(quest=quest).exists())

    def test_auto_badges_are_not_awarded(self):
        badge = Badge.objects.create(code="b1", title="B", condition={"rating_at_least": 1}, reward_coins=3)

        self.assertEqual(award_badges_for_user(self.agent, [badge]), [])
        self.assertFalse(UserBadge.objects.exists())

    def test_manual_badge_is_refused(self):
        badge = Badge.objects.create(code="b2", title="B", reward_coins=3)

        with self.assertRaises(AccrualsDisabled):
            award_badge_manually(self.agent, badge, by="staff")

        self.assertFalse(UserBadge.objects.exists())


class TasksAreClosedTests(AccrualsCase):
    def setUp(self):
        super().setUp()
        self.agent = make_agent("tasks", rating_current=100)
        freeze_accruals()

    def test_weekly_accrual_task_does_nothing(self):
        LessonAttendance.objects.create(
            user=self.agent,
            lxp_class_id="c1",
            lesson_date=timezone.localdate() - timedelta(days=7),
            status=LessonAttendanceStatus.PRESENT,
        )

        result = accrue_polozhenie_week()

        self.assertIn("accruals_disabled", result)
        self.assertFalse(RatingLog.objects.exists())

    def test_strike_task_does_not_touch_streaks(self):
        from apps.progress.models import UserStrike

        result = apply_strike_bonuses_daily()

        self.assertIn("accruals_disabled", result)
        self.assertFalse(UserStrike.objects.exists())
        self.assertFalse(RatingLog.objects.exists())

    def test_verify_task_rewards_nothing(self):
        QuestTemplate.objects.create(
            code="tpl-off", title="T", quest_type=QuestType.DAILY, reward_coins=5, is_active=True
        )

        result = verify_auto_quests()

        self.assertEqual(result.get("skipped"), "accruals_disabled")
        self.assertFalse(QuestRewardTransaction.objects.exists())

    def test_period_quests_are_not_created(self):
        QuestTemplate.objects.create(
            code="tpl-off2", title="T", quest_type=QuestType.DAILY, reward_coins=5, is_active=True
        )

        result = create_period_quests()

        self.assertEqual(result.get("skipped"), "accruals_disabled")
        self.assertFalse(Quest.objects.exists())

    def test_badge_task_awards_nothing(self):
        Badge.objects.create(code="b3", title="B", condition={"rating_at_least": 1}, reward_coins=3)

        result = check_badges_weekly()

        self.assertIn("accruals_disabled", result)
        self.assertFalse(UserBadge.objects.exists())

    def test_duels_are_not_resolved_and_stay_open(self):
        other = make_agent("tasks2", rating_current=100)
        duel = Duel.objects.create(
            challenger=self.agent,
            opponent=other,
            status=DuelStatus.ACCEPTED,
            resolve_after=timezone.now() - timedelta(days=1),
            challenger_rating_start=0,
            opponent_rating_start=0,
        )

        result = resolve_duels()

        duel.refresh_from_db()
        self.assertEqual(result.get("skipped"), "accruals_disabled")
        self.assertEqual(duel.status, DuelStatus.ACCEPTED)
        self.assertIsNone(duel.resolved_at)

    def test_mentorship_pay_leaves_no_markers(self):
        mentee = make_agent("tasks3")
        Mentorship.objects.create(mentor=self.agent, mentee=mentee)

        result = pay_mentorship_weekly()

        self.assertEqual(result.get("skipped"), "accruals_disabled")
        self.assertFalse(RatingLog.objects.exists())
        self.agent.refresh_from_db()
        self.assertEqual(self.agent.coins_balance, 0)


class NothingBackdatedTests(AccrualsCase):
    """В день включения сезон стартует с этого дня, а не с понедельника."""

    def test_attendance_before_launch_is_not_paid(self):
        agent = make_agent("backdated")
        today = timezone.localdate()
        monday = today - timedelta(days=today.weekday())
        freeze_accruals()
        switch_accruals(True)
        # Вчерашние пары (если сегодня не понедельник) — до старта.
        before_launch = today - timedelta(days=1)
        if before_launch < monday:  # сегодня понедельник: берём прошлую неделю
            before_launch = monday - timedelta(days=3)
        LessonAttendance.objects.create(
            user=agent, lxp_class_id="old", lesson_date=before_launch, status=LessonAttendanceStatus.MISSED
        )
        LessonAttendance.objects.create(
            user=agent, lxp_class_id="new", lesson_date=today, status=LessonAttendanceStatus.PRESENT
        )

        result = run_weekly_accrual(today)

        # Вчерашний пропуск до старта не в счёт: посещаемость 100% (13 баллов
        # по тарифу). Будь он в счёте, было бы 50%.
        self.assertEqual(result.users_paid, 1)
        log = RatingLog.objects.get(user=agent, source_id__endswith=":attendance")
        self.assertEqual(log.delta, Decimal("13.00"))

    def test_strikes_skip_days_before_launch(self):
        from apps.progress.services.strike_bonuses import apply_strike_bonuses

        freeze_accruals()
        switch_accruals(True)
        today = timezone.localdate()

        # «Вчера» (день, за который считаем) — до старта.
        result = apply_strike_bonuses(today)

        self.assertEqual(result.get("skipped"), "before_launch")

    def test_late_penalty_before_launch_is_skipped(self):
        from datetime import datetime

        from apps.integrations.services import hik_attendance_processor as proc

        agent = make_agent("late", rating_current=100)
        freeze_accruals()
        switch_accruals(True)
        yesterday = timezone.make_aware(
            datetime.combine(timezone.localdate() - timedelta(days=1), datetime.min.time())
        )

        with override_settings(HIK_LATE_PENALTY_ENABLED=True):
            proc._apply_late_penalty_if_needed(agent, event_dt=yesterday, late_minutes=20)

        self.assertFalse(RatingLog.objects.filter(user=agent).exists())


@override_settings(SECURE_SSL_REDIRECT=False)
class AdminSwitchTests(AccrualsCase):
    def setUp(self):
        super().setUp()
        freeze_accruals()
        self.admin_user = User.objects.create_user(
            username="boss", password="x", callsign="boss", role=Role.ADMIN, is_staff=True
        )
        self.curator = User.objects.create_user(
            username="cur", password="x", callsign="cur", role=Role.CURATOR, is_staff=True
        )
        self.url = reverse("admin:operations_platformsettings_accruals")

    def test_confirmation_page_explains_season_start(self):
        self.client.force_login(self.admin_user)

        response = self.client.get(self.url)

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Включить начисления")
        self.assertContains(response, "сегодняшнего дня")
        self.assertFalse(accruals_enabled())

    def test_get_does_not_switch(self):
        self.client.force_login(self.admin_user)
        self.client.get(self.url)
        self.assertFalse(accruals_enabled())

    def test_post_enables_and_sets_date(self):
        self.client.force_login(self.admin_user)

        self.client.post(self.url, {"apply": "1", "target": "on"})

        self.assertTrue(accruals_enabled())
        self.assertEqual(accruals_start_date(), timezone.localdate())

    def test_post_again_disables(self):
        self.client.force_login(self.admin_user)
        self.client.post(self.url, {"apply": "1", "target": "on"})

        response = self.client.get(self.url)
        self.assertContains(response, "Остановить начисления")
        self.client.post(self.url, {"apply": "1", "target": "off"})

        self.assertFalse(accruals_enabled())

    def test_switch_is_written_to_history(self):
        from django.contrib.admin.models import LogEntry

        self.client.force_login(self.admin_user)
        self.client.post(self.url, {"apply": "1", "target": "on"})

        entry = LogEntry.objects.filter(object_id=str(PlatformSettings.SINGLETON_PK)).latest("action_time")
        self.assertIn("→", entry.get_change_message())

    def test_curator_cannot_switch(self):
        self.client.force_login(self.curator)

        response = self.client.post(self.url, {"apply": "1", "target": "on"})

        self.assertEqual(response.status_code, 403)
        self.assertFalse(accruals_enabled())

    def test_double_post_to_enable_stays_enabled(self):
        """Двойной клик: второй POST с target=on не должен выключить начисления."""
        self.client.force_login(self.admin_user)

        self.client.post(self.url, {"apply": "1", "target": "on"})
        first_date = accruals_start_date()
        self.client.post(self.url, {"apply": "1", "target": "on"})

        self.assertTrue(accruals_enabled())
        self.assertEqual(accruals_start_date(), first_date)

    def test_post_without_target_changes_nothing(self):
        self.client.force_login(self.admin_user)

        self.client.post(self.url, {"apply": "1"})

        self.assertFalse(accruals_enabled())

    def test_period_quest_failure_does_not_break_switch(self):
        self.client.force_login(self.admin_user)

        with mock.patch(
            "apps.quests.services.quest_periods.ensure_period_quests", side_effect=RuntimeError("boom")
        ):
            response = self.client.post(self.url, {"apply": "1", "target": "on"})

        self.assertEqual(response.status_code, 302)
        self.assertTrue(accruals_enabled())

    def test_anonymous_cannot_switch(self):
        self.client.post(self.url, {"apply": "1", "target": "on"})
        self.assertFalse(accruals_enabled())

    def test_status_is_visible_on_admin_index(self):
        self.client.force_login(self.admin_user)

        response = self.client.get(reverse("admin:index"))

        self.assertContains(response, "Начисления выключены")

    def test_manual_correction_is_refused_with_message(self):
        from django.contrib.messages import get_messages

        from apps.accounts.admin import UserAdmin  # noqa: F401  (модель-админ зарегистрирован)

        self.client.force_login(self.admin_user)
        target = make_agent("target", rating_current=100)

        response = self.client.post(
            reverse("admin:accounts_user_changelist"),
            {
                "action": "correct_balance",
                "_selected_action": [target.pk],
                "apply": "1",
                "rating": "5",
                "coins": "5",
                "reason": "тест",
            },
            follow=True,
        )

        target.refresh_from_db()
        self.assertEqual(target.rating_current, 100)
        self.assertFalse(RatingLog.objects.filter(user=target).exists())
        texts = " ".join(str(m) for m in get_messages(response.wsgi_request))
        self.assertIn("Начисления стартуют с запуска платформы", texts)


class UserActionsAreRefusedTests(APITestCase):
    def setUp(self):
        invalidate()
        self.addCleanup(invalidate)
        self.user = make_agent("student", rating_current=100, coins_balance=50)
        self.other = make_agent("other", rating_current=100)
        self.client.force_authenticate(self.user)
        freeze_accruals()

    def test_respect_is_refused(self):
        from apps.social.models import Respect

        response = self.client.post(reverse("social-respects-create"), {"to_username": "other"}, format="json")

        self.assertEqual(response.status_code, 409)
        self.assertIn("Начисления стартуют с запуска платформы", response.json()["detail"])
        self.assertFalse(Respect.objects.exists())

    def test_duel_challenge_is_refused(self):
        response = self.client.post(
            reverse("social-duels-create"), {"opponent_username": "other"}, format="json"
        )

        self.assertEqual(response.status_code, 409)
        self.assertFalse(Duel.objects.exists())

    def test_self_report_is_refused(self):
        Quest.objects.create(code="sr", title="S", quest_type=QuestType.SELF_REPORT, reward_coins=5)

        response = self.client.post(
            reverse("quests-self-report", args=["sr"]), {"comment": "сделал"}, format="json"
        )

        self.assertEqual(response.status_code, 409)

    def test_manual_confirmation_is_refused(self):
        Quest.objects.create(
            code="mc",
            title="M",
            quest_type=QuestType.LONG,
            reward_coins=5,
            conditions={"manual_complete_allowed": True},
        )

        response = self.client.post(reverse("quests-complete", args=["mc"]), {}, format="json")

        self.assertEqual(response.status_code, 409)

    def test_shop_purchase_is_refused(self):
        from apps.shop.models import Purchase, ShopItem

        ShopItem.objects.create(code="it", title="I", price_coins=5, is_active=True)

        response = self.client.post(reverse("shop-purchase"), {"item_code": "it"}, format="json")

        self.assertEqual(response.status_code, 409)
        self.assertFalse(Purchase.objects.exists())
        self.user.refresh_from_db()
        self.assertEqual(self.user.coins_balance, 50)

    def test_dashboard_exposes_the_flag(self):
        response = self.client.get(reverse("dashboard"))

        self.assertEqual(response.status_code, 200)
        self.assertIs(response.json()["accruals_enabled"], False)

    def test_enabled_actions_still_work(self):
        switch_accruals(True)

        response = self.client.post(reverse("social-respects-create"), {"to_username": "other"}, format="json")

        self.assertEqual(response.status_code, 201)


class StaleCacheTests(AccrualsCase):
    def test_old_cached_dict_without_new_keys_does_not_crash(self):
        """После деплоя в Redis ещё лежит словарь без ключей accruals_*."""
        from django.core.cache import cache

        from apps.operations.services.platform_settings import CACHE_KEY, default_values

        old = {k: v for k, v in default_values().items() if not k.startswith("accruals_")}
        cache.set(CACHE_KEY, old, 300)

        self.assertIsInstance(accruals_enabled(), bool)
        self.assertIsNone(accruals_start_date())


class LaunchBoundaryMetricsTests(AccrualsCase):
    def setUp(self):
        super().setUp()
        self.agent = make_agent("metrics")
        freeze_accruals()
        switch_accruals(True)
        self.today = timezone.localdate()

    def test_ct_closed_counts_only_topics_closed_since_launch(self):
        from apps.badges.metrics import compute
        from apps.progress.models import LXPTopicState

        old = (self.today - timedelta(days=3)).isoformat()
        LXPTopicState.objects.create(
            user=self.agent,
            topics={
                "a": {"closed": True, "since": old},
                "b": {"closed": True, "since": self.today.isoformat()},
            },
        )

        self.assertEqual(compute(self.agent, {"ct_closed_at_least"})["ct_closed_at_least"], 1)

    def test_max_pillar_ignores_values_computed_before_launch(self):
        from apps.badges.metrics import compute
        from apps.progress.models import Characteristic

        row = Characteristic.objects.create(user=self.agent, pillar="focus", current=15)
        Characteristic.objects.filter(pk=row.pk).update(last_updated=timezone.now() - timedelta(days=3))

        self.assertEqual(compute(self.agent, {"max_pillar_at_least"})["max_pillar_at_least"], 0)

    def test_max_pillar_counts_values_computed_after_launch(self):
        from apps.badges.metrics import compute
        from apps.progress.models import Characteristic

        Characteristic.objects.create(user=self.agent, pillar="focus", current=15)

        self.assertEqual(compute(self.agent, {"max_pillar_at_least"})["max_pillar_at_least"], 15)

    def test_lxp_attendance_uses_only_lessons_since_launch(self):
        from apps.quests.services.verifiers import verify_lxp_attendance

        self.agent.lxp_user_id = "lxp-att"
        self.agent.save(update_fields=["lxp_user_id"])
        LessonAttendance.objects.create(
            user=self.agent,
            lxp_class_id="old",
            lesson_date=self.today - timedelta(days=2),
            status=LessonAttendanceStatus.MISSED,
        )
        LessonAttendance.objects.create(
            user=self.agent,
            lxp_class_id="new",
            lesson_date=self.today,
            status=LessonAttendanceStatus.PRESENT,
        )

        result = verify_lxp_attendance(self.agent, {"min_percent": 80}, self.today)

        self.assertTrue(result.completed)
        self.assertEqual(result.evidence["percent"], 100.0)


class FrozenAdminsTests(AccrualsCase):
    def test_reward_bearing_admins_are_read_only_while_frozen(self):
        from django.contrib.admin.sites import site

        from apps.progress.models import UserStrike
        from apps.social.models import Respect

        boss = User.objects.create_user(
            username="boss2", password="x", callsign="boss2", role=Role.ADMIN, is_staff=True
        )
        request = mock.Mock(user=boss)
        models = (UserQuestProgress, UserStrike, Respect, Duel)

        freeze_accruals()
        for model in models:
            model_admin = site._registry[model]
            self.assertFalse(model_admin.has_add_permission(request), model)
            self.assertFalse(model_admin.has_change_permission(request), model)

        switch_accruals(True)
        for model in models:
            self.assertTrue(site._registry[model].has_change_permission(request), model)


class PolicyStateTests(APITestCase):
    def test_season_start_follows_activation_date(self):
        invalidate()
        self.addCleanup(invalidate)
        freeze_accruals()
        switch_accruals(True)
        self.client.force_authenticate(make_agent("pol"))

        response = self.client.get(reverse("policy-state"))

        self.assertEqual(response.json()["season_start"], timezone.localdate().isoformat())
