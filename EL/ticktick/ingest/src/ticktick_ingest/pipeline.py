"""One sync run: fetch, gate, load, then update the gate cache.

``run_sync(kind)``:

- ``hint``: a sync hint arrived. An empty delta loads nothing (no load job).
- ``safety``: the 30 min safety net. Always loads, flushes every pending body edit and
  pages closed tasks back to the stored completion cursor.
- ``backfill``: as ``safety``, but pages closed tasks down to their floor. The first
  load of a new dataset.
- ``reset``: fetch from checkpoint 0 whatever the stored bookmark says, and merge every
  task without consulting the gate. The new checkpoint overwrites the old one.

All rows and all bookmarks go through one ``pipeline.run`` call, so they commit
together. The gate cache is written only after that call returns.
"""

from __future__ import annotations

import os
import uuid
from dataclasses import asdict, dataclass, field
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

import dlt

from .client import TickTickClient, TickTickConfig
from .gate import Gate, GateChanges, Pending
from .parse import (
    canonical_hash,
    checkpoint_of,
    delete_tombstones,
    folders_of,
    gate_decision,
    has_closed_update,
    is_empty_delta,
    lane_rows,
    lists_of,
    to_cursor,
    update_entries,
)
from .source import Batch, Envelope, read_bookmarks, selected_resources, ticktick_source, typed_row

Kind = Literal["hint", "safety", "backfill", "reset"]
KINDS: tuple[str, ...] = ("hint", "safety", "backfill", "reset")
PIPELINE_NAME = "ticktick_ingest"
DEFAULT_STATE_DIR = Path.home() / ".local" / "state" / "ticktick_ingest"


@dataclass
class RunSummary:
    run_id: str
    kind: str
    checkpoint_from: int
    checkpoint_to: int | None = None
    loaded: bool = False
    skipped_reason: str | None = None
    rows: dict[str, int] = field(default_factory=dict)
    merged_tasks: int = 0
    pending_tasks: int = 0
    flushed_pending: int = 0
    closed_pages: int = 0
    load_ids: list[str] = field(default_factory=list)

    def as_dict(self) -> dict[str, Any]:
        return asdict(self)


# ---------------------------------------------------------------- configuration


def state_dir() -> Path:
    return Path(os.environ.get("INGEST_STATE_DIR") or DEFAULT_STATE_DIR)


def bigquery_destination() -> Any:
    """BigQuery destination from ``GOOGLE_APPLICATION_CREDENTIALS`` (service-account
    key file), ``DBT_BQ_PROJECT`` and ``DBT_BQ_LOCATION``."""
    from dlt.common.configuration.specs import GcpServiceAccountCredentials

    keyfile = os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
    project = os.environ.get("DBT_BQ_PROJECT")
    if not keyfile or not project:
        raise RuntimeError("GOOGLE_APPLICATION_CREDENTIALS and DBT_BQ_PROJECT must be set")
    credentials = GcpServiceAccountCredentials()
    credentials.parse_native_representation(Path(keyfile).read_text())
    credentials.project_id = project
    return dlt.destinations.bigquery(
        credentials=credentials, location=os.environ.get("DBT_BQ_LOCATION") or "US"
    )


def make_pipeline(
    dataset: str | None = None, destination: Any = None, pipelines_dir: Path | None = None
) -> dlt.Pipeline:
    dataset = dataset or os.environ.get("TICKTICK_INGEST_DATASET")
    if not dataset:
        raise RuntimeError("TICKTICK_INGEST_DATASET must be set")
    return dlt.pipeline(
        pipeline_name=PIPELINE_NAME,
        destination=destination if destination is not None else bigquery_destination(),
        dataset_name=dataset,
        pipelines_dir=str(pipelines_dir or state_dir() / "dlt"),
    )


def open_gate(pipeline: dlt.Pipeline, directory: Path | None = None) -> Gate:
    return Gate.open((directory or state_dir()) / "gate.db", pipeline)


# ---------------------------------------------------------------- planning (pure)


@dataclass
class TaskPlan:
    rows: list[dict[str, Any]]
    changes: GateChanges
    merged: int
    pending: int
    flushed: int


def plan_tasks(
    delta: dict[str, Any], gate: Gate, env: Envelope, *, flush: bool, bypass: bool
) -> TaskPlan:
    """Rows for ``tasks`` and the cache changes to apply once they load.

    One row per task id (a MERGE source must not repeat a key). An update and a delete
    of the same id in one delta: the update wins, since a restore from trash arrives
    as an update while the delete lanes are still replaying.
    """
    rows: dict[str, dict[str, Any]] = {}
    merged: dict[str, dict[str, Any]] = {}
    new_pending: dict[str, Pending] = {}

    for entry in update_entries(delta):
        task_id = entry["id"]
        decision = "merge" if bypass else gate_decision(entry, gate.fingerprint(task_id))
        if decision == "merge" or task_id in merged:
            rows[task_id] = {**typed_row(entry, env), "_deleted": False}
            merged[task_id] = entry
            new_pending.pop(task_id, None)
        else:
            new_pending[task_id] = Pending(entry, env.extracted_at.isoformat(), env.bookmark)

    stored = gate.pending()
    deleted: set[str] = set()
    for tombstone in delete_tombstones(delta):
        task_id = tombstone["id"]
        if task_id in merged or task_id in new_pending:
            continue
        # dlt's upsert INSERTs a hard-delete row whose key is not in the table, and the
        # next replay of the same delete then removes it again. Emit tombstones only
        # for ids the cache says are in `tasks` (it mirrors that table, see gate.py).
        if gate.fingerprint(task_id) is None and task_id not in stored:
            continue
        rows[task_id] = {**tombstone, **env.columns()}
        deleted.add(task_id)

    cleared = {i for i in stored if i in deleted or i in merged}
    flushed = 0
    if rows or flush or bypass:
        waiting = {i: p for i, p in stored.items() if i not in cleared}
        waiting.update(new_pending)
        for task_id, pending in waiting.items():
            penv = Envelope(
                env.run_id, datetime.fromisoformat(pending.extracted_at), pending.bookmark
            )
            rows[task_id] = {**typed_row(pending.payload, penv), "_deleted": False}
            merged[task_id] = pending.payload
            flushed += 1
        cleared |= set(stored)
        new_pending = {}

    changes = GateChanges(
        merged=list(merged.values()), pending=new_pending, cleared=cleared, deleted=deleted
    )
    return TaskPlan(
        rows=list(rows.values()),
        changes=changes,
        merged=len(merged),
        pending=len(new_pending),
        flushed=flushed,
    )


def _now() -> datetime:
    return datetime.now(UTC)


# ---------------------------------------------------------------- the run


def run_sync(
    kind: Kind,
    *,
    run_id: str | None = None,
    client: TickTickClient | None = None,
    pipeline: dlt.Pipeline | None = None,
    gate: Gate | None = None,
) -> RunSummary:
    if kind not in KINDS:
        raise ValueError(f"kind must be one of {KINDS}, got {kind!r}")
    run_id = run_id or f"manual-{uuid.uuid4()}"
    pipeline = pipeline or make_pipeline()
    # Restore bookmarks from the destination when the local working dir is new, and
    # abort packages a failed run left behind: their data is re-fetched below.
    pipeline.sync_destination()
    if pipeline.has_pending_data:
        pipeline.abort_packages()
    own_gate = gate is None
    gate = gate or open_gate(pipeline)
    own_client = client is None
    client = client or TickTickClient(TickTickConfig.from_env())
    try:
        return _run(kind, run_id, client, pipeline, gate)
    finally:
        if own_client:
            client.close()
        if own_gate:
            gate.close()


def _run(
    kind: str, run_id: str, client: TickTickClient, pipeline: dlt.Pipeline, gate: Gate
) -> RunSummary:
    bookmarks = read_bookmarks(pipeline.state)
    cp = 0 if kind == "reset" else bookmarks["checkpoint"]
    summary = RunSummary(run_id=run_id, kind=kind, checkpoint_from=cp)

    delta = client.fetch_delta(cp)
    env = Envelope(run_id, _now(), str(cp))
    summary.checkpoint_to = checkpoint_of(delta)
    if is_empty_delta(delta) and kind == "hint":
        summary.skipped_reason = "empty delta"
        return summary

    batch = Batch(checkpoint_to=checkpoint_of(delta))
    batch.lane_rows = [{**row, **env.columns()} for row in lane_rows(delta)]

    plan = plan_tasks(
        delta, gate, env, flush=kind in ("safety", "backfill"), bypass=kind == "reset"
    )
    batch.task_rows = plan.rows
    summary.merged_tasks, summary.pending_tasks = plan.merged, plan.pending
    summary.flushed_pending = plan.flushed

    for name, items, stored_hash in (
        ("lists", lists_of(delta), bookmarks["lists_hash"]),
        ("folders", folders_of(delta), bookmarks["folders_hash"]),
    ):
        if items is None:
            continue
        setattr(batch, name, [typed_row(item, env) for item in items])
        digest = canonical_hash(items)
        if digest != stored_hash:
            setattr(batch, f"raw_{name}", {"hash": digest, "payload": items, **env.columns()})

    if kind in ("safety", "backfill") or has_closed_update(delta):
        _add_closed(batch, summary, client, run_id, kind, bookmarks["closed_cursor"])

    names = selected_resources(batch)
    info = pipeline.run(ticktick_source(batch).with_resources(*names))
    gate.apply(plan.changes)

    summary.loaded = True
    summary.load_ids = list(info.loads_ids)
    summary.rows = {
        "raw_task_changes": len(batch.lane_rows),
        "tasks": len(batch.task_rows),
        "lists": len(batch.lists or []),
        "folders": len(batch.folders or []),
        "raw_lists": int(batch.raw_lists is not None),
        "raw_folders": int(batch.raw_folders is not None),
        "raw_closed_tasks": len(batch.raw_closed_rows),
        "closed_tasks": len(batch.closed_rows),
    }
    return summary


def _add_closed(
    batch: Batch,
    summary: RunSummary,
    client: TickTickClient,
    run_id: str,
    kind: str,
    stored_cursor: str | None,
) -> None:
    """Page ``completedInAll`` back to the stored cursor (inclusive), or to the floor
    on ``backfill`` and on the first ever page-through."""
    stop_at = None if kind == "backfill" else stored_cursor
    latest: dict[str, dict[str, Any]] = {}
    cursor = stored_cursor
    for page in client.iter_completed(stop_at=stop_at):
        summary.closed_pages += 1
        env = Envelope(run_id, _now(), stop_at)
        for row in page:
            batch.raw_closed_rows.append({"task_id": row["id"], "payload": row, **env.columns()})
            latest[row["id"]] = typed_row(row, env)
            if row.get("completedTime"):
                done = to_cursor(row["completedTime"])
                cursor = done if cursor is None or done > cursor else cursor
    batch.closed_rows = list(latest.values())
    if cursor != stored_cursor:
        batch.closed_cursor_to = cursor
