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
