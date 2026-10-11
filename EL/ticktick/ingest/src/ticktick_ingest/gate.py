"""Body-edit gate cache: SQLite at ``$INGEST_STATE_DIR/gate.db``.

Two tables:
- ``fingerprints(id, fp)``: ``non_body_fingerprint`` of the version of each task last
  merged into ``tasks``.
- ``pending(id, payload, extracted_at, bookmark)``: the newest body-only update not yet
  merged, with the envelope of the fetch that produced it.

The cache is a convenience, never the only copy: when the file is missing it is
rebuilt from the ``tasks`` table (``rebuild_from_bigquery``). Pending payloads are
not recoverable that way; they are also in ``raw_task_changes``, and the next edit
to the same task re-captures them.
"""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Iterable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from .parse import non_body_fingerprint

SCHEMA = """
create table if not exists fingerprints (id text primary key, fp text not null);
create table if not exists pending (
    id text primary key,
    payload text not null,
    extracted_at text not null,
    bookmark text
);
"""


@dataclass(frozen=True)
class Pending:
    payload: dict[str, Any]
    extracted_at: str
    bookmark: str | None


@dataclass
class GateChanges:
    """What to write to the cache once the load has succeeded."""

    merged: list[dict[str, Any]]  # task payloads now in ``tasks``
    pending: dict[str, Pending]  # new or newer body-only payloads
    cleared: set[str]  # pending ids flushed by this load
    deleted: set[str]  # ids hard-deleted by this load


class Gate:
    def __init__(self, path: Path | str) -> None:
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self._db = sqlite3.connect(self.path)
        self._db.executescript(SCHEMA)

    @classmethod
    def open(cls, path: Path | str, pipeline: Any = None) -> Gate:
        """Open the cache; rebuild it from ``pipeline``'s ``tasks`` table if the file
        did not exist."""
        existed = Path(path).exists()
        gate = cls(path)
        if not existed and pipeline is not None:
            gate.rebuild_from_bigquery(pipeline)
        return gate

    def close(self) -> None:
        self._db.close()

    def fingerprint(self, task_id: str) -> str | None:
        row = self._db.execute("select fp from fingerprints where id = ?", (task_id,)).fetchone()
        return row[0] if row else None

    def pending(self) -> dict[str, Pending]:
        rows = self._db.execute("select id, payload, extracted_at, bookmark from pending")
        return {r[0]: Pending(json.loads(r[1]), r[2], r[3]) for r in rows}

    def apply(self, changes: GateChanges) -> None:
        with self._db:
            self._db.executemany(
                "insert or replace into fingerprints values (?, ?)",
                [(t["id"], non_body_fingerprint(t)) for t in changes.merged],
            )
            self._db.executemany(
                "delete from pending where id = ?", [(i,) for i in changes.cleared]
            )
            self._db.executemany(
                "insert or replace into pending values (?, ?, ?, ?)",
                [
                    (i, json.dumps(p.payload), p.extracted_at, p.bookmark)
                    for i, p in changes.pending.items()
                ],
            )
            for table in ("fingerprints", "pending"):
                self._db.executemany(
                    f"delete from {table} where id = ?", [(i,) for i in changes.deleted]
                )

    def load_fingerprints(self, payloads: Iterable[dict[str, Any]]) -> int:
        n = 0
        with self._db:
            self._db.execute("delete from fingerprints")
            for task in payloads:
                self._db.execute(
                    "insert or replace into fingerprints values (?, ?)",
                    (task["id"], non_body_fingerprint(task)),
                )
                n += 1
        return n

    def rebuild_from_bigquery(self, pipeline: Any) -> int:
        """Refill fingerprints from ``tasks.raw_json`` in the pipeline's dataset
        (BigQuery in production; tests use duckdb). Returns the number of tasks
        read; 0 when the table does not exist yet."""
        try:
            with pipeline.sql_client() as client:
                table = client.make_qualified_table_name("tasks")
                sql = f"select raw_json from {table} where raw_json is not null"
                rows = client.execute_sql(sql)
        except Exception as exc:  # table or dataset not created yet
            if _is_missing_table(exc):
                return 0
            raise
        return self.load_fingerprints(json.loads(r[0]) for r in rows or [])


def _is_missing_table(exc: Exception) -> bool:
    from dlt.destinations.exceptions import DatabaseUndefinedRelation

    if isinstance(exc, DatabaseUndefinedRelation):
        return True
    text = str(exc).lower()
    return "not found" in text or "does not exist" in text
