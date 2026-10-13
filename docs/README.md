# Documentation

Every page here is written for a maintainer six months from now who opened
exactly this file from a search result and has nothing else loaded.

This index is generated. Run `scripts/gen-docs-index.sh` after adding or
renaming a page; `--check` fails if it is stale.

<!-- BEGIN GENERATED INDEX -- edit the pages, not this block -->

## Where things live

One page per area of the system. Read before going looking for where
something is implemented.

| page | covers | verified |
|---|---|---|
| [Grafana dashboards, exports and contracts](architecture/grafana-dashboards.md) | where the dashboard JSON comes from, why it contains ${DBT_BQ_PROJECT} placeholders, how dashboard regressions are tested | 2026-10-09 |
| [Legacy Lightdash layer (dashboards as code, retired for Grafana)](architecture/legacy-lightdash.md) | what the Lightdash CI/CD loop did, which files and workflows belong to it, what can be deleted | 2026-10-09 |
| [Legacy v1 pipeline (Open API + dbt snapshots + branch workflow)](architecture/legacy-v1-snapshot.md) | what the incremental_run_gha branch and the Serverless snapshot workflow did, why stg__ticktick__tasks unions snapshot rows, what can be deleted | 2026-10-09 |
| [Current pipeline (websocket hint, Dagster and dlt into BigQuery)](architecture/pipeline-ingest.md) | how a TickTick edit reaches BigQuery today, which run kinds exist, the run lifecycle and what a cancelled, failed or killed run or a lost host does, the body-edit gate, the ingest tables and bookmarks, the compat views the v3 dbt models read, the failure alert, retention and log rotation, where state lives and how to rebuild it, known gaps | 2026-10-13 |
| [Legacy pipeline (v3 poller to Grafana)](architecture/pipeline-v3.md) | (legacy, superseded by pipeline-ingest.md) where TickTick data came from before the ingestion stack, how it reaches BigQuery, which dbt models feed the dashboard, where to restart the poller | 2026-10-09 |

## Traps

Failure modes that produce no error message, indexed by the symptom you
would observe. Read before debugging behaviour that is wrong but not
crashing.

| symptom | page | area | verified |
|---|---|---|---|
| no completed tasks before 2025-05-28" / "history vanished after I reset the poller" / "completed count dropped after redeploy | [COMPLETED_TASKS_MISSING_BEFORE_A_DATE](traps/COMPLETED_TASKS_MISSING_BEFORE_A_DATE.md) | v3 poller replica, checkpoint sync | 2026-10-09 |
| habit streak reset to zero after I renamed the recurring task" / "two different habits share one streak" / "how do I find all occurrences of a recurring task | [HABIT_STREAK_RESETS_OR_MERGES_WHEN_A_RECURRING_TASK_IS_RENAMED](traps/HABIT_STREAK_RESETS_OR_MERGES_WHEN_A_RECURRING_TASK_IS_RENAMED.md) | TickTick v3 source, fct_habit_streaks | 2026-10-09 |
| Dagster UI unreachable after a reboot" / "no new ingest runs since the host restarted" / "cannot assign requested address" / "ticktick-ingest container Exited or Created | [INGEST_STACK_ABSENT_AFTER_HOST_REBOOT](traps/INGEST_STACK_ABSENT_AFTER_HOST_REBOOT.md) | ingest stack host (EL/ticktick/ingest/docker/docker-compose.yml, EL/ticktick/ingest/docker/host/) | 2026-10-11 |
| dashboard data stopped updating" / "ticktick_poller_state loop_running 0" / "action: loop_stopped" / "server_rejected | [POLLER_STOPPED_AND_DASHBOARD_FROZE](traps/POLLER_STOPPED_AND_DASHBOARD_FROZE.md) | v3 poller (EL/ticktick/v3/poller/service.py) | 2026-10-09 |
| I fixed the snapshot model on main but the workflow still runs the old code" / "where is ticktick_fetcher.py" / "Serverless snapshot workflow has no schedule but ran every few minutes | [SNAPSHOT_WORKFLOW_RUNS_CODE_THAT_IS_NOT_ON_MAIN](traps/SNAPSHOT_WORKFLOW_RUNS_CODE_THAT_IS_NOT_ON_MAIN.md) | .github/workflows/serverless_snapshot.yml, incremental_run_gha branch | 2026-10-09 |
| deleted task shows as completed" / "tasks in an archived list counted as done" / "completed_time equals the snapshot run time | [V1_COUNTS_DELETED_AND_MOVED_TASKS_AS_COMPLETED](traps/V1_COUNTS_DELETED_AND_MOVED_TASKS_AS_COMPLETED.md) | legacy v1 models (stg__ticktick__tasks, dbt snapshots) | 2026-10-09 |
| won't do tasks have null completed_time" / "skipped habit shows on the wrong day" / "open task has a completed_time | [WONT_DO_TASKS_MISSING_FROM_COMPLETED_METRICS](traps/WONT_DO_TASKS_MISSING_FROM_COMPLETED_METRICS.md) | stg__ticktick_v3__tasks, fct_habit_streaks, completed-activity marts | 2026-10-09 |

## Reference

Simply true, and expensive to re-derive.

| page | summary | verified |
|---|---|---|
| [Configuration and environment variables](reference/configuration.md) | every deployment-specific value, where it is set (GitHub, poller host, local .env), and its default | 2026-10-11 |
| [TickTick v3 sync payload semantics](reference/ticktick-v3-sync-payload.md) | what /api/v3/batch/check/{checkpoint} returns for each user action, and how the poller merges it | 2026-10-09 |
| [v1 (Open API) vs v3 (sync endpoint) task schema](reference/v1-vs-v3-schema.md) | column-level differences between the two TickTick sources and their dbt chains | 2026-10-09 |

## Guides

Long-form pages that belong to no single area.

| page | summary | verified |
|---|---|---|
| [Known gaps in the TickTick extraction (start here for a redesign)](known-gaps.md) | every known way the current pipeline gets completion, recurrence, deletion or freshness wrong, with the page that explains each | 2026-10-09 |

## Decisions

Why the repo is the way it is. A merged decision is immutable -- supersede
it with a new one rather than editing it.

- [Replace the working-notes folder with indexed docs collections](adr/0001-replace-working-notes-with-docs-collections.md)
- [Extract from TickTick's private sync endpoint, not the Open API](adr/0002-extract-from-the-private-sync-endpoint.md)
- [Grafana for dashboards, dbt for semantics; Lightdash retired](adr/0003-grafana-over-lightdash.md)
- [Test Grafana dashboards with declarative contracts and one generic runner](adr/0004-grafana-contracts-as-data.md)
- [The poller stops on any HTTP rejection and waits for a human](adr/0005-poller-halts-on-any-rejection.md)
- [DuckDB copies the SQLite replica to GCS as Parquet after each changed cycle](adr/0006-duckdb-copies-the-replica-to-gcs.md)
- [The current extraction, storage and orchestration are legacy; redesign from the source up](adr/0007-current-extraction-storage-and-orchestration-are-legacy.md)
- [Ingest on TickTick's sync hints with Dagster and dlt into BigQuery](adr/0008-ingest-on-sync-hints-with-dagster-and-dlt.md)

<!-- END GENERATED INDEX -->
