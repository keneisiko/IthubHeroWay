from django.apps import AppConfig


class OperationsConfig(AppConfig):
    default_auto_field = "django.db.models.BigAutoField"
    name = "apps.operations"
    verbose_name = "Операции"

    def ready(self):
        from django.core.signals import setting_changed

        from apps.operations.services.platform_settings import sync_with_overridden_settings

        setting_changed.connect(sync_with_overridden_settings, dispatch_uid="platform_settings_sync")
