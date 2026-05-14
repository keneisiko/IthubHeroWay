from django.contrib.auth import get_user_model
from django.db.models import Q
from rest_framework import serializers
from rest_framework.exceptions import AuthenticationFailed
from rest_framework_simplejwt.serializers import TokenObtainPairSerializer

from apps.integrations.services.lxp_auth import verify_lxp_credentials


User = get_user_model()


class AuthUserSerializer(serializers.ModelSerializer):
    class Meta:
        model = User
        fields = ("id", "username", "email", "callsign", "role", "first_name", "last_name")


class LoginSerializer(TokenObtainPairSerializer):
    login = serializers.CharField(write_only=True)
    password = serializers.CharField(write_only=True)

    def validate(self, attrs):
        login = (attrs.get("login") or "").strip()
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
        if not user.is_active:
            raise AuthenticationFailed("User account is disabled.")
        if not user.email:
            raise AuthenticationFailed("User email is not configured for LXP verification.")

        ok, reason = verify_lxp_credentials(user.email, password)
        if not ok:
            raise AuthenticationFailed(reason)

        refresh = self.get_token(user)
        data = {"refresh": str(refresh), "access": str(refresh.access_token)}
        data["user"] = AuthUserSerializer(user).data
        return data

