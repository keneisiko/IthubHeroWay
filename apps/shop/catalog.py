"""Каталог товаров магазина.

Каталог лежал внутри `seed_demo_data`, а та отказывается работать
в продакшене — значит на проде магазин оставался пустым, пока кто-нибудь
не заведёт товары руками через админку. Определения вынесены сюда, чтобы
их могла применить и прод-команда `sync_catalogs`.

Цены пересобраны под Положение: учебный блок даёт до 30 монет в неделю
(п. 3.4), квесты — ещё около 15, то есть у активного студента примерно
35-40 монет в неделю. Прежние 50-350 означали, что половина каталога
недостижима за семестр, а дешёвая половина выкупается за неделю и больше
не интересна. Теперь есть недельные покупки, месячная цель и одна крупная
на сезон.

Двух бустов в каталоге нет сознательно: «Буст опыта» и «Двойные монеты»
продавались за 120 и 150 монет и не делали ничего — кода, который умножал бы
начисления, в проекте не существует. Вернуть их можно только вместе
с реализацией.
"""

from __future__ import annotations

from apps.shop.models import ShopItemType

SHOP_ITEMS: tuple[dict, ...] = (
    {
        "code": "service-late-forgive",
        "title": "Прощённое опоздание",
        "description": "Снимает одно опоздание за текущую неделю: серия не рвётся.",
        "item_type": ShopItemType.SERVICE,
        "price_coins": 25,
    },
    {
        "code": "cosmetic-avatar-frame",
        "title": "Рамка аватара «Фиолетовый»",
        "description": "Фиолетовая рамка вокруг аватара в профиле и рейтинге.",
        "item_type": ShopItemType.COSMETIC,
        "price_coins": 30,
    },
    {
        "code": "service-deadline-extend",
        "title": "Продление самоотчёта на 2 дня",
        "description": "Плюс два дня на сдачу отчёта по квесту.",
        "item_type": ShopItemType.SERVICE,
        "price_coins": 35,
    },
    {
        "code": "cosmetic-badge-glow",
        "title": "Свечение значка",
        "description": "Закреплённый значок светится в профиле.",
        "item_type": ShopItemType.COSMETIC,
        "price_coins": 40,
    },
    {
        "code": "service-cv",
        "title": "Разбор резюме",
        "description": "Разбор резюме с наставником колледжа.",
        "item_type": ShopItemType.SERVICE,
        "price_coins": 60,
    },
    {
        "code": "service-mentor",
        "title": "Сессия с ментором",
        "description": "Полчаса с наставником по теме на выбор.",
        "item_type": ShopItemType.SERVICE,
        "price_coins": 80,
    },
    {
        "code": "merch-sticker",
        "title": "Стикерпак IThub",
        "description": "Набор наклеек колледжа. Выдаётся в учебной части.",
        "item_type": ShopItemType.OTHER,
        "price_coins": 120,
    },
    {
        "code": "merch-mug",
        "title": "Кружка «Путь Героя»",
        "description": "Кружка с символикой. Выдаётся в учебной части.",
        "item_type": ShopItemType.OTHER,
        "price_coins": 250,
    },
)

# Товары, снятые с продажи: команда синхронизации их деактивирует, а не
# удаляет — на них могут ссылаться покупки, сделанные раньше.
RETIRED_ITEM_CODES: tuple[str, ...] = ("boost-xp-2h", "boost-coins-day")
