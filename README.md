[![Elementary_Observability_Report](https://img.shields.io/badge/Elementary_Observability_Report-online-green)](https://storage.googleapis.com/life_admin_edr/index.html#/report/dashboard)
# Personal Life Admin dbt Project

This dbt project contains various dbt models for personal life admin. The transformed data is designed to be consumed by [Lightdash](https://www.lightdash.com/) to serve as a Business Intelligence backend.

## News

*   **2025-09-07:** Added a new data source: **Todoist**! This integration fetches raw data from the Todoist API, loads it into a local DuckDB instance, and then stages it as external tables in BigQuery.

## Data Sources

This project aims to integrate data from the following sources:

*   **TickTick:** (Active Development) Models for tasks and projects from the TickTick Open API.
*   **Todoist:** (Active Development) Models for recurring and habit-based tasks.
*   **YNAB:** (Roadmap) Models for financial data.

## Data Ingestion

Data is ingested into the data warehouse using custom Python scripts.

### Todoist

The Todoist data ingestion process involves a few steps:

1.  **Fetch Raw Data**: A Python script (`EL/todoist/fetch_todoist.py`) fetches raw data from the Todoist API.
2.  **Load to DuckDB**: The script then loads this data into a local DuckDB database.
3.  **Dump to GCS**: The data is dumped from DuckDB to Google Cloud Storage (GCS) in JSONL format.
4.  **Stage as BQ Views**: An ad-hoc dbt run (`dbt run-operation stage_external_sources --target dev`) creates external tables in BigQuery that point to the GCS data.

### TickTick

A TickTick edit reaches BigQuery in about a minute. Nothing polls on a timer:

1. **Listener.** A small container holds the same websocket TickTick's web app keeps open. TickTick pushes a `needSync` frame on every change; the listener only records the time of it.
2. **Dagster.** A sensor sees the new hint and launches one sync run, at most one a minute. A schedule runs the same job every 30 minutes as a safety net, and a failed run sends a phone alert through ntfy.
3. **dlt.** The run fetches the change feed since the last checkpoint and writes everything in one load: append-only raw history, current-state tables, and the new checkpoint itself. A load either lands with its checkpoint or not at all.
4. **dbt and Grafana.** Views over the current-state tables feed the existing dbt models and the Grafana planning dashboard.

Both containers run from one compose file on a small VPS, reached over a private VPN. The warehouse is the only state that matters: the stack can be rebuilt on any machine from its `.env` and resumes where the last finished load left off.

Diagrams (excalidraw.com): architecture `https://excalidraw.com/#json=R5hl_wruHCekuCldgNm68,NkzpJ-Qnwep3xDlcBWTkvQ`, run lifecycle and recovery `https://excalidraw.com/#json=fR-TItqRreAkeb0q9_aEJ,Krz31pI7IDpD7eb1aBMEjg`.

How each part works, what happens when a run is cancelled or fails, and how a moved or rebooted host recovers: [docs/architecture/pipeline-ingest.md](docs/architecture/pipeline-ingest.md). Deploying and operating it: [EL/ticktick/ingest/README.md](EL/ticktick/ingest/README.md). Every deployment value is an environment variable, listed in [docs/reference/configuration.md](docs/reference/configuration.md).

## Data Transformation with dbt Snapshots

This project leverages dbt snapshots to capture historical changes in the `projects` and `tasks` data. Snapshots are run on a schedule to capture missing attributes and infer key timestamps:

*   **`created_time`**: Inferred as the minimum `dbt_valid_from` timestamp from the snapshot metadata.
*   **`done_time`**: Inferred as the `dbt_valid_to` date for hard-deleted records in the snapshot.

## Configuration

### TickTick: GTD "Shallow vs. Deep Work" Feature

This guide explains how to set up the "Shallow vs. Deep Work" categorization feature for TickTick data.

### The "Why": Business Use Case

The primary goal of this feature is to provide a visual distinction between "shallow work" and "deep work." This allows you to quickly assess the nature of your completed tasks and strive for a healthy balance between quick, reactive tasks (Shallow Work `🧃`) and more substantial, planned work (Deep Work `🥩`).

This aligns with the GTD (Getting Things Done) workflow, where tasks are either completed immediately (shallow) or go through a formal clarification process before being executed (deep).

### How to Configure

#### 1. Create a `.env` File

If you don't already have one, create a `.env` file in the root of your dbt project. This file will store the environment variables that dbt will use to configure the feature.

#### 2. Define the Environment Variables

Add the following variables to your `.env` file:

```bash
# Enable or disable the GTD feature
ENABLE_GTD_WORK_TYPE_CATEGORIZATION=true

# Define the tags for deep work (as a JSON array)
GTD_DEEP_WORK_TAGS='["clarified"]'

# Define the tags for shallow work (as a JSON array)
GTD_SHALLOW_WORK_TAGS='[""]'
```

#### Variable Explanations:

*   **`ENABLE_GTD_WORK_TYPE_CATEGORIZATION`**: Set this to `true` to enable the feature. If it's set to `false` or not defined, the `gtd_work_type` column will not be populated.
*   **`GTD_DEEP_WORK_TAGS`**: This is a JSON-formatted array of strings. Any task that has one of these tags will be categorized as "Deep Work" (`🥩`).
*   **`GTD_SHALLOW_WORK_TAGS`**: This is also a JSON-formatted array of strings. Any task with one of these tags will be categorized as "Shallow Work" (`🧃`). If a task has no tags, it will also be considered "Shallow Work".

### 3. How It Works

The `dbt_project.yml` file is configured to read these environment variables and use them to control the logic in the `stg_tasks` model. If the environment variables are not set, dbt will use the default values defined in `dbt_project.yml`.

By using a `.env` file, you can easily customize the feature for your specific workflow without modifying the core dbt code, making this project easily adaptable.

## Getting Started

1.  **Set up your Airbyte connection**: Configure the TickTick Airbyte connector to load data into your data warehouse.
2.  **Configure dbt profiles**: Ensure your `profiles.yml` is correctly set up to connect to your data warehouse.
3.  **Run dbt commands**:
    *   To run snapshots: `dbtf snapshot`
    *   To build models: `dbt build`

## Source Specific Notes

### TickTick

This project is an evolution of a previous effort, which can be found at [https://github.com/luutuankiet/ticktick-py-dbt](https://github.com/luutuankiet/ticktick-py-dbt). The key distinction in this iteration is the direct utilization of the TickTick official Open API for data extraction, moving away from a dependency on Airbyte.