"""Хранилище статики, устойчивое к записям вне манифеста.

`CompressedManifestStaticFilesStorage` требует, чтобы каждый путь, запрошенный
через `{% static %}`, был в манифесте, собранном collectstatic. Jazzmin строит
путь к теме из каталога (`vendor/bootswatch`), а каталогов в манифесте нет —
и админка отдавала 500 «Missing staticfiles manifest entry for
'vendor/bootswatch'». В dev этого не видно: там storage без манифеста.

`manifest_strict = False` переводит такие обращения на исходный путь без хеша:
файл отдаётся, страница работает, кеширование по хешу сохраняется для всего
остального.
"""

from __future__ import annotations

from whitenoise.storage import CompressedManifestStaticFilesStorage


class ForgivingManifestStaticFilesStorage(CompressedManifestStaticFilesStorage):
    manifest_strict = False
