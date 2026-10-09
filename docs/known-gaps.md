---
title: Known gaps in the TickTick extraction (start here for a redesign)
summary: every known way the current pipeline gets completion, recurrence, deletion or freshness wrong, with the page that explains each
verified: 2026-10-09
---

# Known gaps in the TickTick extraction

State on `2026-10-09`: the poller container is up, its loop is stopped, GitHub
extraction workflows are disabled, BigQuery and Grafana hold data frozen at
`2026-10-09 04:08Z`. This page lists everything known to be wrong or fragile,
so a redesign can start from the full list. Each row links to the page with
evidence.

## Data correctness

| # | gap | effect | page |
|---|---|---|---|
| 1 | completed recurring occurrences have no series id; only the title links them | habit streaks break on rename, merge across lists | `traps/HABIT_STREAK_RESETS_OR_MERGES_WHEN_A_RECURRING_TASK_IS_RENAMED.md` |
| 2 | staging keeps `completed_time` only for status 2; won't-do (-1) loses it | skipped habits dated by last edit; won't-do absent from closed metrics | `traps/WONT_DO_TASKS_MISSING_FROM_COMPLETED_METRICS.md` |
| 3 | reopened tasks keep a stale `completedTime` | any query not filtering on status over-counts | same page as 2 |
| 4 | the sync endpoint cannot replay old completions; earliest is `2025-05-28` | history before then is gone; a replica reset loses more | `traps/COMPLETED_TASKS_MISSING_BEFORE_A_DATE.md` |
| 5 | GCS Parquet is overwritten, not appended | BigQuery has no history of its own; the SQLite file is the only copy | same page as 4 |
| 6 | v1 inferred completion from snapshot disappearance | deletes, moves, archives counted as done | `traps/V1_COUNTS_DELETED_AND_MOVED_TASKS_AS_COMPLETED.md` |
| 7 | v1 and v3 schemas differ and both chains still build | duplicated logic (GTD work type), easy to query the wrong chain | `reference/v1-vs-v3-schema.md` |
| 8 | deleted projects and folders vanish with no tombstone; children are not cascaded | orphan `project_id`/`group_id` in marts (pinned by a test in `tests/marts/`) | `reference/ticktick-v3-sync-payload.md` |

## Operations

| # | gap | effect | page |
|---|---|---|---|
| 9 | the poller authenticates with a browser cookie and stops on any rejection | dashboard freezes until a human re-imports a cURL | `traps/POLLER_STOPPED_AND_DASHBOARD_FROZE.md` |
| 10 | `/health` reports the process, not data age | a halted loop looks healthy | same page as 9 |
| 11 | the `pollcycle` table logs every poll and is never pruned (560,271 rows after ~8 months) | the SQLite file grows forever | GitHub issue |
| 12 | the v1 snapshot workflow ran code from the `incremental_run_gha` branch, triggered by a scheduler outside the repo | fixes on `main` never ran; an unknown external caller holds a GitHub token | `traps/SNAPSHOT_WORKFLOW_RUNS_CODE_THAT_IS_NOT_ON_MAIN.md` |
| 13 | dbt behaviour switches on target name (`load_raw`, `stage_raw`, `load_snapshot`, `dump_snapshot`) | pipeline stages are hidden in `profiles.yml` and `dbt_project.yml` | `architecture/legacy-v1-snapshot.md` |
| 14 | CI per-PR datasets `PR_20` to `PR_25` were never dropped | clutter in BigQuery | GitHub issue |
| 15 | the private API can change without notice | silent breakage | `adr/0002-extract-from-the-private-sync-endpoint.md` |

## Open questions for the API recon

1. Is there a request in the web app that links completed occurrences to their
   recurring series (a habit or repeat history view)?
2. How far back does a checkpoint-0 load go for closed tasks, and can older
   completions be paged?
3. When a project with tasks is hard-deleted, are the tasks sent in `delete[]`?
4. When a folder is deleted, do its projects get `groupId: null`?
5. Is there a longer-lived credential than the `t` session cookie?
