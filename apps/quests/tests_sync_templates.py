from __future__ import annotations

from io import StringIO

from django.core.management import call_command
from django.core.management.base import CommandError
from django.test import TestCase

from apps.quests.models import Quest, QuestTemplate


class SyncQuestTemplatesTests(TestCase):
    def test_rerun_keeps_manual_edits(self):
        """Повторный прогон не должен откатывать правки, сделанные в админке."""
        call_command("sync_quest_templates", stdout=StringIO())

        quest = Quest.objects.get(code="daily-hik-on-time")
        Quest.objects.filter(pk=quest.pk).update(
            title="Свой заголовок", reward_coins=99, is_active=False
        )
        QuestTemplate.objects.filter(code=quest.code).update(title="Свой шаблон")

        call_command("sync_quest_templates", stdout=StringIO())

        quest.refresh_from_db()
        self.assertEqual(quest.title, "Свой заголовок")
        self.assertEqual(quest.reward_coins, 99)
        self.assertFalse(quest.is_active)
        self.assertEqual(QuestTemplate.objects.get(code=quest.code).title, "Свой шаблон")

    def test_update_existing_flag_restores_defaults(self):
        call_command("sync_quest_templates", stdout=StringIO())
        Quest.objects.filter(code="daily-hik-on-time").update(title="Свой заголовок", reward_coins=99)

        call_command("sync_quest_templates", "--update-existing", stdout=StringIO())

        quest = Quest.objects.get(code="daily-hik-on-time")
        self.assertEqual(quest.title, "Утренний чек-ин")
        self.assertEqual(quest.reward_coins, 5)

    def test_rerun_does_not_duplicate_quests(self):
        call_command("sync_quest_templates", stdout=StringIO())
        count = Quest.objects.count()
        call_command("sync_quest_templates", stdout=StringIO())
        self.assertEqual(Quest.objects.count(), count)


class VerifyQuestsDateTests(TestCase):
    def test_invalid_date_raises_command_error(self):
        with self.assertRaises(CommandError):
            call_command("verify_quests", "--date=31-12-2025", stdout=StringIO())

    def test_valid_date_accepted(self):
        call_command("verify_quests", "--date=2025-01-15", stdout=StringIO())
