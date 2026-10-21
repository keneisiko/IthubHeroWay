from rest_framework_simplejwt.authentication import JWTAuthentication, default_user_authentication_rule
from rest_framework_simplejwt.exceptions import AuthenticationFailed


def user_can_authenticate(user) -> bool:
    return default_user_authentication_rule(user) and not user.login_blocked


class AccountJWTAuthentication(JWTAuthentication):
    def get_user(self, validated_token):
        user = super().get_user(validated_token)
        if not user_can_authenticate(user):
            raise AuthenticationFailed(
                "Вход закрыт. Обратитесь к администратору.", code="user_blocked"
            )
        return user
