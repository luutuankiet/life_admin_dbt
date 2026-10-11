import pytest

from ticktick_ingest.parse import BODY_FIELDS, gate_decision, non_body_fingerprint


@pytest.fixture
def task(load):
    return dict(load("delta_lists.json")["syncTaskBean"]["update"][0])


def test_unknown_task_merges(task):
    assert gate_decision(task, None) == "merge"


def test_body_only_edit_is_pending(task):
    cached = non_body_fingerprint(task)
    edited = {
        **task,
        "content": "typing...",
        "desc": "more",
        "modifiedTime": "2026-10-09T16:07:00.000+0000",
        "etag": "newetag1",
    }
    assert gate_decision(edited, cached) == "pending"


def test_replayed_identical_update_is_pending(task):
    assert gate_decision(task, non_body_fingerprint(task)) == "pending"


@pytest.mark.parametrize(
    "field,value",
    [
        ("title", "renamed"),
        ("status", 2),
        ("dueDate", None),
        ("projectId", "other"),
        ("tags", ["x"]),
    ],
)
def test_non_body_change_merges(task, field, value):
    cached = non_body_fingerprint(task)
    assert gate_decision({**task, field: value, "etag": "e2"}, cached) == "merge"


def test_added_or_removed_field_merges(task):
    cached = non_body_fingerprint(task)
    assert gate_decision({**task, "repeatFlag": "RRULE:FREQ=DAILY"}, cached) == "merge"
    trimmed = {k: v for k, v in task.items() if k != "dueDate"}
    assert gate_decision(trimmed, cached) == "merge"


def test_body_fields_are_exactly_the_spec():
    assert BODY_FIELDS == {"content", "desc", "modifiedTime", "etag"}
