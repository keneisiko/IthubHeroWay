from django.conf import settings
import requests


class LXPClient:
    def __init__(self):
        self.base_url = (settings.LXP_VERIFY_URL or "").rstrip("/")
        self.token = settings.LXP_API_TOKEN

    def fetch_daily_snapshot(self) -> dict:
        if not self.base_url:
            return {"events": []}
        headers = {"Authorization": f"Bearer {self.token}"} if self.token else {}
        response = requests.get(f"{self.base_url}/daily-snapshot", headers=headers, timeout=10)
        response.raise_for_status()
        return response.json()

