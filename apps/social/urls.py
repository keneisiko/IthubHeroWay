from django.urls import path

from .views import DuelAcceptView, DuelCreateView, DuelRejectView, MentorshipCreateView, RespectCreateView

urlpatterns = [
    path("social/respects/", RespectCreateView.as_view(), name="social-respects-create"),
    path("social/duels/", DuelCreateView.as_view(), name="social-duels-create"),
    path("social/duels/<int:duel_id>/accept/", DuelAcceptView.as_view(), name="social-duels-accept"),
    path("social/duels/<int:duel_id>/reject/", DuelRejectView.as_view(), name="social-duels-reject"),
    path("social/mentorships/", MentorshipCreateView.as_view(), name="social-mentorships-create"),
]

