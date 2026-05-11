from django.urls import path

from .views import (
    ActiveQuestListView,
    MyQuestProgressListView,
    QuestCompleteView,
    QuestProgressUpdateView,
    QuestRewardHistoryView,
)

urlpatterns = [
    path("quests/active/", ActiveQuestListView.as_view(), name="quests-active"),
    path("quests/my-progress/", MyQuestProgressListView.as_view(), name="quests-my-progress"),
    path("quests/rewards/history/", QuestRewardHistoryView.as_view(), name="quests-reward-history"),
    path("quests/<str:code>/progress/", QuestProgressUpdateView.as_view(), name="quests-progress-update"),
    path("quests/<str:code>/complete/", QuestCompleteView.as_view(), name="quests-complete"),
]

