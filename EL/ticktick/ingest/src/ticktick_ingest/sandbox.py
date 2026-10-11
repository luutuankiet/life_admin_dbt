"""Sandbox mutations for live tests, through the private API the web app uses.

Only for lists named ``zz-sandbox-ingest-*``: every call checks the name or the
project id it was handed back by ``create_list``. Never point these at real lists.

The calls run under a separate device id (the ``id`` field of ``X-Device``), the way
the capture harness did, so the server treats them as another client and pushes
``needSync`` to the listener's device.
"""

from __future__ import annotations

import json
import os
import secrets
import time
from typing import Any

import httpx

from .client import AuthRejected, TickTickConfig, _error_code

PREFIX = "zz-sandbox-ingest-"
SANDBOX_DEVICE_ID = "6ac90000aaaabbbbccccee13"


def object_id() -> str:
    """A 24-hex id shaped like the web app's: 8 hex of epoch seconds + 16 random hex."""
    return f"{int(time.time()):08x}{secrets.token_hex(8)}"


class Sandbox:
    def __init__(self, config: TickTickConfig, *, transport=None) -> None:
        headers = config.headers() | {"Content-Type": "application/json;charset=utf-8"}
        device = json.loads(config.x_device)
        device["id"] = SANDBOX_DEVICE_ID
        device["name"] = "ingest-sandbox"
        headers["X-Device"] = json.dumps(device, separators=(",", ":"))
        self.timezone = config.timezone
        self._projects: set[str] = set()
        self._http = httpx.Client(
            base_url=config.base_url, headers=headers, timeout=30.0, transport=transport
        )

    @classmethod
    def from_env(cls) -> Sandbox:
        return cls(TickTickConfig.from_env(dict(os.environ)))

    def close(self) -> None:
        self._http.close()

    def __enter__(self) -> Sandbox:
        return self

    def __exit__(self, *exc: object) -> None:
        self.close()

    def _post(self, path: str, body: Any) -> dict[str, Any]:
        response = self._http.post(path, json=body)
        if response.status_code == 401:
            raise AuthRejected(f"TickTick rejected the t cookie (401 {_error_code(response)})")
        response.raise_for_status()
        result = response.json()
        if result.get("id2error"):
            raise RuntimeError(f"{path} id2error: {result['id2error']}")
        return result

    def _own(self, project_id: str) -> None:
        if project_id not in self._projects:
            raise ValueError(f"{project_id} is not a sandbox list created by this session")

    def adopt(self, project_id: str) -> None:
        """Allow calls on a sandbox list created earlier (caller vouches for the name)."""
        self._projects.add(project_id)

    # lists ---------------------------------------------------------------
    def create_list(self, name: str) -> str:
        if not name.startswith(PREFIX):
            raise ValueError(f"sandbox list names must start with {PREFIX!r}")
        pid = object_id()
        body = {
            "add": [{"id": pid, "name": name, "inAll": True, "kind": "TASK",
                     "viewMode": "list", "sortOrder": 0}],
            "update": [],
            "delete": [],
        }
        self._post("/api/v2/batch/project", body)
        self._projects.add(pid)
        return pid

    def delete_list(self, project_id: str) -> None:
        self._own(project_id)
        self._post("/api/v2/batch/project", {"add": [], "update": [], "delete": [project_id]})
        self._projects.discard(project_id)

    # tasks ---------------------------------------------------------------
    def create_task(self, project_id: str, title: str, **fields: Any) -> dict[str, Any]:
        self._own(project_id)
        task = {
            "id": object_id(),
            "projectId": project_id,
            "title": title,
            "status": 0,
            "priority": 0,
            "sortOrder": 0,
            "timeZone": self.timezone,
            "items": [],
            "tags": [],
        } | fields
        result = self._post("/api/v2/batch/task", {"add": [task], "update": [], "delete": []})
        task["etag"] = result.get("id2etag", {}).get(task["id"])
        return task

    def update_task(self, task: dict[str, Any]) -> dict[str, Any]:
        """Send the whole task back with its changes, as the web app does."""
        self._own(task["projectId"])
        result = self._post("/api/v2/batch/task", {"add": [], "update": [task], "delete": []})
        return task | {"etag": result.get("id2etag", {}).get(task["id"])}

    def delete_task(self, project_id: str, task_id: str) -> None:
        """Move to trash (the web app's delete)."""
        self._own(project_id)
        body = {"add": [], "update": [], "delete": [{"taskId": task_id, "projectId": project_id}]}
        self._post("/api/v2/batch/task", body)

