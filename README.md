[![serverless_snapshot](https://github.com/luutuankiet/ticktick_dbt/actions/workflows/serverless_snapshot.yml/badge.svg)](https://github.com/luutuankiet/ticktick_dbt/actions/workflows/serverless_snapshot.yml)
# TickTick dbt Project

This dbt project is designed for transforming data sourced from the TickTick official Open API. It currently supports two primary data streams: `projects` and `tasks`.

## Data Ingestion

Data is ingested into the data warehouse using a purpose-built Airbyte connector for TickTick. You can find more details about the connector here: [https://docs.airbyte.com/integrations/sources/ticktick](https://docs.airbyte.com/integrations/sources/ticktick).

Airbyte loads the raw data into the data warehouse, which then serves as the source for dbt transformations.

## Data Transformation with dbt Snapshots

This project leverages dbt snapshots to capture historical changes in the `projects` and `tasks` data. Snapshots are run on a schedule to capture missing attributes and infer key timestamps:

*   **`created_time`**: Inferred as the minimum `dbt_valid_from` timestamp from the snapshot metadata.
*   **`done_time`**: Inferred as the `dbt_valid_to` date for hard-deleted records in the snapshot.

## Getting Started

1.  **Set up your Airbyte connection**: Configure the TickTick Airbyte connector to load data into your data warehouse.
2.  **Configure dbt profiles**: Ensure your `profiles.yml` is correctly set up to connect to your data warehouse.
3.  **Run dbt commands**:
    *   To run snapshots: `dbtf snapshot`
    *   To build models: `dbt build`

## Notes on Previous Iteration

This project is an evolution of a previous effort, which can be found at [https://github.com/luutuankiet/ticktick-py-dbt](https://github.com/luutuankiet/ticktick-py-dbt). The key distinction in this iteration is the direct utilization of the TickTick official Open API for data extraction.
