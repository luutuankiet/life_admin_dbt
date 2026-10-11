"""run_sync end to end against duckdb, with a fake TickTick client."""

import copy
import json

import dlt
import pytest
from dlt.pipeline.exceptions import PipelineStepFailed

from ticktick_ingest.gate import Gate
from ticktick_ingest.pipeline import run_sync

TASK_ID = "6ac90f6714765b0354155912"


class FakeClient:
    def __init__(self, deltas, closed_pages=None):
        self.deltas = list(deltas)
        self.closed_pages = closed_pages or []
        self.checkpoints = []
        self.stop_ats = []

    def fetch_delta(self, checkpoint):
        self.checkpoints.append(checkpoint)
        return self.deltas.pop(0)

    def iter_completed(self, stop_at=None):
        self.stop_ats.append(stop_at)
        yield from self.closed_pages


@pytest.fixture
def env(tmp_path):
    db = str(tmp_path / "dest.duckdb")

    def make(workdir="w1"):
        pipeline = dlt.pipeline(
            pipeline_name="ticktick_ingest_test",
            destination=dlt.destinations.duckdb(db),
            dataset_name="ingest",
            pipelines_dir=str(tmp_path / workdir),
        )
        gate = Gate.open(tmp_path / workdir / "gate.db", pipeline)
        return pipeline, gate

    return make


def query(pipeline, sql):
    with pipeline.sql_client() as c:
        return c.execute_sql(sql.replace("{ds}", pipeline.dataset_name))


def count(pipeline, table, where="true"):
    return query(pipeline, f"select count(*) from {{ds}}.{table} where {where}")[0][0]


def task_json(pipeline, task_id=TASK_ID):
    sql = f"select raw_json from {{ds}}.tasks where id = '{task_id}'"
    return json.loads(query(pipeline, sql)[0][0])


def loads(pipeline):
    return count(pipeline, "_dlt_loads")


def sync(kind, deltas, pipeline, gate, closed_pages=None, run_id="test-run"):
    client = FakeClient(deltas, closed_pages)
    summary = run_sync(kind, run_id=run_id, client=client, pipeline=pipeline, gate=gate)
    return summary, client


def test_first_load_then_empty_delta_loads_nothing(env, load):
    pipeline, gate = env()
    summary, client = sync("hint", [load("delta_lists.json")], pipeline, gate)
    assert client.checkpoints == [0]
    assert summary.loaded and summary.checkpoint_to == 1791562241035
    assert count(pipeline, "tasks") == 1
    assert count(pipeline, "lists") == 2
    assert count(pipeline, "folders") == 1
    assert count(pipeline, "raw_lists") == 1
    assert count(pipeline, "raw_folders") == 1
    assert count(pipeline, "raw_task_changes") == 1
    row = query(pipeline, "select raw_json, _run_id, _bookmark, _extracted_at from {ds}.tasks")[0]
    assert json.loads(row[0])["id"] == TASK_ID
    assert row[1] == "test-run" and row[2] == "0" and row[3] is not None
    before = loads(pipeline)

    summary, client = sync("hint", [load("delta_empty.json")], pipeline, gate)
    assert client.checkpoints == [1791562241035]
    assert not summary.loaded and summary.skipped_reason == "empty delta"
    assert loads(pipeline) == before


def test_unchanged_lists_replace_but_skip_raw(env, load):
    pipeline, gate = env()
    sync("hint", [load("delta_lists.json")], pipeline, gate)
    again = load("delta_lists.json")
    again["checkPoint"] += 1
    sync("hint", [again], pipeline, gate)
    assert count(pipeline, "raw_lists") == 1
    assert count(pipeline, "lists") == 2


def test_delete_replays_are_idempotent(env, load):
    pipeline, gate = env()
    sync("hint", [load("delta_lists.json")], pipeline, gate)
    for i in range(1, 5):
        sync("hint", [load(f"delta_replay_{i}.json")], pipeline, gate)
    # only the completed task from the replays plus the first task remain
    ids = {r[0] for r in query(pipeline, "select id from {ds}.tasks")}
    assert ids == {TASK_ID, "6ac9158ad15ed517e5e826b2"}
    assert count(pipeline, "raw_task_changes", "lane = 'deletedForever'") == 2


def test_delete_of_a_known_task_removes_it_and_replays_are_noops(env, load):
    pipeline, gate = env()
    sync("hint", [load("delta_lists.json")], pipeline, gate)
    gone = load("delta_empty.json")
    gone["syncTaskBean"]["deletedInTrash"] = [{"taskId": TASK_ID, "projectId": "p"}]
    for _ in range(3):  # the delete lane replays on consecutive polls
        sync("hint", [copy.deepcopy(gone)], pipeline, gate)
        assert count(pipeline, "tasks") == 0
    assert gate.fingerprint(TASK_ID) is None


def test_body_edit_is_pending_until_a_merge(env, load):
    pipeline, gate = env()
    first = load("delta_lists.json")
    sync("hint", [first], pipeline, gate)
    task = first["syncTaskBean"]["update"][0]

    typed = copy.deepcopy(load("delta_empty.json"))
    typed["checkPoint"] += 10_000_000
    typed["syncTaskBean"]["update"] = [{**task, "content": "typing", "etag": "e2"}]
    summary, _ = sync("hint", [typed], pipeline, gate)
    assert summary.loaded and summary.pending_tasks == 1 and summary.merged_tasks == 0
    assert count(pipeline, "raw_task_changes") == 2
    assert task_json(pipeline).get("content") != "typing"
    assert set(gate.pending()) == {TASK_ID}

    other = copy.deepcopy(typed)
    other["checkPoint"] += 1
    other["syncTaskBean"]["update"] = [{**task, "id": "newtask0000000000000001", "title": "n"}]
    summary, _ = sync("hint", [other], pipeline, gate)
    assert summary.flushed_pending == 1
    assert task_json(pipeline)["content"] == "typing"
    assert gate.pending() == {}


def test_safety_flushes_pending_and_loads_on_empty_delta(env, load):
    pipeline, gate = env()
    first = load("delta_lists.json")
    sync("hint", [first], pipeline, gate)
    task = first["syncTaskBean"]["update"][0]
    typed = load("delta_empty.json")
    typed["checkPoint"] += 10_000_000
    typed["syncTaskBean"]["update"] = [{**task, "desc": "body"}]
    sync("hint", [typed], pipeline, gate)
    before = loads(pipeline)

    summary, client = sync("safety", [load("delta_empty.json")], pipeline, gate)
    assert summary.loaded and summary.flushed_pending == 1
    assert loads(pipeline) == before + 1
    assert query(pipeline, 'select "desc" from {ds}.tasks')[0][0] == "body"
    assert client.stop_ats == [None]


def test_backfill_pages_closed_and_stores_cursor(env, load):
    pipeline, gate = env()
    page = load("completed_page.json")
    sync("backfill", [load("delta_lists.json")], pipeline, gate, closed_pages=[page[:4], page[4:]])
    assert count(pipeline, "closed_tasks") == len({r["id"] for r in page})
    assert count(pipeline, "raw_closed_tasks") == len(page)
    newest = max(r["completedTime"] for r in page)[:19].replace("T", " ")

    # a later safety run pages back only to the stored cursor
    _, client = sync("safety", [load("delta_empty.json")], pipeline, gate)
    assert client.stop_ats == [newest]


def test_safety_keeps_only_closed_rows_at_or_after_the_cursor(env, load):
    pipeline, gate = env()
    page = load("completed_page.json")
    sync("backfill", [load("delta_lists.json")], pipeline, gate, closed_pages=[page])
    raw_before = count(pipeline, "raw_closed_tasks")
    cursor = max(r["completedTime"] for r in page)  # 2026-10-09T16:26:37
    equal = next(r for r in page if r["completedTime"] == cursor)
    older = [r for r in page if r["completedTime"] < cursor]
    newer = {
        **equal,
        "id": "newclosed000000000000001",
        "completedTime": "2026-10-10T08:00:00.000+0000",
    }
    mixed = [newer, equal, *older]

    summary, _ = sync(
        "safety", [load("delta_empty.json")], pipeline, gate, closed_pages=[mixed], run_id="safety"
    )
    assert summary.rows["raw_closed_tasks"] == 2 and summary.rows["closed_tasks"] == 2
    assert count(pipeline, "raw_closed_tasks") == raw_before + 2
    new_raw = query(pipeline, "select task_id from {ds}.raw_closed_tasks where _run_id = 'safety'")
    assert {r[0] for r in new_raw} == {newer["id"], equal["id"]}

    # backfill ignores the cursor and keeps every row of the page
    summary, _ = sync(
        "backfill", [load("delta_empty.json")], pipeline, gate, closed_pages=[mixed], run_id="bf"
    )
    assert summary.rows["raw_closed_tasks"] == len(mixed)
    assert summary.rows["closed_tasks"] == len({r["id"] for r in mixed})


def test_bookmark_and_gate_survive_a_lost_working_dir(env, load):
    pipeline, gate = env("w1")
    sync("hint", [load("delta_lists.json")], pipeline, gate)
    fp = gate.fingerprint(TASK_ID)

    pipeline2, gate2 = env("w2")  # new local state, same destination
    assert gate2.fingerprint(TASK_ID) == fp  # rebuilt from tasks.raw_json
    _, client = sync("hint", [load("delta_empty.json")], pipeline2, gate2)
    assert client.checkpoints == [1791562241035]


def test_reset_fetches_checkpoint_zero_and_merges_all(env, load):
    pipeline, gate = env()
    sync("hint", [load("delta_lists.json")], pipeline, gate)
    summary, client = sync("reset", [load("delta_lists.json")], pipeline, gate)
    assert client.checkpoints == [0]
    assert summary.merged_tasks == 1 and summary.pending_tasks == 0
    assert count(pipeline, "tasks") == 1


def test_type_change_fails_the_run_and_keeps_the_gate(env, load):
    pipeline, gate = env()
    first = load("delta_lists.json")
    sync("hint", [first], pipeline, gate)
    task = first["syncTaskBean"]["update"][0]
    drift = load("delta_empty.json")
    drift["checkPoint"] += 10_000_000
    drift["syncTaskBean"]["update"] = [{**task, "priority": "high"}]
    fp = gate.fingerprint(TASK_ID)
    with pytest.raises(PipelineStepFailed):
        sync("hint", [drift], pipeline, gate)
    assert gate.fingerprint(TASK_ID) == fp
    # bookmark did not move: the next run re-fetches the same checkpoint
    _, client = sync("hint", [load("delta_empty.json")], pipeline, gate)
    assert client.checkpoints == [1791562241035]


def test_unknown_kind_rejected():
    with pytest.raises(ValueError):
        run_sync("weekly")
