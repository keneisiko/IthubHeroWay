from django.core.management.base import BaseCommand, CommandError

from apps.integrations.services.lxp_browser_token import BrowserTokenConfig, fetch_lxp_bearer_token
from apps.integrations.services.lxp_graphql_client import LXPGraphQLClient


class Command(BaseCommand):
    help = "Fetch LXP Bearer token via browser bot and save to Redis cache"

    def add_arguments(self, parser):
        parser.add_argument("--debug", action="store_true", help="Print diagnostic details on failure")

    def handle(self, *args, **options):
        client = LXPGraphQLClient()
        if not client.use_browser_token_bot:
            raise CommandError("Set LXP_USE_BROWSER_TOKEN_BOT=1 in env before running this command.")
        if not client.bot_email or not client.bot_password:
            raise CommandError(
                "LXP_BOT_EMAIL/LXP_BOT_PASSWORD are empty. "
                "Set them in environment (.env for local run) and retry."
            )
        debug = bool(options.get("debug"))
        try:
            token = fetch_lxp_bearer_token(
                BrowserTokenConfig(
                    web_base_url=client.browser_web_base_url,
                    login_url=client.browser_login_url,
                    graphql_host=client.browser_graphql_host,
                    email=client.bot_email,
                    password=client.bot_password,
                    headless=client.browser_headless,
                    timeout_ms=client.browser_timeout_ms,
                    debug=debug,
                )
            )
            from django.core.cache import cache

            cache.set(client.TOKEN_CACHE_KEY, token, timeout=client.token_ttl_seconds)
        # Отдельной ветки для LXPAuthError здесь нет: fetch_lxp_bearer_token
        # бросает BrowserTokenFetchError, и та ветка была недостижима.
        except Exception as e:
            raise CommandError(str(e)) from e
        self.stdout.write(self.style.SUCCESS(f"Token captured and cached. Length: {len(token)}"))
