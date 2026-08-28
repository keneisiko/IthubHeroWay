"""Тесты на число запросов.

Эти места деградируют молча: логика остаётся верной, а нагрузка растёт
пропорционально числу студентов. Проверка количеством запросов — единственный
способ поймать возврат N+1 при правке кода.
"""

from datetime import date, datetime

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.utils import timezone

from apps.accounts.models import Role
from apps.integrations.models import ExternalEvent, TelegramAccountLink
from apps.quests.models import Quest, QuestTemplate, QuestVerifierKind
from apps.quests.services.quest_conditions import resolve_verifier_config
from apps.quests.services.verifiers import _hik_events_for_user_on_date, verify_hik_no_late

User = get_user_model()


class HikEventLookupQueryTests(TestCase):
    """Раньше выборка «события пользователя за день» перебирала всю таблицу
    в Python — и делала это для каждого пользователя и каждого дня."""

    def setUp(self):
        self.user = User.objects.create_user(
            username="agent", email="a@test.ru", password="x", callsign="agent_call"
        )
        self.other = User.objects.create_user(
            username="other", email="o@test.ru", password="x", callsign="other_call"
        )
        moment = timezone.make_aware(datetime(2026, 6, 15, 9, 5))
        for idx, owner in enumerate([self.user, self.other, self.other]):
            ExternalEvent.objects.create(
                source="hik",
                external_event_id=f"e{idx}",
                payload={
                    "event_type": "access",
                    "user_id": owner.pk,
                    "event_time": moment.isoformat(),
                },
            )

    def test_single_query_per_lookup(self):
        with self.assertNumQueries(1):
            events = _hik_events_for_user_on_date(self.user.pk, date(2026, 6, 15))
        self.assertEqual(len(events), 1)

    def test_other_users_events_are_not_returned(self):
        events = _hik_events_for_user_on_date(self.user.pk, date(2026, 6, 15))
        self.assertTrue(all(e["user_id"] == self.user.pk for e in events))

    def test_range_check_uses_one_query_for_whole_period(self):
        """Проверка «без опозданий за N дней» делала запрос на каждый день."""
        with self.assertNumQueries(1):
            result = verify_hik_no_late(self.user, {"days": 7}, date(2026, 6, 15))
        self.assertTrue(result.completed)


class VerifierConfigTests(TestCase):
    def test_template_config_is_resolved_from_quest_only(self):
        """Конфигурация зависит только от квеста, поэтому в массовом прогоне
        её достаточно вычислить один раз, а не на каждого пользователя."""
        QuestTemplate.objects.create(
            code="daily-hik",
            title="Приходить вовремя",
            verifier=QuestVerifierKind.HIK_ON_TIME,
            verifier_params={"deadline_hour": 9},
        )
        quest = Quest.objects.create(
            code="q-daily-hik",
            title="Приходить вовремя",
            conditions={"template_code": "daily-hik", "auto_verify": True},
        )

        with self.assertNumQueries(1):
            verifier, params = resolve_verifier_config(quest)

        self.assertEqual(verifier, QuestVerifierKind.HIK_ON_TIME)
        self.assertEqual(params["deadline_hour"], 9)


class VerifyAllTemplateLookupTests(TestCase):
    def setUp(self):
        QuestTemplate.objects.create(
            code="tpl-late",
            title="Без опозданий",
            verifier=QuestVerifierKind.LATE_STREAK,
            verifier_params={"min_days": 3},
        )
        Quest.objects.create(
            code="q-late",
            title="Без опозданий",
            quest_type="daily",
            conditions={"template_code": "tpl-late", "auto_verify": True},
        )
        for i in range(4):
            user = User.objects.create_user(
                username=f"scal{i}",
                email=f"scal{i}@test.ru",
                password="x",
                callsign=f"scal_call_{i}",
                role=Role.AGENT,
            )
            TelegramAccountLink.objects.create(
                user=user,
                telegram_user_id=8_000_000 + user.pk,
                telegram_chat_id=8_000_000 + user.pk,
                is_active=True,
            )

    def test_quest_template_is_queried_once_regardless_of_user_count(self):
        """Конфигурация верификатора зависит только от квеста, но запрашивалась
        внутри цикла по пользователям — чистый N+1 по числу студентов."""
        from django.db import connection
        from django.test.utils import CaptureQueriesContext

        from apps.quests.services.quest_verification import verify_all_auto_quests

        with CaptureQueriesContext(connection) as ctx:
            stats = verify_all_auto_quests(date(2026, 6, 15), quest_types=["daily"])

        self.assertEqual(stats["users"], 4)
        template_queries = [q for q in ctx.captured_queries if "quests_questtemplate" in q["sql"]]
        # Один запрос — создание экземпляров квестов на период, второй —
        # разбор конфигурации верификатора. Оба не зависят от числа студентов.
        self.assertLessEqual(
            len(template_queries),
            2,
            f"шаблон квеста запрошен {len(template_queries)} раз при 4 пользователях",
        )
