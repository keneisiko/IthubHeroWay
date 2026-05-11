from django.urls import path

from .views import AgentLeaderboardView, RatingHistoryView, RatingMeView

urlpatterns = [
    path("rating/me/", RatingMeView.as_view(), name="rating-me"),
    path("rating/history/", RatingHistoryView.as_view(), name="rating-history"),
    path("leaderboard/agents/", AgentLeaderboardView.as_view(), name="leaderboard-agents"),
]

