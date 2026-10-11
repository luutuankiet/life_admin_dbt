"""Pure helpers over TickTick payloads. No I/O, no state."""

from __future__ import annotations

import hashlib
import json
from typing import Any, Literal

LANES = ("update", "delete", "deletedInTrash", "deletedForever")
DELETE_LANES = LANES[1:]

# Fields a body edit touches. Typing in a task body changes only these, and the web
# app sends a sync hint about every 10 s while you type.
BODY_FIELDS = frozenset({"content", "desc", "modifiedTime", "etag"})

GateDecision = Literal["merge", "pending"]


def checkpoint_of(delta: dict[str, Any]) -> int:
    """The bookmark to store after this delta loads."""
    return int(delta["checkPoint"])


def _lane(delta: dict[str, Any], lane: str) -> list[dict[str, Any]]:
    return (delta.get("syncTaskBean") or {}).get(lane) or []


def lane_rows(delta: dict[str, Any]) -> list[dict[str, Any]]:
    """One row per entry of every lane, for ``raw_task_changes``.

    ``payload`` is the whole entry as a dict; serialise it at load time.
    """
    rows = []
    for lane in LANES:
        for entry in _lane(delta, lane):
            if lane == "update":
                task_id, project_id = entry["id"], entry.get("projectId")
            else:
                task_id, project_id = entry["taskId"], entry.get("projectId")
            rows.append(
                {"lane": lane, "task_id": task_id, "project_id": project_id, "payload": entry}
            )
    return rows


def update_entries(delta: dict[str, Any]) -> list[dict[str, Any]]:
    """Task payloads from ``update[]`` (also how a restore from trash arrives)."""
    return list(_lane(delta, "update"))


def delete_tombstones(delta: dict[str, Any]) -> list[dict[str, Any]]:
    """``{"id", "_deleted": True}`` once per task id found in any delete lane.

    Delete lanes replay on several consecutive polls, so the same tombstone may be
    produced again later; a hard-delete merge on ``id`` makes that a no-op.
    """
    ids: dict[str, None] = {}
    for lane in DELETE_LANES:
        for entry in _lane(delta, lane):
            ids.setdefault(entry["taskId"], None)
    return [{"id": task_id, "_deleted": True} for task_id in ids]


def lists_of(delta: dict[str, Any]) -> list[dict[str, Any]] | None:
    """``projectProfiles`` (every list, in full) or None when lists did not change."""
    return delta.get("projectProfiles")


def folders_of(delta: dict[str, Any]) -> list[dict[str, Any]] | None:
    """``projectGroups`` (every folder, in full) or None when folders did not change."""
    return delta.get("projectGroups")


def is_empty_delta(delta: dict[str, Any]) -> bool:
    """True when the delta has no lane entries, no lists and no folders."""
    return not lane_rows(delta) and lists_of(delta) is None and folders_of(delta) is None


def has_closed_update(delta: dict[str, Any]) -> bool:
    """True when an update carries a closed task (status 2 done, -1 won't do)."""
    return any(entry.get("status") in (2, -1) for entry in update_entries(delta))


def canonical_hash(obj: Any) -> str:
    """Stable sha256 of a JSON value (key order ignored)."""
    blob = json.dumps(obj, sort_keys=True, separators=(",", ":"), ensure_ascii=False)
    return hashlib.sha256(blob.encode()).hexdigest()


def non_body_fingerprint(task: dict[str, Any]) -> str:
    """Hash of every field except ``BODY_FIELDS``; what the gate cache stores."""
    return canonical_hash({k: v for k, v in task.items() if k not in BODY_FIELDS})


def gate_decision(task: dict[str, Any], cached_fingerprint: str | None) -> GateDecision:
    """Body-edit gate. ``merge`` when the task is new to the cache or changed in any
    field outside ``BODY_FIELDS``; ``pending`` when only body fields changed (or
    nothing did, as on a replayed update)."""
    if cached_fingerprint is None:
        return "merge"
    return "pending" if non_body_fingerprint(task) == cached_fingerprint else "merge"


def completed_cursor(page: list[dict[str, Any]]) -> str:
    """Next ``to`` for ``completedInAll``: the oldest ``completedTime`` on the page as
    ``yyyy-MM-dd HH:mm:ss`` (UTC, as the server returns it)."""
    oldest = min(row["completedTime"] for row in page)
    return to_cursor(oldest)


def to_cursor(completed_time: str) -> str:
    """``2026-09-29T09:07:35.000+0000`` -> ``2026-09-29 09:07:35``."""
    return completed_time[:19].replace("T", " ")
