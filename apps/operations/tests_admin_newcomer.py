"""Админка глазами нового сотрудника.

Каждый тест — сценарий, на котором новичок спотыкался: поля действий без
подписей, начисление мимо Положения, сырой JSON в формах, кнопки, которых
нет, дашборды с 403. Тесты проверяют поведение, а не только то, что
страница открылась.
"""

from __future__ import annotations

from datetime import date
from unittest import mock

from django.contrib.admin.helpers import ACTION_CHECKBOX_NAME
from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.urls import reverse

from apps.accounts.admin import activity_key_for
from apps.accounts.models import Role, Squad
from apps.badges.models import Badge
from apps.progress.models import PolozhenieAward
from apps.quests.models import (
    Quest,
    QuestTemplate,
    QuestType,
    QuestVerifierKind,
    SelfReportProof,
    SelfReportProofStatus,
    UserQuestProgress,
)

User = get_user_model()


class ActivityKeyTests(TestCase):
    def test_cyrillic_titles_get_different_keys(self):
        """slugify выбрасывал кириллицу: оба названия давали «:2026-10-20»."""
        day = date(2026, 10, 20)

        self.assertNotEqual(
            activity_key_for("Олимпиада по математике", day),
            activity_key_for("Субботник", day),
        )

    def test_same_event_same_day_is_one_key(self):
        day = date(2026, 10, 20)

        self.assertEqual(activity_key_for("Хакатон", day), activity_key_for("  хакатон ", day))

    def test_key_fits_the_ledger_column(self):
        key = activity_key_for("Очень длинное название мероприятия " * 5, date(2026, 10, 20))

        self.assertLessEqual(len(f"event:{key}:speaker"), 64)


@override_settings(SECURE_SSL_REDIRECT=False)
class AdminTestCase(TestCase):
    def setUp(self):
        self.admin_user = User.objects.create_user(
            username="boss", password="x", callsign="boss", role=Role.ADMIN, is_staff=True
        )
        self.client.force_login(self.admin_user)
        self.squad = Squad.objects.create(code="itr", name="3ИТР", course=3)

    def student(self, name: str) -> User:
        return User.objects.create_user(
            username=name, password="x", callsign=name, role=Role.AGENT, squad=self.squad
        )


class AwardActionTests(AdminTestCase):
    url = reverse("admin:accounts_user_changelist")

    def test_first_step_shows_a_labelled_form(self):
        """Раньше поля стояли строкой над списком, без подписей."""
        alice = self.student("alice")

        response = self.client.post(
            self.url, {"action": "grant_polozhenie_award", ACTION_CHECKBOX_NAME: [alice.pk]}
        )

        self.assertEqual(response.status_code, 200)
        self.assertContains(response, "Что засчитываем")
        self.assertContains(response, "Название мероприятия")
        self.assertContains(response, "alice")
        self.assertFalse(PolozhenieAward.objects.exists(), "без подтверждения ничего не начислено")

    def test_confirmation_grants_with_the_event_date(self):
        alice = self.student("alice")

        self.client.post(
            self.url,
            {
                "action": "grant_polozhenie_award",
                ACTION_CHECKBOX_NAME: [alice.pk],
                "apply": "1",
                "tariff_code": "event:college:listener",
                "activity_title": "Субботник",
                "activity_date": "2026-10-14",
            },
        )

        award = PolozhenieAward.objects.get(user=alice)
        self.assertEqual(award.happened_on, date(2026, 10, 14), "дата мероприятия, а не дата нажатия")

    def test_two_cyrillic_events_same_day_are_both_paid(self):
        alice = self.student("alice")
        for title in ("Субботник", "Олимпиада по математике"):
            self.client.post(
                self.url,
                {
                    "action": "grant_polozhenie_award",
                    ACTION_CHECKBOX_NAME: [alice.pk],
                    "apply": "1",
                    "tariff_code": "event:college:listener",
                    "activity_title": title,
                    "activity_date": "2026-10-14",
                },
            )

        self.assertEqual(PolozhenieAward.objects.filter(user=alice).count(), 2)

    def test_bypass_action_is_gone(self):
        """«+10 монет за мероприятие» платило мимо Положения."""
        response = self.client.get(self.url)

        self.assertNotContains(response, "grant_event_bonus")
        self.assertNotContains(response, "create_recovery_quest", msg_prefix="админу — только тьютору")


class ReviewQueueTests(AdminTestCase):
    url = reverse("admin:quests_selfreportproof_changelist")

    def setUp(self):
        super().setUp()
        self.quest = Quest.objects.create(
            code="self-report-lab", title="Лабораторная работа", quest_type=QuestType.SELF_REPORT,
            reward_coins=5, is_active=True,
        )
        alice = self.student("alice")
        progress = UserQuestProgress.objects.create(user=alice, quest=self.quest)
        self.proof = SelfReportProof.objects.create(
            user=alice, quest=self.quest, quest_progress=progress, comment="Сделал лабораторную по сетям",
        )

    def test_list_shows_title_comment_and_buttons(self):
        response = self.client.get(self.url)

        self.assertContains(response, "Лабораторная работа")
        self.assertContains(response, "Сделал лабораторную по сетям")
        self.assertContains(response, 'name="row_approve"')

    def test_row_button_approves(self):
        """Одно нажатие вместо галочки, выбора действия и «Выполнить»."""
        self.client.post(self.url, {"row_approve": str(self.proof.pk)})

        self.proof.refresh_from_db()
        self.assertEqual(self.proof.status, SelfReportProofStatus.APPROVED)

    def test_row_button_rejects(self):
        self.client.post(self.url, {"row_reject": str(self.proof.pk)})

        self.proof.refresh_from_db()
        self.assertEqual(self.proof.status, SelfReportProofStatus.REJECTED)


class BadgeFormTests(AdminTestCase):
    url = reverse("admin:badges_badge_add")

    def base(self, **extra):
        return {
            "title": "Ветеран рейтинга", "description": "", "category": Badge._meta.get_field("category").default,
            "rarity": Badge._meta.get_field("rarity").default, "reward_coins": "5", "is_active": "on",
            "code": "", **extra,
        }

    def test_condition_is_built_from_dropdown(self):
        """Раньше нужно было самому написать {"rating_at_least": 300}."""
        self.client.post(self.url, self.base(award_mode="auto", metric_1="rating_at_least", threshold_1="300"))

        badge = Badge.objects.get(title="Ветеран рейтинга")
        self.assertEqual(badge.condition, {"rating_at_least": 300})
        self.assertTrue(badge.code.isascii() and badge.code, "код собран из названия латиницей")

    def test_manual_badge(self):
        self.client.post(self.url, self.base(award_mode="manual"))

        self.assertEqual(Badge.objects.get(title="Ветеран рейтинга").condition, {"manual": True})

    def test_auto_without_condition_is_rejected_with_message(self):
        response = self.client.post(self.url, self.base(award_mode="auto"))

        self.assertFalse(Badge.objects.filter(title="Ветеран рейтинга").exists())
        self.assertContains(response, "Выберите хотя бы одно условие")


class QuestTemplateFormTests(AdminTestCase):
    url = reverse("admin:quests_questtemplate_add")

    def post(self, **extra):
        data = {
            "title": "Неделя на парах", "description": "", "quest_type": QuestType.SELF_REPORT,
            "reward_coins": "7", "is_active": "on", "code": "", "verifier": QuestVerifierKind.LXP_ATTENDANCE,
            **extra,
        }
        return self.client.post(self.url, data)

    def test_params_come_from_labelled_fields(self):
        self.post(param_min_percent="90")

        tpl = QuestTemplate.objects.get(title="Неделя на парах")
        self.assertEqual(tpl.verifier_params, {"min_percent": 90})
        self.assertEqual(tpl.reward_rating_delta, 0, "квесты дают только монеты")

    def test_non_periodic_template_creates_the_quest(self):
        """Раньше квест из такого шаблона создавала только консольная команда."""
        self.post()

        tpl = QuestTemplate.objects.get(title="Неделя на парах")
        self.assertTrue(Quest.objects.filter(code=tpl.code, is_active=True).exists())


class DashboardTests(AdminTestCase):
    def test_my_dashboard_takes_admin_to_the_college_view(self):
        response = self.client.get(reverse("admin-my-dashboard"))

        self.assertRedirects(response, reverse("admin-hq-dashboard"))

    def test_admin_can_open_college_dashboard(self):
        """Раньше администратору все три дашборда отвечали 403."""
        self.assertEqual(self.client.get(reverse("admin-hq-dashboard")).status_code, 200)


@override_settings(SECURE_SSL_REDIRECT=False)
class LoginRedirectTests(TestCase):
    def test_direct_login_lands_in_admin_not_404(self):
        User.objects.create_user(username="staff", password="pw-123456", callsign="staff",
                                 role=Role.ADMIN, is_staff=True)

        response = self.client.post(reverse("admin:login"), {"username": "staff", "password": "pw-123456"})

        self.assertRedirects(response, "/admin/", fetch_redirect_response=False)


class NotificationQueueTests(TestCase):
    def test_message_goes_through_the_queue(self):
        """Отправка не держит запрос: в нём только постановка в очередь."""
        from apps.notifications.services import telegram

        with mock.patch("apps.notifications.tasks.send_telegram_message.delay") as delay:
            self.assertTrue(telegram.enqueue_message(123, "Привет"))

        delay.assert_called_once_with(123, "Привет")


class StudentCardTests(AdminTestCase):
    """Показатели студента меняются только через журнал начислений."""

    def setUp(self):
        super().setUp()
        self.alice = self.student("alice")
        self.url = reverse("admin:accounts_user_change", args=[self.alice.pk])

    def test_rating_cannot_be_typed_in(self):
        """Раньше рейтинг был обычным полем: правка без основания и следа."""
        page = self.client.get(self.url)
        data = {
            k: v for k, v in page.context["adminform"].form.initial.items()
            if v is not None and not isinstance(v, (list, tuple)) and k != "avatar"
        }
        data.update({"rating_current": "999", "coins_balance": "999", "squad": self.squad.pk, "role": Role.AGENT})

        self.client.post(self.url, data)

        self.alice.refresh_from_db()
        self.assertNotEqual(self.alice.rating_current, 999)
        self.assertNotEqual(self.alice.coins_balance, 999)

    def test_history_links_open_filtered_lists(self):
        for name in (
            "admin:progress_ratinglog_changelist",
            "admin:progress_polozhenieaward_changelist",
            "admin:badges_userbadge_changelist",
            "admin:progress_lessonattendance_changelist",
        ):
            response = self.client.get(f"{reverse(name)}?user__id__exact={self.alice.pk}")
            self.assertEqual(response.status_code, 200, name)
            self.assertNotIn("e=1", response.url if hasattr(response, "url") else "", name)

    def test_correction_goes_through_the_ledger_with_reason(self):
        from apps.progress.models import RatingLog

        self.client.post(
            reverse("admin:accounts_user_changelist"),
            {
                "action": "correct_balance",
                ACTION_CHECKBOX_NAME: [self.alice.pk],
                "apply": "1",
                "rating": "5",
                "coins": "0",
                "reason": "Не засчитали хакатон 14.10, обращение № 3",
            },
        )

        log = RatingLog.objects.filter(user=self.alice).latest("created_at")
        self.assertIn("хакатон", log.reason)
        self.assertEqual(log.confirmed_by, self.admin_user)

    def test_correction_needs_a_reason(self):
        response = self.client.post(
            reverse("admin:accounts_user_changelist"),
            {"action": "correct_balance", ACTION_CHECKBOX_NAME: [self.alice.pk], "apply": "1",
             "rating": "5", "coins": "0", "reason": ""},
        )

        self.assertContains(response, "Основание")
        self.alice.refresh_from_db()
        self.assertEqual(self.alice.rating_current, 0)


class ShopItemFormTests(AdminTestCase):
    url = reverse("admin:shop_shopitem_add")

    def post(self, item_type):
        return self.client.post(
            self.url,
            {"title": "Кружка IThub", "description": "", "item_type": item_type, "price_coins": "50",
             "is_active": "on", "code": ""},
        )

    def test_boost_without_mechanics_is_refused(self):
        """Купленное усиление нигде не читается — монеты ушли бы в никуда."""
        from apps.shop.models import ShopItem, ShopItemType

        response = self.post(ShopItemType.BOOST)

        self.assertFalse(ShopItem.objects.filter(title="Кружка IThub").exists())
        self.assertContains(response, "нет механики")

    def test_code_is_made_from_the_title(self):
        from apps.shop.models import ShopItem, ShopItemType

        self.post(ShopItemType.OTHER)

        self.assertEqual(ShopItem.objects.get(title="Кружка IThub").code, "kruzhka-ithub")


class RelatedWidgetTests(AdminTestCase):
    def test_squad_cannot_be_deleted_from_a_student_card(self):
        """Красный крестик у «Отряда» удалял сам отряд, а не отвязывал студента."""
        alice = self.student("alice")

        response = self.client.get(reverse("admin:accounts_user_change", args=[alice.pk]))

        self.assertNotContains(response, 'id="delete_id_squad"')
        self.assertNotContains(response, 'id="change_id_squad"')


class AwardFormDefaultsTests(TestCase):
    def test_date_field_renders_today_for_the_browser_calendar(self):
        from django.utils import timezone

        from apps.accounts.admin import PolozhenieAwardForm

        html = str(PolozhenieAwardForm()["activity_date"])

        self.assertIn(f'value="{timezone.localdate().isoformat()}"', html)


class BulkActiveActionsTests(AdminTestCase):
    """Включать и выключать пачкой — вместо удаления, стирающего историю."""

    def setUp(self):
        super().setUp()
        self.quests = [
            Quest.objects.create(code=f"q{i}", title=f"Квест {i}", quest_type=QuestType.LONG, is_active=True)
            for i in range(3)
        ]
        self.url = reverse("admin:quests_quest_changelist")

    def test_quests_can_be_switched_off_and_on_in_bulk(self):
        ids = [q.pk for q in self.quests[:2]]

        self.client.post(self.url, {"action": "deactivate_selected", ACTION_CHECKBOX_NAME: ids})
        self.assertEqual(Quest.objects.filter(pk__in=ids, is_active=False).count(), 2)
        self.assertTrue(Quest.objects.get(pk=self.quests[2].pk).is_active, "невыбранный не тронут")

        self.client.post(self.url, {"action": "activate_selected", ACTION_CHECKBOX_NAME: ids})
        self.assertEqual(Quest.objects.filter(pk__in=ids, is_active=True).count(), 2)

    def test_switch_is_recorded_in_history(self):
        from django.contrib.admin.models import LogEntry

        self.client.post(self.url, {"action": "deactivate_selected", ACTION_CHECKBOX_NAME: [self.quests[0].pk]})

        self.assertTrue(LogEntry.objects.filter(object_id=str(self.quests[0].pk), user=self.admin_user).exists())

    def test_admin_cannot_delete_quests_or_badges(self):
        """Удаление квеста стирает прогресс и награды студентов каскадом."""
        # Над пустым списком Django панель действий не показывает вовсе.
        Badge.objects.create(code="b1", title="Нашивка", condition={"manual": True})
        for name in ("admin:quests_quest_changelist", "admin:badges_badge_changelist"):
            response = self.client.get(reverse(name))
            self.assertNotContains(response, 'value="delete_selected"', msg_prefix=name)
            self.assertContains(response, 'value="deactivate_selected"', msg_prefix=name)

    def test_students_have_no_bulk_switch(self):
        """Массово выключить студентов — закрыть им вход."""
        response = self.client.get(reverse("admin:accounts_user_changelist"))

        self.assertNotContains(response, 'value="deactivate_selected"')


class FrequentActionsTests(AdminTestCase):
    """Самые частые действия администрации — без разработчика."""

    users_url = reverse("admin:accounts_user_changelist")

    def test_any_list_exports_to_excel(self):
        alice = self.student("alice")

        response = self.client.post(
            self.users_url, {"action": "export_selected_csv", ACTION_CHECKBOX_NAME: [alice.pk]}
        )

        self.assertEqual(response["Content-Type"], "text/csv; charset=utf-8")
        body = response.content.decode("utf-8-sig")
        self.assertIn("alice", body)
        self.assertIn(";", body.splitlines()[0], "разделитель для русского Excel")

    def test_students_move_to_another_squad(self):
        alice, bob = self.student("alice"), self.student("bob")
        other = Squad.objects.create(code="itp", name="2ИТП", course=2)

        self.client.post(
            self.users_url,
            {"action": "move_to_squad", ACTION_CHECKBOX_NAME: [alice.pk, bob.pk], "apply": "1", "squad": other.pk},
        )

        self.assertEqual(User.objects.filter(squad=other).count(), 2)

    def test_badge_is_awarded_to_a_group_once(self):
        from apps.badges.models import UserBadge

        alice, bob = self.student("alice"), self.student("bob")
        badge = Badge.objects.create(code="intern", title="Стажировка", condition={"manual": True})
        data = {"action": "award_badge", ACTION_CHECKBOX_NAME: [alice.pk, bob.pk], "apply": "1", "badge": badge.pk}

        self.client.post(self.users_url, data)
        self.client.post(self.users_url, data)

        self.assertEqual(UserBadge.objects.filter(badge=badge).count(), 2, "повтор ничего не дублирует")
        self.assertTrue(UserBadge.objects.get(user=alice).source.startswith("manual:boss"))

    def test_quest_deadline_is_extended(self):
        from datetime import timedelta

        from django.utils import timezone

        end = timezone.now() + timedelta(days=2)
        quest = Quest.objects.create(code="q", title="Квест", quest_type=QuestType.LONG, end_at=end)

        self.client.post(
            reverse("admin:quests_quest_changelist"),
            {"action": "extend_deadline", ACTION_CHECKBOX_NAME: [quest.pk], "apply": "1", "days": "5"},
        )

        quest.refresh_from_db()
        self.assertEqual(quest.end_at.date(), (end + timedelta(days=5)).date())

    def test_templates_spawn_todays_quests_now(self):
        tpl = QuestTemplate.objects.create(
            code="daily-x", title="Ежедневный", quest_type=QuestType.DAILY, verifier=QuestVerifierKind.MANUAL
        )

        self.client.post(
            reverse("admin:quests_questtemplate_changelist"),
            {"action": "spawn_today", ACTION_CHECKBOX_NAME: [tpl.pk]},
        )

        self.assertTrue(Quest.objects.filter(code__startswith="daily-x").exists())
