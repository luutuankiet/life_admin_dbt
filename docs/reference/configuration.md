---
title: Configuration and environment variables
summary: every deployment-specific value, where it is set (GitHub, poller host, local .env), and its default
verified: 2026-10-11
---

# Configuration and environment variables

This repository is public. Anything that identifies a deployment (GCP project,
buckets, hosts, emails, tokens) comes from the environment. Locally, copy
`.env.example` to `.env` (gitignored) and fill it in. In GitHub Actions, the same
names are repository **secrets** or **variables**. On the ingestion host they go in
`EL/ticktick/ingest/docker/.env` (template: `EL/ticktick/ingest/docker/.env.example`).
The legacy v3 poller host reads `EL/ticktick/v3/docker/.env`.

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
| `TICKTICK_INGEST_DATASET` | no | `ticktick_ingest` | dataset of source `ticktick_ingest` (`models/staging/ticktick/source_ticktick_ingest.yml`), read by the `compat__ticktick_v3__*` views; must match the dataset the ingestion stack writes to |
| `GCS_RAW_BUCKET` | yes | | bucket behind the external tables in `models/raw/external_table_stage/dump.yml` |
| `GCS_KEY`, `GCS_SECRET` | legacy targets | | GCS HMAC pair for DuckDB targets (`load_raw`, `load_snapshot`, `dump_snapshot`) |
| `GCS_REGION` | no | `auto` | region on those DuckDB S3 secrets |
| `DBT_TIMEZONE` | no | `UTC` | `var('timezone')`; every timestamp is converted to this |
| `DBT_LOAD_INTERVAL` | no | `15` | minutes; used by the v1 "next load" freshness row |
| `ENABLE_GTD_WORK_TYPE_CATEGORIZATION` | no | | `true` fills `gtd_work_type` |
| `GTD_DEEP_WORK_TAGS`, `GTD_SHALLOW_WORK_TAGS` | no | | JSON arrays of tag names |
| `DBT_OWNER_EMAIL` | no | `owner@example.com` | owner on Lightdash exposures |
| `LIGHTDASH_URL` | no | `https://lightdash.example.com` | base URL on Lightdash exposures; also used by the Lightdash workflows (legacy) |

## Ingestion stack (`EL/ticktick/ingest/`)

Read by the dlt pipeline, the websocket listener and the Dagster definitions. On the
host they live in `EL/ticktick/ingest/docker/.env`; `docker-compose.yml` loads that file
into both containers. Real values never go in the repository.

| variable | required | default | used for |
|---|---|---|---|
| `TICKTICK_COOKIE_T` | yes | | value of the TickTick web session cookie `t`; sent by the fetcher and the listener. A 401 means it expired |
| `TICKTICK_USER_AGENT` | yes | | browser user agent the cookie was issued to |
| `TICKTICK_X_DEVICE` | yes | | the web app's `X-Device` JSON header; its `id` field is replaced (next two rows) |
| `INGEST_STACK_NAME` | no | the compose project name (compose sets it) | seeds a device id unique to the stack, so two stacks never share TickTick's per-device push channel; unset outside compose = the header's own `id` is sent |
| `TICKTICK_DEVICE_ID` | no | | explicit device id (24 lowercase hex); wins over `INGEST_STACK_NAME`. Only needed when stacks on different hosts share a project name |
| `INGEST_LISTENER_IDLE_MINUTES` | no | `60` | the listener reconnects after this long without a frame; `0` = never. Each idle reconnect writes one hint, so a quiet account costs one empty fetch per period |
| `TICKTICK_TIMEZONE` | no | `Asia/Ho_Chi_Minh` | the `x-tz` request header |
| `TICKTICK_INGEST_DATASET` | yes | | BigQuery dataset dlt loads into (prod and dev use different datasets) |
| `DBT_BQ_PROJECT` | yes | | BigQuery project of the destination (shared with dbt) |
| `DBT_BQ_LOCATION` | no | `US` | BigQuery location of the destination (shared with dbt) |
| `GOOGLE_APPLICATION_CREDENTIALS` | yes | `/secrets/sa.json` in the containers | service-account key file; compose mounts `docker/secrets/` read-only at `/secrets` |
| `NTFY_URL` | no | | full ntfy topic URL the failure sensor posts to; unset = the alert is only logged |
| `INGEST_STATE_DIR` | no | `/state` in the containers (compose sets it); `~/.local/state/ticktick_ingest` for the CLI outside them | hint file, gate cache, dlt working dir; the Dagster storage sits at `/state/dagster` |
| `DAGSTER_WEB_BIND` | no | `127.0.0.1` | host address the Dagster UI is published on; production uses `0.0.0.0`, which is safe only when the provider-level firewall blocks the port publicly (Docker-published ports bypass host ufw/iptables rules); a VPN address instead also needs the boot-order drop-in in `EL/ticktick/ingest/docker/host/` |
| `DAGSTER_WEB_PORT` | no | `3070` | host port of the Dagster UI |

The credential is the bare `t` cookie, not a pasted cURL. There is no login and no
password anywhere; when TickTick rejects the cookie, replace the value and recreate
the containers.

## v3 poller (`EL/ticktick/v3/poller/config.py`)

Legacy, superseded by the ingestion stack above.

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
| `CI.yml` | disabled (Lightdash, legacy) | pull request; ran `lightdash validate`, built into `PR_<n>`, then drops it with `macros/drop_ci_schema.sql` (`PR_20` to `PR_25` were left behind) |
| `CD.yml` | disabled (Lightdash, legacy) | any push to `main` outside `.github/**` and `lightdash/**` |
| `dbt_docs.yml` | active | push to `main`; publishes dbt docs to GitHub Pages |
| `grafana_contract_ci.yml` | active | pull request |
| `grafana_write_back.yml` | active | manual |
| `LD_write_back.yml` | disabled (Lightdash, legacy) | manual |
| `run_dbt.yml` "Daily dbt job" | disabled | cron `0 23 * * *` |
| `serverless_snapshot.yml` | disabled (legacy) | `repository_dispatch` sent by an n8n job, runs the `incremental_run_gha` branch |
| `todoist_EL.yml` | disabled (inactivity) | |
