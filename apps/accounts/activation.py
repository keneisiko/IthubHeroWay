# Статусы карточки, заведённой импортом из LXP и ещё не тронутой. Импорт
# всего колледжа (lxp_group_import) статус не ставил вовсе — у 555 из 572
# неактивных студентов он пустой. Без него эти студенты не могли бы
# активироваться первым входом, а миграция 0010 закрыла бы им вход.
IMPORT_STATUSES = ("imported_lxp", "")


def is_unused_lxp_import(user) -> bool:
    return (
        not user.is_active
        and not user.login_blocked
        and user.role == "agent"
        and not user.is_staff
        and not user.is_superuser
        and user.status in IMPORT_STATUSES
        and bool((user.lxp_user_id or "").strip())
        and user.last_login is None
        and not user.has_usable_password()
        and not hasattr(user, "telegram_link")
        and not user.policy_acceptances.exists()
    )
