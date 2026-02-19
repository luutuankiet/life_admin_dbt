WITH source AS (
    SELECT
        *
    FROM {{ source('ticktick_raw', 'projects_v3') }}
),

renamed_and_typed AS (
    SELECT
        NULLIF(CAST(project_id AS STRING), '') AS project_id,
        NULLIF(CAST(account_id AS STRING), '') AS account_id,
        NULLIF(CAST(name AS STRING), '') AS project_name,
        COALESCE(SAFE_CAST(sort_order AS INT64), SAFE_CAST(JSON_VALUE(raw_json, '$.sortOrder') AS INT64)) AS sort_order,
        NULLIF(CAST(group_id AS STRING), '') AS group_id,
        NULLIF(CAST(kind AS STRING), '') AS kind,
        NULLIF(CAST(JSON_VALUE(raw_json, '$.color') AS STRING), '') AS color,
        NULLIF(CAST(view_mode AS STRING), '') AS view_mode,
        NULLIF(CAST(JSON_VALUE(raw_json, '$.permission') AS STRING), '') AS permission,
        CASE
            WHEN SAFE_CAST(closed AS INT64) IS NOT NULL THEN SAFE_CAST(closed AS INT64) = 1
            ELSE SAFE_CAST(JSON_VALUE(raw_json, '$.closed') AS BOOL)
        END AS closed,
        NULLIF(CAST(etag AS STRING), '') AS etag,
        SAFE_CAST(modified_time AS TIMESTAMP) AS modified_time,
        SAFE_CAST(updated_at AS TIMESTAMP) AS updated_at,
        raw_json
    FROM source
),

cast_tz AS (
    SELECT
        * EXCEPT (modified_time, updated_at),
        DATETIME(modified_time, "{{ var('timezone') }}") AS modified_time,
        DATETIME(updated_at, "{{ var('timezone') }}") AS updated_at
    FROM renamed_and_typed
)

SELECT
    *
FROM cast_tz