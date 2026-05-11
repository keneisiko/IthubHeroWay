from django.urls import path
from rest_framework_simplejwt.views import TokenObtainPairView, TokenRefreshView

from .views import DashboardView, MeProfileView, PublicProfileView
from .squads_views import SquadLeaderboardView, SquadMembersView, SquadMeView


urlpatterns = [
    path("auth/jwt/create/", TokenObtainPairView.as_view(), name="jwt-create"),
    path("auth/jwt/refresh/", TokenRefreshView.as_view(), name="jwt-refresh"),
    path("profile/me/", MeProfileView.as_view(), name="profile-me"),
    path("profile/<str:username>/", PublicProfileView.as_view(), name="profile-public"),
    path("dashboard/", DashboardView.as_view(), name="dashboard"),
    path("squads/me/", SquadMeView.as_view(), name="squads-me"),
    path("squads/leaderboard/", SquadLeaderboardView.as_view(), name="squads-leaderboard"),
    path("squads/<str:code>/members/", SquadMembersView.as_view(), name="squads-members"),
]

