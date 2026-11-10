from django.contrib.auth.backends import ModelBackend

from apps.accounts.models import User


class AccountModelBackend(ModelBackend):
    def user_can_authenticate(self, user: User) -> bool:
        return super().user_can_authenticate(user) and not user.login_blocked
