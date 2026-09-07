"""Учебные группы LXP: список и состав.

Импорт студентов тянул весь колледж одним списком, без групп и курсов:
743 карточки, у которых не из чего собрать отряд. Для пилота на одной
группе нужен обратный порядок — сначала группа, потом её состав.
"""

from __future__ import annotations

from apps.integrations.services.lxp_graphql_client import LXPGraphQLClient, LXPRequestError

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

    me = client._post(client.GET_ME_SNAPSHOT_QUERY, {}, token=token, timeout=40)
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
        response = client._post(
            client.GET_LEARNING_GROUPS_QUERY,
            {"input": {"organizationId": org_id, "suborganizationId": suborg_id, "isArchived": False}},
            token=token,
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
    response = client._post(
        GROUP_STUDENTS_QUERY,
        {"input": {"filters": {"learningGroupId": group_id, "isExpelled": False}}},
        token=token,
        timeout=60,
    )
    if response.errors:
        raise LXPRequestError(f"searchStudentsInLearningGroup: {response.errors}")
    return client._normalize_graphql_list((response.data or {}).get("searchStudentsInLearningGroup"))
