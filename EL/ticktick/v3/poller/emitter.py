"""GCS Parquet emitter — reads from the SQLite replica via DuckDB, writes Parquet to GCS.

Called after every successful poll cycle that changed state. Errors are logged but never
propagate — the poller loop must not die because GCS is flaky.

GCS auth: HMAC keys (s3-compatible endpoint). Set via env vars / PollerSettings.
"""
from __future__ import annotations

import logging
from pathlib import Path

logger = logging.getLogger(__name__)


def emit_replica_to_gcs(
    db_path: Path,
    gcs_bucket: str,
    gcs_key: str,
    gcs_secret: str,
    account_id: str = "default",
    gcs_prefix: str = "ticktick/v3",
) -> None:
    """Export taskreplica, projectreplica, groupreplica to GCS as Parquet.

    Uses DuckDB's httpfs extension with GCS S3-compatible endpoint.
    Overwrites the destination on every call (full snapshot, not incremental).
    """
    try:
        import duckdb
    except ImportError as exc:
        logger.error("duckdb not installed — skipping GCS emit: %s", exc)
        return

    db_path_str = str(db_path.resolve())
    tasks_dest      = f"s3://{gcs_bucket}/{gcs_prefix}/tasks.parquet"
    projects_dest   = f"s3://{gcs_bucket}/{gcs_prefix}/projects.parquet"
    groups_dest     = f"s3://{gcs_bucket}/{gcs_prefix}/groups.parquet"

    try:
        con = duckdb.connect()
        con.execute("INSTALL httpfs; LOAD httpfs;")
        con.execute("INSTALL sqlite; LOAD sqlite;")

        # GCS via S3-compatible API
        con.execute(f"""
            SET s3_endpoint        = 'storage.googleapis.com';
            SET s3_url_style       = 'path';
            SET s3_region          = 'auto';
            SET s3_access_key_id   = '{gcs_key}';
            SET s3_secret_access_key = '{gcs_secret}';
        """)

        con.execute(f"ATTACH '{db_path_str}' AS replica (TYPE SQLITE, READ_ONLY);")

        # --- tasks ---
        con.execute(f"""
            COPY (
                SELECT
                    task_id,
                    account_id,
                    project_id,
                    sort_order,
                    title,
                    content,
                    timezone,
                    is_floating,
                    is_all_day,
                    reminder,
                    priority,
                    status,
                    deleted,
                    progress,
                    start_date,
                    due_date,
                    repeat_flag,
                    repeat_first_date,
                    completed_time,
                    completed_user_id,
                    creator,
                    parent_id,
                    created_time,
                    modified_time,
                    kind,
                    column_id,
                    etag,
                    raw_json,
                    updated_at
                FROM replica.taskreplica
                WHERE account_id = '{account_id}'
            ) TO '{tasks_dest}'
            WITH (FORMAT PARQUET, COMPRESSION SNAPPY, OVERWRITE_OR_IGNORE true);
        """)
        logger.info("Emitted tasks.parquet → %s", tasks_dest)

        # --- projects ---
        con.execute(f"""
            COPY (
                SELECT
                    project_id,
                    account_id,
                    name,
                    group_id,
                    closed,
                    sort_order,
                    kind,
                    view_mode,
                    modified_time,
                    etag,
                    raw_json,
                    updated_at
                FROM replica.projectreplica
                WHERE account_id = '{account_id}'
            ) TO '{projects_dest}'
            WITH (FORMAT PARQUET, COMPRESSION SNAPPY, OVERWRITE_OR_IGNORE true);
        """)
        logger.info("Emitted projects.parquet → %s", projects_dest)

        # --- groups ---
        con.execute(f"""
            COPY (
                SELECT
                    group_id,
                    account_id,
                    name,
                    deleted,
                    sort_order,
                    sort_type,
                    etag,
                    raw_json,
                    updated_at
                FROM replica.groupreplica
                WHERE account_id = '{account_id}'
            ) TO '{groups_dest}'
            WITH (FORMAT PARQUET, COMPRESSION SNAPPY, OVERWRITE_OR_IGNORE true);
        """)
        logger.info("Emitted groups.parquet → %s", groups_dest)

        con.close()

    except Exception as exc:  # noqa: BLE001
        logger.error("GCS emit failed (poller continues): %s", exc)