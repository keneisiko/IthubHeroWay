"""Слоты косметики и буст «×2 монеты за квест».

Рамка и свечение оба были косметикой, и надеть рамку молча снимало свечение.
Буст в каталоге ничего не делал, пока не появилось удвоение награды за квест.
"""

from __future__ import annotations

from unittest.mock import patch

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.urls import reverse
from django.utils import timezone
from rest_framework.test import APITestCase

from apps.accounts.frames import avatar_frame_for
from apps.accounts.models import Role
from apps.quests.models import Quest, QuestRewardTransaction, QuestType
from apps.quests.services.quest_completion import complete_quest_idempotent
from apps.quests.services.quest_periods import period_key_for
from apps.shop.models import Purchase, ShopItem, ShopItemType
from apps.shop.services import PurchaseNotApplicable, applied_purchases, apply_purchase

User = get_user_model()


def make_user(username: str, coins: int = 500) -> User:
    return User.objects.create_user(
        username=username,
        email=f"{username}@test.ru",
        password="x",
        callsign=f"call_{username}",
        role=Role.AGENT,
        coins_balance=coins,
    )


def make_item(code, slot, item_type=ShopItemType.COSMETIC, price=10) -> ShopItem:
    return ShopItem.objects.create(
        code=code, title=code, item_type=item_type, slot=slot, price_coins=price
    )


def make_quest(code: str, coins: int = 10) -> Quest:
    return Quest.objects.create(
        code=code,
        title=code,
        quest_type=QuestType.WEEKLY,
        period_key=period_key_for(QuestType.WEEKLY, timezone.localdate()),
        reward_coins=coins,
        reward_rating_delta=0,
    )


class SlotIndependenceTests(TestCase):
    def test_frame_glow_and_banner_are_applied_together(self):
        user = make_user("slots")
        items = [
            make_item("cosmetic-frame-gold", "avatar_frame"),
            make_item("cosmetic-glow-gold", "badge_glow"),
            make_item("banner-night", "profile_banner"),
        ]
        for item in items:
            purchase = Purchase.objects.create(user=user, item=item, coins_spent=10)
            apply_purchase(user, purchase.pk)

        self.assertEqual(
            applied_purchases(user),
            {
                "avatar_frame": "cosmetic-frame-gold",
                "badge_glow": "cosmetic-glow-gold",
                "profile_banner": "banner-night",
            },
        )
        self.assertEqual(avatar_frame_for(user), "gold")

    def test_second_item_in_same_slot_replaces_first(self):
        user = make_user("same_slot")
        first = Purchase.objects.create(user=user, item=make_item("banner-a", "profile_banner"), coins_spent=10)
        second = Purchase.objects.create(user=user, item=make_item("banner-b", "profile_banner"), coins_spent=10)
        apply_purchase(user, first.pk)
        apply_purchase(user, second.pk)

        self.assertEqual(applied_purchases(user), {"profile_banner": "banner-b"})

    def test_boost_cannot_be_applied(self):
        user = make_user("no_apply")
        boost = Purchase.objects.create(
            user=user, item=make_item("boost-quest-x2", "boost", ShopItemType.BOOST), coins_spent=10
        )
        with self.assertRaises(PurchaseNotApplicable):
            apply_purchase(user, boost.pk)


class BoostApiTests(APITestCase):
    def setUp(self):
        self.user = make_user("booster")
        self.client.force_authenticate(self.user)
        self.boost = make_item("boost-quest-x2", "boost", ShopItemType.BOOST, price=40)

    def _buy(self):
        return self.client.post(reverse("shop-purchase"), {"item_code": "boost-quest-x2"}, format="json")

    def test_apply_boost_returns_400(self):
        purchase = Purchase.objects.create(user=self.user, item=self.boost, coins_spent=40)
        response = self.client.post(reverse("shop-purchase-apply", args=[purchase.pk]))
        self.assertEqual(response.status_code, 400)

    def test_second_boost_is_refused_until_first_is_used(self):
        self.assertEqual(self._buy().status_code, 201)
        second = self._buy()
        self.assertEqual(second.status_code, 400)
        self.assertEqual(Purchase.objects.filter(user=self.user).count(), 1)
        self.user.refresh_from_db()
        self.assertEqual(self.user.coins_balance, 460)

    def test_boost_can_be_bought_again_after_use(self):
        self._buy()
        Purchase.objects.update(consumed_at=timezone.now())
        self.assertEqual(self._buy().status_code, 201)

    def test_contract_fields(self):
        self._buy()
        row = self.client.get(reverse("shop-my-purchases")).json()[0]
        self.assertEqual(row["item"]["slot"], "boost")
        self.assertIsNone(row["consumed_at"])

    def test_profile_exposes_active_boost_and_applied_items(self):
        self._buy()
        banner = Purchase.objects.create(
            user=self.user, item=make_item("banner-night", "profile_banner"), coins_spent=10
        )
        apply_purchase(self.user, banner.pk)

        from apps.accounts.serializers import MeProfileSerializer, PublicProfileSerializer

        me = MeProfileSerializer(self.user).data
        self.assertEqual(me["active_boost"], {"code": "boost-quest-x2", "title": "boost-quest-x2"})
        self.assertEqual(me["applied_items"], {"profile_banner": "banner-night"})
        public = PublicProfileSerializer(self.user).data
        self.assertEqual(public["applied_items"], {"profile_banner": "banner-night"})

    def test_active_boost_is_null_after_use(self):
        self._buy()
        Purchase.objects.update(consumed_at=timezone.now())
        from apps.accounts.serializers import MeProfileSerializer

        self.assertIsNone(MeProfileSerializer(self.user).data["active_boost"])


class BoostQuestRewardTests(TestCase):
    def setUp(self):
        # По умолчанию дневной предел 10 монет — для проверки удвоения его поднимаем.
        patcher = patch("apps.progress.services.rewards.max_daily_coins", return_value=1000)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.user = make_user("quester", coins=0)
        self.purchase = Purchase.objects.create(
            user=self.user, item=make_item("boost-quest-x2", "boost", ShopItemType.BOOST), coins_spent=40
        )

    def _complete(self, quest):
        complete_quest_idempotent(self.user, quest, reason="тест")
        self.user.refresh_from_db()

    def test_boost_doubles_reward_of_next_quest(self):
        self._complete(make_quest("q1", 10))

        self.assertEqual(self.user.coins_balance, 20)
        self.purchase.refresh_from_db()
        self.assertIsNotNone(self.purchase.consumed_at)
        self.assertEqual(self.purchase.meta["boost"]["granted_coins"], 20)

    def test_boost_works_exactly_once(self):
        self._complete(make_quest("q1", 10))
        self._complete(make_quest("q2", 10))

        self.assertEqual(self.user.coins_balance, 30)

    def test_repeated_completion_does_not_spend_boost_twice(self):
        quest = make_quest("q1", 10)
        self._complete(quest)
        self._complete(quest)

        self.assertEqual(self.user.coins_balance, 20)
        self.assertEqual(QuestRewardTransaction.objects.filter(user=self.user).count(), 1)

    def test_daily_cap_is_not_bypassed(self):
        with patch("apps.progress.services.rewards.max_daily_coins", return_value=15):
            self._complete(make_quest("q1", 10))

        self.assertEqual(self.user.coins_balance, 15)

    def test_boost_is_kept_when_cap_is_exhausted(self):
        with patch("apps.progress.services.rewards.max_daily_coins", return_value=0):
            self._complete(make_quest("q1", 10))

        self.purchase.refresh_from_db()
        self.assertIsNone(self.purchase.consumed_at)


class LegacyAndEdgeTests(TestCase):
    def setUp(self):
        patcher = patch("apps.progress.services.rewards.max_daily_coins", return_value=1000)
        patcher.start()
        self.addCleanup(patcher.stop)
        self.user = make_user("legacy", coins=100)

    def test_legacy_boost_purchase_is_not_a_working_boost(self):
        """Снятые boost-xp-2h/boost-coins-day ничего не делали и не должны стать ×2."""
        old = make_item("boost-coins-day", "", ShopItemType.BOOST)
        legacy = Purchase.objects.create(user=self.user, item=old, coins_spent=150)

        complete_quest_idempotent(self.user, make_quest("q1", 10), reason="тест")
        self.user.refresh_from_db()

        self.assertEqual(self.user.coins_balance, 110)
        legacy.refresh_from_db()
        self.assertIsNone(legacy.consumed_at)

    def test_legacy_boost_does_not_block_new_purchase(self):
        old = make_item("boost-xp-2h", "", ShopItemType.BOOST)
        Purchase.objects.create(user=self.user, item=old, coins_spent=120)
        make_item("boost-quest-x2", "boost", ShopItemType.BOOST, price=40)
        from rest_framework.test import APIClient

        client = APIClient()
        client.force_authenticate(self.user)
        response = client.post(reverse("shop-purchase"), {"item_code": "boost-quest-x2"}, format="json")
        self.assertEqual(response.status_code, 201)

    def test_boost_not_spent_when_it_adds_nothing(self):
        """Остаток лимита 5 при базе 10: и без буста дали бы 5."""
        Purchase.objects.create(
            user=self.user, item=make_item("boost-quest-x2", "boost", ShopItemType.BOOST), coins_spent=40
        )
        with patch("apps.progress.services.rewards.max_daily_coins", return_value=5):
            complete_quest_idempotent(self.user, make_quest("q1", 10), reason="тест")

        self.assertIsNone(Purchase.objects.get(user=self.user).consumed_at)

    def test_non_cosmetic_items_cannot_be_applied(self):
        for n, (item_type, slot) in enumerate(
            [(ShopItemType.SERVICE, ""), (ShopItemType.OTHER, ""), (ShopItemType.COSMETIC, "")]
        ):
            purchase = Purchase.objects.create(
                user=self.user, item=make_item(f"x{n}", slot, item_type), coins_spent=10
            )
            with self.assertRaises(PurchaseNotApplicable):
                apply_purchase(self.user, purchase.pk)


class ShopItemAdminFormTests(TestCase):
    def _form(self, **data):
        from apps.shop.admin import ShopItemAdminForm

        base = {"title": "T", "price_coins": 10, "is_active": True, "code": "t-code"}
        return ShopItemAdminForm(data={**base, **data})

    def test_cosmetic_requires_slot(self):
        self.assertFalse(self._form(item_type="cosmetic", slot="").is_valid())
        self.assertTrue(self._form(item_type="cosmetic", slot="profile_banner").is_valid())

    def test_boost_requires_boost_slot(self):
        self.assertFalse(self._form(item_type="boost", slot="").is_valid())
        self.assertTrue(self._form(item_type="boost", slot="boost").is_valid())
