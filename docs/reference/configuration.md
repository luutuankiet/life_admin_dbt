---
title: Configuration and environment variables
summary: every deployment-specific value, where it is set (GitHub, poller host, local .env), and its default
verified: 2026-10-09
---

# Configuration and environment variables

This repository is public. Anything that identifies a deployment (GCP project,
buckets, hosts, emails, tokens) comes from the environment. Locally, copy
`.env.example` to `.env` (gitignored) and fill it in. In GitHub Actions, the same
names are repository **secrets** or **variables**. On the poller host they go in
`EL/ticktick/v3/docker/.env`.

## dbt (`profiles.yml`, `dbt_project.yml`)

| variable | required | default | used for |
|---|---|---|---|
| `DBT_TARGET` | no | `dev` | default target; also names the elementary dataset |
| `DBT_BQ_PROJECT` | yes | | BigQuery project for every target |
| `DBT_BQ_LOCATION` | yes | | BigQuery location |
| `DBT_BQ_KEYFILE` | no | `./sa.json` | service-account key path (CI writes it from `DBT_BQ_KEYFILE_JSON`) |
| `DBT_DEV_DATASET` | no | `ticktick_dbt_dev` | dataset for `dev` |
| `DBT_PROD_DATASET` | no | `ticktick_dbt_prod` | dataset for `prod`; Grafana queries this one |
| `DBT_CI_SCHEMA` | no | `ticktick_dbt_ci` | per-PR dataset in CI (`PR_<n>`) |
| `GCS_RAW_BUCKET` | yes | | bucket behind the external tables in `models/raw/external_table_stage/dump.yml` |
| `GCS_KEY`, `GCS_SECRET` | legacy targets | | GCS HMAC pair for DuckDB targets (`load_raw`, `load_snapshot`, `dump_snapshot`) |
| `GCS_REGION` | no | `auto` | region on those DuckDB S3 secrets |
| `DBT_TIMEZONE` | no | `UTC` | `var('timezone')`; every timestamp is converted to this |
| `DBT_LOAD_INTERVAL` | no | `15` | minutes; used by the v1 "next load" freshness row |
| `ENABLE_GTD_WORK_TYPE_CATEGORIZATION` | no | | `true` fills `gtd_work_type` |
| `GTD_DEEP_WORK_TAGS`, `GTD_SHALLOW_WORK_TAGS` | no | | JSON arrays of tag names |
| `DBT_OWNER_EMAIL` | no | `owner@example.com` | owner on Lightdash exposures |
| `LIGHTDASH_URL` | no | `https://lightdash.example.com` | base URL on Lightdash exposures; also used by the Lightdash workflow |

## v3 poller (`EL/ticktick/v3/poller/config.py`)

| variable | default | meaning |
|---|---|---|
| `TICKTICK_V3_ROOT` | the `EL/ticktick/v3` directory | base for the paths below |
| `TICKTICK_V3_DB_PATH` | `<root>/data/ticktick_replica.db` | the SQLite replica, **the only copy of history** |
| `TICKTICK_V3_RAW_ARCHIVE_DIR` | `<root>/data/raw_batches` | raw JSON of each delta |
| `TICKTICK_V3_ARCHIVE_RAW` | `1` | keep raw deltas |
| `TICKTICK_V3_RAW_RETENTION_HOURS` | `24` | prune raw deltas older than this |
| `TICKTICK_V3_POLL_INTERVAL` | `30` | seconds between polls |
| `TICKTICK_V3_REQUEST_TIMEOUT` | `30` | seconds |
| `TICKTICK_V3_LEASE_TTL` | `90` | single-writer lease on the replica |
| `TICKTICK_V3_AUTH_PAUSE_SECONDS` | `300` | pause after an auth failure |
| `TICKTICK_V3_ERROR_STREAK_HALT` | `3` | consecutive network errors before the loop stops |
| `TICKTICK_V3_GCS_EMIT_ENABLED` | `0` | `1` writes Parquet to GCS after each changed cycle |
| `TICKTICK_V3_GCS_PREFIX` | `ticktick/v3` | object prefix inside the bucket |
| `GCS_RAW_BUCKET`, `GCS_KEY`, `GCS_SECRET` | | bucket and HMAC pair for the emitter |

The TickTick credential is not an environment variable. It is a browser cURL
pasted into the poller web UI and stored in the replica's `credentialprofile`
table.

## Grafana exporter and workflows

| variable | where | used for |
|---|---|---|
| `GRAFANA_URL` | secret | exporter base URL; replaced by `${GRAFANA_URL}` in exported JSON |
| `GRAFANA_SERVICE_ACCOUNT_TOKEN` | secret | exporter auth |
| `DBT_BQ_PROJECT` | secret | replaced by `${DBT_BQ_PROJECT}` in exported JSON |

## GitHub Actions inventory

Secrets: `AIRBYTE_CONNECTION_ID` (unused), `DBT_BQ_KEYFILE_JSON`,
`DBT_BQ_LOCATION`, `DBT_BQ_PROJECT`, `GCS_EDR_BUCKET` (elementary report),
`GCS_KEY`, `GCS_RAW_BUCKET`, `GCS_SECRET`, `GRAFANA_SERVICE_ACCOUNT_TOKEN`,
`GRAFANA_URL`, `LIGHTDASH_API_KEY`, `LIGHTDASH_PROJECT`, `LIGHTDASH_URL`,
`TICKTICK_API_KEY` (v1 Open API), `TODOIST_API_KEY`.

Variables: `DBT_LOAD_INTERVAL`, `DBT_TIMEZONE`,
`ENABLE_GTD_WORK_TYPE_CATEGORIZATION`, `GTD_DEEP_WORK_TAGS`,
`GTD_SHALLOW_WORK_TAGS`.

`DBT_TARGET` is set per workflow step, not as a repository variable.

| workflow | state | trigger |
|---|---|---|
| `CI.yml` | active | pull request; builds into `PR_<n>`, then drops it with `macros/drop_ci_schema.sql` (`PR_20` to `PR_25` were left behind) |
| `CD.yml` | active | merge to `main` |
| `dbt_docs.yml` | active | publishes dbt docs to GitHub Pages |
| `grafana_contract_ci.yml` | active | pull request |
| `grafana_write_back.yml` | active | manual |
| `LD_write_back.yml` | active | Lightdash (legacy) |
| `run_dbt.yml` "Daily dbt job" | disabled | cron `0 23 * * *` |
| `serverless_snapshot.yml` | disabled | external `repository_dispatch`, runs the `incremental_run_gha` branch |
| `todoist_EL.yml` | disabled (inactivity) | |
