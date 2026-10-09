# DuckDB copies the SQLite replica to GCS as Parquet after each changed cycle

BigQuery cannot read the poller's SQLite file. After every poll cycle that
changed state, the poller runs DuckDB `COPY ... TO 's3://...parquet'` over the
GCS S3-compatible API with an HMAC key. BigQuery reads the result as external
tables. Emitter failures are logged and swallowed so GCS trouble never stops
polling.

## Considered options

- **Load into BigQuery directly from the poller.** Rejected: adds the BigQuery client and a service account to the poller host.

## Consequences

Each file is a full overwrite, so BigQuery has no history beyond the current
replica. See `docs/traps/COMPLETED_TASKS_MISSING_BEFORE_A_DATE.md`.
