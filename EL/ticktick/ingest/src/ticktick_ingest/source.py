"""The dlt source: one resource per BigQuery table, fed by an already-fetched ``Batch``.

Fetching and the body-edit gate live in ``pipeline.py``; this module only fixes table
shapes, write dispositions, schema contracts and where each bookmark is kept.

Bookmarks live in dlt resource state, so they commit in the destination together with
the rows they describe:

- ``raw_task_changes``: ``checkpoint`` (the sync-feed checkpoint to fetch from next)
- ``raw_closed_tasks``: ``cursor`` (newest ``completedTime`` loaded, ``yyyy-MM-dd HH:mm:ss``)
- ``raw_lists`` / ``raw_folders``: ``hash`` of the last stored array
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any

import dlt

SOURCE_NAME = "ticktick"

RAW_CONTRACT = {"tables": "evolve", "columns": "evolve", "data_type": "evolve"}
TYPED_CONTRACT = {"tables": "evolve", "columns": "evolve", "data_type": "freeze"}

ENVELOPE_COLUMNS = {
    "_run_id": {"data_type": "text", "nullable": False},
    "_extracted_at": {"data_type": "timestamp", "nullable": False},
    "_bookmark": {"data_type": "text", "nullable": True},
}
RAW_JSON_COLUMN = {"raw_json": {"data_type": "text", "nullable": True}}
PAYLOAD_COLUMN = {"payload": {"data_type": "json", "nullable": True}}

ALL_RESOURCES = (
    "raw_task_changes",
    "raw_lists",
    "raw_folders",
    "raw_closed_tasks",
    "tasks",
    "closed_tasks",
    "lists",
    "folders",
)


@dataclass
class Envelope:
    run_id: str
    extracted_at: datetime
    bookmark: str | None

    def columns(self) -> dict[str, Any]:
        return {
            "_run_id": self.run_id,
            "_extracted_at": self.extracted_at,
            "_bookmark": self.bookmark,
        }


@dataclass
class Batch:
    """Everything one run loads. Rows already carry their envelope columns."""

    checkpoint_to: int | None = None
    lane_rows: list[dict[str, Any]] = field(default_factory=list)
    task_rows: list[dict[str, Any]] = field(default_factory=list)
    raw_lists: dict[str, Any] | None = None  # {"hash", "payload", envelope...}
    raw_folders: dict[str, Any] | None = None
    lists: list[dict[str, Any]] | None = None
    folders: list[dict[str, Any]] | None = None
    raw_closed_rows: list[dict[str, Any]] = field(default_factory=list)
    closed_rows: list[dict[str, Any]] = field(default_factory=list)
    closed_cursor_to: str | None = None


def typed_row(obj: dict[str, Any], envelope: Envelope) -> dict[str, Any]:
    """Top-level fields for dlt to type, plus the original object as ``raw_json``."""
    return {**obj, "raw_json": json.dumps(obj, ensure_ascii=False), **envelope.columns()}


@dlt.resource(
    name="raw_task_changes",
    write_disposition="append",
    schema_contract=RAW_CONTRACT,
    columns={**ENVELOPE_COLUMNS, **PAYLOAD_COLUMN},
)
def raw_task_changes(batch: Batch) -> Iterator[dict[str, Any]]:
    yield from batch.lane_rows
    if batch.checkpoint_to is not None:
        dlt.current.resource_state()["checkpoint"] = batch.checkpoint_to


def _raw_snapshot(batch_row: dict[str, Any] | None) -> Iterator[dict[str, Any]]:
    if batch_row is None:
        return
    yield batch_row
    dlt.current.resource_state()["hash"] = batch_row["hash"]


@dlt.resource(
    name="raw_lists",
    write_disposition="append",
    schema_contract=RAW_CONTRACT,
    columns={**ENVELOPE_COLUMNS, **PAYLOAD_COLUMN},
)
def raw_lists(batch: Batch) -> Iterator[dict[str, Any]]:
    yield from _raw_snapshot(batch.raw_lists)


@dlt.resource(
    name="raw_folders",
    write_disposition="append",
    schema_contract=RAW_CONTRACT,
    columns={**ENVELOPE_COLUMNS, **PAYLOAD_COLUMN},
)
def raw_folders(batch: Batch) -> Iterator[dict[str, Any]]:
    yield from _raw_snapshot(batch.raw_folders)


@dlt.resource(
    name="raw_closed_tasks",
    write_disposition="append",
    schema_contract=RAW_CONTRACT,
    columns={**ENVELOPE_COLUMNS, **PAYLOAD_COLUMN},
)
def raw_closed_tasks(batch: Batch) -> Iterator[dict[str, Any]]:
    yield from batch.raw_closed_rows
    if batch.closed_cursor_to is not None:
        dlt.current.resource_state()["cursor"] = batch.closed_cursor_to


@dlt.resource(
    name="tasks",
    write_disposition={"disposition": "merge", "strategy": "upsert"},
    primary_key="id",
    schema_contract=TYPED_CONTRACT,
    columns={
        **ENVELOPE_COLUMNS,
        **RAW_JSON_COLUMN,
        "_deleted": {"data_type": "bool", "nullable": True, "hard_delete": True},
    },
)
def tasks(batch: Batch) -> Iterator[dict[str, Any]]:
    yield from batch.task_rows


@dlt.resource(
    name="closed_tasks",
    write_disposition={"disposition": "merge", "strategy": "upsert"},
    primary_key="id",
    schema_contract=TYPED_CONTRACT,
    columns={**ENVELOPE_COLUMNS, **RAW_JSON_COLUMN},
)
def closed_tasks(batch: Batch) -> Iterator[dict[str, Any]]:
    yield from batch.closed_rows


@dlt.resource(
    name="lists",
    write_disposition="replace",
    primary_key="id",
    schema_contract=TYPED_CONTRACT,
    columns={**ENVELOPE_COLUMNS, **RAW_JSON_COLUMN},
)
def lists(batch: Batch) -> Iterator[dict[str, Any]]:
    yield from batch.lists or []


@dlt.resource(
    name="folders",
    write_disposition="replace",
    primary_key="id",
    schema_contract=TYPED_CONTRACT,
    columns={**ENVELOPE_COLUMNS, **RAW_JSON_COLUMN},
)
def folders(batch: Batch) -> Iterator[dict[str, Any]]:
    yield from batch.folders or []


@dlt.source(name=SOURCE_NAME, max_table_nesting=0)
def ticktick_source(batch: Batch):
    """All eight resources. Select the ones a run loads with ``.with_resources``:
    ``lists``/``folders`` are ``replace``, so selecting them with no rows would empty
    the table."""
    # Keep timestamps as the strings TickTick sends; auto-detection would split a
    # column into variants the frozen contract then rejects. Read them from raw_json.
    dlt.current.source_schema().remove_type_detection("iso_timestamp")
    return (
        raw_task_changes(batch),
        raw_lists(batch),
        raw_folders(batch),
        raw_closed_tasks(batch),
        tasks(batch),
        closed_tasks(batch),
        lists(batch),
        folders(batch),
    )


def selected_resources(batch: Batch) -> list[str]:
    """Resources a run must load. ``raw_task_changes`` always runs: it carries the
    checkpoint. Replace tables only when the delta carried them."""
    names = ["raw_task_changes", "tasks"]
    if batch.raw_lists is not None:
        names.append("raw_lists")
    if batch.raw_folders is not None:
        names.append("raw_folders")
    if batch.lists is not None:
        names.append("lists")
    if batch.folders is not None:
        names.append("folders")
    if batch.raw_closed_rows or batch.closed_cursor_to is not None:
        names += ["raw_closed_tasks", "closed_tasks"]
    return names


def read_bookmarks(state: dict[str, Any]) -> dict[str, Any]:
    """Bookmarks out of a dlt pipeline state dict (empty values on a first run)."""
    resources = state.get("sources", {}).get(SOURCE_NAME, {}).get("resources", {})
    return {
        "checkpoint": int(resources.get("raw_task_changes", {}).get("checkpoint", 0)),
        "closed_cursor": resources.get("raw_closed_tasks", {}).get("cursor"),
        "lists_hash": resources.get("raw_lists", {}).get("hash"),
        "folders_hash": resources.get("raw_folders", {}).get("hash"),
    }
