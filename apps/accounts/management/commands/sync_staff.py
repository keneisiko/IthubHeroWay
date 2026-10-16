"""Учётные записи персонала с правами по Положению.

Состав — пункт 11.2 Положения, права — по тому, что каждый подтверждает
(см. `apps/accounts/staff_roster.py`).

    python manage.py sync_staff --dry-run
    python manage.py sync_staff
    python manage.py sync_staff --reset-password dygova

Пароль печатается один раз при создании: в базе он хранится только хешем,
и восстановить его нельзя — можно лишь выдать новый. Пароль нужен для входа
в административную панель; в саму платформу персонал входит так же, как
студенты, — пароль проверяется в LXP.

Команда не удаляет и не понижает никого молча: если у существующей учётной
записи роль отличается от роспиcи, она меняется только с `--update-existing`,
а о расхождении команда сообщает.
"""

from __future__ import annotations

import secrets
import string

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.accounts.models import Role, User
from apps.accounts.staff_roster import ROLE_NOTES, STAFF

PASSWORD_ALPHABET = string.ascii_letters + string.digits + "!@#$%^&*-_"
PASSWORD_LENGTH = 16


def generate_password() -> str:
    return "".join(secrets.choice(PASSWORD_ALPHABET) for _ in range(PASSWORD_LENGTH))


def callsign_for(row: dict) -> str:
    """Позывной обязателен и уникален, но персоналу он не нужен по смыслу."""
    return f"staff-{row['username']}"


class Command(BaseCommand):
    help = "Создаёт и обновляет учётные записи персонала по пункту 11.2 Положения."

    def add_arguments(self, parser):
        parser.add_argument("--dry-run", action="store_true", help="Показать, что будет сделано.")
        parser.add_argument(
            "--update-existing",
            action="store_true",
            help="Привести роль, должность и права существующих записей к роспиcи.",
        )
        parser.add_argument(
            "--reset-password",
            type=str,
            default="",
            help="Выдать новый пароль одному сотруднику по логину.",
        )

    def handle(self, *args, **options):
        if options["reset_password"]:
            self._reset_password(options["reset_password"])
            return

        if options["dry_run"]:
            self._preview()
            return

        created, updated, skipped = self._sync(options["update_existing"])

        self.stdout.write(
            self.style.SUCCESS(
                f"\nСотрудников в роспиcи: {len(STAFF)}. Создано: {len(created)}, "
                f"обновлено: {updated}, без изменений: {skipped}."
            )
        )
        if created:
            self.stdout.write(
                self.style.WARNING(
                    "\nПароли показываются один раз — сохраните их и передайте лично.\n"
                )
            )
            self.stdout.write(f"{'Логин':<14}{'Пароль':<20}Сотрудник")
            for username, password, title in created:
                self.stdout.write(f"{username:<14}{password:<20}{title}")

        self._warn_about_guessed_emails()
        self.stdout.write(
            "\nВход в административную панель: https://hero.ithub-nalchik.ru/admin/\n"
            "Пароль смените после первого входа."
        )

    def _sync(self, update_existing: bool):
        created: list[tuple[str, str, str]] = []
        updated = 0
        skipped = 0

        with transaction.atomic():
            for row in STAFF:
                user = User.objects.filter(username=row["username"]).first()
                if user is None:
                    password = generate_password()
                    user = User.objects.create_user(
                        username=row["username"],
                        email=row["email"],
                        password=password,
                        callsign=callsign_for(row),
                        first_name=row["first_name"],
                        last_name=row["last_name"],
                        role=row["role"],
                        is_staff=True,
                        is_active=True,
                        is_superuser=bool(row.get("is_superuser")),
                        status=row["position"][:64],
                    )
                    created.append((user.username, password, self._title(row)))
                    continue

                changes = self._differences(user, row)
                if not changes:
                    skipped += 1
                    continue
                if not update_existing:
                    self.stdout.write(
                        self.style.WARNING(
                            f"{user.username}: расходится с роспиcью ({', '.join(changes)}). "
                            "Повторите с --update-existing, чтобы привести к роспиcи."
                        )
                    )
                    skipped += 1
                    continue

                user.first_name = row["first_name"]
                user.last_name = row["last_name"]
                user.email = row["email"]
                user.role = row["role"]
                user.is_staff = True
                user.is_active = True
                user.is_superuser = bool(row.get("is_superuser"))
                user.status = row["position"][:64]
                user.save(
                    update_fields=[
                        "first_name",
                        "last_name",
                        "email",
                        "role",
                        "is_staff",
                        "is_active",
                        "is_superuser",
                        "status",
                    ]
                )
                updated += 1
        return created, updated, skipped

    def _differences(self, user: User, row: dict) -> list[str]:
        diffs = []
        if user.role != row["role"]:
            diffs.append(f"роль {user.role} вместо {row['role']}")
        if bool(user.is_superuser) != bool(row.get("is_superuser")):
            diffs.append("полный доступ")
        if not user.is_staff:
            diffs.append("нет доступа в админку")
        if not user.is_active:
            diffs.append("вход закрыт")
        if (user.email or "").lower() != row["email"].lower():
            diffs.append("адрес почты")
        return diffs

    def _title(self, row: dict) -> str:
        middle = f" {row['middle_name']}" if row.get("middle_name") else ""
        return f"{row['last_name']} {row['first_name']}{middle}"

    def _preview(self) -> None:
        self.stdout.write(
            f"{'Логин':<14}{'Роль':<10}{'Полный':<8}{'Состояние':<16}Сотрудник и обязанности"
        )
        for row in STAFF:
            user = User.objects.filter(username=row["username"]).first()
            if user is None:
                state = "будет создан"
            else:
                diffs = self._differences(user, row)
                state = "совпадает" if not diffs else "расходится"
            full = "да" if row.get("is_superuser") else "—"
            self.stdout.write(
                f"{row['username']:<14}{row['role']:<10}{full:<8}{state:<16}"
                f"{self._title(row)} — {row['duties']}"
            )

        self.stdout.write("\nЧто даёт роль:")
        for role, note in ROLE_NOTES.items():
            self.stdout.write(f"  {Role(role).label:<12}{note}")
        self._warn_about_guessed_emails()

    def _warn_about_guessed_emails(self) -> None:
        guessed = [self._title(row) for row in STAFF if row.get("email_guessed")]
        if not guessed:
            return
        self.stdout.write(
            self.style.WARNING(
                "\nАдреса почты выведены по образцу и не подтверждены: "
                + ", ".join(guessed)
                + ".\nДля входа в админку это не важно, для входа в платформу — важно: "
                "пароль проверяется в LXP по адресу. Подтверждённые адреса "
                "подставьте в apps/accounts/staff_roster.py."
            )
        )

    def _reset_password(self, username: str) -> None:
        user = User.objects.filter(username=username).first()
        if user is None:
            raise CommandError(f"Сотрудник не найден: {username}")
        if not any(row["username"] == username for row in STAFF):
            raise CommandError(
                f"{username} не входит в роспись персонала — пароль через эту команду не выдаётся."
            )
        password = generate_password()
        user.set_password(password)
        user.save(update_fields=["password"])
        self.stdout.write(self.style.SUCCESS(f"Новый пароль для {username}: {password}"))
        self.stdout.write("Показан один раз. Передайте лично и смените после входа.")
