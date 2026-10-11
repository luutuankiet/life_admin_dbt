---
name: codebase-map
description: Where behaviour lives in this repo — a per-area map of which files and line ranges own what, so you can open the right file instead of searching for it. Use before hunting for where something is implemented, before adding a feature that touches existing behaviour, and when a change seems to need edits in more places than expected.
---

# Where things live

This repo is large enough that finding the right file costs more than reading it.
The pages below are maps: for each area, which files own it and roughly where in
them.

**Pick the area, open that one page, then go straight to the file.** Do not read
every page — that defeats the point.

<!-- BEGIN GENERATED INDEX -- edit the pages, not this block -->

## Where things live

One page per area of the system. Read before going looking for where
something is implemented.

| page | covers | verified |
|---|---|---|
| [Grafana dashboards, exports and contracts](../../../docs/architecture/grafana-dashboards.md) | where the dashboard JSON comes from, why it contains ${DBT_BQ_PROJECT} placeholders, how dashboard regressions are tested | 2026-10-09 |
| [Legacy Lightdash layer (dashboards as code, retired for Grafana)](../../../docs/architecture/legacy-lightdash.md) | what the Lightdash CI/CD loop did, which files and workflows belong to it, what can be deleted | 2026-10-09 |
| [Legacy v1 pipeline (Open API + dbt snapshots + branch workflow)](../../../docs/architecture/legacy-v1-snapshot.md) | what the incremental_run_gha branch and the Serverless snapshot workflow did, why stg__ticktick__tasks unions snapshot rows, what can be deleted | 2026-10-09 |
| [Current pipeline (websocket hint, Dagster and dlt into BigQuery)](../../../docs/architecture/pipeline-ingest.md) | how a TickTick edit reaches BigQuery today, which run kinds exist, the run lifecycle and what a cancelled, failed or killed run or a lost host does, the body-edit gate, the ingest tables and bookmarks, the compat views the v3 dbt models read, the failure alert, where state lives and how to rebuild it, known gaps | 2026-10-11 |
| [Legacy pipeline (v3 poller to Grafana)](../../../docs/architecture/pipeline-v3.md) | (legacy, superseded by pipeline-ingest.md) where TickTick data came from before the ingestion stack, how it reaches BigQuery, which dbt models feed the dashboard, where to restart the poller | 2026-10-09 |

## Guides

Long-form pages that belong to no single area.

| page | summary | verified |
|---|---|---|
| [Known gaps in the TickTick extraction (start here for a redesign)](../../../docs/known-gaps.md) | every known way the current pipeline gets completion, recurrence, deletion or freshness wrong, with the page that explains each | 2026-10-09 |

<!-- END GENERATED INDEX -->

The same table, browsable, is [docs/README.md](../../../docs/README.md).

## How to read a line range

Every entry is `file — lines — what lives there`. **The line numbers are a
starting point, not an address.** They drift with every commit that touches the
file above them, and nothing regenerates them.

So: jump to roughly that line, then confirm you are in the right place by what the
code says, not by the number. If a range is off by more than a screen or two, fix
it in the page and re-date it — that is a one-line edit and it is how the map
stays worth having.

Line ranges are given at all because the files that matter most here are big:
`models/marts/marts.yml` (1,770 lines of column docs and tests) and the exported dashboard `grafana/dashboards/gtd-migration/gtd-main-tasks-v3.json` (1,078 lines). "It's in <that file>" is not an
answer.

## What this map does not tell you

It tells you **where**, not **why it is dangerous**. Several of the areas below
have failure modes that produce no error message. Those are catalogued
separately, by symptom, in the `repo-maintenance` skill and in
[docs/README.md](../../../docs/README.md). If you are about to change shared state
or anything on how `completed_time` and `status` are derived (`models/staging/ticktick/stg__ticktick_v3__tasks.sql`) or the poller's SQLite replica, look there first.

## Keeping it accurate

A map that lies is worse than none, because it sends people confidently to the
wrong file. Two habits keep it honest:

- **Re-date what you touch.** If you worked in an area and the page was right,
  bump `verified:`. If it was wrong, fix it and bump.
- **Add an area when you create one, not later.** A new subsystem with no page is
  invisible; the next person re-derives its shape from scratch.

To add a page, follow the same rules as any other doc — see the `repo-maintenance`
skill. Frontmatter for an area page is `title`, `covers` (what someone would be
looking for, phrased as they would phrase it), and `verified`. Then run
`scripts/gen-docs-index.sh`; the block above is generated and hand edits to it
are overwritten.
