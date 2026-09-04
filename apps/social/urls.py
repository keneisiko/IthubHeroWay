from django.urls import path

from .views import (
    DuelAcceptView,
    DuelCancelView,
    DuelCreateView,
    DuelListView,
    DuelRejectView,
    MentorshipCreateView,
    MentorshipEndView,
    MentorshipListView,
    RespectCreateView,
)

urlpatterns = [
    path("social/respects/", RespectCreateView.as_view(), name="social-respects-create"),
    path("social/duels/", DuelCreateView.as_view(), name="social-duels-create"),
    path("social/duels/my/", DuelListView.as_view(), name="social-duels-my"),
    path("social/duels/<int:duel_id>/accept/", DuelAcceptView.as_view(), name="social-duels-accept"),
    path("social/duels/<int:duel_id>/reject/", DuelRejectView.as_view(), name="social-duels-reject"),
    path("social/duels/<int:duel_id>/cancel/", DuelCancelView.as_view(), name="social-duels-cancel"),
    path("social/mentorships/", MentorshipCreateView.as_view(), name="social-mentorships-create"),
    path("social/mentorships/my/", MentorshipListView.as_view(), name="social-mentorships-my"),
    path(
        "social/mentorships/<int:mentorship_id>/end/",
        MentorshipEndView.as_view(),
        name="social-mentorships-end",
    ),
]
