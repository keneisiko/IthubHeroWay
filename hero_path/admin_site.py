"""Глобальные подписи стандартной админки Django."""


def setup_admin_site() -> None:
    from django.contrib import admin

    admin.site.site_header = "Путь героя IThub — администрирование"
    admin.site.site_title = "Админ-панель"
    admin.site.index_title = "Панель управления"
