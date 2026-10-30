"""Каталоги магазина и нашивок ставятся и в продакшене.

Товары и нашивки заводила только `seed_demo_data`, запрещённая в продакшене:
на проде разделы «Магазин» и «Нашивки» оставались пустыми, и заметить это
можно было только глазами студента.
"""

from __future__ import annotations

from io import StringIO

from django.core.management import call_command
from django.test import TestCase, override_settings

from apps.badges.catalog import BADGES
from apps.badges.models import Badge
from apps.shop.catalog import RETIRED_ITEM_CODES, SHOP_ITEMS
from apps.shop.models import ShopItem, ShopItemType


def run(*args) -> str:
    out = StringIO()
    call_command("sync_catalogs", *args, stdout=out)
    return out.getvalue()


class SyncCatalogsTests(TestCase):
    def test_creates_both_catalogs(self):
        run()

        self.assertEqual(ShopItem.objects.count(), len(SHOP_ITEMS))
        # «Самый страшный» заводит миграция, а не каталог
        self.assertEqual(Badge.objects.exclude(code="halloween-scariest").count(), len(BADGES))

    @override_settings(ENVIRONMENT_NAME="production", DEBUG=False)
    def test_works_in_production(self):
        """Главное отличие от seed_demo_data: команда не падает на проде."""
        run()

        self.assertEqual(ShopItem.objects.count(), len(SHOP_ITEMS))

    def test_rerun_changes_nothing(self):
        run()
        before = list(ShopItem.objects.values_list("code", "price_coins").order_by("code"))

        run()

        after = list(ShopItem.objects.values_list("code", "price_coins").order_by("code"))
        self.assertEqual(before, after)
        self.assertEqual(ShopItem.objects.count(), len(SHOP_ITEMS))

    def test_manual_edits_survive_by_default(self):
        """Цену могли поправить в админке осознанно — не затираем."""
        run()
        ShopItem.objects.filter(code="merch-mug").update(price_coins=999, title="Своя кружка")

        run()

        item = ShopItem.objects.get(code="merch-mug")
        self.assertEqual(item.price_coins, 999)
        self.assertEqual(item.title, "Своя кружка")

    def test_update_existing_applies_prices_from_code(self):
        run()
        ShopItem.objects.filter(code="merch-mug").update(price_coins=999)

        run("--update-existing")

        expected = next(row["price_coins"] for row in SHOP_ITEMS if row["code"] == "merch-mug")
        self.assertEqual(ShopItem.objects.get(code="merch-mug").price_coins, expected)

    def test_retired_items_are_deactivated_not_deleted(self):
        """Снятый с продажи буст должен остаться в истории покупок."""
        retired_code = RETIRED_ITEM_CODES[0]
        ShopItem.objects.create(
            code=retired_code,
            title="Буст опыта",
            item_type=ShopItemType.BOOST,
            price_coins=120,
            is_active=True,
        )

        run()

        item = ShopItem.objects.get(code=retired_code)
        self.assertFalse(item.is_active)

    def test_dry_run_writes_nothing(self):
        output = run("--dry-run")

        self.assertEqual(ShopItem.objects.count(), 0)
        self.assertFalse(Badge.objects.exclude(code="halloween-scariest").exists())
        self.assertIn("будет создан", output)

    def test_badges_reward_only_coins(self):
        """Нашивки не начисляют рейтинг: Положение не знает такого источника."""
        for row in BADGES:
            with self.subTest(code=row["code"]):
                self.assertNotIn("reward_rating_delta", row)
