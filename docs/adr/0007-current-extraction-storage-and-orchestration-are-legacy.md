# The current extraction, storage and orchestration are legacy; redesign from the source up

Everything between TickTick and Grafana was built to keep a live dashboard
alive on free infrastructure, not to record what happened to a task. It
polls, it overwrites, and it infers. None of it is event-driven, and completion
history exists only in one SQLite file. Rather than patch each gap in
`docs/known-gaps.md`, we treat the whole path as legacy and redesign it, starting
from a reverse-engineered map of TickTick's private web API.

Declared legacy, with the record each one supersedes as the target design:

| part | what it does today | replaces as target |
|---|---|---|
| v1 Open API + dbt snapshots | infers completion from a task leaving the open list | (already frozen) |
| `incremental_run_gha` branch + `serverless_snapshot.yml` | runs a separate copy of the pipeline every few minutes on GitHub Actions | |
| n8n dispatch job | fires that workflow with an embedded personal GitHub token | |
| dbt target switching (`load_raw`, `stage_raw`, `load_snapshot`, `dump_snapshot`) | hides pipeline stages in `profiles.yml` and `dbt_project.yml` | |
| Parquet on GCS as the warehouse | DuckDB overwrites one Parquet file per table; BigQuery reads it as external tables; every dbt model on top is a view, so each dashboard query re-reads the bucket | `0006-duckdb-copies-the-replica-to-gcs.md` |
| Lightdash and its CI/CD | dashboards as code with a two-way sync | `0003-grafana-over-lightdash.md` already retired it; workflows disabled `2026-10-09` |

Not declared legacy: Grafana with contracts as data (`0004`), the dbt marts'
business rules, and the private sync endpoint itself (`0002`). The endpoint's
future is the first question for the recon.

## Considered options

- **Patch in place.** Rejected: issues #29 to #32 and the traps each fix one symptom; the root causes (overwrite instead of append, polling instead of events, state spread over branches and targets) would remain.
- **Keep the public-repo GitHub Actions loop.** Rejected: it exists only because Actions minutes are free on public repositories, and it splits code from its trigger.

## Consequences

No new features go into the legacy parts; fixes only if the dashboard is needed
before the redesign lands. The redesign brief and its starting questions are in
`docs/known-gaps.md`. Deletion lists live in `docs/architecture/legacy-v1-snapshot.md`
and `docs/architecture/legacy-lightdash.md`.
