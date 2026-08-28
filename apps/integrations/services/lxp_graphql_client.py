from __future__ import annotations

import hashlib
import json
import logging
import time
from dataclasses import dataclass
from datetime import date

import requests
from django.conf import settings
from django.core.cache import cache

from .lxp_browser_token import BrowserTokenConfig, BrowserTokenFetchError, fetch_lxp_bearer_token

logger = logging.getLogger(__name__)


class LXPAuthError(RuntimeError):
    pass


class LXPRequestError(RuntimeError):
    pass


@dataclass(frozen=True)
class GraphQLResponse:
    data: dict
    errors: list | None = None


class LXPGraphQLClient:
    TOKEN_CACHE_KEY = "lxp:gql:token"
    # Блокировка на время входа, чтобы параллельные задачи не логинились
    # одновременно (а в браузерном режиме — не поднимали несколько Chromium).
    TOKEN_LOCK_KEY = "lxp:gql:token:lock"
    TOKEN_LOCK_TTL = 180
    CATEGORY_CANDIDATES = {
        "attendance": [
            "averageAttendanceStudentsAnalytics",
            "absenteeismStatisticsInCsvV2",
            "lateStudents",
        ],
        "control_points": [
            "scoresAnalytics",
            "studentsScoreStatisticsInCsvV2",
            "studentsScoreStatisticsInCsv",
        ],
        "grades": [
            "scoresAnalytics",
            "getDisciplineScoreJournal",
            "getStudentDisciplineScoreJournal",
        ],
        "course_progress": [
            "studentGroupProgress",
            "disciplineGroupProgress",
            "acceptedAndLearningStudents",
        ],
    }
    SEARCH_STUDENTS_PERFORMANCE_QUERY = """
    query StudentsPerformance($input: SearchStudentsInput!) {
      searchStudents(input: $input) {
        total
        totalPages
        page
        perPage
        hasMore
        items {
          id
          hasAttendance
          isLearning
          user {
            id
            email
            firstName
            lastName
          }
        }
      }
    }
    """

    # Запросы из рабочего каталога LXP (getMe → группы → дисциплины → studentDiscipline)
    GET_ME_SNAPSHOT_QUERY = """
    query SnapshotGetMe {
      getMe {
        id
        roles
        assignedSuborganizations {
          suborganizationId
          suborganization {
            id
            name
            organizationId
          }
        }
      }
    }
    """
    GET_LEARNING_GROUPS_QUERY = """
    query SnapshotLearningGroups($input: GetLearningGroupsInput!) {
      getLearningGroups(input: $input) {
        id
        name
      }
    }
    """
    DISCIPLINES_BY_GROUPS_QUERY = """
    query SnapshotDisciplinesByGroups($input: DisciplinesByGroupsInput!) {
      disciplinesByGroups(input: $input) {
        id
        name
        code
      }
    }
    """

    def __init__(self):
        self.endpoint = getattr(settings, "LXP_GRAPHQL_ENDPOINT", "").strip()
        self.static_token = getattr(settings, "LXP_API_TOKEN", "").strip()
        self.bot_email = getattr(settings, "LXP_BOT_EMAIL", "").strip()
        self.bot_password = getattr(settings, "LXP_BOT_PASSWORD", "").strip()
        self.token_ttl_seconds = int(getattr(settings, "LXP_TOKEN_TTL_SECONDS", 23 * 3600))
        self.use_browser_token_bot = bool(getattr(settings, "LXP_USE_BROWSER_TOKEN_BOT", False))
        self.browser_web_base_url = getattr(settings, "LXP_WEB_BASE_URL", "https://newlxp.ru").strip()
        self.browser_login_url = getattr(settings, "LXP_WEB_LOGIN_URL", "").strip() or self.browser_web_base_url
        self.browser_graphql_host = getattr(settings, "LXP_BROWSER_GRAPHQL_HOST", "api.newlxp.ru").strip()
        self.browser_headless = bool(getattr(settings, "LXP_BROWSER_HEADLESS", True))
        self.browser_timeout_ms = int(getattr(settings, "LXP_BROWSER_TIMEOUT_MS", 60000))

    def _post(self, query: str, variables: dict | None = None, token: str | None = None, timeout: int = 20) -> GraphQLResponse:
        if not self.endpoint:
            raise LXPRequestError("LXP_GRAPHQL_ENDPOINT is not configured")
        headers = {"Content-Type": "application/json"}
        if token:
            headers["Authorization"] = f"Bearer {token}"
        payload = {"query": query, "variables": variables or {}}
        try:
            resp = requests.post(self.endpoint, json=payload, headers=headers, timeout=timeout)
        except requests.RequestException as e:
            raise LXPRequestError(str(e)) from e
        if resp.status_code in (401, 403):
            # Токен отвергнут — выбрасываем его из кеша, иначе следующий вызов
            # возьмёт тот же протухший токен и будет получать 401 до истечения
            # TTL (почти сутки), а снимки за это время сохранятся пустыми.
            cache.delete(self.TOKEN_CACHE_KEY)
            raise LXPRequestError(f"HTTP {resp.status_code}: токен LXP отвергнут")
        if resp.status_code >= 400:
            # Тело ответа в текст исключения не кладём: оно уходит в Telegram-алерт
            # и может содержать токены и персональные данные. Для разбора хватает
            # кода ответа, тело пишем в лог.
            logger.warning("LXP HTTP %s на запрос (%s символов ответа)", resp.status_code, len(resp.text))
            raise LXPRequestError(f"LXP ответил HTTP {resp.status_code}")
        try:
            body = resp.json()
        except ValueError as e:
            raise LXPRequestError("LXP вернул не JSON") from e
        return GraphQLResponse(data=body.get("data") or {}, errors=body.get("errors"))

    def login(self) -> str:
        if not self.bot_email or not self.bot_password:
            raise LXPAuthError("LXP_BOT_EMAIL/LXP_BOT_PASSWORD are not configured")
    
        if self.use_browser_token_bot:
            return self.login_via_browser()
    
        # Правильная query для LXP (SignIn)
        query = """
        query SignIn($input: SignInInput!) {
            signIn(input: $input) {
                accessToken
                refreshToken
                user {
                    id
                    email
                }
            }
        }
        """
        
        variables = {
            "input": {
                "email": self.bot_email,
                "password": self.bot_password
            }
        }
        
        payload = {
            "query": query,
            "variables": variables,
            "operationName": "SignIn"
        }
        
        # Тело ответа сюда попадать не должно: оно содержит accessToken
        # и refreshToken, а текст исключения уходит в Telegram-алерт и в логи.
        try:
            response = requests.post(
                self.endpoint,
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=20
            )
        except requests.RequestException as e:
            raise LXPAuthError(f"LXP недоступен: {type(e).__name__}") from e

        if response.status_code >= 400:
            raise LXPAuthError(f"LXP ответил HTTP {response.status_code}")

        try:
            result = response.json()
        except ValueError as e:
            raise LXPAuthError("LXP вернул не JSON на запрос входа") from e

        # Из ошибок GraphQL берём только коды и сообщения, без расширений
        # и данных запроса.
        if result.get('errors'):
            reasons = "; ".join(
                str(err.get("message") or "unknown")[:120]
                for err in result["errors"][:3]
                if isinstance(err, dict)
            )
            raise LXPAuthError(f"LXP отклонил вход: {reasons or 'без сообщения'}")

        # Токен лежит в data.signIn.accessToken
        sign_in_data = result.get('data', {}).get('signIn', {})
        token = sign_in_data.get('accessToken')

        if not token:
            raise LXPAuthError(
                "В ответе LXP нет accessToken — проверьте LXP_BOT_EMAIL/LXP_BOT_PASSWORD"
            )

        # refresh-токен раньше сохранялся в кеш и больше нигде не читался:
        # мутации обновления в клиенте нет вовсе. Лишний секрет в Redis
        # без применения — только риск, поэтому не храним.
        cache.set(self.TOKEN_CACHE_KEY, token, timeout=self.token_ttl_seconds)
        cache.delete(self.TOKEN_LOCK_KEY)
        return token

    def login_via_browser(self) -> str:
        try:
            token = fetch_lxp_bearer_token(
                BrowserTokenConfig(
                    web_base_url=self.browser_web_base_url,
                    login_url=self.browser_login_url,
                    graphql_host=self.browser_graphql_host,
                    email=self.bot_email,
                    password=self.bot_password,
                    headless=self.browser_headless,
                    timeout_ms=self.browser_timeout_ms,
                )
            )
        except BrowserTokenFetchError as e:
            cache.delete(self.TOKEN_LOCK_KEY)
            raise LXPAuthError(f"Browser token fetch failed: {e}") from e
        cache.set(self.TOKEN_CACHE_KEY, token, timeout=self.token_ttl_seconds)
        cache.delete(self.TOKEN_LOCK_KEY)
        return token

    def get_token(self, *, force_refresh: bool = False) -> str:
        """Вернуть токен LXP, при необходимости выполнив вход.

        Вход защищён блокировкой: без неё это классический check-then-act —
        при промахе кеша каждый параллельный Celery-воркер шёл логиниться
        самостоятельно, а при `LXP_USE_BROWSER_TOKEN_BOT=1` каждый поднимал
        собственный Chromium. Несколько одновременных входов бот-аккаунта
        LXP выглядят подозрительно и рискуют его блокировкой.
        """
        if self.static_token:
            return self.static_token

        if not force_refresh:
            token = cache.get(self.TOKEN_CACHE_KEY)
            if token:
                return str(token)

        if not cache.add(self.TOKEN_LOCK_KEY, "1", self.TOKEN_LOCK_TTL):
            # Вход уже идёт в другом процессе — дождёмся его результата,
            # вместо того чтобы логиниться параллельно.
            deadline = time.monotonic() + self.TOKEN_LOCK_TTL
            while time.monotonic() < deadline:
                time.sleep(1)
                token = cache.get(self.TOKEN_CACHE_KEY)
                if token:
                    return str(token)
                if not cache.get(self.TOKEN_LOCK_KEY):
                    break

        try:
            return self.login()
        except LXPAuthError as e:
            # Снимаем блокировку сразу: держать её до истечения TTL значило бы
            # заставить остальные задачи ждать впустую.
            cache.delete(self.TOKEN_LOCK_KEY)
            from apps.integrations.services.telegram_alert import send_alert_to_admin

            send_alert_to_admin(
                title="Ошибка обновления токена LXP",
                message=(
                    f"Не удалось получить токен LXP:\n{e}\n\n"
                    f"Email: {self.bot_email}\nEndpoint: {self.endpoint}"
                ),
                error_type="auth",
                deduplicate_key="lxp_auth",
                is_critical=True,
            )
            raise

    def _cached_query(
        self,
        name: str,
        query: str,
        variables: dict,
        token: str,
        ttl_seconds: int = 3600,
        timeout: int = 40,
    ) -> dict:
        # Токен входит в ключ: ответы LXP зависят от того, под каким аккаунтом
        # сделан запрос, а раньше ключ строился только по имени, тексту запроса
        # и переменным — данные, полученные под одним аккаунтом, отдавались
        # под другим. В ключ идёт хеш токена, а не сам токен.
        token_fingerprint = hashlib.sha256((token or "").encode("utf-8")).hexdigest()[:16]
        key_seed = json.dumps(
            {"n": name, "q": query, "v": variables, "t": token_fingerprint},
            sort_keys=True,
            ensure_ascii=False,
        ).encode("utf-8")
        key = "lxp:gql:" + hashlib.sha256(key_seed).hexdigest()
        cached = cache.get(key)
        if cached is not None:
            return cached
        res = self._post(query, variables, token=token, timeout=timeout)
        if res.errors:
            raise LXPRequestError(f"GraphQL errors: {res.errors}")
        cache.set(key, res.data, timeout=ttl_seconds)
        return res.data

    def _schema_fields(self, token: str) -> list[dict]:
        query = """
        query QueryFields {
          __schema {
            queryType {
              fields {
                name
                args {
                  name
                  type {
                    kind
                    name
                    ofType {
                      kind
                      name
                      ofType {
                        kind
                        name
                      }
                    }
                  }
                }
                type {
                  kind
                  name
                  ofType {
                    kind
                    name
                    ofType {
                      kind
                      name
                    }
                  }
                }
              }
            }
          }
        }
        """
        data = self._cached_query("schema_query_fields", query, {}, token, ttl_seconds=12 * 3600)
        return (((data or {}).get("__schema") or {}).get("queryType") or {}).get("fields") or []

    @staticmethod
    def _type_chain(type_node: dict | None) -> list[dict]:
        chain: list[dict] = []
        node = type_node
        while node:
            chain.append({"kind": node.get("kind"), "name": node.get("name")})
            node = node.get("ofType")
        return chain

    def _build_zero_arg_query(self, field_name: str, field_type: dict) -> str:
        chain = self._type_chain(field_type)
        has_object = any(node.get("kind") == "OBJECT" for node in chain)
        if has_object:
            return f"query Auto_{field_name} {{ {field_name} {{ __typename }} }}"
        return f"query Auto_{field_name} {{ {field_name} }}"

    def _fetch_category_payload(self, category: str, token: str) -> dict:
        fields = self._schema_fields(token)
        by_name = {f.get("name"): f for f in fields if f.get("name")}
        for candidate in self.CATEGORY_CANDIDATES.get(category, []):
            info = by_name.get(candidate)
            if not info:
                continue
            # Skip fields with required args: we do not have stable args contract yet.
            args = info.get("args") or []
            required_args = []
            for arg in args:
                chain = self._type_chain(arg.get("type"))
                if any(n.get("kind") == "NON_NULL" for n in chain):
                    required_args.append(arg.get("name"))
            if required_args:
                continue
            query = self._build_zero_arg_query(candidate, info.get("type") or {})
            result = self._safe_cached_query(
                f"auto_{category}_{candidate}",
                query,
                {},
                token,
                ttl_seconds=6 * 3600,
            )
            if result.get("ok"):
                return {
                    "ok": True,
                    "field": candidate,
                    "data": result.get("data"),
                }
        return {
            "ok": False,
            "error": f"No zero-arg GraphQL field matched category '{category}'",
        }

    def _safe_cached_query(
        self,
        name: str,
        query: str,
        variables: dict,
        token: str,
        ttl_seconds: int = 3600,
        timeout: int = 40,
    ) -> dict:
        try:
            data = self._cached_query(name, query, variables, token, ttl_seconds=ttl_seconds, timeout=timeout)
            return {"ok": True, "data": data}
        except LXPRequestError as e:
            return {"ok": False, "error": str(e)}

    @staticmethod
    def _normalize_graphql_list(raw):
        if raw is None:
            return []
        if isinstance(raw, list):
            return raw
        if isinstance(raw, dict):
            return raw.get("items") or raw.get("nodes") or []
        return []

    @staticmethod
    def _escape_graphql_string(value: str) -> str:
        return json.dumps(value)[1:-1]

    def _build_group_student_discipline_query(self, discipline_ids: list[str]) -> str:
        lines: list[str] = []
        for idx, did in enumerate(discipline_ids):
            esc = self._escape_graphql_string(did)
            lines.append(
                f"""
      d{idx}: studentDiscipline(disciplineId: "{esc}") {{
        disciplineGrade
        disciplineGrade_V2
        scoreForAnsweredTasks
        maxScoreForAnsweredTasks
        disciplineAttendance {{
          visited
          total
          percent
        }}
        topics {{
          ... on StudentTopic {{
            status
            topicScore
            topic {{ id name }}
          }}
        }}
      }}
                """.strip()
            )
        inner = "\n".join(lines)
        return f"""
query SnapshotGroupStudents($input: SearchStudentsInLearningGroupInput!) {{
  searchStudentsInLearningGroup(input: $input) {{
    items {{
      id
      user {{ id lastName firstName middleName }}
      {inner}
    }}
  }}
}}
""".strip()

    def _build_group_student_discipline_query_minimal(self, discipline_ids: list[str]) -> str:
        lines: list[str] = []
        for idx, did in enumerate(discipline_ids):
            esc = self._escape_graphql_string(did)
            lines.append(
                f"""
      d{idx}: studentDiscipline(disciplineId: "{esc}") {{
        disciplineGrade
        disciplineGrade_V2
        scoreForAnsweredTasks
        maxScoreForAnsweredTasks
        disciplineAttendance {{
          visited
          total
          percent
        }}
      }}
                """.strip()
            )
        inner = "\n".join(lines)
        return f"""
query SnapshotGroupStudentsMinimal($input: SearchStudentsInLearningGroupInput!) {{
  searchStudentsInLearningGroup(input: $input) {{
    items {{
      id
      user {{ id lastName firstName middleName }}
      {inner}
    }}
  }}
}}
""".strip()

    def _merge_discipline_chunk(
        self,
        result: dict,
        discipline_ids: list[str],
        grades_by_user: dict[str, dict],
        control_points_by_user: dict[str, dict],
        discipline_attendance_by_user: dict[str, dict],
    ) -> None:
        data = (result.get("data") or {}) if result.get("ok") else {}
        root = data.get("searchStudentsInLearningGroup")
        if isinstance(root, dict):
            items = root.get("items") or []
        elif isinstance(root, list):
            items = root
        else:
            items = []

        for item in items:
            user = item.get("user") or {}
            uid = str(user.get("id") or "")
            if not uid:
                continue
            for idx, did in enumerate(discipline_ids):
                alias = f"d{idx}"
                sd = item.get(alias)
                if not sd:
                    continue
                grades_by_user.setdefault(uid, {})[did] = {
                    "disciplineGrade": sd.get("disciplineGrade"),
                    "disciplineGrade_V2": sd.get("disciplineGrade_V2"),
                    "scoreForAnsweredTasks": sd.get("scoreForAnsweredTasks"),
                    "maxScoreForAnsweredTasks": sd.get("maxScoreForAnsweredTasks"),
                }
                da = sd.get("disciplineAttendance") or {}
                if da:
                    discipline_attendance_by_user.setdefault(uid, {})[did] = {
                        "visited": da.get("visited"),
                        "total": da.get("total"),
                        "percent": da.get("percent"),
                    }
                topics = sd.get("topics") or []
                capped = topics[:80] if isinstance(topics, list) else []
                control_points_by_user.setdefault(uid, {})[did] = {"topics": capped}

    def _fetch_learning_groups_performance(self, token: str, cache_prefix: str) -> dict:
        """
        Успеваемость и КТ по цепочке из каталога запросов LXP
        (группы подорганизаций → дисциплины → studentDiscipline).
        """
        max_suborgs = int(getattr(settings, "LXP_SNAPSHOT_MAX_SUBORGS", 20))
        max_groups = int(getattr(settings, "LXP_SNAPSHOT_MAX_GROUPS", 50))
        chunk_size = max(1, int(getattr(settings, "LXP_SNAPSHOT_DISCIPLINES_PER_QUERY", 8)))

        me = self._safe_cached_query(
            f"{cache_prefix}_get_me",
            self.GET_ME_SNAPSHOT_QUERY,
            {},
            token,
            ttl_seconds=3600,
            timeout=60,
        )
        if not me.get("ok"):
            return {
                "me_query_ok": False,
                "assigned_suborganizations_count": 0,
                "ok": False,
                "error": me.get("error"),
                "grades": {},
                "control_points": {},
                "discipline_attendance": {},
                "groups_processed": 0,
                "errors": [str(me.get("error") or "")],
            }

        assigned = (((me.get("data") or {}).get("getMe") or {}).get("assignedSuborganizations")) or []
        if not assigned:
            return {
                "me_query_ok": True,
                "assigned_suborganizations_count": 0,
                "ok": True,
                "grades": {},
                "control_points": {},
                "discipline_attendance": {},
                "groups_processed": 0,
                "errors": [],
            }
        grades_by_user: dict[str, dict] = {}
        control_points_by_user: dict[str, dict] = {}
        discipline_attendance_by_user: dict[str, dict] = {}
        groups_processed = 0
        errors: list[str] = []

        for slot in assigned[:max_suborgs]:
            sub = slot.get("suborganization") or {}
            org_id = sub.get("organizationId")
            suborg_id = slot.get("suborganizationId") or sub.get("id")
            if not org_id or not suborg_id:
                continue

            lg = self._safe_cached_query(
                f"{cache_prefix}_lg_{org_id}_{suborg_id}",
                self.GET_LEARNING_GROUPS_QUERY,
                {"input": {"organizationId": org_id, "suborganizationId": suborg_id, "isArchived": False}},
                token,
                ttl_seconds=6 * 3600,
                timeout=60,
            )
            if not lg.get("ok"):
                errors.append(f"getLearningGroups:{lg.get('error')}")
                continue

            groups_raw = (lg.get("data") or {}).get("getLearningGroups")
            groups = self._normalize_graphql_list(groups_raw)

            for group in groups:
                if groups_processed >= max_groups:
                    break
                gid = group.get("id")
                if not gid:
                    continue

                dg = self._safe_cached_query(
                    f"{cache_prefix}_disc_{gid}",
                    self.DISCIPLINES_BY_GROUPS_QUERY,
                    {"input": {"groupIds": [gid]}},
                    token,
                    ttl_seconds=6 * 3600,
                    timeout=60,
                )
                disciplines: list[dict] = []
                if dg.get("ok"):
                    d_raw = (dg.get("data") or {}).get("disciplinesByGroups")
                    disciplines = self._normalize_graphql_list(d_raw)
                disc_ids = [str(d.get("id")) for d in disciplines if d.get("id")]

                if not disc_ids:
                    groups_processed += 1
                    continue

                for i in range(0, len(disc_ids), chunk_size):
                    chunk = disc_ids[i : i + chunk_size]
                    q = self._build_group_student_discipline_query(chunk)
                    res = self._safe_cached_query(
                        f"{cache_prefix}_sg_{gid}_d{i}",
                        q,
                        {"input": {"filters": {"learningGroupId": gid, "isExpelled": False}}},
                        token,
                        ttl_seconds=1800,
                        timeout=90,
                    )
                    if not res.get("ok"):
                        qm = self._build_group_student_discipline_query_minimal(chunk)
                        res = self._safe_cached_query(
                            f"{cache_prefix}_sgmin_{gid}_d{i}",
                            qm,
                            {"input": {"filters": {"learningGroupId": gid, "isExpelled": False}}},
                            token,
                            ttl_seconds=1800,
                            timeout=90,
                        )
                    if not res.get("ok"):
                        errors.append(f"searchStudentsInLearningGroup:{gid}:{res.get('error')}")
                        continue
                    self._merge_discipline_chunk(res, chunk, grades_by_user, control_points_by_user, discipline_attendance_by_user)

                groups_processed += 1

            if groups_processed >= max_groups:
                break

        has_catalog_rows = bool(grades_by_user or control_points_by_user or discipline_attendance_by_user)
        return {
            "me_query_ok": True,
            "assigned_suborganizations_count": len(assigned),
            "ok": has_catalog_rows or groups_processed > 0,
            "grades": grades_by_user,
            "control_points": control_points_by_user,
            "discipline_attendance": discipline_attendance_by_user,
            "groups_processed": groups_processed,
            "errors": errors,
        }

    def _fetch_students_performance(
        self,
        token: str,
        page_size: int = 50,
        max_pages: int = 20,
        cache_prefix: str = "",
    ) -> dict:
        students: list[dict] = []
        page = 1
        total_pages = 1
        prefix = f"{cache_prefix}_" if cache_prefix else ""
        while page <= total_pages and page <= max_pages:
            result = self._safe_cached_query(
                name=f"{prefix}students_performance_page_{page}_size_{page_size}",
                query=self.SEARCH_STUDENTS_PERFORMANCE_QUERY,
                variables={"input": {"page": page, "pageSize": page_size}},
                token=token,
                ttl_seconds=6 * 3600,
            )
            if not result.get("ok"):
                return {"ok": False, "error": result.get("error")}
            payload = ((result.get("data") or {}).get("searchStudents")) or {}
            page_items = payload.get("items") or []
            students.extend(page_items)
            total_pages = int(payload.get("totalPages") or total_pages or 1)
            has_more = bool(payload.get("hasMore"))
            if not has_more:
                break
            page += 1

        attendance = {}
        course_progress = {}
        for item in students:
            user = item.get("user") or {}
            uid = str(user.get("id") or item.get("id") or "")
            if not uid:
                continue
            attendance[uid] = {"has_attendance": bool(item.get("hasAttendance"))}
            course_progress[uid] = {"is_learning": item.get("isLearning")}

        return {
            "ok": True,
            "field": "searchStudents",
            "data": {
                "students_total_loaded": len(students),
                "students_pages_loaded": page,
                "attendance": attendance,
                "course_progress": course_progress,
            },
        }

    def fetch_all_data(self, date: date) -> dict:
        token = self.get_token()
        date_str = date.isoformat()

        catalog = self._fetch_learning_groups_performance(token, cache_prefix=date_str)
        students_performance = self._fetch_students_performance(
            token=token,
            page_size=50,
            max_pages=20,
            cache_prefix=date_str,
        )

        quick_att: dict = {}
        quick_cp: dict = {}
        if students_performance.get("ok"):
            spd = students_performance.get("data") or {}
            quick_att = spd.get("attendance") or {}
            quick_cp = spd.get("course_progress") or {}

        disc_att = catalog.get("discipline_attendance") or {}
        merged_att: dict[str, dict] = {}
        for uid in set(quick_att) | set(disc_att):
            row = dict(quick_att.get(uid) or {})
            if uid in disc_att:
                row["by_discipline"] = disc_att[uid]
            merged_att[str(uid)] = row

        grades_map = catalog.get("grades") or {}
        ct_map = catalog.get("control_points") or {}
        assigned_count = int(catalog.get("assigned_suborganizations_count") or 0)
        cat_errors = catalog.get("errors") or []
        gp = int(catalog.get("groups_processed") or 0)
        grades_ok = bool(catalog.get("me_query_ok")) and (
            assigned_count == 0 or bool(grades_map) or (gp > 0 and not cat_errors)
        )
        ct_ok = bool(catalog.get("me_query_ok")) and (
            assigned_count == 0 or bool(ct_map) or (gp > 0 and not cat_errors)
        )

        grades_block = {
            "ok": grades_ok,
            "field": "searchStudentsInLearningGroup.studentDiscipline",
            "data": grades_map,
        }
        if not grades_ok and cat_errors:
            grades_block["error"] = "; ".join(cat_errors[:8])

        control_points_block = {
            "ok": ct_ok,
            "field": "searchStudentsInLearningGroup.studentDiscipline.topics",
            "data": ct_map,
        }
        if not ct_ok and cat_errors:
            control_points_block["error"] = "; ".join(cat_errors[:8])

        attendance_ok = bool(students_performance.get("ok")) or bool(disc_att)
        attendance_block = {
            "ok": attendance_ok,
            "field": "searchStudents.hasAttendance+disciplineAttendance",
            "data": merged_att if attendance_ok else quick_att,
        }
        if not students_performance.get("ok") and not disc_att:
            attendance_block["error"] = students_performance.get("error")

        cp_quick_ok = bool(students_performance.get("ok"))
        course_progress_block = {
            "ok": cp_quick_ok,
            "field": "searchStudents.isLearning",
            "data": quick_cp,
        }
        if not cp_quick_ok:
            course_progress_block["error"] = students_performance.get("error")

        payload = {
            "date": date_str,
            "attendance": attendance_block,
            "control_points": control_points_block,
            "grades": grades_block,
            "course_progress": course_progress_block,
        }
        payload["meta"] = {
            "source": "graphql",
            "catalog_queries": "getMe→getLearningGroups→disciplinesByGroups→searchStudentsInLearningGroup",
            "partial": not all(
                payload[k].get("ok") for k in ("attendance", "control_points", "grades", "course_progress")
            ),
            "students_total_loaded": (students_performance.get("data") or {}).get("students_total_loaded", 0),
            "students_pages_loaded": (students_performance.get("data") or {}).get("students_pages_loaded", 0),
            "catalog_groups_processed": catalog.get("groups_processed", 0),
            "assigned_suborganizations_count": assigned_count,
            "catalog_errors": (catalog.get("errors") or [])[:12],
        }

        if not students_performance.get("ok") and not catalog.get("me_query_ok"):
            payload["meta"]["fallback_reason"] = students_performance.get("error") or catalog.get("error")

        if not any(
            [
                students_performance.get("ok"),
                catalog.get("me_query_ok"),
                grades_map,
                ct_map,
                disc_att,
            ]
        ):
            payload = {
                "date": date_str,
                "attendance": self._fetch_category_payload("attendance", token),
                "control_points": self._fetch_category_payload("control_points", token),
                "grades": self._fetch_category_payload("grades", token),
                "course_progress": self._fetch_category_payload("course_progress", token),
            }
            payload["meta"] = {
                "source": "graphql",
                "partial": not all(
                    payload[k].get("ok") for k in ("attendance", "control_points", "grades", "course_progress")
                ),
                "fallback_reason": "catalog_and_searchStudents_failed",
            }

        return payload

