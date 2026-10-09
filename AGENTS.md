# life_admin_dbt

A personal analytics project for a GTD practice. Tasks come out of TickTick and get
modelled in dbt on BigQuery. The result is a planning dashboard in Grafana: what is
due over the next five weeks, how work splits across life areas, and habit streaks.
One person runs it, and it is public on GitHub.

## Hard constraints

- **TickTick has no webhooks and no official change feed.** Every extractor here
  polls. The current extractor uses TickTick's private web-app sync endpoint, so
  any TickTick release can change the payload without notice.
- **The source does not reliably say what got closed.** Won't-do, reopened,
  recurring and deleted tasks each break a "completed" metric in a different
  way. Read `docs/known-gaps.md` before you trust any completion number.
- **The SQLite replica on the poller host is the only copy of completion
  history.** The sync endpoint cannot replay old completions. Resetting the
  replica loses them for good.
- **The repo is public.** Deployment values (project ids, hosts, buckets, emails)
  come from environment variables. They are listed in
  `docs/reference/configuration.md`. Never commit a literal value.

## Layout

```
EL/ticktick/v3/poller/     - current extractor: FastAPI + SQLite replica, emits Parquet to GCS
EL/ticktick/v3/docker/     - compose file and .env.example for the poller host
EL/ticktick/fetch_ticktick.py - legacy v1 Open API fetcher (frozen)
EL/todoist/                - legacy Todoist fetcher (habits moved to TickTick)
models/raw/                - external table definitions over GCS (dbt-external-tables)
models/staging/ticktick/   - base__* typing, stg__* business rules; *_v3 = current chain
models/marts/              - dim_*/fct_* views; *_v3 feed Grafana, fct_habit* feed streaks
tests/marts/               - singular dbt data tests on the v3 marts
grafana/                   - exported dashboards, contract YAML, exporter script
tests/grafana/             - pytest runner for the Grafana contracts
lightdash/, models/lightdash_exposures.yml - legacy BI layer, superseded by Grafana
.github/workflows/         - Grafana CI, dbt docs; extraction + Lightdash disabled (legacy)
docs/                      - architecture, traps, reference, decision records
```

## Commands

```sh
uv sync --group dev                             # root project: dbt + test deps
DBT_PROFILES_DIR=. uv run dbt parse             # needs the variables in .env.example
DBT_PROFILES_DIR=. uv run dbt build -s +fct_tasks_v3_semantic_base   # needs BigQuery creds
uv run --group dev pytest tests/grafana -q      # Grafana contracts, offline
scripts/gen-docs-index.sh                        # regenerate docs/README.md and skill indexes
```

`grafana/scripts/` is a separate uv project for the exporter. Run it from that
directory.

<!-- Standard block. Everything above belongs to this project; everything below is
     the pointer every repo laid out this way carries. -->

## Documentation

Indexed in [docs/README.md](docs/README.md). Every page is self-contained — it
assumes you opened that one file and have nothing else loaded.

| where | what | read it |
|---|---|---|
| [architecture/](docs/architecture/) | where behaviour lives, one page per area | before going looking for something |
| [traps/](docs/traps/) | failure modes with no error message, indexed by symptom | before debugging something wrong but not crashing |
| [reference/](docs/reference/) | simply true, expensive to re-derive | when you need the detail |
| [adr/](docs/adr/) | why the repo is the way it is | before changing something that looks odd |

## Before you wrap up

Leave the repo holding what this session cost you to find out. Four rules.

1. **Sort it, and expect most of it to go nowhere.** A next action is an issue. A
   durable, expensive-to-re-derive fact is a page. A choice that was hard to
   reverse, surprising without context and a real trade-off is a decision record
   under `docs/adr/`. Status, dates, version pins and plans are none of those —
   delete them.
2. **A doc is the last resort.** Type error → test → comment at the site → doc.
   Name the single line you would have commented instead; if you can name it,
   comment it and stop.
3. **Verify against running code before writing, and date the page `verified:`.**
   Anything remembered from earlier in the session is stale until re-read. Deleting
   a draft because the problem is already fixed is a success.
4. **Append, never rewrite.** Supersede a merged decision record with a new one
   naming what it replaces. A trap filename is an identifier quoted elsewhere:
   edit the body, never the name.

Then run `scripts/gen-docs-index.sh`. Never hand-maintain an index.
