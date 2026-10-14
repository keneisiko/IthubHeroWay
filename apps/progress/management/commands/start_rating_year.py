"""Старт нового сезона: все начинают с одинакового значения.

Пункты 2.3 и 2.5 Положения: сезон начинается 1 сентября, при его завершении
рейтинг обнуляется, а неиспользованные монеты сгорают и не переносятся.
Итоги и история завершённого сезона сохраняются: журнал `RatingLog` остаётся,
и по нему видно вклад каждого года.

Монеты обнуляются вместе с рейтингом — прежде команда их не трогала, и
баланс переходил в новый сезон, чего Положение прямо не допускает.
"""

from __future__ import annotations

from decimal import Decimal

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from apps.accounts.models import Role, User
from apps.progress.models import LXPTopicState, RatingChangeSource, RatingLog
from apps.progress.services.academic_year import academic_year_label


class Command(BaseCommand):
    help = (
        "Сбрасывает рейтинг и монеты агентов на стартовые значения нового "
        "сезона и фиксирует итог прошлого в журнале (п. 2.5 Положения)."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Показать, что будет сделано, ничего не меняя.",
        )
        parser.add_argument(
            "--keep-topic-state",
            action="store_true",
            help=(
                "Не сбрасывать состояние тем LXP. По умолчанию оно очищается: "
                "программа нового года другая, и старые темы не должны "
                "считаться просроченными."
            ),
        )

    def handle(self, *args, **options):
        limits = getattr(settings, "RATING_LIMITS", {})
        start_value = Decimal(str(limits.get("DEFAULT_RATING_START", 0)))
        today = timezone.localdate()
        year = academic_year_label(today)

        agents = User.objects.filter(role=Role.AGENT)
        total = agents.count()

        if options["dry_run"]:
            self.stdout.write(
                self.style.NOTICE(
                    f"Затронуло бы {total} агентов: рейтинг → {start_value}, "
                    f"монеты → 0, год {year} (--dry-run)."
                )
            )
            return

        reset = 0
        with transaction.atomic():
            for user in agents.iterator(chunk_size=200):
                before = Decimal(str(user.rating_current))
                coins_before = Decimal(str(user.coins_balance))
                if before == start_value and coins_before == 0 and user.unclosed_ct_count == 0:
                    continue
                user.rating_current = start_value
                user.coins_balance = Decimal("0")
                user.unclosed_ct_count = 0
                user.save(update_fields=["rating_current", "coins_balance", "unclosed_ct_count"])
                RatingLog.objects.create(
                    user=user,
                    value_before=before,
                    value_after=start_value,
                    delta=start_value - before,
                    coins_delta=-coins_before,
                    source=RatingChangeSource.SYSTEM,
                    source_id=f"year_start:{year}",
                    reason=(
                        f"Старт сезона {year}: итог прошлого — рейтинг {before}, "
                        f"монет сгорело {coins_before}"
                    ),
                )
                reset += 1

            if not options["keep_topic_state"]:
                LXPTopicState.objects.all().delete()

        self.stdout.write(
            self.style.SUCCESS(
                f"Сезон {year}: рейтинг и монеты сброшены у {reset} из {total} агентов "
                f"(стартовый рейтинг {start_value}, монеты 0)."
            )
        )
