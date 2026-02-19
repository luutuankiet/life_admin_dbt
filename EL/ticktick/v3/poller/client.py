from __future__ import annotations

import requests

from .models import CredentialProfile
from .schemas import TickTickDelta


class TickTickBatchClient:
    def __init__(self, profile: CredentialProfile, timeout_seconds: int = 30):
        self.profile = profile
        self.timeout_seconds = timeout_seconds
        self.session = requests.Session()
        self.session.headers.update(
            {
                "User-Agent": profile.user_agent,
                "X-Device": profile.x_device,
                "x-tz": profile.timezone,
                "hl": profile.locale,
                "Cookie": profile.cookie_header,
                "Accept": "application/json, text/plain, */*",
            }
        )
        if profile.csrf_header:
            self.session.headers["X-Csrftoken"] = profile.csrf_header

    def fetch_delta(self, checkpoint: int) -> TickTickDelta:
        url = f"{self.profile.base_url}/api/v3/batch/check/{checkpoint}"
        response = self.session.get(url, timeout=self.timeout_seconds)
        response.raise_for_status()
        payload = response.json()
        return TickTickDelta.model_validate(payload)