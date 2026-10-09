---
symptom: "dashboard data stopped updating" / "ticktick_poller_state loop_running 0" / "action: loop_stopped" / "server_rejected"
area: v3 poller (EL/ticktick/v3/poller/service.py)
verified: 2026-10-09
---

# The poller stops on the first rejection and stays stopped

**Symptom.** Grafana shows the same numbers for hours or days. Nothing errors in
dbt or BigQuery. The Parquet files in GCS have an old modified time. The poller
log ends with a JSON line containing `"action": "loop_stopped"`.

**Mechanism.** This is deliberate. `service.py` (around lines 183-210) stops the
loop when:

- **any HTTP error** comes back from TickTick (`status == "server_rejected"`),
  immediately; or
- **network errors** (DNS, timeout, connection) happen
  `TICKTICK_V3_ERROR_STREAK_HALT` times in a row (default `3`).

The endpoint is private and authenticates with a browser session cookie (`t=`)
plus a replayed `User-Agent`. An expired cookie, a rate limit and a changed
endpoint all look alike: some 4xx or 5xx. Retrying an expired session at a
30-second interval risks the account, so the trade chosen was to stop and wait
for a human. See `docs/adr/0005-poller-halts-on-any-rejection.md`.

Nothing restarts it. The container stays up and `/health` stays green, because
the web app is fine; only the loop is off.

**Fix.**

1. Check `GET /status` and the last rows of `GET /cycles` for the error.
2. If it is auth: log into TickTick in a browser, copy any
   `/api/v3/batch/check/...` request as cURL, and `POST` it to
   `/profiles/import-curl` (or use the form at `/`).
3. `POST /poll/start`.

**Verify.** `ticktick_poller_state{loop_running="1"}` in `/metrics`, and new
rows in `/cycles` with a success status.

**General rule.** A health check that reports the process, not the work, lies
during a halt. Alert on data age (newest `modified_time` or Parquet mtime), not
on the container.
