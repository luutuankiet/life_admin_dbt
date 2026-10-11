from ticktick_ingest.parse import (
    checkpoint_of,
    completed_cursor,
    delete_tombstones,
    folders_of,
    has_closed_update,
    is_empty_delta,
    lane_rows,
    lists_of,
    update_entries,
)

SERIES = "6ac9158ac4028cdf6431afd7"
FOREVER = "6ac9158add914fa42fcaddca"


def test_empty_delta(load):
    delta = load("delta_empty.json")
    assert is_empty_delta(delta)
    assert lane_rows(delta) == []
    assert checkpoint_of(delta) == 1791561968860


def test_lane_rows_cover_every_lane(load):
    delta = load("delta_replay_3.json")
    rows = lane_rows(delta)
    assert [(r["lane"], r["task_id"][-6:]) for r in rows] == [
        ("update", "e826b2"),
        ("delete", "31afd7"),
        ("delete", "caddca"),
        ("deletedInTrash", "31afd7"),
        ("deletedForever", "caddca"),
    ]
    assert all(r["project_id"] == "6ac91589e15fe56a167f5107" for r in rows)
    assert rows[0]["payload"]["status"] == 2
    assert rows[4]["payload"] == {"taskId": FOREVER, "projectId": "6ac91589e15fe56a167f5107"}
    assert not is_empty_delta(delta)
    assert has_closed_update(delta)


def test_tombstones_dedupe_across_lanes(load):
    delta = load("delta_replay_3.json")
    assert delete_tombstones(delta) == [
        {"id": SERIES, "_deleted": True},
        {"id": FOREVER, "_deleted": True},
    ]


def test_lists_and_folders(load):
    delta = load("delta_lists.json")
    assert len(lists_of(delta)) == 2
    assert folders_of(delta)[0]["id"] == "fixture-group-1"
    assert not is_empty_delta(delta)
    assert lists_of(load("delta_replay_1.json")) is None


def test_delta_with_only_lists_is_not_empty(load):
    delta = load("delta_lists.json")
    delta["syncTaskBean"] = {"update": [], "delete": [], "empty": True}
    assert lane_rows(delta) == []
    assert not is_empty_delta(delta)


def test_idempotent_replay(load):
    """The same delete shows on consecutive polls; every poll yields the same rows."""
    deltas = [load(f"delta_replay_{i}.json") for i in (1, 2, 3)]
    tombstones = [[t for t in delete_tombstones(d) if t["id"] == SERIES] for d in deltas]
    assert tombstones[0] == tombstones[1] == tombstones[2] == [{"id": SERIES, "_deleted": True}]
    raw = [
        [(r["lane"], r["task_id"], r["payload"]) for r in lane_rows(d) if r["task_id"] == SERIES]
        for d in deltas
    ]
    assert raw[0] == raw[1] == raw[2]
    # the restored task replays in update[] with an identical payload too
    upd = [update_entries(d) for d in (deltas[1], deltas[2])]
    assert upd[0] == upd[1]


def test_completed_cursor(load):
    page = load("completed_page.json")
    assert completed_cursor(page) == "2026-10-09 16:25:58"
