from django.contrib.auth import get_user_model

from apps.integrations.models import TelegramAccountLink


def activate_telegram_account(
    *,
    email: str,
    telegram_user_id: int,
    telegram_chat_id: int,
    telegram_username: str,
) -> tuple[bool, str]:
    User = get_user_model()
    user = User.objects.filter(email__iexact=email).first()
    if not user:
        return False, "User with this email is not found in platform."

    TelegramAccountLink.objects.update_or_create(
        user=user,
        defaults={
            "telegram_user_id": telegram_user_id,
            "telegram_chat_id": telegram_chat_id,
            "telegram_username": telegram_username or "",
            "is_active": True,
        },
    )
    return True, f"Аккаунт активирован для {user.username}."

