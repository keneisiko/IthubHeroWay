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

Буст «×2 монеты за квест» теперь настоящий: он удваивает награду за ближайший
выполненный квест (apps.quests.services.quest_completion), с учётом дневного
предела. Прежние «Буст опыта» и «Двойные монеты» продавались за 120 и 150 монет
и не делали ничего — они сняты с продажи (RETIRED_ITEM_CODES), а не возвращены.

Услуги и мерч с ценами — по документу «Магазин и мерч IThub» (октябрь 2026):
активный студент копит около 80 монет в неделю, мелочь выкупается за
неделю-две, футболка — за полтора месяца, худи — за семестр.

Косметика разложена по слотам (ShopItem.slot): рамка, свечение и баннер
профиля надеваются независимо друг от друга.
"""

from __future__ import annotations

from apps.shop.models import ShopItemSlot, ShopItemType

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
        "slot": ShopItemSlot.AVATAR_FRAME,
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
        "slot": ShopItemSlot.BADGE_GLOW,
        "price_coins": 40,
    },
    {
        "code": "service-cv",
        "title": "Разбор резюме",
        "description": "Разбор резюме с наставником колледжа.",
        "item_type": ShopItemType.SERVICE,
        "price_coins": 75,
    },
    {
        "code": "service-mentor",
        "title": "Консультация преподавателя",
        "description": "Дополнительные 30 минут с преподавателем по теме на выбор.",
        "item_type": ShopItemType.SERVICE,
        "price_coins": 100,
    },
    {
        "code": "service-lunch",
        "title": "Бесплатный обед",
        "description": "Обед в столовой колледжа на 300 ₽.",
        "item_type": ShopItemType.SERVICE,
        "price_coins": 400,
    },
    {
        "code": "merch-sticker",
        "title": "Стикерпак IThub",
        "description": "Набор стикеров с символикой колледжа. Выдаётся в учебной части.",
        "item_type": ShopItemType.OTHER,
        "price_coins": 80,
    },
    {
        "code": "merch-laptop-stickers",
        "title": "Наклейки на ноутбук",
        "description": "Пак из 5–6 наклеек. Выдаётся в учебной части.",
        "item_type": ShopItemType.OTHER,
        "price_coins": 60,
    },
    {
        "code": "merch-notebook",
        "title": "Блокнот A5",
        "description": "Блокнот с символикой IThub. Выдаётся в учебной части.",
        "item_type": ShopItemType.OTHER,
        "price_coins": 150,
    },
    {
        "code": "merch-mousepad",
        "title": "Коврик для мыши",
        "description": "Коврик с символикой IThub. Выдаётся в учебной части.",
        "item_type": ShopItemType.OTHER,
        "price_coins": 150,
    },
    {
        "code": "merch-pin",
        "title": "Эмалевый значок",
        "description": "Металлический значок IThub. Выдаётся в учебной части.",
        "item_type": ShopItemType.OTHER,
        "price_coins": 150,
    },
    {
        "code": "merch-shopper",
        "title": "Шоппер",
        "description": "Сумка-шоппер IThub. Выдаётся в учебной части.",
        "item_type": ShopItemType.OTHER,
        "price_coins": 250,
    },
    {
        "code": "merch-cap",
        "title": "Кепка",
        "description": "Кепка с логотипом IThub. Выдаётся в учебной части.",
        "item_type": ShopItemType.OTHER,
        "price_coins": 250,
    },
    {
        "code": "merch-socks",
        "title": "Носки",
        "description": "Носки с символикой IThub. Выдаётся в учебной части.",
        "item_type": ShopItemType.OTHER,
        "price_coins": 250,
    },
    {
        "code": "merch-mug",
        "title": "Кружка «Путь Героя»",
        "description": "Кружка с символикой. Выдаётся в учебной части.",
        "item_type": ShopItemType.OTHER,
        "price_coins": 250,
    },
    {
        "code": "merch-powerbank",
        "title": "Power Bank",
        "description": "Внешний аккумулятор с логотипом IThub. Выдаётся в учебной части.",
        "item_type": ShopItemType.OTHER,
        "price_coins": 350,
    },
    {
        "code": "merch-bottle",
        "title": "Бутылка или термокружка",
        "description": "Бутылка или термокружка IThub на выбор. Выдаётся в учебной части.",
        "item_type": ShopItemType.OTHER,
        "price_coins": 350,
    },
    {
        "code": "merch-tshirt",
        "title": "Футболка",
        "description": "Футболка IThub. Выдаётся в учебной части.",
        "item_type": ShopItemType.OTHER,
        "price_coins": 500,
    },
    {
        "code": "merch-hoodie",
        "title": "Худи (лимитка с номером)",
        "description": "Худи ограниченного тиража с личным номером. Выдаётся в учебной части.",
        "item_type": ShopItemType.OTHER,
        "price_coins": 1000,
    },
    {
        "code": "merch-gaming-set",
        "title": "Игровая мышь и клавиатура",
        "description": "Игровой комплект: мышь и клавиатура. Выдаётся в учебной части.",
        "item_type": ShopItemType.OTHER,
        "price_coins": 2000,
    },
    {
        "code": "cosmetic-frame-gold",
        "title": "Золотая рамка",
        "description": "Золотая рамка вокруг аватара в профиле и рейтинге.",
        "item_type": ShopItemType.COSMETIC,
        "slot": ShopItemSlot.AVATAR_FRAME,
        "price_coins": 70,
    },
    {
        "code": "cosmetic-frame-neon",
        "title": "Неоновая рамка",
        "description": "Неоновая рамка вокруг аватара в профиле и рейтинге.",
        "item_type": ShopItemType.COSMETIC,
        "slot": ShopItemSlot.AVATAR_FRAME,
        "price_coins": 90,
    },
    {
        "code": "cosmetic-frame-flame",
        "title": "Пламенная рамка",
        "description": "Пламенная рамка вокруг аватара в профиле и рейтинге.",
        "item_type": ShopItemType.COSMETIC,
        "slot": ShopItemSlot.AVATAR_FRAME,
        "price_coins": 140,
    },
    {
        "code": "cosmetic-glow-gold",
        "title": "Золотое свечение",
        "description": "Закреплённый значок светится золотом.",
        "item_type": ShopItemType.COSMETIC,
        "slot": ShopItemSlot.BADGE_GLOW,
        "price_coins": 60,
    },
    {
        "code": "cosmetic-glow-rainbow",
        "title": "Радужное свечение",
        "description": "Закреплённый значок переливается радугой.",
        "item_type": ShopItemType.COSMETIC,
        "slot": ShopItemSlot.BADGE_GLOW,
        "price_coins": 110,
    },
    {
        "code": "banner-night",
        "title": "Ночной город",
        "description": "Фон шапки профиля: ночной город.",
        "item_type": ShopItemType.COSMETIC,
        "slot": ShopItemSlot.PROFILE_BANNER,
        "price_coins": 45,
    },
    {
        "code": "banner-sunset",
        "title": "Закат",
        "description": "Фон шапки профиля: закат.",
        "item_type": ShopItemType.COSMETIC,
        "slot": ShopItemSlot.PROFILE_BANNER,
        "price_coins": 45,
    },
    {
        "code": "banner-matrix",
        "title": "Матрица",
        "description": "Фон шапки профиля: поток символов.",
        "item_type": ShopItemType.COSMETIC,
        "slot": ShopItemSlot.PROFILE_BANNER,
        "price_coins": 80,
    },
    {
        "code": "banner-pixels",
        "title": "Пиксели",
        "description": "Фон шапки профиля: пиксельный узор.",
        "item_type": ShopItemType.COSMETIC,
        "slot": ShopItemSlot.PROFILE_BANNER,
        "price_coins": 60,
    },
    {
        "code": "banner-aurora",
        "title": "Северное сияние",
        "description": "Фон шапки профиля: северное сияние.",
        "item_type": ShopItemType.COSMETIC,
        "slot": ShopItemSlot.PROFILE_BANNER,
        "price_coins": 120,
    },
    {
        "code": "banner-gold",
        "title": "Легенда",
        "description": "Фон шапки профиля: золотой баннер для легенд.",
        "item_type": ShopItemType.COSMETIC,
        "slot": ShopItemSlot.PROFILE_BANNER,
        "price_coins": 200,
    },
    {
        "code": "boost-quest-x2",
        "title": "×2 монеты за квест",
        "description": "Монеты за следующий выполненный квест удваиваются.",
        "item_type": ShopItemType.BOOST,
        "slot": ShopItemSlot.BOOST,
        "price_coins": 40,
    },
)

# Товары, снятые с продажи: команда синхронизации их деактивирует, а не
# удаляет — на них могут ссылаться покупки, сделанные раньше.
RETIRED_ITEM_CODES: tuple[str, ...] = ("boost-xp-2h", "boost-coins-day")
