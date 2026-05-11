import os

import telebot
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from apps.integrations.models import TelegramAccountLink
from apps.integrations.services.lxp_auth import verify_lxp_credentials
from apps.integrations.services.telegram_activation import activate_telegram_account
from apps.quests.models import Quest, UserQuestProgress


BOT_STATES: dict[int, dict] = {}


class Command(BaseCommand):
    help = "Runs Telegram bot for account activation and daily quests."

    def handle(self, *args, **options):
        token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
        if not token:
            raise CommandError("TELEGRAM_BOT_TOKEN is not set.")

        bot = telebot.TeleBot(token)

        @bot.message_handler(commands=["start", "help"])
        def start(message):
            bot.reply_to(
                message,
                "Привет! Команды:\n"
                "/activate - активировать аккаунт по email+паролю LXP\n"
                "/daily_quests - показать ежедневные квесты\n"
                "/profile - показать привязанный профиль",
            )

        @bot.message_handler(commands=["activate"])
        def activate(message):
            BOT_STATES[message.chat.id] = {"step": "await_email"}
            bot.reply_to(message, "Введи учебную почту (LXP email):")

        @bot.message_handler(commands=["profile"])
        def profile(message):
            link = TelegramAccountLink.objects.filter(
                telegram_user_id=message.from_user.id,
                is_active=True,
            ).select_related("user").first()
            if not link:
                bot.reply_to(message, "Аккаунт не привязан. Используй /activate.")
                return
            user = link.user
            bot.reply_to(
                message,
                f"Профиль:\nusername: {user.username}\nпозывной: {user.callsign}\n"
                f"рейтинг: {user.rating_current}\nмонеты: {user.coins_balance}",
            )

        @bot.message_handler(commands=["daily_quests"])
        def daily_quests(message):
            link = TelegramAccountLink.objects.filter(
                telegram_user_id=message.from_user.id,
                is_active=True,
            ).select_related("user").first()
            if not link:
                bot.reply_to(message, "Сначала активируй аккаунт через /activate.")
                return

            now = timezone.now()
            quests = Quest.objects.filter(
                is_active=True,
                quest_type="daily",
            ).filter(
                start_at__isnull=True
            ) | Quest.objects.filter(
                is_active=True,
                quest_type="daily",
                start_at__lte=now,
            )
            quests = quests.order_by("id")[:10]
            if not quests:
                bot.reply_to(message, "Сегодня нет активных ежедневных квестов.")
                return

            lines = ["Ежедневные квесты:"]
            for quest in quests:
                progress = UserQuestProgress.objects.filter(user=link.user, quest=quest).first()
                progress_value = progress.progress_value if progress else 0
                completed = "да" if progress and progress.is_completed else "нет"
                lines.append(
                    f"- {quest.code}: {quest.title} | прогресс: {progress_value} | выполнен: {completed}"
                )
            bot.reply_to(message, "\n".join(lines))

        @bot.message_handler(func=lambda m: True)
        def message_router(message):
            state = BOT_STATES.get(message.chat.id)
            if not state:
                return

            if state["step"] == "await_email":
                state["email"] = message.text.strip()
                state["step"] = "await_password"
                bot.reply_to(message, "Теперь введи пароль от LXP:")
                return

            if state["step"] == "await_password":
                email = state.get("email", "").strip()
                password = message.text.strip()
                ok, reason = verify_lxp_credentials(email, password)
                if not ok:
                    bot.reply_to(message, f"Активация не удалась: {reason}")
                    BOT_STATES.pop(message.chat.id, None)
                    return

                activated, msg = activate_telegram_account(
                    email=email,
                    telegram_user_id=message.from_user.id,
                    telegram_chat_id=message.chat.id,
                    telegram_username=message.from_user.username or "",
                )
                bot.reply_to(message, msg if activated else "Не удалось активировать аккаунт.")
                BOT_STATES.pop(message.chat.id, None)

        self.stdout.write(self.style.SUCCESS("Telegram bot started (polling mode)."))
        bot.infinity_polling(skip_pending=True)

