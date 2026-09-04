"""Общие параметры запуска Playwright для браузерных интеграций (Hik, LXP).

Зачем модуль: портал hik-connectru отдаёт пустую страницу (≈1 КБ вместо 135 КБ),
если в user-agent есть «HeadlessChrome» — то есть дефолтный headless-режим
Playwright там не работает в принципе, а в Docker другого режима нет. Достаточно
подставить обычный user-agent, и страница рендерится нормально.

Настройки собраны здесь, чтобы обе интеграции запускали браузер одинаково
и починка не разъезжалась по файлам.
"""

from __future__ import annotations

# Обычный desktop-Chrome. Версия намеренно без минорных цифр: она попадает
# в UA большинства реальных браузеров и не выдаёт автоматизацию.
DEFAULT_USER_AGENT = (
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/145.0.0.0 Safari/537.36"
)

# --disable-blink-features=AutomationControlled убирает navigator.webdriver,
# по которому SPA тоже умеют отсекать ботов.
DEFAULT_LAUNCH_ARGS = [
    "--disable-blink-features=AutomationControlled",
    "--disable-dev-shm-usage",  # в Docker /dev/shm мал, Chromium падает без этого
    "--no-sandbox",  # контейнер работает не от root, песочница Chromium там недоступна
]

DEFAULT_VIEWPORT = {"width": 1440, "height": 900}


def launch_kwargs(*, headless: bool = True, extra_args: list[str] | None = None) -> dict:
    args = list(DEFAULT_LAUNCH_ARGS)
    if extra_args:
        args.extend(extra_args)
    return {"headless": headless, "args": args}


def context_kwargs(*, locale: str = "ru-RU", accept_downloads: bool = False, **extra) -> dict:
    kwargs = {
        "user_agent": DEFAULT_USER_AGENT,
        "locale": locale,
        "viewport": dict(DEFAULT_VIEWPORT),
    }
    if accept_downloads:
        kwargs["accept_downloads"] = True
    kwargs.update(extra)
    return kwargs


# Баннеры согласия на cookies. Отклоняем всё необязательное: аналитика порталу
# нужна, нам — нет, а баннер перекрывает форму входа.
COOKIE_REJECT_LABELS = (
    # На hik-connectru кнопки называются «Decline All» / «Accept All»:
    # без точного совпадения баннер оставался висеть поверх кнопки входа.
    "Decline All",
    "Отклонить все",
    "Reject",
    "Отклонить",
    "Decline",
    "Отказаться",
    "Only necessary",
    "Только необходимые",
)


def dismiss_cookie_banner(page) -> bool:
    """Закрыть баннер cookies, выбрав отказ от необязательных.

    Баннер перекрывает кнопку входа, а его кнопки живут вне формы, поэтому
    закрываем до заполнения полей. Отсутствие баннера — не ошибка.
    """
    for label in COOKIE_REJECT_LABELS:
        try:
            button = page.get_by_role("button", name=label, exact=False).first
            if button.count() and button.is_visible():
                button.click(timeout=3_000)
                page.wait_for_timeout(500)
                return True
        except Exception:
            continue
    return False
