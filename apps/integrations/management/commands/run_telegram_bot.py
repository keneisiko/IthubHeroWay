"""Telegram-бот: активация аккаунта и просмотр квестов.

Активация требует ввода учебной почты и пароля от LXP прямо в чате, поэтому
здесь важнее обычного: диалог ведётся только в личке, сообщение с паролем
удаляется сразу после проверки, попытки ограничены по частоте, а состояние
диалога привязано к конкретному пользователю, а не к чату.
"""

from __future__ import annotations

import logging
import os
import time

import telebot
from django.core.management.base import BaseCommand, CommandError
from django.utils import timezone

from apps.integrations.models import TelegramAccountLink
from apps.integrations.services.lxp_auth import verify_lxp_credentials
from apps.integrations.services.telegram_activation import (
    activate_telegram_account,
    attempts_exceeded,
)
from apps.integrations.services.telegram_alert import send_alert_to_admin
from apps.quests.models import UserQuestProgress
from apps.quests.services.quest_periods import quests_for_date

logger = logging.getLogger(__name__)

# Состояние диалога держится в памяти процесса. Ключ — Telegram-пользователь,
# а не чат: раньше состояние ключевалось по chat.id, а привязка делалась
# по from_user.id, и в групповом чате следующее сообщение любого участника
# попадало в чужой шаг диалога — аккаунт активировался не на того человека.
BOT_STATES: dict[int, dict] = {}

# Брошенный диалог не должен жить вечно: раньше словарь не чистился вовсе.
STATE_TTL_SECONDS = 600


def _prune_states(now: float | None = None) -> None:
    now = now or time.monotonic()
    expired = [key for key, state in BOT_STATES.items() if now - state["created_at"] > STATE_TTL_SECONDS]
    for key in expired:
        BOT_STATES.pop(key, None)


def _is_private(message) -> bool:
    return getattr(message.chat, "type", "private") == "private"


class Command(BaseCommand):
    help = "Runs Telegram bot for account activation and daily quests."

    def handle(self, *args, **options):
        token = os.getenv("TELEGRAM_BOT_TOKEN", "").strip()
        if not token:
            raise CommandError("TELEGRAM_BOT_TOKEN is not set.")

        bot = telebot.TeleBot(token)

        def delete_message_safely(message) -> bool:
            """Удалить сообщение пользователя (пароль не должен оставаться в чате)."""
            try:
                bot.delete_message(message.chat.id, message.message_id)
                return True
            except Exception:
                # В личке у бота обычно есть право удалять свои и чужие сообщения,
                # но полагаться на это нельзя — предупредим пользователя.
                logger.info("Не удалось удалить сообщение с учётными данными")
                return False

        def linked_user(message):
            return (
                TelegramAccountLink.objects.filter(
                    telegram_user_id=message.from_user.id,
                    is_active=True,
                )
                .select_related("user")
                .first()
            )

        @bot.message_handler(commands=["start", "help"])
        def start(message):
            bot.reply_to(
                message,
                "Привет! Команды:\n"
                "/activate — привязать аккаунт (учебная почта и пароль от LXP)\n"
                "/daily_quests — показать ежедневные квесты\n"
                "/profile — показать привязанный профиль\n"
                "/cancel — прервать активацию",
            )

        @bot.message_handler(commands=["cancel"])
        def cancel(message):
            BOT_STATES.pop(message.from_user.id, None)
            bot.reply_to(message, "Активация прервана.")

        @bot.message_handler(commands=["activate"])
        def activate(message):
            _prune_states()
            if not _is_private(message):
                # В группе следующее сообщение может прислать кто угодно,
                # а пароль от колледжа увидят все участники.
                bot.reply_to(
                    message,
                    "Активация возможна только в личном чате с ботом: "
                    "в группе пароль увидят все участники.",
                )
                return

            BOT_STATES[message.from_user.id] = {
                "step": "await_email",
                "created_at": time.monotonic(),
            }
            bot.reply_to(
                message,
                "Введи учебную почту (LXP email).\n"
                "Следующим сообщением попрошу пароль — я удалю его из чата сразу после проверки.",
            )

        @bot.message_handler(commands=["profile"])
        def profile(message):
            link = linked_user(message)
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
            link = linked_user(message)
            if not link:
                bot.reply_to(message, "Сначала активируй аккаунт через /activate.")
                return

            # Ежедневные квесты живут экземплярами на дату: без выборки по
            # сегодняшнему периоду бот показывал бы и все вчерашние.
            quests = list(quests_for_date(timezone.localdate(), ["daily"])[:10])
            if not quests:
                bot.reply_to(message, "Сегодня нет активных ежедневных квестов.")
                return

            # Один запрос вместо запроса на каждый квест.
            progress_by_quest = {
                p.quest_id: p
                for p in UserQuestProgress.objects.filter(user=link.user, quest__in=quests)
            }

            lines = ["Ежедневные квесты:"]
            for quest in quests:
                progress = progress_by_quest.get(quest.id)
                progress_value = progress.progress_value if progress else 0
                completed = "да" if progress and progress.is_completed else "нет"
                lines.append(
                    f"- {quest.code}: {quest.title} | прогресс: {progress_value} | выполнен: {completed}"
                )
            bot.reply_to(message, "\n".join(lines))

        @bot.message_handler(func=lambda m: True)
        def message_router(message):
            _prune_states()
            state = BOT_STATES.get(message.from_user.id)
            if not state or not _is_private(message):
                return

            if state["step"] == "await_email":
                state["email"] = (message.text or "").strip()
                state["step"] = "await_password"
                bot.reply_to(message, "Теперь введи пароль от LXP:")
                return

            if state["step"] == "await_password":
                email = state.get("email", "").strip()
                password = (message.text or "").strip()

                # Пароль убираем из чата до любых сетевых вызовов: проверка
                # в LXP может занять секунды, и всё это время он висит в истории.
                deleted = delete_message_safely(message)
                BOT_STATES.pop(message.from_user.id, None)

                if attempts_exceeded(telegram_user_id=message.from_user.id, email=email):
                    bot.send_message(
                        message.chat.id,
                        "Слишком много попыток активации. Попробуй через час "
                        "или обратись к куратору.",
                    )
                    return

                ok, reason = verify_lxp_credentials(email, password)
                if not ok:
                    bot.send_message(message.chat.id, f"Активация не удалась: {reason}")
                    return

                activated, msg = activate_telegram_account(
                    email=email,
                    telegram_user_id=message.from_user.id,
                    telegram_chat_id=message.chat.id,
                    telegram_username=message.from_user.username or "",
                )
                text = msg if activated else "Не удалось активировать аккаунт."
                if activated and not deleted:
                    text += "\n\nУдали, пожалуйста, сообщение с паролем вручную — мне не хватило прав."
                bot.send_message(message.chat.id, text)

        self.stdout.write(self.style.SUCCESS("Telegram bot started (polling mode)."))
        try:
            bot.infinity_polling(skip_pending=True)
        except Exception as exc:
            # Падение бота раньше проходило незамеченным: health-monitor его
            # не проверяет, а логи контейнера никто не читает.
            logger.exception("Telegram bot polling failed")
            send_alert_to_admin(
                title="Telegram-бот остановлен",
                message=f"Опрос Telegram прерван: {type(exc).__name__}: {exc}",
                error_type="critical",
                deduplicate_key="telegram_bot_down",
                is_critical=True,
            )
            raise
