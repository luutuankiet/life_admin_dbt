# Ingest on TickTick's sync hints with Dagster and dlt into BigQuery

Supersedes, as the target design named in `0007`: the poller loop
(`0005`) and the SQLite replica copied to GCS (`0006`). Keeps the private sync
endpoint (`0002`).

TickTick's web app holds a websocket and the server pushes `needSync` on every
change. A listener holds that socket and only records the time of the last push;
a Dagster sensor turns it into at most one fetch a minute, and a 30-minute schedule
fetches regardless. Each run hands the delta, the closed history and the new
bookmarks to one dlt load into native BigQuery tables: append-only raw history plus
current-state tables. dbt reads them through compat views shaped like the old raw
tables, so the v3 models and the Grafana dashboard did not change.

## Considered options

- **Poll on a timer, as the legacy poller did.** Rejected: one-minute freshness
  24/7 means about 1,440 fetches a day, mostly empty, and traffic no person's open
  tab would make.
- **Cloud Run or GitHub Actions on a schedule.** Rejected: a websocket needs a
  long-lived process, and the schedule loses the one-minute planning loop.
- **Keep SQLite as the state and copy it out.** Rejected: it made one host file the
  only copy of completion history. Now the bookmark commits in the warehouse with
  the rows, so any host resumes from BigQuery.

## Consequences

- The stack runs on one always-on host (a small VPS) and holds no state that
  matters there; rebuilding it needs the `.env` and the service-account key only.
- Session expiry is a human step: a 401 alerts and nothing retries or logs in.
- A list archive or delete sends no task change; tasks of such lists keep their
  last state (see `docs/architecture/pipeline-ingest.md`, "Known gaps").
- The compat views are a bridge. Modelling directly on the new tables is the next
  piece of work, after which they go.
