"""Dagster wiring: sensor decision, ntfy message, definitions load. Offline."""

from __future__ import annotations

import httpx
from dagster._utils.error import SerializableErrorInfo

from ticktick_ingest import defs as d


def err(cls_name: str, message: str, cause=None) -> SerializableErrorInfo:
    return SerializableErrorInfo(message=message, stack=[], cls_name=cls_name, cause=cause)


# ---------------------------------------------------------------- hint_decision


def test_no_hint_file_never_launches():
    assert d.hint_decision(None, d.HintCursor(), now_ms=10**12) is None


def test_newer_hint_launches_and_moves_cursor():
    nxt = d.hint_decision(1_000_000, d.HintCursor(hint=900_000, launched_at=0), now_ms=2_000_000)
    assert nxt == d.HintCursor(hint=1_000_000, launched_at=2_000_000)


def test_same_or_older_hint_does_not_launch():
    cur = d.HintCursor(hint=1_000_000, launched_at=0)
    assert d.hint_decision(1_000_000, cur, now_ms=5_000_000) is None
    assert d.hint_decision(999_999, cur, now_ms=5_000_000) is None


def test_newer_hint_inside_gap_waits_then_launches():
    cur = d.HintCursor(hint=1_000_000, launched_at=2_000_000)
    assert d.hint_decision(1_500_000, cur, now_ms=2_000_000 + 60_000) is None
    nxt = d.hint_decision(1_500_000, cur, now_ms=2_000_000 + 60_001)
    assert nxt == d.HintCursor(hint=1_500_000, launched_at=2_060_001)


def test_cursor_round_trips_and_tolerates_garbage():
    cur = d.HintCursor(hint=5, launched_at=7)
    assert d.HintCursor.parse(cur.dump()) == cur
    assert d.HintCursor.parse(None) == d.HintCursor()
    assert d.HintCursor.parse("not json") == d.HintCursor()
    assert d.HintCursor.parse("[1]") == d.HintCursor()


# ---------------------------------------------------------------- ntfy_message


def test_auth_rejected_says_paste_cookie():
    wrapped = err(
        "DagsterExecutionStepExecutionError",
        'Error occurred while executing op "ticktick_sync_tables"',
        cause=err("AuthRejected", "401 user_not_sign_on"),
    )
    title, body = d.ntfy_message("r1", "ticktick_sync", "step failed", [wrapped])
    assert title == "ticktick-ingest failed"
    assert body.splitlines()[0] == "cookie rejected: paste a fresh t"
    assert "AuthRejected: 401 user_not_sign_on" in body
    assert "r1" in body


def test_other_error_uses_inner_cause_and_truncates():
    long = "x" * 1000
    wrapped = err("DagsterExecutionStepExecutionError", "wrapper", cause=err("ValueError", long))
    _, body = d.ntfy_message("r2", "ticktick_sync", "step failed", [wrapped])
    first = body.splitlines()[0]
    assert "cookie rejected" not in body
    assert first.startswith("ValueError: xxx")
    assert len(first) == 300


def test_no_step_errors_falls_back_to_run_message():
    _, body = d.ntfy_message("r3", "ticktick_sync", "run worker crashed", [])
    assert body.splitlines()[0] == "run worker crashed"


def test_post_ntfy_sends_title_header_and_body():
    seen = {}

    def handler(request: httpx.Request) -> httpx.Response:
        seen["title"] = request.headers["Title"]
        seen["body"] = request.content.decode()
        return httpx.Response(200)

    status = d.post_ntfy("https://ntfy.invalid/t", "T", "B", transport=httpx.MockTransport(handler))
    assert status == 200 and seen == {"title": "T", "body": "B"}


# ---------------------------------------------------------------- definitions


def test_definitions_resolve():
    job = d.defs.resolve_job_def("ticktick_sync")
    assert len(job.asset_layer.executable_asset_keys) == len(d.TABLES)
    assert d.hint_sensor.minimum_interval_seconds == 30
    assert d.safety_net.cron_schedule == "*/30 * * * *"
    assert {s.name for s in d.defs.sensors} == {"hint_sensor", "ntfy_on_failure"}


def test_job_runs_with_kind_and_dagster_run_id(monkeypatch):
    calls = []

    class Summary:
        kind = "safety"
        rows = {"tasks": 2, "raw_lists": 0}
        load_ids = ["1"]

        def as_dict(self):
            return {"kind": self.kind}

    def fake_run_sync(kind, *, run_id):
        calls.append((kind, run_id))
        return Summary()

    monkeypatch.setattr("ticktick_ingest.pipeline.run_sync", fake_run_sync)
    job = d.defs.resolve_job_def("ticktick_sync")
    result = job.execute_in_process(run_config=d.run_config("safety"))
    assert result.success
    assert calls == [("safety", result.run_id)]
    keys = {m.asset_key.path[-1] for m in result.asset_materializations_for_node(d.OP_NAME)}
    assert keys == {"tasks"}
