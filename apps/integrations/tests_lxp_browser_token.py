"""Тесты чистых функций получения токена LXP через браузер.

Playwright здесь не запускается: `page`/`context` подменяются моками. Модуль
целиком был без тестов, при этом в нём живёт разбор чужих ответов и
автозаполнение формы входа — то место, где ошибка стоит блокировки бота на
портале за подозрение в переборе пароля.
"""

from unittest.mock import Mock

from django.test import SimpleTestCase

from apps.integrations.services.lxp_browser_token import (
    _extract_bearer,
    _extract_token_from_json,
    _force_fill_auth_inputs,
    _token_from_cookies,
    _token_from_web_storage,
)

# Формой похож на JWT, но подписан не нами — используется только как образец строки.
JWT = "eyJhbGciOiJIUzI1NiJ9.eyJzdWIiOiIxIn0.s1gn4tur3-_x"


class ExtractBearerTests(SimpleTestCase):
    def test_plain_token_is_accepted(self):
        self.assertEqual(_extract_bearer(JWT), JWT)

    def test_bearer_prefix_is_stripped(self):
        """В заголовке Authorization токен приходит с префиксом, в localStorage — без."""
        self.assertEqual(_extract_bearer(f"Bearer {JWT}"), JWT)
        self.assertEqual(_extract_bearer(f"  bearer   {JWT}  "), JWT)

    def test_empty_and_none_give_none(self):
        self.assertIsNone(_extract_bearer(None))
        self.assertIsNone(_extract_bearer(""))
        self.assertIsNone(_extract_bearer("   "))

    def test_values_without_three_segments_are_rejected(self):
        for raw in ("abc", "a.b", "a.b.c.d", "{}", "https://newlxp.ru/x"):
            with self.subTest(raw=raw):
                self.assertIsNone(_extract_bearer(raw))

    def test_any_three_dot_separated_segments_are_accepted(self):
        """Фиксирует текущее (дефектное) поведение: проверки на JWT нет.

        Регексп смотрит только на форму `a.b.c`, поэтому в токен проходит
        любое значение из localStorage подходящей формы — например версия
        сборки или идентификатор с дефисами. Тест стоит здесь, чтобы смена
        поведения была осознанной, а не случайной.
        """
        self.assertEqual(_extract_bearer("not-a-jwt.at-all.really"), "not-a-jwt.at-all.really")
        self.assertEqual(_extract_bearer("1.2.3"), "1.2.3")


class ExtractTokenFromJsonTests(SimpleTestCase):
    def test_token_is_found_in_nested_structure(self):
        """Портал прячет accessToken на разной глубине ответа GraphQL."""
        payload = {"data": {"signIn": {"user": {"id": "1"}, "accessToken": JWT}}}
        self.assertEqual(_extract_token_from_json(payload), JWT)

    def test_token_is_found_inside_lists(self):
        payload = {"items": [{"meta": {}}, {"auth": {"jwt": JWT}}]}
        self.assertEqual(_extract_token_from_json(payload), JWT)

    def test_bare_string_is_checked_too(self):
        self.assertEqual(_extract_token_from_json(JWT), JWT)

    def test_absent_token_gives_none(self):
        payload = {"data": {"signIn": None}, "errors": [{"message": "Invalid credentials"}]}
        self.assertIsNone(_extract_token_from_json(payload))

    def test_non_string_values_do_not_break_traversal(self):
        """В ответах встречаются числа и null рядом с ключом token."""
        payload = {"token": 123, "nested": {"count": None, "accessToken": JWT}}
        self.assertEqual(_extract_token_from_json(payload), JWT)


class TokenFromWebStorageTests(SimpleTestCase):
    def test_token_is_taken_from_storage_pairs(self):
        page = Mock()
        page.evaluate.return_value = [["theme", "dark"], ["access_token", JWT]]
        self.assertEqual(_token_from_web_storage(page), JWT)

    def test_storage_without_token_gives_none(self):
        page = Mock()
        page.evaluate.return_value = [["theme", "dark"], ["locale", "ru"]]
        self.assertIsNone(_token_from_web_storage(page))

    def test_empty_storage_gives_none(self):
        """`page.evaluate` возвращает None, если страница ещё не готова."""
        page = Mock()
        page.evaluate.return_value = None
        self.assertIsNone(_token_from_web_storage(page))


class TokenFromCookiesTests(SimpleTestCase):
    def test_token_is_taken_from_cookie_value(self):
        context = Mock()
        context.cookies.return_value = [
            {"name": "csrftoken", "value": "plain-value"},
            {"name": "auth", "value": f"Bearer {JWT}"},
        ]
        self.assertEqual(_token_from_cookies(context), JWT)

    def test_cookies_without_token_give_none(self):
        context = Mock()
        context.cookies.return_value = [{"name": "sessionid", "value": "abcdef"}]
        self.assertIsNone(_token_from_cookies(context))

    def test_cookie_without_value_key_does_not_crash(self):
        context = Mock()
        context.cookies.return_value = [{"name": "jwt"}]
        self.assertIsNone(_token_from_cookies(context))


def _page_with_frames(result, frames=()):
    """Мок страницы: `evaluate` отдаёт готовый результат JS-скрипта."""
    page = Mock()
    page.frames = list(frames)
    page.evaluate.return_value = result
    return page


class ForceFillAuthInputsTests(SimpleTestCase):
    def test_submit_false_is_passed_into_js_and_form_is_not_sent(self):
        """Форму отправляет вызывающий код, а не эта функция.

        Раньше вход уходил на портал трижды подряд (requestSubmit отсюда,
        клик по кнопке и Enter), и портал считал это перебором пароля.
        Проверяем, что при submit=False флаг доезжает до JS и в отчёте
        стоит submitted=False.
        """
        page = _page_with_frames(
            {"email_len": 5, "password_len": 8, "has_form": True, "submitted": False}
        )

        totals = _force_fill_auth_inputs(page, "a@b.ru", "secret42", submit=False)

        self.assertFalse(totals["submitted"])
        args = page.evaluate.call_args[0][1]
        self.assertEqual(args, ["a@b.ru", "secret42", False])

    def test_submit_true_is_passed_into_js(self):
        page = _page_with_frames(
            {"email_len": 5, "password_len": 8, "has_form": True, "submitted": True}
        )

        totals = _force_fill_auth_inputs(page, "a@b.ru", "secret42")

        self.assertTrue(totals["submitted"])
        self.assertEqual(page.evaluate.call_args[0][1][2], True)

    def test_lengths_are_maximum_across_frames(self):
        """Форма входа часто лежит во фрейме — берём лучший результат по всем."""
        frame = _page_with_frames({"email_len": 9, "password_len": 0, "has_form": True})
        page = _page_with_frames(
            {"email_len": 0, "password_len": 8, "has_form": False}, frames=[frame]
        )

        totals = _force_fill_auth_inputs(page, "a@b.ru", "secret42", submit=False)

        self.assertEqual(totals["email_len"], 9)
        self.assertEqual(totals["password_len"], 8)
        self.assertTrue(totals["has_form"])

    def test_failing_frame_does_not_break_the_rest(self):
        """Кросс-доменный фрейм бросает исключение на evaluate — это норма."""
        broken = Mock()
        broken.frames = []
        broken.evaluate.side_effect = Exception("cross-origin")
        page = _page_with_frames(
            {"email_len": 5, "password_len": 8, "has_form": True}, frames=[broken]
        )

        totals = _force_fill_auth_inputs(page, "a@b.ru", "secret42", submit=False)

        self.assertEqual(totals["password_len"], 8)

    def test_missing_keys_in_js_result_are_treated_as_zero(self):
        page = _page_with_frames({})

        totals = _force_fill_auth_inputs(page, "a@b.ru", "secret42", submit=False)

        self.assertEqual(
            totals, {"email_len": 0, "password_len": 0, "has_form": False, "submitted": False}
        )
