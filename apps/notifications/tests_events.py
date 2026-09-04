"""Уведомления студентам.

Механики работали, но человек о них не узнавал: вызвали на дуэль — тишина,
куратор отклонил подтверждение — тишина, заявка на проверку лежала в админке,
пока кто-нибудь случайно не заглядывал.
"""

from __future__ import annotations

from datetime import timedelta
from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase, override_settings
from django.utils import timezone

from apps.accounts.models import Role, Squad
from apps.integrations.models import TelegramAccountLink
from apps.notifications.services import events
from apps.notifications.services.telegram import notify_user
from apps.quests.models import Quest, QuestType, SelfReportProof, SelfReportProofStatus, UserQuestProgress
from apps.social.models import Duel, DuelStatus, Mentorship, Respect

User = get_user_model()


def make_user(username: str, *, role: str = Role.AGENT, squad=None, linked: bool = True) -> User:
    user = User.objects.create_user(
        username=username,
        email=f"{username}@test.ru",
        password="x",
        callsign=f"Позывной-{username}",
        role=role,
        squad=squad,
    )
    if linked:
        TelegramAccountLink.objects.create(
            user=user,
            telegram_user_id=900_000 + user.pk,
            telegram_chat_id=900_000 + user.pk,
            is_active=True,
        )
    return user


@override_settings(TELEGRAM_NOTIFICATIONS_ENABLED=True, TELEGRAM_BOT_TOKEN="test-token")
class NotifyUserTests(TestCase):
    def setUp(self):
        self.user = make_user("receiver")

    @patch("apps.notifications.services.telegram.send_message", return_value=(True, "ok"))
    def test_message_goes_to_linked_chat(self, send):
        result = notify_user(self.user, "Привет")

        self.assertTrue(result)
        chat_id, text = send.call_args.args
        self.assertEqual(chat_id, 900_000 + self.user.pk)
        self.assertEqual(text, "Привет")

    @patch("apps.notifications.services.telegram.send_message")
    def test_user_without_link_is_skipped(self, send):
        stranger = make_user("no_link", linked=False)

        self.assertFalse(notify_user(stranger, "Привет"))
        send.assert_not_called()

    @patch("apps.notifications.services.telegram.send_message")
    @override_settings(TELEGRAM_NOTIFICATIONS_ENABLED=False)
    def test_switch_turns_notifications_off(self, send):
        self.assertFalse(notify_user(self.user, "Привет"))
        send.assert_not_called()

    @patch("apps.notifications.services.telegram.send_message", side_effect=RuntimeError("boom"))
    def test_delivery_failure_does_not_break_the_caller(self, _send):
        """Уведомление — побочный эффект: падение Telegram не должно ронять действие."""
        duel = Duel.objects.create(
            challenger=make_user("ch"), opponent=self.user, status=DuelStatus.PENDING
        )

        self.assertEqual(events.duel_invited(duel), 0)


@override_settings(TELEGRAM_NOTIFICATIONS_ENABLED=True, TELEGRAM_BOT_TOKEN="test-token")
@patch("apps.notifications.services.telegram.send_message", return_value=(True, "ok"))
class EventTextTests(TestCase):
    def setUp(self):
        self.squad = Squad.objects.create(code="sq", name="Отряд", course=1)
        self.student = make_user("student", squad=self.squad)
        self.rival = make_user("rival", squad=self.squad)
        self.curator = make_user("curator", role=Role.CURATOR, squad=self.squad)

    def _text(self, send) -> str:
        return send.call_args.args[1]

    def test_duel_invite_names_the_challenger(self, send):
        duel = Duel.objects.create(
            challenger=self.rival, opponent=self.student, status=DuelStatus.PENDING, bet_coins=5
        )

        events.duel_invited(duel)

        self.assertIn("Позывной-rival", self._text(send))
        self.assertIn("5 монет", self._text(send))

    def test_duel_accept_tells_the_challenger_the_deadline(self, send):
        duel = Duel.objects.create(
            challenger=self.student,
            opponent=self.rival,
            status=DuelStatus.ACCEPTED,
            resolve_after=timezone.now() + timedelta(days=7),
        )

        events.duel_answered(duel, accepted=True)

        self.assertIn("принял вызов", self._text(send))

    def test_duel_result_reaches_both(self, send):
        duel = Duel.objects.create(
            challenger=self.student,
            opponent=self.rival,
            status=DuelStatus.FINISHED,
            winner=self.student,
            bet_coins=5,
        )

        sent = events.duel_resolved(duel)

        self.assertEqual(sent, 2)

    def test_draw_notifies_both_without_a_winner(self, send):
        duel = Duel.objects.create(
            challenger=self.student, opponent=self.rival, status=DuelStatus.FINISHED
        )

        events.duel_resolved(duel)

        self.assertIn("ничьёй", self._text(send))

    def test_respect_notification_mentions_coins(self, send):
        respect = Respect.objects.create(from_user=self.rival, to_user=self.student)

        events.respect_received(respect, 3)

        self.assertIn("+3 монет", self._text(send))

    def test_mentee_learns_about_the_mentor(self, send):
        mentorship = Mentorship.objects.create(mentor=self.rival, mentee=self.student)

        events.mentorship_started(mentorship)

        chat_id, text = send.call_args.args
        self.assertEqual(chat_id, 900_000 + self.student.pk)
        self.assertIn("наставником", text)

    def test_proof_goes_to_squad_curators(self, send):
        quest = Quest.objects.create(code="q1", title="Хакатон", quest_type=QuestType.LONG)
        progress = UserQuestProgress.objects.create(user=self.student, quest=quest)
        proof = SelfReportProof.objects.create(
            quest=quest, user=self.student, quest_progress=progress, comment="."
        )

        sent = events.proof_submitted(proof)

        chat_id, text = send.call_args.args
        self.assertEqual(sent, 1)
        self.assertEqual(chat_id, 900_000 + self.curator.pk)
        self.assertIn("Хакатон", text)

    def test_curator_of_another_squad_is_not_notified(self, send):
        other_squad = Squad.objects.create(code="sq2", name="Другой", course=2)
        make_user("curator2", role=Role.CURATOR, squad=other_squad)
        quest = Quest.objects.create(code="q2", title="Проект", quest_type=QuestType.LONG)
        progress = UserQuestProgress.objects.create(user=self.student, quest=quest)
        proof = SelfReportProof.objects.create(
            quest=quest, user=self.student, quest_progress=progress, comment="."
        )

        self.assertEqual(events.proof_submitted(proof), 1)

    def test_review_result_reaches_the_student(self, send):
        quest = Quest.objects.create(code="q3", title="Лаба", quest_type=QuestType.SELF_REPORT)
        progress = UserQuestProgress.objects.create(user=self.student, quest=quest)
        proof = SelfReportProof.objects.create(
            quest=quest,
            user=self.student,
            quest_progress=progress,
            comment=".",
            status=SelfReportProofStatus.REJECTED,
        )

        events.proof_reviewed(proof, approved=False)

        chat_id, text = send.call_args.args
        self.assertEqual(chat_id, 900_000 + self.student.pk)
        self.assertIn("отклонено", text)
