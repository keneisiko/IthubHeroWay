"""Учебные группы LXP: список и состав.

Импорт студентов тянул весь колледж одним списком, без групп и курсов:
743 карточки, у которых не из чего собрать отряд. Для пилота на одной
группе нужен обратный порядок — сначала группа, потом её состав.
"""

from __future__ import annotations

import time

from apps.integrations.services.lxp_graphql_client import (
    LXPAuthError,
    LXPGraphQLClient,
    LXPRequestError,
)

# Сеть колледжа рвёт часть TLS-соединений к api.newlxp.ru (SSL EOF): один
# запрос проходит, следующий обрывается. Импорт группы из-за этого падал
# на середине, и его приходилось запускать заново вручную.
ATTEMPTS = 4
RETRY_PAUSE_SECONDS = 3


def _post_with_retry(client: LXPGraphQLClient, query: str, variables: dict, token: str, timeout: int):
    last_error: Exception | None = None
    for attempt in range(1, ATTEMPTS + 1):
        try:
            return client._post(query, variables, token=token, timeout=timeout)
        except (LXPRequestError, LXPAuthError) as e:
            last_error = e
            if attempt < ATTEMPTS:
                time.sleep(RETRY_PAUSE_SECONDS)
    raise LXPRequestError(f"{last_error} (после {ATTEMPTS} попыток)")

GROUP_STUDENTS_QUERY = """
query GroupStudents($input: SearchStudentsInLearningGroupInput!) {
  searchStudentsInLearningGroup(input: $input) {
    items {
      id
      user { id email firstName lastName middleName }
    }
  }
}
"""


def list_groups(client: LXPGraphQLClient | None = None) -> list[dict]:
    """Все неархивные учебные группы подорганизаций бот-аккаунта."""
    client = client or LXPGraphQLClient()
    token = client.get_token()

    me = _post_with_retry(client, client.GET_ME_SNAPSHOT_QUERY, {}, token, timeout=40)
    if me.errors:
        raise LXPRequestError(f"getMe: {me.errors}")
    assigned = ((me.data or {}).get("getMe") or {}).get("assignedSuborganizations") or []

    groups: list[dict] = []
    seen: set[str] = set()
    for slot in assigned:
        sub = slot.get("suborganization") or {}
        org_id = sub.get("organizationId")
        suborg_id = slot.get("suborganizationId") or sub.get("id")
        if not org_id or not suborg_id:
            continue
        response = _post_with_retry(
            client,
            client.GET_LEARNING_GROUPS_QUERY,
            {"input": {"organizationId": org_id, "suborganizationId": suborg_id, "isArchived": False}},
            token,
            timeout=60,
        )
        if response.errors:
            raise LXPRequestError(f"getLearningGroups: {response.errors}")
        for group in client._normalize_graphql_list((response.data or {}).get("getLearningGroups")):
            gid = str(group.get("id") or "")
            if not gid or gid in seen:
                continue
            seen.add(gid)
            groups.append({"id": gid, "name": (group.get("name") or "").strip(), "suborganization": sub.get("name") or ""})
    return groups


def group_students(group_id: str, client: LXPGraphQLClient | None = None) -> list[dict]:
    """Состав группы: отчисленные не в счёт — пилот на них не рассчитан."""
    client = client or LXPGraphQLClient()
    token = client.get_token()
    response = _post_with_retry(
        client,
        GROUP_STUDENTS_QUERY,
        {"input": {"filters": {"learningGroupId": group_id, "isExpelled": False}}},
        token,
        timeout=60,
    )
    if response.errors:
        raise LXPRequestError(f"searchStudentsInLearningGroup: {response.errors}")
    return client._normalize_graphql_list((response.data or {}).get("searchStudentsInLearningGroup"))


GROUP_CLASSES_QUERY = """
query GroupClasses($input: SearchClassesInput!) {
  searchClasses(input: $input) {
    total
    items {
      id
      from
      to
      discipline { name }
      learningGroupId
    }
  }
}
"""


def group_classes(group_id: str, start, end, client: LXPGraphQLClient | None = None) -> list[dict]:
    """Занятия группы за период: время начала, окончания и дисциплина.

    Из этого строится расписание отряда. Без него дедлайн «Утреннего
    чек-ина» брался общий — 10:00, — и студент, у которого первая пара
    в 12:50, получал опоздание, придя вовремя.
    """
    client = client or LXPGraphQLClient()
    token = client.get_token()
    response = _post_with_retry(
        client,
        GROUP_CLASSES_QUERY,
        {
            "input": {
                "filters": {
                    "interval": {"from": start.isoformat(), "to": end.isoformat()},
                    "learningGroupsIds": [group_id],
                }
            }
        },
        token,
        timeout=60,
    )
    if response.errors:
        raise LXPRequestError(f"searchClasses: {response.errors}")
    root = (response.data or {}).get("searchClasses") or {}
    return client._normalize_graphql_list(root.get("items"))


GROUP_CLASS_ATTENDANCE_QUERY = """
query GroupClassAttendance($input: SearchClassesInput!) {
  searchClasses(input: $input) {
    total
    items {
      id
      from
      to
      discipline { name }
      attendance { studentId status }
    }
  }
}
"""


def group_class_attendance(group_id: str, start, end, client: LXPGraphQLClient | None = None) -> list[dict]:
    """Занятия группы вместе с поимённым списком отметок.

    Из `studentDiscipline` посещаемость приходит одним процентом за семестр;
    здесь — кто был на каждой конкретной паре.
    """
    client = client or LXPGraphQLClient()
    token = client.get_token()
    response = _post_with_retry(
        client,
        GROUP_CLASS_ATTENDANCE_QUERY,
        {
            "input": {
                "filters": {
                    "interval": {"from": start.isoformat(), "to": end.isoformat()},
                    "learningGroupsIds": [group_id],
                }
            }
        },
        token,
        timeout=90,
    )
    if response.errors:
        raise LXPRequestError(f"searchClasses: {response.errors}")
    root = (response.data or {}).get("searchClasses") or {}
    return client._normalize_graphql_list(root.get("items"))
