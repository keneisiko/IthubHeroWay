from dataclasses import dataclass

YELLOW_ZONE_MIN = 200
YELLOW_ZONE_MAX = 399


@dataclass(frozen=True)
class AntiCheatResult:
    can_increase_rating: bool
    hard_cap_rating: int | None  # если задано — выше этого рейтинга поднимать нельзя
    reason_code: str | None


UNCLOSED_TESTS_THRESHOLD = 2


def apply_unclosed_tests_rule(
    *,
    current_rating: int,
    unclosed_tests_count: int,
) -> AntiCheatResult:
    """
    Анти-накрутка (регламент): если 2+ незакрытых КТ,
    блокируем рост рейтинга выше жёлтой зоны.

    Потолок ставится независимо от текущего рейтинга. Прежнее условие
    `current_rating >= YELLOW_ZONE_MIN` оставляло лазейку: студент с рейтингом
    ниже жёлтой зоны мог одним крупным начислением перепрыгнуть потолок,
    потому что правило к нему просто не применялось.
    """
    if unclosed_tests_count >= UNCLOSED_TESTS_THRESHOLD:
        return AntiCheatResult(
            # Рост как таковой не запрещён — запрещён рост выше потолка.
            can_increase_rating=current_rating < YELLOW_ZONE_MAX,
            hard_cap_rating=YELLOW_ZONE_MAX,
            reason_code="many_unclosed_tests",
        )
    return AntiCheatResult(can_increase_rating=True, hard_cap_rating=None, reason_code=None)

