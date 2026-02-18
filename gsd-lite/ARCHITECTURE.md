# Architecture

*Mapped: 2026-02-18*

## Project Structure Overview

```
life_admin_dbt/
├── .github/workflows/           # CI/CD and extraction pipelines
│   ├── serverless_snapshot.yml  # TickTick extraction (triggers incremental_run_gha branch)
│   ├── todoist_EL.yml           # Todoist extraction (hourly, main branch)
│   ├── CI.yml / CD.yml          # dbt CI/CD
│   └── LD_write_back.yml        # Lightdash sync
│
├── EL/                          # Extract-Load scripts (main branch)
│   ├── ticktick/fetch_ticktick.py
│   └── todoist/fetch_todoist.py
│
├── models/                      # dbt models (main branch - BQ views)
│   ├── raw/                     # External table definitions
│   │   ├── external_table_stage/  # BQ external table configs
│   │   └── todoist/               # Todoist raw models
│   ├── staging/
│   │   ├── ticktick/            # TickTick staging + base models
│   │   │   ├── base/            # Type casting, snapshot integration
│   │   │   └── stg__*.sql       # Staging transformations
│   │   └── todoist/             # Todoist staging + base models
│   └── marts/                   # Dimensional models
│       ├── fct_tasks.sql        # Core fact table (TickTick)
│       ├── fct_habit.sql        # Habit fact table (Todoist)
│       ├── dim_projects.sql     # Project dimension
│       ├── dim_folders.sql      # Folder dimension (H2: Areas)
│       ├── dim_tags.sql         # Tag dimension
│       └── dim_date_spine.sql   # Date spine for lookahead joins
│
├── lightdash/                   # Dashboard-as-code
│   ├── dashboards/
│   │   ├── gtd-dash-v1-0.yml    # Main GTD dashboard (3 tabs)
│   │   └── todoist-tracker.yml  # Habit tracker dashboard
│   └── charts/                  # Individual chart definitions
│
├── tmp/branches/incremental_run_gha/  # Worktree: snapshot pipeline
│   ├── ticktick_fetcher.py      # TickTick extraction script
│   ├── snapshots/               # dbt snapshot configs (SCD2)
│   └── models/
│       ├── 1_load_statefull_to_mem/   # Load GCS → DuckDB
│       └── 2_dump_snapshot_to_gcs/    # Dump snapshot → GCS
│
└── gsd-lite/                    # Project documentation
```

## Tech Stack

| Layer | Technology | Notes |
|-------|------------|-------|
| **Extraction** | Python + requests_ratelimiter | Rate-limited API clients |
| **Orchestration** | GitHub Actions | Scheduled workflows, no persistent compute |
| **Snapshot Engine** | DuckDB (in-memory) | Runs in GHA, persists to GCS |
| **Storage** | GCS buckets | JSONL/CSV files, serves as snapshot backup |
| **Warehouse** | BigQuery | External tables pointing to GCS (views only) |
| **Transform** | dbt-core + dbt-bigquery | All models materialized as views |
| **BI** | Lightdash | Self-hosted on EU VM (Docker + Traefik) |

## Data Flow

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                           TICKTICK PIPELINE                                 │
│                     (incremental_run_gha branch)                            │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│  TickTick API ──▶ ticktick_fetcher.py ──▶ tasks_raw.json                   │
│       │              (rate limited)        projects_raw.json                │
│       │                                          │                          │
│       │                                          ▼                          │
│       │                              ┌─────────────────────┐                │
│       │                              │  DuckDB (in-memory) │                │
│       │                              │  dbt snapshot SCD2  │                │
│       │                              └──────────┬──────────┘                │
│       │                                         │                           │
│       │                                         ▼                           │
│       │                              GCS: tasks_snapshot.jsonl              │
│       │                                   projects_snapshot.jsonl           │
│       │                                                                     │
└───────┼─────────────────────────────────────────┼───────────────────────────┘
        │                                         │
        │ (API limitation: completed             │
        │  tasks disappear from endpoint)        │
        │                                         │
        ▼                                         ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                           BIGQUERY LAYER                                    │
│                          (main branch)                                      │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│   External Tables (GCS → BQ)                                                │
│   ├── ticktick_raw.tasks_snapshot                                          │
│   ├── ticktick_raw.projects_snapshot                                       │
│   ├── todoist_raw.active_tasks                                             │
│   └── todoist_raw.completed_tasks                                          │
│              │                                                              │
│              ▼                                                              │
│   Staging Models (views)                                                    │
│   ├── base__ticktick__tasks_snapshot  ← infers completed_time from SCD2   │
│   ├── stg__ticktick__tasks            ← UNION: live + snapshot (done)     │
│   └── stg__todoist__tasks                                                  │
│              │                                                              │
│              ▼                                                              │
│   Mart Models (views)                                                       │
│   ├── fct_tasks    ← GTD work type categorization (🥩/🧃)                  │
│   ├── fct_habit    ← Todoist habits                                        │
│   ├── dim_projects ← H1: Projects                                          │
│   ├── dim_folders  ← H2: Areas of Responsibility                           │
│   └── dim_date_spine ← Lookahead join workaround                           │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
                              │
                              ▼
┌─────────────────────────────────────────────────────────────────────────────┐
│                         LIGHTDASH (EU VM)                                   │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                             │
│   gtd-dash-v1-0 (3 tabs)                                                    │
│   ├── main tasks      ← lookahead, distribution, "what did you do"         │
│   ├── recurring tasks ← todoist habits                                     │
│   └── GTD weekly review ← inbox count, empty projects, project pulse       │
│                                                                             │
│   todoist-tracker                                                           │
│   └── Today's habits, streak tracking                                       │
│                                                                             │
└─────────────────────────────────────────────────────────────────────────────┘
```

## Key Design Decisions

### 1. Snapshot-based Completion Tracking (CRITICAL)

**Problem:** TickTick API removes completed tasks from the endpoint — no completion metadata available.

**Solution:** SCD2 snapshots detect "deletion" as completion:
- Task present in snapshot N, absent in N+1 → `dbt_valid_to` = completion time
- `stg__ticktick__tasks` UNIONs live tasks (status=0) with snapshot "completed" tasks (status=2)

**Risk:** Snapshot table is irreplaceable source of truth. Cannot rebuild from API.

### 2. Two-Branch Architecture

| Branch | Purpose | Runs On |
|--------|---------|---------|
| `main` | BQ models, Lightdash charts, Todoist EL | Local dev, CI/CD |
| `incremental_run_gha` | TickTick snapshot pipeline | GHA only (every 15 min) |

**Why:** Snapshot models use DuckDB; main models use BigQuery. Different adapters, different targets.

**Pain point:** Hard to observe, hard to test, snapshot models outside main lineage.

### 3. All Views, No Materialization

All dbt models are `materialized: view` to minimize BigQuery costs (no extraction charges at rest). Queries only incur cost when Lightdash actually runs them.

### 4. Lookahead Join Workaround

Lightdash doesn't support lookahead queries natively. Workaround:
- `dim_date_spine` generates future dates
- `marts.yml` joins `fct_tasks` to `dim_date_spine` on `due_date`
- Enables "tasks due in next 5 weeks" filtering

## Entry Points

| Task | Command / Location |
|------|-------------------|
| **Run TickTick extraction** | GHA: `serverless_snapshot.yml` (dispatches to `incremental_run_gha`) |
| **Run Todoist extraction** | GHA: `todoist_EL.yml` or `python EL/todoist/fetch_todoist.py` |
| **Build BQ models locally** | `dbt build --target dev` |
| **Stage external tables** | `dbt run-operation stage_external_sources --target stage_raw` |
| **Sync Lightdash charts** | GHA: `LD_write_back.yml` or `lightdash deploy` |

## Environment Variables

| Variable | Purpose |
|----------|---------|
| `TICKTICK_API_KEY` | TickTick Open API auth |
| `TODOIST_API_KEY` | Todoist API auth |
| `GCS_KEY` / `GCS_SECRET` | GCS HMAC credentials for DuckDB httpfs |
| `GCS_RAW_BUCKET` | Bucket name for snapshot storage |
| `DBT_BQ_PROJECT` / `DBT_BQ_LOCATION` | BigQuery project config |
| `DBT_TARGET` | Target profile (dev/prod/load_snapshot/dump_snapshot) |
| `ENABLE_GTD_WORK_TYPE_CATEGORIZATION` | Toggle deep/shallow work tagging |

## Known Technical Debt

1. **Two-branch split** — Snapshot pipeline isolated, hard to observe lineage
2. **Manual bootstrap** — First-run requires manual bucket creation, schema setup
3. **No automated backup** — Snapshot GCS files are source of truth but not versioned
4. **Lightdash latency** — EU VM serving Asia user; ~8s query vs 1s direct BQ
5. **Batch extraction** — 15-min intervals, ~1 min full extract due to rate limits
6. **Lookahead workaround** — `dim_date_spine` join is brittle, couples model to BI layer

---

*This document is the "how" — see PROJECT.md for the "why".*
