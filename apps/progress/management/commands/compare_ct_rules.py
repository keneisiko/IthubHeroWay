"""Сравнение способов определить «актуальные КТ текущего семестра».

Пункт 3.1 Положения считает успеваемость по актуальным контрольным точкам
текущего семестра. Признака семестра в выгрузке LXP нет, и любой способ его
восстановить — приближение. Разные приближения дают разные деньги, поэтому
выбор делает колледж, а команда показывает цифры, на которых его делать.

    python manage.py compare_ct_rules
    python manage.py compare_ct_rules --date 2026-10-12

Команда ничего не меняет: только читает снимок и считает.

Правила:

1. «решённые» — действующее. Актуальны темы с вынесенным решением: сданные
   и возвращённые. Беда в том, что LXP держит тему в `NOT_PASSED_YET` до
   первой сдачи, поэтому у студента без возвращённых работ знаменатель равен
   числу сданных — и выходит 100% при двух сданных темах из ста.

2. «+проверка» — то же, плюс сданное на проверку считается несданным.
   Различает студентов, но наказывает за то, что преподаватель не успел
   проверить, и всё равно даёт 100% тем, у кого на проверке ничего нет.

3. «текущие дисциплины» — актуальны все темы тех дисциплин, по которым в
   этом семестре уже были занятия (в снимке у дисциплины `total` больше
   нуля). Ближе всего к букве пункта 3.1. Следствие: темы, до которых
   семестр ещё не дошёл, считаются несданными, поэтому в начале семестра
   процент у всех низкий и растёт к сессии.

4. «к норме курса» — доля сданного от ожидаемого к этой дате: всё число тем
   программы, умноженное на долю прошедших учебных недель. Не буква пункта
   3.1, зато прямо отвечает смыслу пункта 3.4 — оплачивается поддерживаемый
   темп.
"""

from __future__ import annotations

from datetime import date
from decimal import Decimal

from django.conf import settings
from django.core.management.base import BaseCommand, CommandError

from apps.accounts.models import Role, User
from apps.integrations.models import LXPSnapshot
from apps.integrations.services.account_gate import agents_for_scoring
from apps.integrations.services.lxp_snapshot_format import unwrap_category
from apps.progress.services.ct_status import is_topic_closed
from apps.progress.services.polozhenie_academic import is_future_topic, is_pending_topic
from apps.progress.services.polozhenie_period import quantize_money


def _topics(discipline) -> list[dict]:
    topics = discipline.get("topics") or []
    if isinstance(topics, dict):
        topics = list(topics.values())
    return [t for t in topics if isinstance(t, dict)] if isinstance(topics, list) else []


def _status(topic: dict):
    return topic.get("status") or topic.get("state")


def _percent(passed: int, actual: int) -> Decimal | None:
    if actual <= 0:
        return None
    return quantize_money(Decimal(min(passed, actual)) * 100 / Decimal(actual))


class Command(BaseCommand):
    help = "Считает успеваемость по четырём правилам определения актуальных КТ."

    def add_arguments(self, parser):
        parser.add_argument("--date", type=str, default="", help="Дата снимка (ГГГГ-ММ-ДД).")

    def handle(self, *args, **options):
        snap = self._snapshot(options["date"])
        raw = snap.data or {}
        ct_block = raw.get("control_points")
        if not isinstance(ct_block, dict) or not ct_block.get("ok"):
            raise CommandError(f"В снимке {snap.date} нет годных данных по КТ.")
        ct_data = unwrap_category(ct_block)
        att_data = unwrap_category(raw.get("attendance"))

        share = self._season_share(snap.date)
        self.stdout.write(
            self.style.MIGRATE_HEADING(
                f"\nСнимок {snap.date}. Прошло {round(share * 100, 1)}% учебного года "
                f"от {settings.POLOZHENIE_PERIOD['FULL_SEASON_WEEKS']} недель.\n"
            )
        )

        header = (
            f"{'Студент':<26}{'решённые':>10}{'+проверка':>11}"
            f"{'дисциплины':>12}{'к норме':>9}   {'тем всего':>9}{'сдано':>7}"
        )
        self.stdout.write(header)
        self.stdout.write("-" * len(header))

        audience = agents_for_scoring(User.objects.filter(role=Role.AGENT))
        totals: dict[str, list[Decimal]] = {"decided": [], "pending": [], "taught": [], "norm": []}

        for user in audience.order_by("last_name", "first_name"):
            uid = (user.lxp_user_id or "").strip()
            row = ct_data.get(uid)
            if not isinstance(row, dict) or not row:
                continue
            by_discipline = (att_data.get(uid) or {}).get("by_discipline") or {}
            rules = self._rules(row, by_discipline, share)

            for key, value in rules.items():
                if isinstance(value, Decimal):
                    totals[key].append(value)

            name = (user.get_full_name() or user.username)[:25]
            self.stdout.write(
                f"{name:<26}"
                f"{self._cell(rules['decided']):>10}"
                f"{self._cell(rules['pending']):>11}"
                f"{self._cell(rules['taught']):>12}"
                f"{self._cell(rules['norm']):>9}   "
                f"{rules['topics_total']:>9}{rules['passed']:>7}"
            )

        self._print_summary(totals)

    def _cell(self, value) -> str:
        return "—" if value is None else f"{value}"

    def _snapshot(self, raw_date: str) -> LXPSnapshot:
        if raw_date:
            try:
                target = date.fromisoformat(raw_date)
            except ValueError as exc:
                raise CommandError(f"Неверная дата: {raw_date}") from exc
            snap = LXPSnapshot.objects.filter(date=target).first()
        else:
            snap = LXPSnapshot.objects.order_by("-date").first()
        if snap is None:
            raise CommandError("Снимков LXP в базе нет.")
        return snap

    def _season_share(self, today: date) -> Decimal:
        """Какая доля учебного года прошла к дате снимка."""
        period = settings.POLOZHENIE_PERIOD
        year = today.year if today.month >= int(period["SEASON_START_MONTH"]) else today.year - 1
        start = date(year, int(period["SEASON_START_MONTH"]), int(period["SEASON_START_DAY"]))
        weeks_total = Decimal(str(period["FULL_SEASON_WEEKS"]))
        weeks_passed = Decimal((today - start).days) / Decimal("7")
        if weeks_passed <= 0:
            return Decimal("0")
        return min(Decimal("1"), weeks_passed / weeks_total)

    def _rules(self, row: dict, by_discipline: dict, share: Decimal) -> dict:
        passed = decided_open = pending = topics_total = 0
        taught_actual = taught_passed = 0

        for discipline_id, discipline in row.items():
            if not isinstance(discipline, dict):
                continue
            att = by_discipline.get(discipline_id) or {}
            lessons = att.get("total")
            is_taught = isinstance(lessons, (int, float)) and lessons > 0

            for topic in _topics(discipline):
                status = _status(topic)
                topics_total += 1
                closed = is_topic_closed(status)
                future = is_future_topic(status)
                waiting = is_pending_topic(status)

                if closed:
                    passed += 1
                elif waiting:
                    pending += 1
                elif not future:
                    decided_open += 1

                # Правило 3: всё, что входит в преподаваемую дисциплину,
                # кроме сданного на проверку.
                if is_taught and not waiting:
                    taught_actual += 1
                    if closed:
                        taught_passed += 1

        expected = int(Decimal(topics_total) * share)
        return {
            "decided": _percent(passed, passed + decided_open),
            "pending": _percent(passed, passed + decided_open + pending),
            "taught": _percent(taught_passed, taught_actual),
            "norm": _percent(passed, expected),
            "topics_total": topics_total,
            "passed": passed,
        }

    def _print_summary(self, totals: dict[str, list[Decimal]]) -> None:
        labels = {
            "decided": "1. решённые (сейчас)",
            "pending": "2. + на проверке",
            "taught": "3. текущие дисциплины",
            "norm": "4. к норме курса",
        }
        ct_max = Decimal(str(settings.POLOZHENIE_ACADEMIC["CT_WEEKLY_MAX"]))
        self.stdout.write(self.style.MIGRATE_HEADING("\nИтог по группе\n"))
        self.stdout.write(
            f"{'Правило':<26}{'медиана':>9}{'баллов':>8}{'на 100%':>9}{'у всех 100%':>13}"
        )
        for key, label in labels.items():
            values = sorted(totals[key])
            if not values:
                self.stdout.write(f"{label:<26}{'нет данных':>9}")
                continue
            median = values[len(values) // 2]
            full = sum(1 for v in values if v == 100)
            verdict = "да, негодно" if full > len(values) * 0.8 else "нет"
            self.stdout.write(
                f"{label:<26}{median:>9}{round(ct_max * median / 100, 2):>8}"
                f"{full:>9}{verdict:>13}"
            )
        self.stdout.write(
            "\nПравило меняется настройкой POLOZHENIE_CT_SCOPE — пока она не введена, "
            "действует правило 1. Выбор за колледжем: см. docs/POLOZHENIE.md."
        )
