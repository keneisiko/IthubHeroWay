"""Старт нового учебного года: все начинают с одинакового значения.

Рейтинг копится за год, поэтому его нужно обнулять на границе года — иначе
четверокурсник соревнуется с первокурсником, имея фору за три прошлых года.
Накопленное не пропадает: журнал `RatingLog` остаётся, и по нему видно вклад
каждого года.
"""

from __future__ import annotations

from django.conf import settings
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from apps.accounts.models import Role, User
from apps.progress.models import LXPTopicState, RatingChangeSource, RatingLog
from apps.progress.services.academic_year import academic_year_label


class Command(BaseCommand):
    help = (
        "Сбрасывает рейтинг агентов на стартовое значение нового учебного года "
        "и фиксирует итог прошлого года в журнале."
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
        start_value = int(limits.get("DEFAULT_RATING_START", 300))
        today = timezone.localdate()
        year = academic_year_label(today)

        agents = User.objects.filter(role=Role.AGENT)
        total = agents.count()

        if options["dry_run"]:
            self.stdout.write(
                self.style.NOTICE(
                    f"Затронуло бы {total} агентов: рейтинг → {start_value}, год {year} (--dry-run)."
                )
            )
            return

        reset = 0
        with transaction.atomic():
            for user in agents.iterator(chunk_size=200):
                before = int(user.rating_current)
                if before == start_value and user.unclosed_ct_count == 0:
                    continue
                user.rating_current = start_value
                user.unclosed_ct_count = 0
                user.save(update_fields=["rating_current", "unclosed_ct_count"])
                RatingLog.objects.create(
                    user=user,
                    value_before=before,
                    value_after=start_value,
                    delta=start_value - before,
                    source=RatingChangeSource.SYSTEM,
                    source_id=f"year_start:{year}",
                    reason=f"Старт учебного года {year}: итог прошлого года — {before}",
                )
                reset += 1

            if not options["keep_topic_state"]:
                LXPTopicState.objects.all().delete()

        self.stdout.write(
            self.style.SUCCESS(
                f"Учебный год {year}: рейтинг сброшен у {reset} из {total} агентов "
                f"(стартовое значение {start_value})."
            )
        )
