from __future__ import annotations

import threading
from datetime import datetime, timezone

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse, PlainTextResponse
from sqlmodel import Session

from .auth import parse_curl_profile
from .config import PollerSettings
from .db import build_engine, init_db
from .repository import ReplicaRepository
from .schemas import ImportCurlRequest, PollControlRequest
from .service import PollerService, classify_poll_error


class LoopController:
    def __init__(self, service: PollerService):
        self.service = service
        self._thread: threading.Thread | None = None
        self._stop_event = threading.Event()
        self._lock = threading.Lock()
        self._context: dict[str, str | int | None] = {
            "account_id": None,
            "owner_id": None,
            "interval_seconds": None,
            "auth_pause_seconds": service.settings.auth_pause_seconds,
            "state": "stopped",
            "last_error": None,
            "last_tick_at": None,
        }

    def status(self) -> dict:
        with self._lock:
            return {
                "running": self._thread is not None and self._thread.is_alive(),
                **self._context,
            }

    def start(self, account_id: str, owner_id: str, interval_seconds: int) -> None:
        with self._lock:
            if self._thread is not None and self._thread.is_alive():
                raise RuntimeError("Loop already running")

            self._stop_event = threading.Event()
            self._context = {
                "account_id": account_id,
                "owner_id": owner_id,
                "interval_seconds": interval_seconds,
                "auth_pause_seconds": self.service.settings.auth_pause_seconds,
                "state": "running",
                "last_error": None,
                "last_tick_at": None,
            }
            self._thread = threading.Thread(
                target=self._worker,
                args=(account_id, owner_id, interval_seconds),
                daemon=True,
            )
            self._thread.start()

    def stop(self) -> None:
        with self._lock:
            if self._thread is None:
                return
            self._stop_event.set()
            thread = self._thread

        thread.join(timeout=5)

        with self._lock:
            self._thread = None
            self._context["state"] = "stopped"

    def _worker(self, account_id: str, owner_id: str, interval_seconds: int) -> None:
        while not self._stop_event.is_set():
            wait_seconds = interval_seconds
            try:
                self.service.run_once(account_id=account_id, owner_id=owner_id)
                with self._lock:
                    self._context["state"] = "running"
                    self._context["last_error"] = None
            except Exception as exc:  # noqa: BLE001
                status = classify_poll_error(exc)
                if status == "auth_required":
                    wait_seconds = self.service.settings.auth_pause_seconds

                with self._lock:
                    self._context["state"] = status
                    self._context["last_error"] = str(exc)

            finally:
                with self._lock:
                    self._context["last_tick_at"] = datetime.now(timezone.utc).isoformat()

            if self._stop_event.wait(wait_seconds):
                break


def _serialize_cycle(cycle) -> dict:
    return {
        "id": cycle.id,
        "account_id": cycle.account_id,
        "owner_id": cycle.owner_id,
        "status": cycle.status,
        "source_checkpoint": cycle.source_checkpoint,
        "response_checkpoint": cycle.response_checkpoint,
        "updates_count": cycle.updates_count,
        "deletes_count": cycle.deletes_count,
        "projects_count": cycle.projects_count,
        "groups_count": cycle.groups_count,
        "started_at": cycle.started_at.isoformat() if cycle.started_at else None,
        "finished_at": cycle.finished_at.isoformat() if cycle.finished_at else None,
        "error_message": cycle.error_message,
    }


def _build_status_payload(engine, account_id: str, loop_status: dict) -> dict:
    with Session(engine) as session:
        repo = ReplicaRepository(session)
        profile = repo.get_active_profile(account_id)
        state = repo.get_checkpoint_state(account_id)
        lease = repo.get_lease(account_id)
        counts = repo.get_row_counts(account_id)
        latest_cycles = repo.list_cycles(account_id, limit=1)

    latest_cycle = _serialize_cycle(latest_cycles[0]) if latest_cycles else None

    return {
        "account_id": account_id,
        "active_profile": {
            "id": profile.id,
            "created_at": profile.created_at.isoformat(),
            "updated_at": profile.updated_at.isoformat(),
        }
        if profile
        else None,
        "checkpoint": {
            "value": state.checkpoint,
            "last_status": state.last_status,
            "last_error": state.last_error,
            "error_streak": state.error_streak,
            "updated_at": state.updated_at.isoformat() if state.updated_at else None,
            "last_success_at": state.last_success_at.isoformat() if state.last_success_at else None,
        },
        "lease": {
            "owner_id": lease.owner_id,
            "lease_until": lease.lease_until.isoformat(),
            "heartbeat_at": lease.heartbeat_at.isoformat(),
        }
        if lease
        else None,
        "replica_counts": counts,
        "latest_cycle": latest_cycle,
        "loop": loop_status,
    }


def _compute_state_gauge(status_payload: dict) -> int:
    loop = status_payload.get("loop", {})
    checkpoint = status_payload.get("checkpoint", {})

    loop_state = str(loop.get("state") or "")
    checkpoint_status = str(checkpoint.get("last_status") or "")
    running = bool(loop.get("running"))

    if loop_state == "auth_required" or checkpoint_status == "auth_required":
        return 2
    if loop_state in {"degraded", "error"} or checkpoint_status == "error":
        return 1
    if not running:
        return 3
    return 0


def _render_metrics(status_payload: dict) -> str:
    account_id = str(status_payload.get("account_id", "default")).replace('"', '\\"')
    value = _compute_state_gauge(status_payload)
    loop_running = "1" if status_payload.get("loop", {}).get("running") else "0"
    lines = [
        "# HELP ticktick_poller_state Poller state gauge. 0=running 1=degraded 2=auth_required 3=stopped",
        "# TYPE ticktick_poller_state gauge",
        f'ticktick_poller_state{{account_id="{account_id}",loop_running="{loop_running}"}} {value}',
    ]
    return "\n".join(lines) + "\n"


def create_app() -> FastAPI:
    settings = PollerSettings.from_env()
    engine = build_engine(settings)
    init_db(engine)
    service = PollerService(settings, engine)
    loop_controller = LoopController(service)

    app = FastAPI(title="TickTick v3 Operator", version="0.1.0")

    @app.get("/health")
    def health() -> dict:
        return {"status": "ok"}

    @app.get("/metrics", response_class=PlainTextResponse)
    def metrics(account_id: str = "default") -> str:
        payload = _build_status_payload(engine, account_id, loop_controller.status())
        return _render_metrics(payload)

    @app.get("/", response_class=HTMLResponse)
    def home() -> str:
        return """
<!doctype html>
<html>
<head>
  <meta charset=\"utf-8\" />
  <title>TickTick v3 Operator</title>
  <style>
    body { font-family: sans-serif; margin: 24px; max-width: 980px; }
    textarea { width: 100%; height: 180px; }
    input, button { padding: 8px; margin: 4px 0; }
    .row { margin-bottom: 20px; }
    pre { background: #f5f5f5; padding: 12px; overflow: auto; }
  </style>
</head>
<body>
  <h1>TickTick v3 Operator</h1>

  <div class=\"row\">
    <h3>Import Curl Profile</h3>
    <input id=\"account\" value=\"default\" placeholder=\"account id\" />
    <textarea id=\"curl\" placeholder=\"paste copy-as-curl here\"></textarea>
    <button onclick=\"importCurl()\">Import</button>
  </div>

  <div class=\"row\">
    <h3>Poller Controls</h3>
    <input id=\"owner\" value=\"web\" placeholder=\"owner id\" />
    <input id=\"interval\" value=\"30\" placeholder=\"interval seconds\" />
    <button onclick=\"runOnce()\">Run Once</button>
    <button onclick=\"startLoop()\">Start Loop</button>
    <button onclick=\"stopLoop()\">Stop Loop</button>
    <button onclick=\"loadStatus()\">Refresh Status</button>
  </div>

  <div class=\"row\">
    <h3>Status</h3>
    <pre id=\"status\">loading...</pre>
  </div>

<script>
async function importCurl() {
  const body = {
    account_id: document.getElementById('account').value,
    curl_text: document.getElementById('curl').value
  };
  const res = await fetch('/profiles/import-curl', {
    method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(body)
  });
  alert(await res.text());
  loadStatus();
}

async function runOnce() {
  const body = {
    account_id: document.getElementById('account').value,
    owner_id: document.getElementById('owner').value
  };
  const res = await fetch('/poll/run-once', {
    method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(body)
  });
  document.getElementById('status').textContent = await res.text();
}

async function startLoop() {
  const body = {
    account_id: document.getElementById('account').value,
    owner_id: document.getElementById('owner').value,
    interval_seconds: Number(document.getElementById('interval').value)
  };
  const res = await fetch('/poll/start', {
    method: 'POST', headers: {'Content-Type': 'application/json'}, body: JSON.stringify(body)
  });
  alert(await res.text());
  loadStatus();
}

async function stopLoop() {
  const res = await fetch('/poll/stop', {method: 'POST'});
  alert(await res.text());
  loadStatus();
}

async function loadStatus() {
  const account = document.getElementById('account').value || 'default';
  const res = await fetch('/status?account_id=' + encodeURIComponent(account));
  const data = await res.json();
  document.getElementById('status').textContent = JSON.stringify(data, null, 2);
}

loadStatus();
</script>
</body>
</html>
"""

    @app.post("/profiles/import-curl")
    def import_curl(payload: ImportCurlRequest) -> dict:
        profile_in = parse_curl_profile(payload.curl_text, account_id=payload.account_id)
        with Session(engine) as session:
            repo = ReplicaRepository(session)
            profile = repo.upsert_active_profile(profile_in)

        return {"ok": True, "profile_id": profile.id, "account_id": payload.account_id}

    @app.get("/status")
    def status(account_id: str = "default") -> dict:
        return _build_status_payload(engine, account_id, loop_controller.status())

    @app.get("/cycles")
    def cycles(account_id: str = "default", limit: int = 50) -> dict:
        with Session(engine) as session:
            repo = ReplicaRepository(session)
            rows = repo.list_cycles(account_id, limit=min(limit, 200))
        return {"account_id": account_id, "items": [_serialize_cycle(row) for row in rows]}

    @app.post("/poll/run-once")
    def poll_run_once(payload: PollControlRequest) -> dict:
        summary = service.run_once(account_id=payload.account_id, owner_id=payload.owner_id)
        return summary.model_dump()

    @app.post("/poll/start")
    def poll_start(payload: PollControlRequest) -> dict:
        interval = payload.interval_seconds or settings.poll_interval_seconds
        try:
            loop_controller.start(payload.account_id, payload.owner_id, interval)
        except RuntimeError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        return {"ok": True, "running": True}

    @app.post("/poll/stop")
    def poll_stop() -> dict:
        loop_controller.stop()
        return {"ok": True, "running": False}

    return app


app = create_app()