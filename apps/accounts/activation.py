def is_unused_lxp_import(user) -> bool:
    return (
        not user.is_active
        and not user.login_blocked
        and user.role == "agent"
        and not user.is_staff
        and not user.is_superuser
        and user.status == "imported_lxp"
        and bool((user.lxp_user_id or "").strip())
        and user.last_login is None
        and not user.has_usable_password()
        and not hasattr(user, "telegram_link")
        and not user.policy_acceptances.exists()
    )
