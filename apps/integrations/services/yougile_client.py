from django.conf import settings
import requests


class YouGileClient:
    def __init__(self):
        self.base_url = (settings.YOUGILE_API_URL or "").rstrip("/")
        self.token = settings.YOUGILE_API_TOKEN

    def list_events(self) -> dict:
        if not self.base_url:
            return {"events": []}
        headers = {"Authorization": f"Bearer {self.token}"} if self.token else {}
        response = requests.get(f"{self.base_url}/events", headers=headers, timeout=10)
        response.raise_for_status()
        return response.json()

