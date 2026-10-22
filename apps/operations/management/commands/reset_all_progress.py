"""Полное обнуление данных студентов перед запуском платформы.

Остаётся база пользователей (логины, ФИО, отряд, трек, позывной, аватар,
идентификаторы LXP/Hik), а всё накопленное студентами — рейтинг, монеты,
журналы, квесты, нашивки, покупки, характеристики, соцсвязи, активация —
сбрасывается. Каталоги (нашивки, квесты, магазин), расписание, настройки
и сырые данные интеграций не трогаются. Сотрудники не затрагиваются.

По умолчанию — пробный прогон в откатываемой транзакции.
"""

from __future__ import annotations

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction
from django.db.models import Q

from apps.accounts.models import PolicyAcceptance, Role, User
from apps.badges.models import UserBadge
from apps.integrations.models import TelegramAccountLink
from apps.operations.models import PlatformSettings
from apps.operations.services.cache import delete_pattern, invalidate_leaderboards
from apps.progress.models import (
    Characteristic,
    CharacteristicHistory,
    LXPTopicState,
    PolozhenieAward,
    RatingLog,
    StudentRoleAssignment,
    UserStrike,
)
from apps.quests.models import (
    QuestRewardTransaction,
    SelfReportProof,
    SquadLeaderboardSnapshot,
    UserQuestProgress,
    WeeklyFocus,
)
from apps.shop.models import Purchase
from apps.social.models import Duel, Mentorship, Respect

CONFIRM_WORD = "RESET"
IMPORTED_STATUS = "imported_lxp"


def _default(name: str):
    return User._meta.get_field(name).default


def _both(ids, first: str, second: str) -> Q:
    """Пары «студент–студент»: связи со второй стороной-сотрудником не трогаем."""
    return Q(**{f"{first}__in": ids}) & Q(**{f"{second}__in": ids})


def _accruals_enabled() -> bool:
    row = PlatformSettings.objects.filter(pk=PlatformSettings.SINGLETON_PK).first()
    return bool(getattr(row, "accruals_enabled", False))


class Command(BaseCommand):
    help = "Обнулить все данные студентов (role=agent), оставив базу пользователей"

    def add_arguments(self, parser):
        parser.add_argument("--apply", action="store_true", help="Выполнить (без флага — пробный прогон)")
        parser.add_argument("--confirm", default="", help=f"Подтверждение: {CONFIRM_WORD} (обязательно с --apply)")
        parser.add_argument(
            "--keep-badge",
            action="append",
            default=[],
            metavar="CODE",
            help="Код нашивки, которую не снимать (можно повторять), например developer",
        )

        parser.add_argument(
            "--keep-roles", action="store_true", help="Не удалять роли студентов (StudentRoleAssignment)"
        )
        parser.add_argument(
            "--expect-students", type=int, default=None, help="Ожидаемое число студентов (обязательно с --apply)"
        )

    def handle(self, *args, **options):
        apply = options["apply"]
        if apply:
            self._check_apply(options)
        keep_badges = [c.strip() for c in options["keep_badge"] if c.strip()]

        with transaction.atomic():
            self._reset(keep_badges, options["keep_roles"])
            if not apply:
                transaction.set_rollback(True)

        if apply:
            # Не cache.clear(): Redis общий с брокером Celery, токеном LXP и сессиями.
            delete_pattern("profile:*")
            invalidate_leaderboards()
            self.stdout.write(
                self.style.SUCCESS("Готово: данные студентов обнулены, кэш профилей и рейтингов сброшен.")
            )
        else:
            self.stdout.write(
                self.style.WARNING("Пробный прогон: ничего не изменено (для запуска: --apply --confirm RESET)")
            )

    def _check_apply(self, options) -> None:
        if options["confirm"] != CONFIRM_WORD:
            raise CommandError(f"Для --apply нужно --confirm {CONFIRM_WORD}")
        if _accruals_enabled():
            raise CommandError("Сначала остановите начисления в админке (Настройки платформы)")
        expected = options["expect_students"]
        if expected is None:
            raise CommandError("Для --apply нужно --expect-students N (число студентов)")
        actual = User.objects.filter(role=Role.AGENT).count()
        if actual != expected:
            raise CommandError(f"Студентов {actual}, ожидалось {expected}: запуск отменён")
        self.stdout.write(self.style.WARNING("Убедитесь, что сделан pg_dump: откатить обнуление нельзя."))

    def _reset(self, keep_badges: list[str], keep_roles: bool) -> None:
        students = User.objects.filter(role=Role.AGENT)
        ids = students.values("pk")
        self.stdout.write(f"Студентов (role=agent): {students.count()}")

        badges = UserBadge.objects.filter(user__in=ids).exclude(badge__code__in=keep_badges)
        steps = [
            ("Нашивки студентов (UserBadge)", badges),
            ("Награды за квесты (QuestRewardTransaction)", QuestRewardTransaction.objects.filter(user__in=ids)),
            ("Самоотчёты (SelfReportProof)", SelfReportProof.objects.filter(user__in=ids)),
            ("Прогресс квестов (UserQuestProgress)", UserQuestProgress.objects.filter(user__in=ids)),
            ("Цели недели (WeeklyFocus)", WeeklyFocus.objects.filter(user__in=ids)),
            ("Журнал рейтинга (RatingLog)", RatingLog.objects.filter(user__in=ids)),
            ("Разовые начисления (PolozhenieAward)", PolozhenieAward.objects.filter(user__in=ids)),
            ("Серии (UserStrike)", UserStrike.objects.filter(user__in=ids)),
            ("Состояние тем LXP (LXPTopicState)", LXPTopicState.objects.filter(user__in=ids)),
            ("История характеристик (CharacteristicHistory)", CharacteristicHistory.objects.filter(characteristic__user__in=ids)),
            ("Характеристики (Characteristic)", Characteristic.objects.filter(user__in=ids)),
            ("Покупки (Purchase)", Purchase.objects.filter(user__in=ids)),
            ("Респекты (Respect)", Respect.objects.filter(_both(ids, "from_user", "to_user"))),
            ("Дуэли (Duel)", Duel.objects.filter(_both(ids, "challenger", "opponent"))),
            ("Наставничества (Mentorship)", Mentorship.objects.filter(_both(ids, "mentor", "mentee"))),
            ("Снимки рейтинга отрядов (SquadLeaderboardSnapshot)", SquadLeaderboardSnapshot.objects.all()),
            ("Привязки Telegram (TelegramAccountLink)", TelegramAccountLink.objects.filter(user__in=ids)),
            ("Принятия Положения (PolicyAcceptance)", PolicyAcceptance.objects.filter(user__in=ids)),
        ]
        if not keep_roles:
            steps.append(
                ("Роли студентов (StudentRoleAssignment)", StudentRoleAssignment.objects.filter(user__in=ids))
            )
        for label, queryset in steps:
            self.stdout.write(f"  {label}: удалится {queryset.count()}")
            queryset.delete()

        values = {
            "rating_current": _default("rating_current"),
            "coins_balance": _default("coins_balance"),
            "level": _default("level"),
            "unclosed_ct_count": _default("unclosed_ct_count"),
            "is_active": False,
            "status": IMPORTED_STATUS,
            "last_login": None,
        }
        changing = students.exclude(**values).count()
        students.update(**values)
        self.stdout.write(f"  Пользователи (User): изменится {changing}")

        if keep_badges:
            self.stdout.write(f"  Нашивки с кодами оставлены: {', '.join(keep_badges)}")
        nonzero = students.exclude(rating_current=0, coins_balance=0).count()
        active = students.filter(is_active=True).count()
        self.stdout.write(f"Итог: студентов с rating/coins != 0: {nonzero}; активированных: {active}")
