"""Dagster definitions: ``dagster dev -m ticktick_ingest.defs``.

- ``ticktick_sync``: one multi-asset (one asset per BigQuery table) that calls
  ``run_sync(kind, run_id=<dagster run id>)``. Run config picks the kind.
- ``hint_sensor``: launches ``kind=hint`` when the listener wrote a newer ``last_hint``.
- ``safety_net``: every 30 min, ``kind=safety``.
- ``ntfy_on_failure``: posts any failed run to ``$NTFY_URL``.
- ``purge_old_runs``: daily, deletes run records older than 7 days (OSS Dagster has no
  run retention setting; tick retention lives in ``dagster.yaml``).

The dlt work is not wired through dagster-dlt: ``run_sync`` owns the gate, the pending
set and the decision to load nothing, which the integration's one-``pipeline.run``
asset cannot express.
"""

import json
import os
import time
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from typing import Any

import dagster as dg

from .listener import read_hint
from .pipeline import KINDS, state_dir

TABLES: tuple[str, ...] = (
    "raw_task_changes",
    "raw_lists",
    "raw_folders",
    "raw_closed_tasks",
    "tasks",
    "closed_tasks",
    "lists",
    "folders",
)
ASSET_PREFIX = "ticktick_ingest"
OP_NAME = "ticktick_sync_tables"
MIN_GAP_MS = 60_000
NTFY_TITLE = "ticktick-ingest failed"
AUTH_HINT = "cookie rejected: paste a fresh t"
ERROR_CHARS = 300
RUN_RETENTION_DAYS = 7


class SyncConfig(dg.Config):
    kind: str = "hint"


def run_config(kind: str) -> dict[str, Any]:
    return {"ops": {OP_NAME: {"config": {"kind": kind}}}}


@dg.multi_asset(
    name=OP_NAME,
    specs=[
        dg.AssetSpec([ASSET_PREFIX, t], group_name=ASSET_PREFIX, skippable=True) for t in TABLES
    ],
    can_subset=False,
)
def ticktick_tables(context: dg.AssetExecutionContext, config: SyncConfig):
    from .pipeline import run_sync

    if config.kind not in KINDS:
        raise ValueError(f"kind must be one of {KINDS}, got {config.kind!r}")
    summary = run_sync(config.kind, run_id=context.run.run_id)  # type: ignore[arg-type]
    context.log.info("run summary: %s", json.dumps(summary.as_dict()))
    for table, n in summary.rows.items():
        if n:
            yield dg.MaterializeResult(
                asset_key=[ASSET_PREFIX, table],
                metadata={"rows": n, "kind": summary.kind, "load_ids": summary.load_ids},
            )


ticktick_sync = dg.define_asset_job(
    "ticktick_sync",
    selection=dg.AssetSelection.assets(ticktick_tables),
    config=run_config("hint"),
)

# ---------------------------------------------------------------- hint sensor


@dataclass(frozen=True)
class HintCursor:
    hint: int = 0
    launched_at: int = 0

    @classmethod
    def parse(cls, raw: str | None) -> "HintCursor":
        if not raw:
            return cls()
        try:
            data = json.loads(raw)
            return cls(int(data.get("hint", 0)), int(data.get("launched_at", 0)))
        except (ValueError, TypeError, AttributeError):
            return cls()

    def dump(self) -> str:
        return json.dumps({"hint": self.hint, "launched_at": self.launched_at})


def hint_decision(
    last_hint: int | None, cursor: HintCursor, now_ms: int, min_gap_ms: int = MIN_GAP_MS
) -> "HintCursor | None":
    """The cursor to store when a run should launch, else ``None``.

    Launch when the listener's hint is newer than the one last launched for and the
    last launch is over ``min_gap_ms`` ago. A hint inside the gap is not lost: the
    cursor stays put, so a later tick launches for it.
    """
    if last_hint is None or last_hint <= cursor.hint:
        return None
    if now_ms - cursor.launched_at <= min_gap_ms:
        return None
    return HintCursor(hint=last_hint, launched_at=now_ms)


def _now_ms() -> int:
    return int(time.time() * 1000)


@dg.sensor(
    job=ticktick_sync,
    minimum_interval_seconds=30,
    default_status=dg.DefaultSensorStatus.RUNNING,
)
def hint_sensor(context: dg.SensorEvaluationContext):
    last_hint = read_hint(state_dir())
    cursor = HintCursor.parse(context.cursor)
    nxt = hint_decision(last_hint, cursor, _now_ms())
    if nxt is None:
        return dg.SkipReason(f"last_hint={last_hint} cursor={cursor.dump()}")
    context.update_cursor(nxt.dump())
    return dg.RunRequest(
        run_key=f"hint-{nxt.hint}", run_config=run_config("hint"), tags={"kind": "hint"}
    )


safety_net = dg.ScheduleDefinition(
    name="safety_net",
    job=ticktick_sync,
    cron_schedule="*/30 * * * *",
    run_config=run_config("safety"),
    tags={"kind": "safety"},
    default_status=dg.DefaultScheduleStatus.RUNNING,
)

# ---------------------------------------------------------------- failure alert


def _error_chain(error: Any) -> Iterable[Any]:
    seen = 0
    stack = [error]
    while stack and seen < 20:
        e = stack.pop()
        if e is None:
            continue
        seen += 1
        yield e
        stack.extend([getattr(e, "context", None), getattr(e, "cause", None)])


def ntfy_message(run_id: str, job: str, message: str, errors: Iterable[Any]) -> tuple[str, str]:
    """``(title, body)`` for a failed run. ``errors`` are Dagster
    ``SerializableErrorInfo`` objects (anything with ``cls_name``, ``message``,
    ``cause``, ``context``); a ``AuthRejected`` anywhere in a chain means the cookie."""
    chain = [e for err in errors for e in _error_chain(err)]
    auth = next((e for e in chain if getattr(e, "cls_name", None) == "AuthRejected"), None)
    # Dagster wraps the user's exception; its own wrapper text says nothing useful.
    picked = auth or next(
        (e for e in chain if not str(getattr(e, "cls_name", "")).startswith("Dagster")),
        chain[0] if chain else None,
    )
    detail = f"{picked.cls_name}: {picked.message}" if picked is not None else ""
    text = (detail or message or "unknown error").strip()[:ERROR_CHARS]
    lines = [AUTH_HINT] if auth is not None else []
    lines += [text, f"job {job} run {run_id}"]
    return NTFY_TITLE, "\n".join(lines)


def post_ntfy(url: str, title: str, body: str, *, transport: Any = None) -> int:
    import httpx

    with httpx.Client(timeout=10, transport=transport) as client:
        resp = client.post(
            url, content=body.encode(), headers={"Title": title, "Priority": "high", "Tags": "x"}
        )
        return resp.status_code


@dg.run_failure_sensor(name="ntfy_on_failure", default_status=dg.DefaultSensorStatus.RUNNING)
def ntfy_on_failure(context: dg.RunFailureSensorContext):
    errors = [
        ev.event_specific_data.error
        for ev in context.get_step_failure_events()
        if ev.event_specific_data is not None and ev.event_specific_data.error is not None
    ]
    title, body = ntfy_message(
        context.dagster_run.run_id,
        context.dagster_run.job_name,
        context.failure_event.message or "",
        errors,
    )
    url = os.environ.get("NTFY_URL")
    if not url:
        context.log.warning("NTFY_URL unset; not sending: %s", title)
        return
    status = post_ntfy(url, title, body)
    context.log.info("ntfy answered %s", status)


# ---------------------------------------------------------------- run retention


@dg.op
def purge_runs(context: dg.OpExecutionContext) -> int:
    cutoff = datetime.now(UTC) - timedelta(days=RUN_RETENTION_DAYS)
    records = context.instance.get_run_records(
        filters=dg.RunsFilter(created_before=cutoff), limit=1000
    )
    n = 0
    for record in records:
        run_id = record.dagster_run.run_id
        if run_id != context.run_id:
            context.instance.delete_run(run_id)
            # delete_run leaves the run's stdout/stderr files behind.
            context.instance.compute_log_manager.delete_logs(prefix=[run_id])
            n += 1
    context.log.info("deleted %d runs older than %s", n, cutoff.isoformat())
    return n


@dg.job
def purge_old_runs():
    purge_runs()


purge_schedule = dg.ScheduleDefinition(
    name="purge_old_runs_daily",
    job=purge_old_runs,
    cron_schedule="17 3 * * *",
    default_status=dg.DefaultScheduleStatus.RUNNING,
)

defs = dg.Definitions(
    assets=[ticktick_tables],
    jobs=[ticktick_sync, purge_old_runs],
    sensors=[hint_sensor, ntfy_on_failure],
    schedules=[safety_net, purge_schedule],
)
