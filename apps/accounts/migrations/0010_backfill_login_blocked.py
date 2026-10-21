from django.contrib.auth.hashers import is_password_usable
from django.db import migrations


def block_previously_disabled_accounts(apps, schema_editor):
    # Keep this predicate frozen: ambiguous legacy imports require staff review.
    User = apps.get_model("accounts", "User")
    users = User.objects.using(schema_editor.connection.alias)
    unused_imports = users.filter(
        is_active=False,
        login_blocked=False,
        role="agent",
        is_staff=False,
        is_superuser=False,
        status="imported_lxp",
        last_login__isnull=True,
        telegram_link__isnull=True,
        policy_acceptances__isnull=True,
    ).values_list("pk", "lxp_user_id", "password")
    unused_import_ids = [
        pk
        for pk, lxp_user_id, password in unused_imports.iterator()
        if (lxp_user_id or "").strip() and not is_password_usable(password)
    ]
    users.filter(is_active=False, login_blocked=False).exclude(
        pk__in=unused_import_ids
    ).update(login_blocked=True)


class Migration(migrations.Migration):
    dependencies = [
        ("accounts", "0009_user_login_blocked"),
        ("integrations", "0001_initial"),
    ]

    operations = [
        # Rollback must not reopen accounts or erase existing staff blocks.
        migrations.RunPython(block_previously_disabled_accounts, migrations.RunPython.noop),
    ]
