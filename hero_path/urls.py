from django.contrib import admin
from django.urls import include, path

from hero_path.admin_site import setup_admin_site

setup_admin_site()
from drf_spectacular.views import SpectacularAPIView, SpectacularSwaggerView
from django_prometheus import exports
from apps.operations.health_views import HealthView, ReadyView
from apps.operations.admin_views import curator_dashboard, hq_dashboard, tutor_dashboard

urlpatterns = [
    path("admin/curator/", curator_dashboard, name="admin-curator-dashboard"),
    path("admin/tutor/", tutor_dashboard, name="admin-tutor-dashboard"),
    path("admin/hq/", hq_dashboard, name="admin-hq-dashboard"),
    path("admin/", admin.site.urls),
    path("schema/", SpectacularAPIView.as_view(), name="schema"),
    path("swagger/", SpectacularSwaggerView.as_view(url_name="schema"), name="swagger-ui"),
    path("health/", HealthView.as_view(), name="health"),
    path("ready/", ReadyView.as_view(), name="ready"),
    path("", include("django_prometheus.urls")),
    path("metrics/", exports.ExportToDjangoView, name="prometheus-metrics"),
    path("api/v1/", include("apps.accounts.urls")),  # профиль, auth, dashboard
    path("api/v1/", include("apps.authapp.urls")),
    path("api/v1/", include("apps.quests.urls")),
    path("api/v1/", include("apps.shop.urls")),
    path("api/v1/", include("apps.badges.urls")),
    path("api/v1/", include("apps.progress.urls")),
    path("api/v1/", include("apps.social.urls")),
    path("api/v1/", include("apps.integrations.urls")),
]

