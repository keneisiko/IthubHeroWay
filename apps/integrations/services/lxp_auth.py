import logging
from typing import Tuple

import requests
from django.conf import settings
from django.contrib.auth import get_user_model

logger = logging.getLogger(__name__)


def verify_lxp_credentials(email: str, password: str) -> Tuple[bool, str]:
    """Проверить учебную почту и пароль в LXP.

    Если LXP не настроен, в разработке допускается запасной путь — проверка
    локального пароля Django. В продакшене такой откат недопустим: он молча
    превращает вход «через LXP» во вход по локальному паролю, о чём
    пользователю продолжают писать обратное.
    """
    # Раньше URL читался из окружения напрямую, в обход настроек, — получалось
    # два независимых источника одного и того же параметра.
    lxp_verify_url = (getattr(settings, "LXP_VERIFY_URL", "") or "").strip()
    lxp_graphql_endpoint = (getattr(settings, "LXP_GRAPHQL_ENDPOINT", "") or "").strip()

    # Preferred verification path for current LXP API.
    if lxp_graphql_endpoint:
        query = """
        query VerifySignIn($input: SignInInput!) {
          signIn(input: $input) {
            accessToken
            refreshToken
            user { id email }
          }
        }
        """
        try:
            response = requests.post(
                lxp_graphql_endpoint,
                json={"query": query, "variables": {"input": {"email": email, "password": password}}},
                headers={"Content-Type": "application/json"},
                timeout=12,
            )
        except requests.RequestException:
            return False, "LXP is temporarily unavailable."
        if response.status_code >= 400:
            return False, "LXP is temporarily unavailable."
        # WAF или страница-заглушка возвращают HTML — без защиты это 500
        # прямо на входе пользователя вместо понятного «LXP недоступен».
        try:
            body = response.json() if response.content else {}
        except ValueError:
            logger.warning("LXP вернул не JSON на проверку учётных данных (HTTP %s)", response.status_code)
            return False, "LXP временно недоступен, попробуйте позже."
        if body.get("errors"):
            return False, "Invalid LXP email/password."
        data = (body.get("data") or {}).get("signIn") or {}
        if data.get("accessToken"):
            return True, "verified"
        return False, "Invalid LXP email/password."

    if lxp_verify_url:
        try:
            response = requests.post(
                lxp_verify_url,
                json={"email": email, "password": password},
                timeout=8,
            )
        except requests.RequestException:
            return False, "LXP is temporarily unavailable."

        if response.status_code == 200:
            return True, "verified"
        return False, "Invalid LXP email/password."

    # Запасной путь только для разработки: в продакшене отсутствие настроек LXP —
    # это ошибка конфигурации, а не повод пускать по локальному паролю.
    if not settings.DEBUG:
        logger.error(
            "LXP не настроен (LXP_GRAPHQL_ENDPOINT/LXP_VERIFY_URL пусты), "
            "вход по локальному паролю в продакшене запрещён"
        )
        return False, "Вход временно недоступен: не настроена проверка учётных данных."

    User = get_user_model()
    user = User.objects.filter(email__iexact=email).first()
    if not user:
        return False, "No user with this email."
    if not user.check_password(password):
        return False, "Invalid email/password."
    return True, "verified"

