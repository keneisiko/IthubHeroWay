from django.urls import path

from .views import BadgeAwardCheckView, BadgeHoldersView, BadgeListView, BadgePinView, MyBadgeListView

urlpatterns = [
    path("badges/", BadgeListView.as_view(), name="badges-list"),
    path("badges/my/", MyBadgeListView.as_view(), name="badges-my"),
    path("badges/award-check/", BadgeAwardCheckView.as_view(), name="badges-award-check"),
    path("badges/<str:code>/pin/", BadgePinView.as_view(), name="badges-pin"),
    path("badges/<str:code>/holders/", BadgeHoldersView.as_view(), name="badges-holders"),
]

