---
title: Known gaps in the TickTick extraction (start here for a redesign)
summary: every known way the current pipeline gets completion, recurrence, deletion or freshness wrong, with the page that explains each
verified: 2026-10-09
---

# Known gaps in the TickTick extraction

State on `2026-10-09`: the poller container is up, its loop is stopped, GitHub
extraction and Lightdash workflows are disabled, BigQuery and Grafana hold data frozen at
`2026-10-09 04:08Z`. This page lists everything known to be wrong or fragile,
so a redesign can start from the full list. Each row links to the page with
evidence. The whole path is declared legacy in
`adr/0007-current-extraction-storage-and-orchestration-are-legacy.md`.

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
| 12 | the v1 snapshot workflow ran code from the `incremental_run_gha` branch, triggered by an n8n job outside the repo | fixes on `main` never ran; the n8n job embeds a personal GitHub token that may still be valid | `traps/SNAPSHOT_WORKFLOW_RUNS_CODE_THAT_IS_NOT_ON_MAIN.md` |
| 13 | dbt behaviour switches on target name (`load_raw`, `stage_raw`, `load_snapshot`, `dump_snapshot`) | pipeline stages are hidden in `profiles.yml` and `dbt_project.yml` | `architecture/legacy-v1-snapshot.md` |
| 14 | CI per-PR datasets `PR_20` to `PR_25` were never dropped | clutter in BigQuery | GitHub issue |
| 15 | the private API can change without notice | silent breakage | `adr/0002-extract-from-the-private-sync-endpoint.md` |
| 16 | every BigQuery model is a view over external Parquet on GCS | no warehouse state of its own; each dashboard query re-reads the bucket; storage design is overwrite-only | `adr/0006-duckdb-copies-the-replica-to-gcs.md` |
| 17 | Lightdash `CD.yml` fired on every push to `main` and tried to deploy to an unused instance (disabled `2026-10-09`) | stuck `pending` runs; a bot could commit back to `main` | `architecture/legacy-lightdash.md` |
| 18 | `CI.yml` was the only dbt build on pull requests and is now disabled with Lightdash | no automated dbt check on PRs until a replacement exists | `reference/configuration.md` |

## Open questions for the API recon

1. Is there a request in the web app that links completed occurrences to their
   recurring series (a habit or repeat history view)?
2. How far back does a checkpoint-0 load go for closed tasks, and can older
   completions be paged?
3. When a project with tasks is hard-deleted, are the tasks sent in `delete[]`?
4. When a folder is deleted, do its projects get `groupId: null`?
5. Is there a longer-lived credential than the `t` session cookie?

## Redesign brief for the next session

Goal: decide, top to bottom, the idiomatic way to get TickTick data into a
dashboard now that the private web API can be mapped directly (Firefox driven by
an agent while logged in, plus a TickTick MCP server), instead of inferring
history from polls. Walk these in order; each answer constrains the next.

1. **Source.** Which web-app requests carry completion events, won't-do,
   reopen, delete and recurrence lineage? Answer the five questions above first.
2. **Credential.** What does the web app use to stay logged in, and can a
   service hold it without a human re-pasting a cURL?
3. **Change capture.** Is there anything event-like (websocket, push channel,
   per-entity history endpoint), or is polling the checkpoint still the only way?
   If polling, what is the cheapest cadence that loses nothing?
4. **History.** Where does an append-only record of every state change live, so
   that no single file is the only copy (issue #30)?
5. **Storage and load.** Replace overwrite-Parquet-plus-views
   (`adr/0006`) with something that keeps its own state: native BigQuery tables
   loaded incrementally, or a different warehouse entirely.
6. **Orchestration.** Nothing on GitHub Actions branches or n8n dispatch; one
   place holds both the code and its schedule. Decide whether the repo still
   needs to be public once Actions minutes no longer matter.
7. **Modelling.** Rebuild staging on the new raw shape; retire the v1 chain and
   its target switching (deletion list in `architecture/legacy-v1-snapshot.md`).
8. **Serving.** Grafana and its contracts stay; re-point panels at the new marts.
