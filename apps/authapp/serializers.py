import logging

from django.contrib.auth import get_user_model
from django.db.models import Q
from rest_framework import serializers
from rest_framework.exceptions import AuthenticationFailed
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from apps.integrations.services.lxp_auth import verify_lxp_credentials

User = get_user_model()
logger = logging.getLogger(__name__)


class AuthUserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ("id", "username", "email", "callsign", "role", "first_name", "last_name")


class LoginSerializer(TokenObtainPairSerializer):
    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        username_field = self.username_field
        if username_field in self.fields:
            self.fields[username_field].required = False
            self.fields[username_field].allow_blank = True
        self.fields["login"] = serializers.CharField(write_only=True)

    def validate(self, attrs):
        login = (attrs.get("login") or attrs.get(self.username_field) or "").strip()
        password = attrs.get("password") or ""
        if not login or not password:
            raise AuthenticationFailed("Invalid credentials.")

        user = (
            User.objects.filter(
                Q(username__iexact=login) | Q(email__iexact=login) | Q(callsign__iexact=login)
            )
            .order_by("id")
            .first()
        )
        if not user:
            raise AuthenticationFailed("Invalid credentials.")
        if user.login_blocked:
            raise AuthenticationFailed("Вход закрыт. Обратитесь к администратору.")
        if not user.email:
            raise AuthenticationFailed("User email is not configured for LXP verification.")

        ok, reason = verify_lxp_credentials(user.email, password)
        if not ok:
            raise AuthenticationFailed(reason)

        if not user.is_active:
            # Первый вход активирует аккаунт. Раньше импортированная карточка
            # открывалась только через /activate в боте — и к 21.10 так вошли
            # двое из 557. Бот проверяет ровно то же: учебную почту и пароль от
            # LXP, так что вход с верным паролем подтверждает личность не хуже.
            # Отключённых сотрудником отсекает login_blocked выше.
            user.is_active = True
            update_fields = ["is_active"]
            if user.status == "imported_lxp":
                user.status = "activated_web"
                update_fields.append("status")
            user.save(update_fields=update_fields)
            logger.info("Аккаунт %s активирован первым входом на сайт", user.username)

        refresh = self.get_token(user)
        data = {"refresh": str(refresh), "access": str(refresh.access_token)}
        data["user"] = AuthUserSerializer(user).data
        return data

