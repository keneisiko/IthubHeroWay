"""Импорт одной учебной группы LXP в отряд.

`import_lxp_students` тянет весь колледж без деления на группы: для пилота
на одной группе 3 курса из такого списка отряд не собрать. Здесь наоборот —
сначала выбирается группа, затем её состав попадает в отряд.
"""

from __future__ import annotations

import re

from django.core.management.base import BaseCommand, CommandError
from django.db import transaction

from apps.accounts.models import Role, Squad, User
from apps.integrations.services.lxp_graphql_client import LXPAuthError, LXPRequestError
from apps.integrations.services.lxp_groups import group_students, list_groups


def _slug(raw: str, fallback: str) -> str:
    value = re.sub(r"[^a-z0-9._-]+", "_", (raw or "").strip().lower()).strip("._-")
    return value[:50] or fallback


class Command(BaseCommand):
    help = "Импортировать состав учебной группы LXP в отряд платформы"

    def add_arguments(self, parser):
        parser.add_argument("--list", action="store_true", help="Показать доступные группы и выйти")
        parser.add_argument("--group-id", type=str, default="", help="ID группы из --list")
        parser.add_argument("--squad-code", type=str, default="", help="Код отряда (латиницей)")
        parser.add_argument("--squad-name", type=str, default="", help="Название отряда; по умолчанию — имя группы")
        parser.add_argument("--course", type=int, default=0, help="Курс отряда, например 3")
        parser.add_argument("--dry-run", action="store_true", help="Показать, что произойдёт, ничего не записывая")

    def handle(self, *args, **options):
        try:
            if options["list"]:
                self._print_groups()
                return
            self._import(options)
        except (LXPAuthError, LXPRequestError) as e:
            raise CommandError(f"LXP: {e}") from e

    def _print_groups(self):
        groups = list_groups()
        if not groups:
            self.stdout.write(self.style.WARNING("Групп не нашлось: у бот-аккаунта нет подорганизаций"))
            return
        for group in groups:
            suffix = f"  ({group['suborganization']})" if group["suborganization"] else ""
            self.stdout.write(f"{group['id']}  {group['name']}{suffix}")
        self.stdout.write(self.style.NOTICE(f"Всего групп: {len(groups)}"))

    def _import(self, options):
        group_id = (options["group_id"] or "").strip()
        if not group_id:
            raise CommandError("Укажите --group-id (список групп: --list)")
        course = int(options["course"] or 0)
        if not 1 <= course <= 4:
            raise CommandError("Укажите --course от 1 до 4")

        students = group_students(group_id)
        if not students:
            raise CommandError(f"В группе {group_id} нет действующих студентов")

        squad_code = _slug(options["squad_code"] or f"lxp-{group_id}", fallback=f"lxp_{group_id}"[:50])
        squad_name = (options["squad_name"] or "").strip() or f"Группа {group_id}"

        if options["dry_run"]:
            self.stdout.write(f"Отряд {squad_code} «{squad_name}», курс {course}: {len(students)} студентов")
            for item in students[:200]:
                user = item.get("user") or {}
                name = " ".join(filter(None, [user.get("lastName"), user.get("firstName")])) or user.get("id")
                self.stdout.write(f"  {name}  {user.get('email') or ''}")
            return

        with transaction.atomic():
            squad, squad_created = Squad.objects.get_or_create(
                code=squad_code, defaults={"name": squad_name, "course": course}
            )
            if not squad_created and (squad.name != squad_name or squad.course != course):
                squad.name, squad.course = squad_name, course
                squad.save(update_fields=["name", "course"])

            created = matched = 0
            for item in students:
                user_data = item.get("user") or {}
                lxp_user_id = str(user_data.get("id") or item.get("id") or "")
                email = (user_data.get("email") or "").strip().lower()
                first_name = (user_data.get("firstName") or "").strip()
                last_name = (user_data.get("lastName") or "").strip()

                # Импорт всего колледжа уже завёл карточки: ищем по id LXP,
                # иначе по почте, и только потом заводим новую.
                user = None
                if lxp_user_id:
                    user = User.objects.filter(lxp_user_id=lxp_user_id).first()
                if user is None and email:
                    user = User.objects.filter(email__iexact=email).first()

                if user is None:
                    user = self._create_user(lxp_user_id, email, first_name, last_name)
                    created += 1
                else:
                    matched += 1

                fields = []
                if user.squad_id != squad.id:
                    user.squad = squad
                    fields.append("squad")
                if lxp_user_id and user.lxp_user_id != lxp_user_id:
                    user.lxp_user_id = lxp_user_id
                    fields.append("lxp_user_id")
                if fields:
                    user.save(update_fields=fields)

        self.stdout.write(
            self.style.SUCCESS(
                f"Отряд {squad.code} «{squad.name}», курс {squad.course}: "
                f"{len(students)} студентов (новых карточек {created}, уже были {matched}). "
                "Вход открывается после привязки Telegram."
            )
        )

    def _create_user(self, lxp_user_id: str, email: str, first_name: str, last_name: str) -> User:
        base = _slug(email.split("@", 1)[0] if email else lxp_user_id, fallback="student")
        username = (f"{base}_{lxp_user_id[:8]}" if lxp_user_id else base)[:150]
        suffix = 1
        while User.objects.filter(username=username).exists():
            username = f"{username[:140]}_{suffix}"[:150]
            suffix += 1

        callsign = (f"lxp_{lxp_user_id[:12]}" if lxp_user_id else f"lxp_{base}")[:50]
        cs_suffix = 1
        while User.objects.filter(callsign=callsign).exists():
            callsign = f"{callsign[:45]}_{cs_suffix}"[:50]
            cs_suffix += 1

        user = User.objects.create(
            username=username,
            callsign=callsign,
            email=email,
            first_name=first_name,
            last_name=last_name,
            role=Role.AGENT,
            # Как и в import_lxp_students: карточка заводится закрытой,
            # вход открывает привязка Telegram.
            is_active=False,
            status="imported_lxp",
            lxp_user_id=lxp_user_id or None,
        )
        user.set_unusable_password()
        user.save(update_fields=["password"])
        return user
