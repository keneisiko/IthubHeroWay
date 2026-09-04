"""Наполнение базы данными «как в жизни» — для проверки интерфейса.

`seed_demo_data` заводит каталоги: треки, отряды, товары, шаблоны квестов.
Но у студента после него пустая история, нулевой прогресс по всем квестам
и одинаковые карточки — проверить на глаз, как выглядят шкала прогресса,
цвета сегментов и счётчик «осталось N дней», по такой базе нельзя.

Эта команда добавляет к каталогам живое состояние одного студента и его
отряда: квесты с разными сроками и разной готовностью, историю наград
и рейтинга за месяц, значки, покупки, характеристики и серии.

Значения подобраны так, чтобы каждая ветка интерфейса была видна хотя бы раз:
шкала прогресса красная, оранжевая, жёлтая и зелёная; срок «сегодня»,
«через несколько дней» и «без срока»; и выполненные, и активные квесты.
"""

from __future__ import annotations

import random
from datetime import timedelta

from django.contrib.auth import get_user_model
from django.core.management.base import BaseCommand
from django.db import transaction
from django.utils import timezone

from apps.accounts.models import Role, Squad, Track
from apps.badges.models import Badge, UserBadge
from apps.integrations.models import ExternalEvent, TelegramAccountLink
from apps.operations.services.environment import ensure_not_production
from apps.progress.models import (
    Characteristic,
    CharacteristicHistory,
    RatingChangeSource,
    RatingLog,
    UserStrike,
)
from apps.progress.services.pillar_labels import UI_PILLARS
from apps.quests.models import (
    Quest,
    QuestRewardTransaction,
    QuestType,
    SelfReportProof,
    SelfReportProofStatus,
    UserQuestProgress,
)
from apps.quests.services.quest_periods import ensure_period_quests
from apps.schedule.models import Schedule
from apps.shop.models import Purchase, ShopItem
from apps.shop.services import apply_purchase

User = get_user_model()

SHOWCASE_TELEGRAM_BASE = 5_200_000_000

# Прогресс подобран по порогам цветов шкалы (Quests.tsx: <30 красный,
# 30–49 оранжевый, 50–79 жёлтый, ≥80 зелёный).
PROGRESS_BY_COLOR = (0.15, 0.35, 0.62, 0.88)

# Долгие квесты с реальными сроками: интерфейс показывает «осталось N дней».
LONG_QUESTS = (
    {
        "code": "showcase-hackathon",
        "title": "Хакатон направления",
        "description": "Собери команду и доведи прототип до защиты.",
        "days_left": 1,
        "progress": 0.9,
        "reward_coins": 40,
        "reward_rating_delta": 25,
    },
    {
        "code": "showcase-course-project",
        "title": "Курсовой проект",
        "description": "Сдай курсовой проект научному руководителю.",
        "days_left": 5,
        "progress": 0.45,
        "reward_coins": 60,
        "reward_rating_delta": 35,
    },
    {
        "code": "showcase-open-day",
        "title": "День открытых дверей",
        "description": "Проведи экскурсию для абитуриентов.",
        "days_left": 14,
        "progress": 0.2,
        "reward_coins": 30,
        "reward_rating_delta": 20,
    },
)

RATING_EVENTS = (
    (-3, "Опоздание на первую пару (Hik)"),
    (20, "Закрыта КТ: Основы алгоритмов"),
    (-5, "Опоздание 12 минут (Hik)"),
    (30, "Все КТ закрыты"),
    (15, "Неделя без пропусков"),
    (20, "Закрыта КТ: Базы данных"),
    (-20, "Просрочена КТ: Английский язык"),
    (5, "Серия 7 дней без опозданий"),
    (20, "Закрыта КТ: Веб-разработка"),
    (-8, "Опоздание 25 минут (Hik)"),
    (25, "Движ: участие в мероприятии"),
    (20, "Закрыта КТ: Операционные системы"),
)


class Command(BaseCommand):
    help = (
        "Наполняет базу состоянием одного студента и его отряда: квесты с разными "
        "сроками и прогрессом, история наград и рейтинга, значки, покупки, серии. "
        "Нужна, чтобы проверить интерфейс на данных, а не на пустых карточках."
    )

    def add_arguments(self, parser):
        parser.add_argument(
            "--username",
            default="demo",
            help="Кому наполнять профиль (по умолчанию demo).",
        )
        parser.add_argument(
            "--squad-size",
            type=int,
            default=8,
            help="Сколько сокурсников завести в отряде (по умолчанию 8).",
        )
        parser.add_argument(
            "--force",
            action="store_true",
            help="Выполнить даже в продакшен-окружении.",
        )

    def handle(self, *args, **options):
        # Команда переписывает прогресс, рейтинг и историю пользователя —
        # в продакшене это уничтожает настоящие данные.
        ensure_not_production(
            "Наполнение витринными данными", allow_force=True, force=options.get("force", False)
        )

        username = options["username"]
        squad_size = max(0, int(options["squad_size"]))
        random.seed(f"showcase:{username}")

        with transaction.atomic():
            user = self._ensure_hero(username)
            squad = user.squad
            self._ensure_schedule(squad)
            mates = self._ensure_squadmates(squad, user, squad_size)

            ensure_period_quests()
            periodic = self._fill_periodic_quests(user)
            long_quests = self._fill_long_quests(user)
            self_reports = self._fill_self_reports(user)
            completed = self._fill_completed_quests(user)
            rating_entries = self._fill_rating_history(user)
            badges = self._fill_badges(user)
            purchases = self._fill_purchases(user)
            self._fill_characteristics(user)
            self._fill_strike(user)
            hik_days = self._fill_hik_events(user)
            mates_done = self._fill_squad_bonus(mates)

        self.stdout.write(
            self.style.SUCCESS(
                f"Витрина готова для {user.username}: "
                f"квестов на период {periodic}, долгих {long_quests}, самоотчётов {self_reports}, "
                f"выполнено {completed}, записей рейтинга {rating_entries}, значков {badges}, "
                f"покупок {purchases}, дней проходов {hik_days}, "
                f"сокурсников {len(mates)} (недельный квест закрыли {mates_done})."
            )
        )
        self.stdout.write(
            f"Рейтинг: {user.rating_current}, монет: {user.coins_balance}. "
            f"Интерфейс: http://localhost:5173"
        )

    # --- Персонажи -------------------------------------------------------

    def _ensure_hero(self, username: str) -> User:
        track = Track.objects.order_by("id").first() or Track.objects.create(
            code="dev-backend", name="Бэкенд-разработка"
        )
        squad = Squad.objects.order_by("id").first() or Squad.objects.create(
            code="alpha", name="Отряд Альфа", course=2
        )
        user, _ = User.objects.get_or_create(
            username=username,
            defaults={
                "callsign": "Демо-агент",
                "email": f"{username}@nalchik.ithub.ru",
                "role": Role.AGENT,
            },
        )
        user.squad = user.squad or squad
        user.track = user.track or track
        user.role = Role.AGENT if user.role == Role.AGENT else user.role
        user.is_active = True
        user.level = 4
        user.rating_current = 612
        user.coins_balance = 340
        user.unclosed_ct_count = 1
        user.status = "На маршруте"
        user.save()

        TelegramAccountLink.objects.update_or_create(
            user=user,
            defaults={
                "telegram_user_id": SHOWCASE_TELEGRAM_BASE + user.pk,
                "telegram_chat_id": SHOWCASE_TELEGRAM_BASE + user.pk,
                "is_active": True,
            },
        )
        return user

    def _ensure_schedule(self, squad: Squad | None) -> None:
        """Расписание нужно квесту «Утренний чек-ин»: дедлайн берётся из него."""
        if not squad:
            return
        from datetime import time

        for dow in range(5):
            Schedule.objects.get_or_create(
                squad=squad,
                day_of_week=dow,
                start_time=time(8, 30),
                defaults={"end_time": time(15, 0), "is_active": True},
            )

    def _ensure_squadmates(self, squad: Squad | None, hero: User, count: int) -> list[User]:
        """Сокурсники: без них пусты лидерборд, состав отряда и командный бонус."""
        if not squad or count <= 0:
            return []

        names = [
            ("Барс", "barss"),
            ("Ветер", "veter"),
            ("Гром", "grom"),
            ("Дельта", "delta"),
            ("Ёж", "yozh"),
            ("Жар", "zhar"),
            ("Зенит", "zenit"),
            ("Искра", "iskra"),
            ("Кедр", "kedr"),
            ("Луч", "luch"),
        ]
        mates: list[User] = []
        for i, (callsign, slug) in enumerate(names[:count]):
            mate, _ = User.objects.get_or_create(
                username=f"showcase_{slug}",
                defaults={
                    "callsign": callsign,
                    "email": f"showcase_{slug}@nalchik.ithub.ru",
                    "role": Role.AGENT,
                },
            )
            mate.squad = squad
            mate.track = hero.track
            mate.is_active = True
            mate.level = 2 + (i % 4)
            # Рейтинги вокруг героя: в лидерборде видно и тех, кто выше, и тех, кто ниже.
            mate.rating_current = 300 + (i * 57) % 480
            mate.coins_balance = 40 + i * 15
            mate.save()
            TelegramAccountLink.objects.update_or_create(
                user=mate,
                defaults={
                    "telegram_user_id": SHOWCASE_TELEGRAM_BASE + mate.pk,
                    "telegram_chat_id": SHOWCASE_TELEGRAM_BASE + mate.pk,
                    "is_active": True,
                },
            )
            mates.append(mate)
        return mates

    # --- Квесты ----------------------------------------------------------

    def _fill_periodic_quests(self, user: User) -> int:
        """Разный прогресс у ежедневных и недельных: шкала должна показать все цвета."""
        quests = list(
            Quest.objects.filter(
                is_active=True, quest_type__in=[QuestType.DAILY, QuestType.WEEKLY]
            )
            .exclude(period_key="")
            .order_by("quest_type", "id")
        )
        for i, quest in enumerate(quests):
            progress = PROGRESS_BY_COLOR[i % len(PROGRESS_BY_COLOR)]
            UserQuestProgress.objects.update_or_create(
                user=user,
                quest=quest,
                defaults={"progress_value": progress, "is_completed": False},
            )
        return len(quests)

    def _fill_long_quests(self, user: User) -> int:
        now = timezone.now()
        for row in LONG_QUESTS:
            quest, _ = Quest.objects.update_or_create(
                code=row["code"],
                defaults={
                    "title": row["title"],
                    "description": row["description"],
                    "quest_type": QuestType.LONG,
                    "reward_coins": row["reward_coins"],
                    "reward_rating_delta": row["reward_rating_delta"],
                    "is_active": True,
                    "start_at": now - timedelta(days=3),
                    "end_at": now + timedelta(days=row["days_left"]),
                    "conditions": {"manual_complete_allowed": True},
                },
            )
            UserQuestProgress.objects.update_or_create(
                user=user,
                quest=quest,
                defaults={"progress_value": row["progress"], "is_completed": False},
            )
        return len(LONG_QUESTS)

    def _fill_self_reports(self, user: User) -> int:
        """Самоотчёты: один на проверке, один одобрен.

        Одобренный открывает веху «Продукт» на карте пути.
        """
        created = 0
        rows = (
            ("self-report-lab", SelfReportProofStatus.PENDING, "Отчёт по лабораторной отправлен"),
            ("self-report-project", SelfReportProofStatus.APPROVED, "Мини-проект принят куратором"),
        )
        for code, status, comment in rows:
            quest = Quest.objects.filter(code=code).first()
            if not quest:
                continue
            progress, _ = UserQuestProgress.objects.update_or_create(
                user=user,
                quest=quest,
                defaults={
                    "progress_value": 1.0 if status == SelfReportProofStatus.APPROVED else 0.5,
                    "is_completed": status == SelfReportProofStatus.APPROVED,
                },
            )
            SelfReportProof.objects.update_or_create(
                quest_progress=progress,
                defaults={
                    "quest": quest,
                    "user": user,
                    "comment": comment,
                    "status": status,
                    "reviewed_at": timezone.now() if status != SelfReportProofStatus.PENDING else None,
                },
            )
            created += 1
        return created

    def _fill_completed_quests(self, user: User) -> int:
        """Выполненные квесты за прошлые дни: вкладка «Выполненные» и история наград."""
        now = timezone.now()
        history = (
            ("showcase-done-checkin", "Утренний чек-ин", QuestType.DAILY, 5, 2, 1),
            ("showcase-done-noon", "День без опозданий", QuestType.DAILY, 5, 3, 2),
            ("showcase-done-week", "Неделя без опозданий", QuestType.WEEKLY, 20, 12, 4),
            ("showcase-done-ct", "Закрыть контрольную точку", QuestType.WEEKLY, 15, 8, 6),
            ("showcase-done-sprint", "Спринт YouGile", QuestType.WEEKLY, 25, 10, 9),
        )
        for code, title, quest_type, coins, rating, days_ago in history:
            quest, _ = Quest.objects.update_or_create(
                code=code,
                defaults={
                    "title": title,
                    "description": "Выполнен ранее.",
                    "quest_type": quest_type,
                    "reward_coins": coins,
                    "reward_rating_delta": rating,
                    "is_active": True,
                    "period_key": f"done-{days_ago}",
                    "start_at": now - timedelta(days=days_ago + 1),
                    "end_at": now - timedelta(days=days_ago),
                },
            )
            progress, _ = UserQuestProgress.objects.update_or_create(
                user=user,
                quest=quest,
                defaults={
                    "progress_value": 1.0,
                    "is_completed": True,
                    "completed_at": now - timedelta(days=days_ago),
                },
            )
            tx, created = QuestRewardTransaction.objects.get_or_create(
                user=user,
                quest=quest,
                defaults={"progress": progress, "coins_delta": coins, "rating_delta": rating},
            )
            if created:
                # granted_at заполняется автоматически, поэтому дату выставляем
                # запросом: иначе вся история выглядит выданной «только что».
                QuestRewardTransaction.objects.filter(pk=tx.pk).update(
                    granted_at=now - timedelta(days=days_ago)
                )
        return len(history)

    # --- Рейтинг, значки, покупки ---------------------------------------

    def _fill_rating_history(self, user: User) -> int:
        """История рейтинга: лента активности и график в профиле."""
        RatingLog.objects.filter(user=user, source_id__startswith="showcase:").delete()
        now = timezone.now()
        value = user.rating_current - sum(delta for delta, _ in RATING_EVENTS)
        created = 0
        for i, (delta, reason) in enumerate(RATING_EVENTS):
            before = value
            value += delta
            log = RatingLog.objects.create(
                user=user,
                value_before=before,
                value_after=value,
                delta=delta,
                source=RatingChangeSource.SYSTEM,
                source_id=f"showcase:{i}",
                reason=reason,
            )
            RatingLog.objects.filter(pk=log.pk).update(
                created_at=now - timedelta(days=len(RATING_EVENTS) - i, hours=2)
            )
            created += 1
        return created

    def _fill_badges(self, user: User) -> int:
        codes = list(Badge.objects.filter(is_active=True).values_list("code", flat=True)[:4])
        now = timezone.now()
        for i, code in enumerate(codes):
            badge = Badge.objects.get(code=code)
            user_badge, _ = UserBadge.objects.update_or_create(
                user=user,
                badge=badge,
                # Первые три закреплены: в профиле есть отдельный блок для них.
                defaults={"is_pinned": i < 3, "source": "showcase"},
            )
            # Даты разносим: иначе все значки выданы одной секундой и лента
            # активности состоит из них одних, вытесняя рейтинг и квесты.
            UserBadge.objects.filter(pk=user_badge.pk).update(
                acquired_at=now - timedelta(days=3 + i * 7)
            )
        return len(codes)

    def _fill_purchases(self, user: User) -> int:
        items = list(ShopItem.objects.filter(is_active=True).order_by("id")[:3])
        purchases = []
        for item in items:
            purchase, _ = Purchase.objects.get_or_create(
                user=user, item=item, defaults={"coins_spent": item.price_coins}
            )
            purchases.append(purchase)
        if purchases:
            # Одна покупка надета — видно состояние «Применена» и кнопку «Снять».
            apply_purchase(user, purchases[0].pk)
        return len(purchases)

    def _fill_characteristics(self, user: User) -> None:
        """Опоры для пятиугольника: разные значения, иначе фигура правильная и скучная."""
        values = {"rhythm": 16.5, "discipline": 12.0, "power": 18.0, "teamwork": 9.5, "initiative": 14.0}
        for pillar, _label in UI_PILLARS:
            current = values.get(pillar, 10.0)
            characteristic, _ = Characteristic.objects.update_or_create(
                user=user,
                pillar=pillar,
                defaults={"current": current, "peak": min(20.0, current + 1.5)},
            )
            if not characteristic.history_entries.exists():
                for value in (current - 4, current - 2.5, current - 1, current):
                    CharacteristicHistory.objects.create(
                        characteristic=characteristic,
                        value=max(0.0, value),
                        formula_version="showcase_v1",
                    )

    def _fill_strike(self, user: User) -> None:
        """Серия 9 дней: блок на дашборде показывает пройденную веху 7 и путь к 14."""
        today = timezone.localdate()
        UserStrike.objects.update_or_create(
            user=user,
            defaults={
                "attendance_strike": 12,
                "late_strike": 9,
                "last_attendance_date": today - timedelta(days=1),
                "last_late_date": today - timedelta(days=1),
            },
        )

    def _fill_hik_events(self, user: User) -> int:
        """Проходы турникета за прошлую неделю — источник посещаемости и опозданий."""
        today = timezone.localdate()
        days = 0
        for offset in range(1, 8):
            day = today - timedelta(days=offset)
            if day.weekday() >= 5:
                continue
            late = offset == 3
            moment = timezone.make_aware(
                timezone.datetime.combine(
                    day, timezone.datetime.min.time().replace(hour=9 if late else 8, minute=12)
                )
            )
            ExternalEvent.objects.update_or_create(
                source="hik",
                external_event_id=f"showcase-{user.pk}-{day}",
                defaults={
                    "user": user,
                    "event_date": day,
                    "event_type": "late" if late else "access",
                    "payload": {
                        "event_type": "late" if late else "access",
                        "late_minutes": 42 if late else 0,
                        "event_time": moment.isoformat(),
                    },
                },
            )
            days += 1
        return days

    def _fill_squad_bonus(self, mates: list[User]) -> int:
        """Часть отряда закрывает недельный квест — блок командного бонуса оживает."""
        weekly = (
            Quest.objects.filter(is_active=True, quest_type=QuestType.WEEKLY)
            .exclude(period_key="")
            .order_by("id")
            .first()
        )
        if not weekly or not mates:
            return 0
        done = 0
        for i, mate in enumerate(mates):
            completed = i % 3 != 0
            UserQuestProgress.objects.update_or_create(
                user=mate,
                quest=weekly,
                defaults={"progress_value": 1.0 if completed else 0.4, "is_completed": completed},
            )
            done += int(completed)
        return done
