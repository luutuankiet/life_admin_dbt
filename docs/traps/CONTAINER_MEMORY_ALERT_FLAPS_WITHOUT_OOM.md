---
symptom: "ContainerHighMemory flaps several times a day on the dagster container" / "memory alert fires at 80% and resolves at 99.9%" / "memory looks like a leak but no OOM kills"
area: ingest stack memory (EL/ticktick/ingest/docker/docker-compose.yml, the deploy host's Prometheus alert rule)
verified: 2026-10-27
---

# The container memory alert flaps, but nothing is leaking

**Symptom.** A host-side alert on container memory (usage above 80% of the limit)
fires and resolves 5 to 10 times a day on the `dagster` ingest container. It fires
at about 80% and "resolves" at about 99.9%. Usage climbs for about a week after a
restart, which looks like a leak, yet the container never gets OOM-killed and runs
keep succeeding.

**Mechanism.** `container_memory_usage_bytes` counts reclaimable page cache, not
just the memory the processes hold. `dagster dev` with SQLite storage
(`EL/ticktick/ingest/docker/dagster.yaml`) keeps one `.db` file per run under the
state dir's `history/runs`. The `purge_old_runs_daily` schedule
(`EL/ticktick/ingest/src/ticktick_ingest/defs.py`) deletes runs older than 7 days,
so that history stops growing once the 7-day window is full (a few hundred MB).
Its page cache still counts toward the cgroup. So after a restart, resident memory
and cache both grow for about a week and then level off.

At that plateau, under the old 1536 MiB cap, an idle container sat at about 79.5%
(about 900 MiB working set plus about 350 MiB cache). Any run pushed it past 80%.
The "resolve at 99.9%" is the kernel reclaiming cache when it reaches the limit,
which is normal behaviour, not a near miss.

The real budget is the working set (usage minus inactive file cache). It peaked
at about 1,210 MiB: webserver, daemon, the gRPC code server (about 490 MiB) and one
subprocess per run (about 300 MiB).

**Fix.**

1. The `dagster` `mem_limit` is now `2048m` (commit `c6017cf`), which leaves room
   for a run on top of the steady state.
2. The alert rule lives on the deploy host, not in this repo. It now uses
   `container_memory_working_set_bytes` with `for: 5m`. Backtested over 10 days,
   the old rule would have fired 63 times and the new rule 0.

**Verify.** `docker inspect` shows the container memory limit as `2147483648`, and
the working set stays well below the alert threshold between runs.

**General rule.** Judge this container's memory by working set, not usage. If the
working set nears the cap, raise `mem_limit` instead of loosening the alert.
