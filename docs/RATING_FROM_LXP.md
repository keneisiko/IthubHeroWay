# Рейтинг из снимка LXP

Сервис: `apps.progress.services.lxp_rating_from_snapshot.apply_rating_from_lxp_snapshot`.

## Участники пересчёта

- Пользователи с заполненным `User.lxp_user_id` и активной привязкой Telegram (`TelegramAccountLink.is_active`).
- Коэффициенты: `hero_path/settings/rating_coefficients.py`, в рантайме через `django.conf.settings` (`RATING_KP`, `RATING_LIMITS`).

## Маппинг полей снимка

| Источник в `LXPSnapshot.data` | Условие | Действие | Коэффициент / лимит |
|------------------------------|---------|----------|---------------------|
| `control_points.data[lxp_user_id][discipline_id].topics[].status` | Тема считается закрытой, если в статусе есть подстрока (без регистра): `PASSED`, `DONE`, `SUCCESS`, `ACCEPTED`, `CLOSED`, `COMPLETE`, `ЗАЧТ`, `СДАН`, `APPROVED` | Закрытые / открытые темы суммируются | За кадр снимка: `+CT_ON_TIME` за каждую закрытую (потолок `LXP_SNAPSHOT_CT_POSITIVE_CAP`), `CT_NOT_SUBMITTED` за каждую открытую (пол `LXP_SNAPSHOT_CT_NEGATIVE_CAP`) |
| То же | После подсчёта открытых тем | Обновление `User.unclosed_ct_count` | Число открытых тем |
| То же | `unclosed_ct_count >= CT_UNCLOSED_BLOCK_THRESHOLD` | Потолок рейтинга | `min(rating, MAX_RATING_WHEN_BLOCKED)` |
| `attendance.data[lxp_user_id].has_attendance === false` | Один раз за проход на пользователя | Штраф | `ABSENCE_UNEXCUSED`, пол по модулю `LXP_SNAPSHOT_ABSENCE_CAP` |
| Блок `control_points.ok === false` или для пользователя нет записей по темам | Нет данных по КТ | Старый `unclosed_ct_count` не перезаписывается пустым объектом | — |

## Ограничения v1

- Нет журнала пар из `classesForStudentProfile` — правила опозданий (`LATE_*`) из снимка **не** применяются.
- Блок «Движ» (`RATING_DRIVE`) из снимка LXP **не** начисляется — только квесты и другие модули.
- Интерпретация статусов тем — эвристика; при смене enum на стороне LXP таблицу выше нужно обновить.

## Журнал

Каждое изменение фиксируется записью `RatingLog` с `source=system`, `source_id=<дата ISO снимка>`, текст причины усечён до 250 символов.
