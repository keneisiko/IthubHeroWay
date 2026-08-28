from django.urls import path

from .views import YouGileWebhookView

urlpatterns = [
    path("integrations/yougile/webhook/", YouGileWebhookView.as_view(), name="yougile-webhook"),
]

