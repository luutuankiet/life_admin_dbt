---
symptom: "no completed tasks before 2025-05-28" / "history vanished after I reset the poller" / "completed count dropped after redeploy"
area: v3 poller replica, checkpoint sync
verified: 2026-10-09
---

# Completion history has a floor, and a replica reset lowers it

**Symptom.** The earliest `completed_time` in BigQuery is `2025-05-28`, even
though the TickTick account is older. After the poller's SQLite file is
recreated, older completions disappear from every dashboard.

**Mechanism.** The poller syncs from `/api/v3/batch/check/{checkpoint}`. A first
sync from checkpoint `0` returns what the web app would load on a fresh login.
That includes open tasks and only a **recent window** of closed ones. Older
completed tasks are not in that payload, and later deltas only carry changes.
The replica therefore holds:

- everything the endpoint returned on its first sync, plus
- every change observed while the loop was running.

Anything closed while the loop was stopped, and older than the window at the
next bootstrap, is never seen. The Parquet files in GCS are full rewrites of
the replica, not an append log, so **BigQuery holds no history the replica does
not have**.

The current replica's first poll cycle is `2026-02-20 00:54:13`. It still holds
completions back to `2025-05-28` because that was the window on that first sync.

A per-project completed-task endpoint (`/api/v2/project/{ids}/completed`) was
looked at and rejected at the time, so there is no backfill path in the code.

**Fix.** Before any reset or redesign:

1. Copy `ticktick_replica.db` off the poller host (stop the loop first).
2. Archive the current `tasks.parquet` under a dated prefix in the bucket.
3. Seed the new store from that archive, or union it in dbt.

For the longer term, keep an append-only history (date-partitioned Parquet or
a BigQuery table loaded on every emit) instead of only the latest snapshot.

**Verify.**

```sql
select min(completed_time) from `ticktick_raw.tasks_v3` where status in (2, -1);
```

Record the value before a reset and compare after.

**General rule.** If a sync API cannot replay history, the first store that saw
an event is the system of record. Back it up like one.
