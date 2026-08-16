from rest_framework import permissions
from rest_framework.response import Response
from rest_framework.views import APIView
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from .serializers import AuthUserSerializer, LoginSerializer
from .throttling import LoginIdentifierThrottle, LoginIPThrottle


class LoginView(TokenObtainPairView):
    serializer_class = LoginSerializer
    permission_classes = [permissions.AllowAny]
    # Пароль уходит на проверку в LXP, поэтому перебор здесь бьёт по учебному
    # порталу, а не только по нам.
    throttle_classes = [LoginIPThrottle, LoginIdentifierThrottle]


class RefreshView(TokenRefreshView):
    permission_classes = [permissions.AllowAny]
    throttle_classes = [LoginIPThrottle]


class MeView(APIView):
    permission_classes = [permissions.IsAuthenticated]

    def get(self, request):
        return Response(AuthUserSerializer(request.user).data)

