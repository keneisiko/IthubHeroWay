"""Idempotent demo seed for local testing."""

from __future__ import annotations

from datetime import time

from django.contrib.auth import get_user_model
from django.core.management import call_command
from django.core.management.base import BaseCommand
from django.db.models import Q
from django.utils import timezone

from apps.accounts.models import Role, Squad, Track
from apps.badges.models import Badge, BadgeCategory, BadgeRarity
from apps.integrations.models import TelegramAccountLink
from apps.operations.services.environment import ensure_not_production
from apps.progress.models import Characteristic, CharacteristicHistory, UserStrike
from apps.progress.services.pillar_labels import UI_PILLARS
from apps.quests.models import Quest, QuestType, UserQuestProgress
from apps.schedule.models import Schedule
from apps.shop.models import ShopItem, ShopItemType

User = get_user_model()
SYNTHETIC_TELEGRAM_BASE = 5_100_000_000

TRACKS = [
    {"code": "dev-backend", "name": "Backend-разработка"},
    {"code": "dev-frontend", "name": "Frontend-разработка"},
]

SQUADS = [
    {"code": "alpha-2025", "name": "Отряд Альфа", "course": 2, "capacity": 20},
    {"code": "beta-2025", "name": "Отряд Бета", "course": 3, "capacity": 20},
]

SHOP_ITEMS = [
    {"code": "cosmetic-avatar-frame", "title": "Рамка аватара «Фиолетовый»", "item_type": ShopItemType.COSMETIC, "price_coins": 50},
    {"code": "cosmetic-badge-glow", "title": "Свечение значка", "item_type": ShopItemType.COSMETIC, "price_coins": 80},
    {"code": "boost-xp-2h", "title": "Буст опыта ×1.5 (2 ч)", "item_type": ShopItemType.BOOST, "price_coins": 120},
    {"code": "boost-coins-day", "title": "Двойные монеты (1 день)", "item_type": ShopItemType.BOOST, "price_coins": 150},
    {"code": "merch-sticker", "title": "Стикерпак IThub", "item_type": ShopItemType.OTHER, "price_coins": 200},
    {"code": "merch-mug", "title": "Кружка «Путь Героя»", "item_type": ShopItemType.OTHER, "price_coins": 350},
    {"code": "service-mentor", "title": "Сессия с ментором", "item_type": ShopItemType.SERVICE, "price_coins": 100},
    {"code": "service-cv", "title": "Разбор резюме", "item_type": ShopItemType.SERVICE, "price_coins": 75},
]

BADGES = [
    {
        "code": "first-quest",
        "title": "Первый шаг",
        "description": "Выполни первый квест",
        "category": BadgeCategory.PROGRESS,
        "rarity": BadgeRarity.COMMON,
        "condition": {"completed_quests_at_least": 1},
        "reward_coins": 10,
    },
    {
        "code": "quest-master",
        "title": "Мастер квестов",
        "description": "Выполни 3 квеста",
        "category": BadgeCategory.PROGRESS,
        "rarity": BadgeRarity.RARE,
        "condition": {"completed_quests_at_least": 3},
        "reward_coins": 25,
    },
    # Две последние вехи карты пути отмечает куратор: событий «вышел на
    # стажировку» и «выпустился» нет ни в LXP, ни в Hik.
    {
        "code": "path-internship",
        "title": "Стажировка",
        "description": "Веха карты пути: студент вышел на стажировку. Выдаётся куратором.",
        "category": BadgeCategory.SPECIAL,
        "rarity": BadgeRarity.EPIC,
        "condition": {"manual": True},
        "reward_coins": 0,
    },
    {
        "code": "path-graduation",
        "title": "Выпуск",
        "description": "Веха карты пути: студент завершил обучение. Выдаётся куратором.",
        "category": BadgeCategory.SPECIAL,
        "rarity": BadgeRarity.LEGENDARY,
        "condition": {"manual": True},
        "reward_coins": 0,
    },
]

PILLAR_DEMO_VALUES = [
    {"rhythm": 14, "discipline": 12, "power": 16, "teamwork": 11, "initiative": 13},
    {"rhythm": 10, "discipline": 15, "power": 12, "teamwork": 14, "initiative": 9},
    {"rhythm": 8, "discipline": 11, "power": 18, "teamwork": 10, "initiative": 12},
]


class Command(BaseCommand):
    help = "Seed demo data for local testing (idempotent)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--force",
            action="store_true",
            help="Выполнить даже в продакшен-окружении (перезапишет данные реальных пользователей)",
        )
        parser.add_argument(
            "--assign-email",
            type=str,
            default="",
            help="Assign this user (by email) to squad alpha-2025",
        )
        parser.add_argument(
            "--with-hik",
            action="store_true",
            help="Синтетический HikSnapshot за сегодня + verify daily quests",
        )

    def handle(self, *args, **options):
        # Команда перезаписывает поля существующих пользователей (отряд, монеты,
        # рейтинг, серии) и пересинхронизирует квесты, откатывая ручные правки
        # в админке. В продакшене это недопустимо.
        ensure_not_production(
            "Заполнение демо-данными", allow_force=True, force=options.get("force", False)
        )

        assign_email = (options.get("assign_email") or "").strip().lower()
        stats: dict[str, int] = {}

        for track_data in TRACKS:
            Track.objects.update_or_create(code=track_data["code"], defaults={"name": track_data["name"]})
        stats["tracks"] = len(TRACKS)

        for squad_data in SQUADS:
            Squad.objects.update_or_create(
                code=squad_data["code"],
                defaults={
                    "name": squad_data["name"],
                    "course": squad_data["course"],
                    "capacity": squad_data["capacity"],
                },
            )
        stats["squads"] = len(SQUADS)

        for squad in Squad.objects.filter(code__in=[s["code"] for s in SQUADS]):
            for day in range(5):
                Schedule.objects.update_or_create(
                    squad=squad,
                    day_of_week=day,
                    start_time=time(9, 0),
                    defaults={
                        "end_time": time(10, 30),
                        "discipline": "Demo",
                        "is_active": True,
                    },
                )

        call_command("sync_quest_templates")
        stats["quests"] = Quest.objects.filter(is_active=True).count()

        for item_data in SHOP_ITEMS:
            ShopItem.objects.update_or_create(
                code=item_data["code"],
                defaults={
                    "title": item_data["title"],
                    "description": f"Демо-товар: {item_data['title']}",
                    "item_type": item_data["item_type"],
                    "price_coins": item_data["price_coins"],
                    "is_active": True,
                },
            )
        stats["shop_items"] = len(SHOP_ITEMS)

        for badge_data in BADGES:
            Badge.objects.update_or_create(
                code=badge_data["code"],
                defaults={
                    "title": badge_data["title"],
                    "description": badge_data["description"],
                    "category": badge_data["category"],
                    "rarity": badge_data["rarity"],
                    "condition": badge_data["condition"],
                    "reward_coins": badge_data["reward_coins"],
                    "is_active": True,
                },
            )
        stats["badges"] = len(BADGES)

        telegram_created = self._ensure_synthetic_telegram()
        stats["telegram_links"] = telegram_created

        alpha = Squad.objects.get(code="alpha-2025")
        beta = Squad.objects.get(code="beta-2025")
        track_backend = Track.objects.get(code="dev-backend")
        track_frontend = Track.objects.get(code="dev-frontend")

        agents_qs = User.objects.filter(role=Role.AGENT).order_by("id")
        if assign_email:
            agents_qs = agents_qs.exclude(email__iexact=assign_email)

        agents = list(agents_qs[:6])
        for idx, agent in enumerate(agents):
            squad = alpha if idx < 3 else beta
            track = track_backend if idx % 2 == 0 else track_frontend
            agent.squad = squad
            agent.track = track
            agent.coins_balance = max(agent.coins_balance, 500)
            agent.rating_current = max(agent.rating_current, 320 + idx * 40)
            agent.status = "active"
            agent.save(update_fields=["squad", "track", "coins_balance", "rating_current", "status"])
            self._ensure_telegram(agent)
            self._seed_characteristics(agent, PILLAR_DEMO_VALUES[idx % len(PILLAR_DEMO_VALUES)])
            self._seed_quest_progress(agent, idx)

        if agents:
            demo_strike_user = agents[0]
            strike, _ = UserStrike.objects.get_or_create(user=demo_strike_user)
            strike.late_strike = 12
            strike.attendance_strike = 5
            strike.save(update_fields=["late_strike", "attendance_strike"])

        if assign_email:
            user = User.objects.filter(email__iexact=assign_email).first()
            if user:
                user.squad = alpha
                user.track = track_backend
                user.coins_balance = max(user.coins_balance, 500)
                self._ensure_telegram(user)
                user.save(update_fields=["squad", "track", "coins_balance"])
                self._seed_characteristics(user, PILLAR_DEMO_VALUES[0])
                self.stdout.write(self.style.SUCCESS(f"Assigned {assign_email} to {alpha.code}"))
            else:
                self.stdout.write(self.style.WARNING(f"User not found: {assign_email}"))

        if options.get("with_hik"):
            call_command(
                "pull_hik_attendance",
                synthetic=True,
                assign_hik_cards=True,
                verify_quests=True,
            )
            self.stdout.write(self.style.SUCCESS("Synthetic Hik snapshot imported"))

        self.stdout.write(
            self.style.SUCCESS(
                f"Demo seed complete: tracks={stats['tracks']}, squads={stats['squads']}, "
                f"quests={stats['quests']}, shop={stats['shop_items']}, badges={stats['badges']}, "
                f"telegram_links={stats['telegram_links']}, agents_in_squads={len(agents)}"
            )
        )

    def _ensure_synthetic_telegram(self) -> int:
        created = 0
        qs = User.objects.filter(role=Role.AGENT).exclude(Q(lxp_user_id__isnull=True) | Q(lxp_user_id=""))
        missing = qs.filter(telegram_link__isnull=True)
        for u in missing.iterator(chunk_size=200):
            self._ensure_telegram(u)
            created += 1
        return created

    def _ensure_telegram(self, user: User) -> None:
        telegram_user_id = SYNTHETIC_TELEGRAM_BASE + int(user.pk)
        TelegramAccountLink.objects.update_or_create(
            user=user,
            defaults={
                "telegram_user_id": telegram_user_id,
                "telegram_chat_id": telegram_user_id,
                "telegram_username": "",
                "is_active": True,
            },
        )

    def _seed_characteristics(self, user: User, values: dict[str, float]) -> None:
        for pillar, _label in UI_PILLARS:
            val = float(values.get(pillar, 10))
            char_obj, _ = Characteristic.objects.update_or_create(
                user=user,
                pillar=pillar,
                defaults={"current": val, "peak": max(val, val + 2)},
            )
            if not char_obj.history_entries.exists():
                for v in [val - 2, val - 1, val - 0.5, val, val, val]:
                    CharacteristicHistory.objects.create(
                        characteristic=char_obj,
                        value=max(0, v),
                        formula_version="seed_v1",
                    )

    def _seed_quest_progress(self, user: User, idx: int) -> None:
        daily = Quest.objects.filter(quest_type=QuestType.DAILY, is_active=True).order_by("id")
        weekly = Quest.objects.filter(quest_type=QuestType.WEEKLY, is_active=True).order_by("id")
        if daily.exists() and idx % 2 == 0:
            q = daily.first()
            UserQuestProgress.objects.update_or_create(
                user=user,
                quest=q,
                defaults={"progress_value": 0.6, "is_completed": False},
            )
        if weekly.exists() and idx % 3 == 0:
            q = weekly.first()
            UserQuestProgress.objects.update_or_create(
                user=user,
                quest=q,
                defaults={"progress_value": 1.0, "is_completed": True, "completed_at": timezone.now()},
            )
