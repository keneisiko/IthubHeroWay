from django.contrib.auth.hashers import make_password
from django.db import connection
from django.db.migrations.executor import MigrationExecutor
from django.test import TransactionTestCase
from django.utils import timezone


class LegacyInactiveAccountBackfillTests(TransactionTestCase):
    def setUp(self):
        self.executor = MigrationExecutor(connection)
        self.latest_targets = self.executor.loader.graph.leaf_nodes()
        self.executor.migrate([("accounts", "0009_user_login_blocked")])
        self.addCleanup(self.restore_latest_migrations)
        old_apps = self.executor.loader.project_state(
            [
                ("accounts", "0009_user_login_blocked"),
                ("integrations", "0012_hikevent_unmatched"),
            ]
        ).apps
        self.User = old_apps.get_model("accounts", "User")
        self.PolicyAcceptance = old_apps.get_model("accounts", "PolicyAcceptance")
        self.TelegramAccountLink = old_apps.get_model("integrations", "TelegramAccountLink")
        self.sequence = 0

    def restore_latest_migrations(self):
        MigrationExecutor(connection).migrate(self.latest_targets)

    def create_import(self, **overrides):
        self.sequence += 1
        defaults = {
            "username": f"legacy_{self.sequence}",
            "callsign": f"legacy_{self.sequence}",
            "email": f"legacy_{self.sequence}@nalchik.ithub.ru",
            "password": make_password(None),
            "role": "agent",
            "is_active": False,
            "status": "imported_lxp",
            "lxp_user_id": f"legacy-lxp-{self.sequence}",
        }
        defaults.update(overrides)
        return self.User.objects.create(**defaults)

    def test_backfill_blocks_legacy_deactivations_but_preserves_unused_imports(self):
        unused_import = self.create_import()
        active_user = self.create_import(is_active=True, status="activated_web")
        existing_block = self.create_import(login_blocked=True)
        blocked_users = [
            self.create_import(status="activated_web"),
            self.create_import(status="activated_telegram"),
            self.create_import(status=""),
            self.create_import(status="disabled"),
            self.create_import(role="curator"),
            self.create_import(is_staff=True),
            self.create_import(is_superuser=True),
            self.create_import(lxp_user_id=None),
            self.create_import(lxp_user_id=""),
            self.create_import(lxp_user_id="   "),
            self.create_import(password=make_password("former-local-password")),
            self.create_import(last_login=timezone.now()),
        ]
        for link_active in (False, True):
            linked_user = self.create_import()
            self.TelegramAccountLink.objects.create(
                user=linked_user,
                telegram_user_id=1000 + linked_user.pk,
                telegram_chat_id=1000 + linked_user.pk,
                is_active=link_active,
            )
            blocked_users.append(linked_user)
        policy_user = self.create_import()
        self.PolicyAcceptance.objects.create(user=policy_user, version="1")
        blocked_users.append(policy_user)

        self.restore_latest_migrations()

        for user in blocked_users:
            with self.subTest(username=user.username):
                user.refresh_from_db()
                self.assertTrue(user.login_blocked)
                self.assertFalse(user.is_active)
        unused_import.refresh_from_db()
        self.assertFalse(unused_import.login_blocked)
        self.assertFalse(unused_import.is_active)
        active_user.refresh_from_db()
        self.assertFalse(active_user.login_blocked)
        self.assertTrue(active_user.is_active)
        existing_block.refresh_from_db()
        self.assertTrue(existing_block.login_blocked)

    def test_rollback_does_not_remove_staff_or_backfilled_blocks(self):
        existing_block = self.create_import(login_blocked=True)
        legacy_disabled = self.create_import(status="activated_web")
        self.restore_latest_migrations()

        MigrationExecutor(connection).migrate([("accounts", "0009_user_login_blocked")])

        existing_block.refresh_from_db()
        legacy_disabled.refresh_from_db()
        self.assertTrue(existing_block.login_blocked)
        self.assertTrue(legacy_disabled.login_blocked)
