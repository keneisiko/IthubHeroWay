"""Тесты привязки Telegram.

Активация подтверждается паролем от колледжа, поэтому проверяем не только
happy path, но и защиту от перебора и от захвата чужого аккаунта.
"""

from django.contrib.auth import get_user_model
from django.core.cache import cache
from django.test import TestCase

from apps.integrations.models import TelegramAccountLink
from apps.integrations.services.telegram_activation import (
    MAX_ATTEMPTS_PER_TELEGRAM_USER,
    activate_telegram_account,
    attempts_exceeded,
    reset_attempts,
)

User = get_user_model()


class ActivationTests(TestCase):
    def setUp(self):
        cache.clear()
        self.user = User.objects.create_user(
            username="student",
            email="Student@nalchik.ithub.ru",
            password="x",
            callsign="student_call",
        )

    def test_activation_links_account(self):
        ok, message = activate_telegram_account(
            email="student@nalchik.ithub.ru",
            telegram_user_id=777,
            telegram_chat_id=777,
            telegram_username="stud",
        )

        self.assertTrue(ok)
        self.assertIn("student", message)
        link = TelegramAccountLink.objects.get(user=self.user)
        self.assertEqual(link.telegram_user_id, 777)
        self.assertTrue(link.is_active)

    def test_unknown_email_is_rejected(self):
        ok, _ = activate_telegram_account(
            email="nobody@nalchik.ithub.ru",
            telegram_user_id=778,
            telegram_chat_id=778,
            telegram_username="",
        )
        self.assertFalse(ok)
        self.assertFalse(TelegramAccountLink.objects.exists())

    def test_telegram_account_cannot_be_linked_to_second_student(self):
        """Уникальность telegram_user_id раньше приводила к IntegrityError
        вместо понятного ответа."""
        other = User.objects.create_user(
            username="other", email="other@nalchik.ithub.ru", password="x", callsign="other_call"
        )
        TelegramAccountLink.objects.create(
            user=other, telegram_user_id=999, telegram_chat_id=999, is_active=True
        )

        ok, message = activate_telegram_account(
            email="student@nalchik.ithub.ru",
            telegram_user_id=999,
            telegram_chat_id=999,
            telegram_username="",
        )

        self.assertFalse(ok)
        self.assertIn("уже привязан", message)
        self.assertFalse(TelegramAccountLink.objects.filter(user=self.user).exists())

    def test_reactivation_of_same_pair_is_allowed(self):
        activate_telegram_account(
            email="student@nalchik.ithub.ru",
            telegram_user_id=777,
            telegram_chat_id=777,
            telegram_username="stud",
        )
        ok, _ = activate_telegram_account(
            email="student@nalchik.ithub.ru",
            telegram_user_id=777,
            telegram_chat_id=778,
            telegram_username="stud2",
        )
        self.assertTrue(ok)
        self.assertEqual(TelegramAccountLink.objects.count(), 1)


class ActivationThrottleTests(TestCase):
    def setUp(self):
        cache.clear()

    def test_attempts_are_limited_per_telegram_user(self):
        """Бот принимает пароль от колледжа — перебор через него недопустим."""
        email_pattern = "victim{}@nalchik.ithub.ru"
        exceeded_at = None
        for i in range(MAX_ATTEMPTS_PER_TELEGRAM_USER + 2):
            if attempts_exceeded(telegram_user_id=555, email=email_pattern.format(i)):
                exceeded_at = i
                break
        self.assertIsNotNone(exceeded_at)
        self.assertLessEqual(exceeded_at, MAX_ATTEMPTS_PER_TELEGRAM_USER)

    def test_attempts_are_limited_per_email_across_accounts(self):
        """Распределённый перебор одной жертвы с разных Telegram-аккаунтов."""
        exceeded = False
        for tg_id in range(1000, 1010):
            if attempts_exceeded(telegram_user_id=tg_id, email="victim@nalchik.ithub.ru"):
                exceeded = True
                break
        self.assertTrue(exceeded)

    def test_successful_activation_resets_counters(self):
        attempts_exceeded(telegram_user_id=42, email="a@nalchik.ithub.ru")
        attempts_exceeded(telegram_user_id=42, email="a@nalchik.ithub.ru")
        reset_attempts(telegram_user_id=42, email="a@nalchik.ithub.ru")

        self.assertFalse(attempts_exceeded(telegram_user_id=42, email="a@nalchik.ithub.ru"))
