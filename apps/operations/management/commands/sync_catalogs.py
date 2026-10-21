"""Каталоги товаров и нашивок — в том числе в продакшене.

Товары и нашивки заводила только `seed_demo_data`, а она отказывается
работать в продакшене: разделы «Магазин» и «Нашивки» на проде оставались
пустыми, пока кто-нибудь не заведёт записи руками. Эта команда ставит те же
каталоги и никаких пользовательских данных не трогает.

    python manage.py sync_catalogs
    python manage.py sync_catalogs --dry-run
    python manage.py sync_catalogs --update-existing

По умолчанию существующие записи не меняются: цену или название могли
поправить в админке осознанно. `--update-existing` возвращает значения из
кода — им и применяется ребаланс цен.
"""

from __future__ import annotations

from django.core.management.base import BaseCommand
from django.db import transaction

from apps.badges.catalog import BADGES
from apps.badges.models import Badge
from apps.shop.catalog import RETIRED_ITEM_CODES, SHOP_ITEMS
from apps.shop.models import ShopItem


class Command(BaseCommand):
    help = "Создаёт и обновляет каталоги магазина и нашивок (безопасно для продакшена)."

    def add_arguments(self, parser):
        parser.add_argument(
            "--update-existing",
            action="store_true",
            help="Перезаписать поля существующих записей значениями из кода.",
        )
        parser.add_argument(
            "--dry-run",
            action="store_true",
            help="Показать, что изменится, ничего не записывая.",
        )

    def handle(self, *args, **options):
        update_existing = bool(options["update_existing"])
        dry_run = bool(options["dry_run"])

        if dry_run:
            self._preview()
            return

        with transaction.atomic():
            items = self._sync_items(update_existing)
            badges = self._sync_badges(update_existing)
            retired = self._retire_items()

        self.stdout.write(
            self.style.SUCCESS(
                f"Товары: новых {items['created']}, обновлено {items['updated']}, "
                f"без изменений {items['skipped']}, снято с продажи {retired}. "
                f"Нашивки: новых {badges['created']}, обновлено {badges['updated']}, "
                f"без изменений {badges['skipped']}."
            )
        )
        if not update_existing and (items["skipped"] or badges["skipped"]):
            self.stdout.write(
                self.style.NOTICE(
                    "Существующие записи не тронуты. Чтобы применить цены и награды "
                    "из кода, повторите с --update-existing."
                )
            )

    def _item_defaults(self, row: dict) -> dict:
        return {
            "title": row["title"],
            "description": row.get("description", ""),
            "item_type": row["item_type"],
            "slot": row.get("slot", ""),
            "price_coins": row["price_coins"],
            "is_active": True,
        }

    def _badge_defaults(self, row: dict) -> dict:
        return {
            "title": row["title"],
            "description": row.get("description", ""),
            "category": row["category"],
            "rarity": row["rarity"],
            "condition": row["condition"],
            "reward_coins": row["reward_coins"],
            "is_active": True,
        }

    def _sync_items(self, update_existing: bool) -> dict:
        created = updated = skipped = 0
        for row in SHOP_ITEMS:
            defaults = self._item_defaults(row)
            item, was_created = ShopItem.objects.get_or_create(code=row["code"], defaults=defaults)
            if was_created:
                created += 1
            elif update_existing:
                for field, value in defaults.items():
                    setattr(item, field, value)
                item.save(update_fields=list(defaults))
                updated += 1
            else:
                skipped += 1
        return {"created": created, "updated": updated, "skipped": skipped}

    def _sync_badges(self, update_existing: bool) -> dict:
        created = updated = skipped = 0
        for row in BADGES:
            defaults = self._badge_defaults(row)
            badge, was_created = Badge.objects.get_or_create(code=row["code"], defaults=defaults)
            if was_created:
                created += 1
            elif update_existing:
                for field, value in defaults.items():
                    setattr(badge, field, value)
                badge.save(update_fields=list(defaults))
                updated += 1
            else:
                skipped += 1
        return {"created": created, "updated": updated, "skipped": skipped}

    def _retire_items(self) -> int:
        """Снять с продажи то, что больше не продаётся.

        Деактивация, а не удаление: на товар могут ссылаться покупки,
        сделанные раньше, и студент должен видеть их в своей истории.
        """
        return ShopItem.objects.filter(code__in=RETIRED_ITEM_CODES, is_active=True).update(
            is_active=False
        )

    def _preview(self) -> None:
        self.stdout.write(self.style.MIGRATE_HEADING("Товары"))
        self.stdout.write(f"{'Код':<28}{'Название':<34}{'Цена':>6}  Состояние")
        for row in SHOP_ITEMS:
            existing = ShopItem.objects.filter(code=row["code"]).first()
            if existing is None:
                state = "будет создан"
            elif existing.price_coins != row["price_coins"]:
                state = f"в базе {existing.price_coins} (нужен --update-existing)"
            else:
                state = "совпадает"
            self.stdout.write(
                f"{row['code']:<28}{row['title'][:33]:<34}{row['price_coins']:>6}  {state}"
            )

        retired = ShopItem.objects.filter(code__in=RETIRED_ITEM_CODES, is_active=True)
        for item in retired:
            self.stdout.write(f"{item.code:<28}{item.title[:33]:<34}{'':>6}  будет снят с продажи")

        self.stdout.write(self.style.MIGRATE_HEADING("\nНашивки"))
        self.stdout.write(f"{'Код':<28}{'Название':<34}{'Монеты':>7}  Состояние")
        for row in BADGES:
            existing = Badge.objects.filter(code=row["code"]).first()
            state = "совпадает" if existing else "будет создана"
            if existing and existing.reward_coins != row["reward_coins"]:
                state = f"в базе {existing.reward_coins} (нужен --update-existing)"
            self.stdout.write(
                f"{row['code']:<28}{row['title'][:33]:<34}{row['reward_coins']:>7}  {state}"
            )
